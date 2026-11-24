import os
from fastapi import HTTPException, UploadFile

from app.core import config


async def read_upload(file: UploadFile, allowed_ext: set | None = None) -> tuple[bytes, str, str]:
    """Read an upload into memory with a size cap. Returns (data, safe_filename, content_type)."""
    name = os.path.basename(file.filename or "file")[:200]
    ext = os.path.splitext(name)[1].lower()
    allowed = allowed_ext or set(config.ALLOWED_UPLOAD_TYPES)
    if ext not in allowed:
        raise HTTPException(status_code=400, detail=f"File type {ext or '(none)'} not allowed. "
                                                    f"Allowed: {', '.join(sorted(allowed))}")
    max_bytes = int(config.MAX_UPLOAD_MB * 1024 * 1024)
    chunks, size = [], 0
    while chunk := await file.read(1024 * 1024):
        size += len(chunk)
        if size > max_bytes:
            raise HTTPException(status_code=413, detail=f"File larger than {config.MAX_UPLOAD_MB:g} MB")
        chunks.append(chunk)
    data = b"".join(chunks)
    if not data:
        raise HTTPException(status_code=400, detail="The file is empty")
    if ext == ".pdf" and not data.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="The file is not a valid PDF.")
    return data, name, config.ALLOWED_UPLOAD_TYPES.get(ext, "application/octet-stream")


def extract_pdf_text(data: bytes) -> str:
    import io
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(data))
        return "\n".join((p.extract_text() or "") for p in reader.pages).strip()
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not read the PDF: {e}")
