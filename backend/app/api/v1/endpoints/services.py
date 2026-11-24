from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core import config
from app.core.database import get_db
from app.core.deps import get_current_user, get_optional_user, current_freelancer, current_client
from app.models import Service, Consultant, Client, Order, Document, User
from app.schemas.marketplace import ServiceIn, ServiceUpdate, ServiceOrderIn
from app.services import audit
from app.services.access import owns_service
from app.services.realtime import publish_all
from app.services.serializers import service_out, order_out

router = APIRouter()


def _get(db: Session, sid: int) -> Service:
    s = db.get(Service, sid)
    if not s:
        raise HTTPException(status_code=404, detail="Service not found")
    return s


@router.get("", summary="Browse services (public)")
def browse(q: Optional[str] = None, category: Optional[str] = None, skill: Optional[str] = None,
           max_price: Optional[int] = None, limit: int = Query(24, ge=1, le=100), offset: int = Query(0, ge=0),
           db: Session = Depends(get_db)):
    query = (db.query(Service).join(Consultant, Consultant.id == Service.consultant_id)
             .filter(Service.status == "active", Consultant.is_public.is_(True)))
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(or_(Service.title.ilike(like), Service.description.ilike(like),
                                 Service.category.ilike(like)))
    if category:
        query = query.filter(Service.category == category)
    if max_price:
        query = query.filter(Service.price <= max_price)
    rows = query.order_by(Service.id.desc()).all()
    if skill:
        s = skill.strip().lower()
        rows = [x for x in rows if any(s in (k or "").lower() for k in (x.skills or []))]
    return {"total": len(rows), "items": [service_out(s) for s in rows[offset:offset + limit]]}


@router.get("/categories", summary="Categories in use (services and jobs)")
def categories(db: Session = Depends(get_db)):
    from app.models import Job
    cats = {c for (c,) in db.query(Service.category).filter(Service.category.isnot(None)).distinct()}
    cats |= {c for (c,) in db.query(Job.category).filter(Job.category.isnot(None)).distinct()}
    return sorted(c for c in cats if c)


@router.get("/mine", summary="My services (freelancer)")
def mine(me: Consultant = Depends(current_freelancer), db: Session = Depends(get_db)):
    return [service_out(s) for s in db.query(Service).filter(Service.consultant_id == me.id)
            .order_by(Service.id.desc()).all()]


@router.post("", summary="Offer a new service (freelancer)")
def create(payload: ServiceIn, request: Request, me: Consultant = Depends(current_freelancer),
           db: Session = Depends(get_db)):
    data = payload.model_dump()
    data["currency"] = data.get("currency") or me.currency or "INR"
    s = Service(consultant_id=me.id, **data)
    db.add(s)
    db.commit()
    db.refresh(s)
    audit.log(db, "service.create", me.user_id, "service", s.id, {"title": s.title}, request)
    return service_out(s)


@router.get("/{service_id}", summary="Service details")
def get_service(service_id: int, db: Session = Depends(get_db), user: Optional[User] = Depends(get_optional_user)):
    s = _get(db, service_id)
    owner = owns_service(user, s)
    if (s.status != "active" or not s.consultant.is_public) and not owner:
        raise HTTPException(status_code=404, detail="Service not found")
    out = service_out(s)
    out["viewer_is_owner"] = owner
    return out


@router.put("/{service_id}", summary="Edit a service (owner)")
def update(service_id: int, payload: ServiceUpdate, user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    s = _get(db, service_id)
    if not owns_service(user, s):
        raise HTTPException(status_code=404, detail="Service not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        if k == "currency" and v is None:
            continue
        setattr(s, k, v)
    db.commit()
    db.refresh(s)
    return service_out(s)


@router.delete("/{service_id}", summary="Delete a service (owner)")
def delete(service_id: int, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = _get(db, service_id)
    if not owns_service(user, s):
        raise HTTPException(status_code=404, detail="Service not found")
    db.query(Document).filter(Document.owner_type == "service", Document.owner_id == s.id).delete()
    db.delete(s)
    db.commit()
    audit.log(db, "service.delete", user.id, "service", service_id, None, request)
    return {"status": "deleted", "id": service_id}


@router.post("/{service_id}/order", summary="Buy a service (client) — creates an order to pay for")
async def order_service(service_id: int, payload: ServiceOrderIn, request: Request,
                        client: Client = Depends(current_client), db: Session = Depends(get_db)):
    s = _get(db, service_id)
    if s.status != "active" or not s.consultant.is_public:
        raise HTTPException(status_code=400, detail="This service isn't available right now")
    amount = s.price * 100
    o = Order(client_id=client.id, consultant_id=s.consultant_id, service_id=s.id, title=s.title, currency=s.currency,
              requirements=payload.requirements, amount_paise=amount,
              platform_fee_paise=round(amount * config.PLATFORM_FEE_PERCENT / 100), status="pending_payment")
    db.add(o)
    db.commit()
    db.refresh(o)
    audit.log(db, "order.create", client.owner_user_id, "order", o.id, {"service_id": s.id}, request)
    return order_out(o)
