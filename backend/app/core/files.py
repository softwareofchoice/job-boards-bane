import contextlib
import hashlib
import mimetypes
import re
import uuid
from collections.abc import Collection
from pathlib import Path

import filetype
from fastapi import UploadFile

from app.core.errors import NotFoundError, UnsupportedFileTypeError, UploadTooLargeError
from app.core.models import StoredFile

_CATEGORY_RE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
_UNSAFE_CHARS_RE = re.compile(r"[^A-Za-z0-9._-]+")
_MAX_NAME_LEN = 100
_CHUNK = 1024 * 1024


def sanitize_filename(name: str) -> str:
    """A filename that is safe to use as one path component.

    Directory parts are dropped, unsafe characters become `_`, and leading dots are removed
    so the result can't be hidden or refer to a parent directory.
    """
    base = re.split(r"[\\/]", name)[-1]
    base = _UNSAFE_CHARS_RE.sub("_", base).lstrip("._")
    if len(base) > _MAX_NAME_LEN:
        stem, dot, ext = base.rpartition(".")
        if dot and 0 < len(ext) <= 10:
            base = stem[: _MAX_NAME_LEN - len(ext) - 1] + "." + ext
        else:
            base = base[:_MAX_NAME_LEN]
    return base or "file"


def detect_content_type(data: bytes, filename: str) -> str:
    """The content type from the file's bytes (magic numbers), falling back to its extension.

    The extension is only trusted for formats with no magic number (plain text, CSV, YAML).
    """
    kind = filetype.guess(data)
    if kind is not None:
        return str(kind.mime)
    guessed, _ = mimetypes.guess_type(filename)
    if guessed and guessed.startswith("text/") and _looks_like_text(data):
        return guessed
    return "application/octet-stream"


def _looks_like_text(data: bytes) -> bool:
    try:
        data[:4096].decode("utf-8")
    except UnicodeDecodeError:
        return False
    return b"\x00" not in data[:4096]


async def read_upload(upload: UploadFile, max_bytes: int) -> bytes:
    """Read an upload, stopping as soon as it goes over the size limit (FND-5.3)."""
    buf = bytearray()
    while chunk := await upload.read(_CHUNK):
        buf.extend(chunk)
        if len(buf) > max_bytes:
            raise UploadTooLargeError(
                f"{upload.filename or 'File'} is larger than the "
                f"{max_bytes // (1024 * 1024)} MB limit."
            )
    return bytes(buf)


class FileStore:
    """Keeps files under one data directory; the database stores paths relative to it (FND-2.3)."""

    def __init__(self, root: Path, max_bytes: int) -> None:
        self.root = root.resolve()
        self.max_bytes = max_bytes

    def save(
        self,
        category: str,
        filename: str,
        data: bytes,
        allowed_types: Collection[str] | None = None,
    ) -> StoredFile:
        """Write the file and return an unsaved StoredFile row for the caller to add."""
        if not _CATEGORY_RE.match(category):
            raise ValueError(f"Invalid file category: {category!r}")
        if len(data) > self.max_bytes:
            raise UploadTooLargeError(
                f"{filename} is larger than the {self.max_bytes // (1024 * 1024)} MB limit."
            )
        content_type = detect_content_type(data, filename)
        if allowed_types is not None and content_type not in allowed_types:
            raise UnsupportedFileTypeError(
                f"{filename} is not an accepted file type (detected {content_type})."
            )

        safe_name = sanitize_filename(filename)
        relative = Path(category) / uuid.uuid4().hex / safe_name
        target = self._resolve(relative.as_posix())
        target.parent.mkdir(parents=True)
        target.write_bytes(data)

        return StoredFile(
            category=category,
            relative_path=relative.as_posix(),
            original_name=filename,
            content_type=content_type,
            size_bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
        )

    def path(self, stored: StoredFile) -> Path:
        target = self._resolve(stored.relative_path)
        if not target.is_file():
            raise NotFoundError("The file is missing from the data directory.")
        return target

    def delete(self, stored: StoredFile) -> None:
        """Delete the file and its folder. A file that is already gone is not an error."""
        target = self._resolve(stored.relative_path)
        target.unlink(missing_ok=True)
        with contextlib.suppress(OSError):  # not empty, or already gone
            target.parent.rmdir()

    def _resolve(self, relative_path: str) -> Path:
        target = (self.root / relative_path).resolve()
        if not target.is_relative_to(self.root):
            raise ValueError(f"Path escapes the data directory: {relative_path!r}")
        return target
