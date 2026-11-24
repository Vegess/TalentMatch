from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import Review, Order, Consultant, Client, User
from app.services import audit
from app.services.access import order_party
from app.services.notify import notify
from app.services.realtime import publish_all

router = APIRouter()


class ReviewIn(BaseModel):
    order_id: int
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = Field(None, max_length=2000)


def review_out(r: Review) -> dict:
    who = None
    if r.reviewer:
        if r.reviewee_role == "freelancer" and r.order and r.order.client:
            who = r.order.client.company_name or r.order.client.name
        else:
            who = r.reviewer.name
    return {"id": r.id, "order_id": r.order_id, "rating": r.rating, "comment": r.comment, "reviewee_role": r.reviewee_role,
            "reviewer_name": who, "order_title": r.order.title if r.order else None, "created_at": r.created_at}


def _recompute(db: Session, consultant_id: Optional[int] = None, client_id: Optional[int] = None):
    if consultant_id:
        avg, n = db.query(func.avg(Review.rating), func.count(Review.id)).filter(
            Review.consultant_id == consultant_id, Review.reviewee_role == "freelancer").one()
        c = db.get(Consultant, consultant_id)
        c.rating_avg, c.rating_count = (float(avg) if avg is not None else None), n
    if client_id:
        avg, n = db.query(func.avg(Review.rating), func.count(Review.id)).filter(
            Review.client_id == client_id, Review.reviewee_role == "client").one()
        c = db.get(Client, client_id)
        c.rating_avg, c.rating_count = (float(avg) if avg is not None else None), n


@router.post("", summary="Review the other side of a completed order (once per order)")
async def create_review(payload: ReviewIn, request: Request, user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    o = db.get(Order, payload.order_id)
    party = order_party(user, o) if o else None
    if not o or party not in ("client", "freelancer"):
        raise HTTPException(status_code=404, detail="Order not found")
    if o.status != "completed":
        raise HTTPException(status_code=400, detail="You can leave a review once the order is approved")
    role = "freelancer" if party == "client" else "client"
    r = Review(order_id=o.id, reviewer_user_id=user.id, reviewee_role=role, rating=payload.rating,
               comment=(payload.comment or "").strip() or None,
               consultant_id=o.consultant_id if role == "freelancer" else None,
               client_id=o.client_id if role == "client" else None)
    db.add(r)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="You've already reviewed this order")
    _recompute(db, r.consultant_id, r.client_id)
    db.commit()
    db.refresh(r)
    audit.log(db, "review.create", user.id, "order", o.id, {"rating": r.rating, "role": role}, request)
    target = o.consultant.user_id if role == "freelancer" and o.consultant else (o.client.owner_user_id if o.client else None)
    stars = "★" * r.rating + "☆" * (5 - r.rating)
    events = notify(db, target, "review", f"New {r.rating}-star review", f"{stars} for “{o.title}”"
                    + (f": “{r.comment[:200]}”" if r.comment else ""), f"/orders/{o.id}")
    await publish_all(events)
    return review_out(r)


@router.get("/freelancer/{consultant_id}", summary="Reviews of a freelancer (public)")
def freelancer_reviews(consultant_id: int, db: Session = Depends(get_db)):
    c = db.get(Consultant, consultant_id)
    if not c or not c.is_public:
        raise HTTPException(status_code=404, detail="Freelancer not found")
    rows = db.query(Review).filter(Review.consultant_id == c.id, Review.reviewee_role == "freelancer") \
        .order_by(Review.id.desc()).limit(100).all()
    dist = {str(i): 0 for i in range(1, 6)}
    for r in rows:
        dist[str(r.rating)] += 1
    return {"rating_avg": c.rating_avg, "rating_count": c.rating_count or 0, "distribution": dist,
            "items": [review_out(r) for r in rows]}


@router.get("/client/{client_id}", summary="Reviews of a client company (signed-in users)")
def client_reviews(client_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = db.get(Client, client_id)
    if not c:
        raise HTTPException(status_code=404, detail="Client not found")
    rows = db.query(Review).filter(Review.client_id == c.id, Review.reviewee_role == "client") \
        .order_by(Review.id.desc()).limit(100).all()
    return {"rating_avg": c.rating_avg, "rating_count": c.rating_count or 0, "items": [review_out(r) for r in rows]}


@router.get("/order/{order_id}", summary="Reviews on one order (the two parties and admins)")
def order_reviews(order_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    o = db.get(Order, order_id)
    party = order_party(user, o) if o else None
    if not party:
        raise HTTPException(status_code=404, detail="Order not found")
    rows = db.query(Review).filter(Review.order_id == o.id).all()
    mine = next((r for r in rows if r.reviewer_user_id == user.id), None)
    return {"items": [review_out(r) for r in rows], "can_review": party in ("client", "freelancer")
            and o.status == "completed" and mine is None}
