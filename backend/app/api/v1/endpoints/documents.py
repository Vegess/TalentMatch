from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.ratelimit import limit
from app.models import Document, DocumentBlob, User
from app.models.document import OWNER_TYPES
from app.schemas.marketplace import LinkDocumentIn
from app.services import audit
from app.services.access import get_owner, can_read_attachments, can_write_attachments
from app.services.serializers import document_out
from app.services.uploads import read_upload

router = APIRouter()
MAX_DOCS_PER_OWNER = 20


def _check_owner_type(owner_type: str):
    if owner_type not in OWNER_TYPES:
        raise HTTPException(status_code=400, detail=f"owner_type must be one of {', '.join(OWNER_TYPES)}")


def _guard_write(db: Session, user: User, owner_type: str, owner_id: int):
    _check_owner_type(owner_type)
    obj = get_owner(db, owner_type, owner_id)
    if not can_write_attachments(db, user, owner_type, obj):
        raise HTTPException(status_code=404, detail=f"{owner_type.capitalize()} not found")
    if db.query(Document).filter(Document.owner_type == owner_type, Document.owner_id == owner_id).count() \
            >= MAX_DOCS_PER_OWNER:
        raise HTTPException(status_code=400, detail=f"At most {MAX_DOCS_PER_OWNER} documents per item")


@router.get("", summary="Documents and links attached to a job, profile, service or order")
def list_documents(owner_type: str, owner_id: int, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    _check_owner_type(owner_type)
    obj = get_owner(db, owner_type, owner_id)
    if not can_read_attachments(db, user, owner_type, obj):
        raise HTTPException(status_code=404, detail=f"{owner_type.capitalize()} not found")
    rows = db.query(Document).filter(Document.owner_type == owner_type, Document.owner_id == owner_id) \
        .order_by(Document.id.desc()).all()
    return [document_out(d) for d in rows]


@router.post("/upload", summary="Upload a file (PDF, Word, text, image; max 10 MB)",
             dependencies=[Depends(limit("upload", 30, 300))])
async def upload(request: Request, owner_type: str = Form(...), owner_id: int = Form(...),
                 title: str = Form(""), file: UploadFile = File(...), user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    _guard_write(db, user, owner_type, owner_id)
    data, name, ctype = await read_upload(file)
    d = Document(owner_type=owner_type, owner_id=owner_id, kind="file", title=(title.strip() or name)[:200],
                 filename=name, content_type=ctype, size_bytes=len(data), uploaded_by=user.id)
    d.blob = DocumentBlob(data=data)
    db.add(d)
    db.commit()
    db.refresh(d)
    audit.log(db, "document.upload", user.id, owner_type, owner_id, {"document_id": d.id, "file": name}, request)
    return document_out(d)


@router.post("/link", summary="Attach a URL (Google Drive, Notion, GitHub, portfolio, hosted PDF …)")
def add_link(payload: LinkDocumentIn, request: Request, user: User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    _guard_write(db, user, payload.owner_type, payload.owner_id)
    d = Document(owner_type=payload.owner_type, owner_id=payload.owner_id, kind="url", title=payload.title.strip(),
                 url=payload.url, uploaded_by=user.id)
    db.add(d)
    db.commit()
    db.refresh(d)
    audit.log(db, "document.link", user.id, payload.owner_type, payload.owner_id, {"document_id": d.id}, request)
    return document_out(d)


@router.get("/{document_id}/download", summary="Download an uploaded file")
def download(document_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    d = db.get(Document, document_id)
    if not d or d.kind != "file":
        raise HTTPException(status_code=404, detail="Document not found")
    obj = get_owner(db, d.owner_type, d.owner_id)
    if not can_read_attachments(db, user, d.owner_type, obj):
        raise HTTPException(status_code=404, detail="Document not found")
    blob = db.get(DocumentBlob, d.id)
    inline = d.content_type in ("application/pdf", "image/png", "image/jpeg", "text/plain")
    disp = "inline" if inline else "attachment"
    return Response(content=blob.data, media_type=d.content_type or "application/octet-stream", headers={
        "Content-Disposition": f"{disp}; filename*=UTF-8''{quote(d.filename or 'file')}",
        "X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"})


@router.delete("/{document_id}", summary="Remove a document or link")
def delete(document_id: int, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    d = db.get(Document, document_id)
    if not d:
        raise HTTPException(status_code=404, detail="Document not found")
    obj = get_owner(db, d.owner_type, d.owner_id)
    if not (can_write_attachments(db, user, d.owner_type, obj)):
        raise HTTPException(status_code=404, detail="Document not found")
    db.delete(d)
    db.commit()
    audit.log(db, "document.delete", user.id, d.owner_type, d.owner_id, {"document_id": document_id}, request)
    return {"status": "deleted", "id": document_id}
