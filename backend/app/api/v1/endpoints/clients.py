from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import current_client, require_admin
from app.models import Client, User, Document, Job
from app.schemas.profiles import ClientUpdate
from app.services import audit
from app.services.serializers import client_out

router = APIRouter()


@router.get("/me", summary="My company")
def my_company(me: Client = Depends(current_client), db: Session = Depends(get_db)):
    return client_out(db, me)


@router.put("/me", summary="Update my company")
def update_my_company(payload: ClientUpdate, me: Client = Depends(current_client), db: Session = Depends(get_db)):
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(me, k, v)
    if me.owner:
        me.owner.name = me.name
    db.commit()
    db.refresh(me)
    return client_out(db, me)


@router.get("", summary="Admin: all clients")
def list_clients(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return [client_out(db, c) for c in db.query(Client).order_by(Client.id.desc()).all()]


@router.get("/{client_id}", summary="Admin: one client")
def get_client(client_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    c = db.get(Client, client_id)
    if not c:
        raise HTTPException(status_code=404, detail="Client not found")
    return client_out(db, c)


@router.delete("/{client_id}", summary="Admin: delete a client and all its jobs")
def delete_client(client_id: int, request: Request, admin: User = Depends(require_admin),
                  db: Session = Depends(get_db)):
    c = db.get(Client, client_id)
    if not c:
        raise HTTPException(status_code=404, detail="Client not found")
    job_ids = [j.id for j in db.query(Job.id).filter(Job.client_id == c.id).all()]
    if job_ids:
        db.query(Document).filter(Document.owner_type == "job", Document.owner_id.in_(job_ids)).delete()
    db.delete(c)
    db.commit()
    audit.log(db, "client.delete", admin.id, "client", client_id, None, request)
    return {"status": "deleted", "id": client_id}
