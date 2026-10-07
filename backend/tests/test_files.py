import io

import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.errors import UnsupportedFileTypeError, UploadTooLargeError
from app.core.files import FileStore, detect_content_type, read_upload, sanitize_filename

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
PDF = b"%PDF-1.7\n" + b"0" * 64


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("resume.pdf", "resume.pdf"),
        ("../../etc/passwd", "passwd"),
        ("..\\..\\windows\\win.ini", "win.ini"),
        ("..", "file"),
        (".bashrc", "bashrc"),
        ("my résumé (final).docx", "my_r_sum_final_.docx"),
        ("", "file"),
    ],
)
def test_sanitize_filename(name: str, expected: str) -> None:
    assert sanitize_filename(name) == expected


def test_sanitize_filename_keeps_extension_when_truncating() -> None:
    result = sanitize_filename("a" * 300 + ".pdf")
    assert len(result) == 100
    assert result.endswith(".pdf")


def test_detect_content_type_uses_bytes_not_extension() -> None:
    assert detect_content_type(PNG, "photo.pdf") == "image/png"
    assert detect_content_type(PDF, "doc.png") == "application/pdf"
    assert detect_content_type(b"MZ\x90\x00" + b"\x00" * 64, "resume.pdf") != "application/pdf"
    assert detect_content_type(b"a,b\n1,2\n", "data.csv") == "text/csv"
    assert detect_content_type(b"\x00\x01binary", "data.csv") == "application/octet-stream"


def test_save_writes_file_and_metadata(file_store: FileStore) -> None:
    stored = file_store.save("resume", "../../My Resume.pdf", PDF)
    path = file_store.path(stored)
    assert path.read_bytes() == PDF
    assert path.is_relative_to(file_store.root)
    assert stored.relative_path.startswith("resume/")
    assert stored.relative_path.endswith("/My_Resume.pdf")
    assert stored.original_name == "../../My Resume.pdf"
    assert stored.content_type == "application/pdf"
    assert stored.size_bytes == len(PDF)
    assert len(stored.sha256) == 64


def test_save_rejects_oversized_file(file_store: FileStore) -> None:
    with pytest.raises(UploadTooLargeError):
        file_store.save("resume", "big.pdf", PDF + b"0" * file_store.max_bytes)


def test_save_rejects_wrong_content_type(file_store: FileStore) -> None:
    exe = b"MZ\x90\x00" + b"\x00" * 64
    with pytest.raises(UnsupportedFileTypeError):
        file_store.save("resume", "resume.pdf", exe, allowed_types={"application/pdf"})
    assert not any(file_store.root.rglob("*.pdf"))


def test_save_rejects_bad_category(file_store: FileStore) -> None:
    with pytest.raises(ValueError):
        file_store.save("../escape", "a.pdf", PDF)


def test_path_refuses_to_escape_data_dir(file_store: FileStore) -> None:
    stored = file_store.save("resume", "a.pdf", PDF)
    stored.relative_path = "../../etc/passwd"
    with pytest.raises(ValueError):
        file_store.path(stored)


def test_delete_removes_file_and_folder(file_store: FileStore) -> None:
    stored = file_store.save("screenshot", "shot.png", PNG)
    path = file_store.path(stored)
    file_store.delete(stored)
    assert not path.exists()
    assert not path.parent.exists()
    file_store.delete(stored)  # already gone: not an error


async def test_read_upload_stops_at_limit() -> None:
    upload = UploadFile(io.BytesIO(b"x" * 2048), filename="big.bin")
    with pytest.raises(UploadTooLargeError):
        await read_upload(upload, max_bytes=1024)
    upload = UploadFile(io.BytesIO(b"x" * 100), filename="small.bin")
    assert await read_upload(upload, max_bytes=1024) == b"x" * 100


def test_download_endpoint(client: TestClient, file_store: FileStore, session: Session) -> None:
    stored = file_store.save("screenshot", "shot.png", PNG)
    session.add(stored)
    session.commit()

    response = client.get(f"/api/files/{stored.id}")
    assert response.status_code == 200
    assert response.content == PNG
    assert response.headers["content-type"] == "image/png"
    assert response.headers["content-disposition"].startswith("inline")
    assert response.headers["x-content-type-options"] == "nosniff"

    pdf = file_store.save("resume", "cv.pdf", PDF)
    session.add(pdf)
    session.commit()
    response = client.get(f"/api/files/{pdf.id}")
    assert response.headers["content-disposition"].startswith("attachment")


def test_download_unknown_file_is_404(client: TestClient) -> None:
    response = client.get("/api/files/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_transaction_deletes_saved_files_when_block_raises(file_store: FileStore) -> None:
    with pytest.raises(RuntimeError), file_store.transaction() as files:
        first = files.save("resume", "a.pdf", PDF)
        second = files.save("screenshot", "b.png", PNG)
        raise RuntimeError("commit failed")
    for stored in (first, second):
        assert not (file_store.root / stored.relative_path).exists()


def test_transaction_keeps_files_on_success(file_store: FileStore) -> None:
    with file_store.transaction() as files:
        stored = files.save("resume", "a.pdf", PDF)
    assert file_store.path(stored).read_bytes() == PDF
