"""Reading uploaded files from multipart forms, with errors reported per field."""

from dataclasses import dataclass

from fastapi import UploadFile

from app.core.errors import UploadTooLargeError
from app.core.files import FileStore, detect_content_type, read_upload
from app.core.validation import FieldErrors


@dataclass(frozen=True)
class Upload:
    filename: str
    data: bytes


async def read_checked_file(
    errors: FieldErrors,
    field: str,
    upload: UploadFile | None,
    allowed: dict[str, str],
    store: FileStore,
    *,
    required: bool,
) -> Upload | None:
    """Read an uploaded file, recording a field error if it's missing, too big or the wrong type.

    Browsers send an empty part when no file is chosen, so that counts as "not provided".
    """
    if upload is None or not upload.filename:
        if required:
            errors.add(field, "Choose a file.")
        return None
    try:
        data = await read_upload(upload, store.max_bytes)
    except UploadTooLargeError as exc:
        errors.add(field, exc.message)
        return None
    if not data:
        errors.add(field, "The file is empty.")
        return None
    if detect_content_type(data, upload.filename) not in allowed:
        errors.add(field, f"Upload a {' or '.join(allowed.values())} file.")
        return None
    return Upload(filename=upload.filename, data=data)
