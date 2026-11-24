from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File, Request, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import current_freelancer, get_optional_user, require_admin
from app.core.ratelimit import limit
from app.models import Order
from app.services.serializers import order_out
from app.models import Consultant, Match, Job, Service, Document, DocumentBlob, User
from app.schemas.profiles import FreelancerUpdate, FreelancerAdminCreate, PayoutDetailsIn
from app.services import matching, audit, payouts
from app.services.access import owns_consultant
from app.services.cv_parser import parse_profile_text
from app.services.serializers import freelancer_out, service_out, job_out
from app.services.uploads import read_upload, extract_pdf_text

router = APIRouter()


@router.get("", summary="Browse freelancers (public)")
def browse(q: Optional[str] = None, skill: Optional[str] = None, available: Optional[bool] = None,
           country: Optional[str] = None, region: Optional[str] = None, language: Optional[str] = None,
           min_rating: Optional[float] = Query(None, ge=0, le=5), verified: Optional[bool] = None,
           sort: str = Query("experience", pattern="^(experience|rating|rate_low|newest)$"),
           limit: int = Query(24, ge=1, le=100), offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    query = db.query(Consultant).filter(Consultant.is_public.is_(True))
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(or_(Consultant.name.ilike(like), Consultant.headline.ilike(like),
                                 Consultant.bio.ilike(like), Consultant.location.ilike(like)))
    if available is not None:
        query = query.filter(Consultant.availability == ("available" if available else "busy"))
    if country:
        query = query.filter(Consultant.country == country.upper())
    if min_rating:
        query = query.filter(Consultant.rating_avg >= min_rating)
    if verified:
        query = query.filter(Consultant.verified_at.isnot(None))
    order = {"experience": (Consultant.experience_years.desc(),),
             "rating": (Consultant.rating_avg.desc().nullslast(), Consultant.rating_count.desc()),
             "rate_low": (Consultant.hourly_rate.asc().nullslast(),), "newest": (Consultant.id.desc(),)}[sort]
    rows = query.order_by(*order, Consultant.id).all()
    if skill:  # JSON arrays: filter in Python so it works on SQLite and Postgres alike
        s = skill.strip().lower()
        rows = [c for c in rows if any(s in (x or "").lower() for x in (c.skills or []))]
    if language:
        lang = language.strip().lower()
        rows = [c for c in rows if any(lang == (x or "").lower() for x in (c.languages or []))]
    if region:
        from app.core.geo import region_of
        rows = [c for c in rows if region_of(c.timezone) == region.lower()]
    total = len(rows)
    return {"total": total, "items": [freelancer_out(c, db=db) for c in rows[offset:offset + limit]]}


@router.get("/me", summary="My freelancer profile")
def my_profile(me: Consultant = Depends(current_freelancer), db: Session = Depends(get_db)):
    return freelancer_out(me, private=True, db=db)


@router.put("/me", summary="Update my profile (re-matches against open jobs)")
def update_my_profile(payload: FreelancerUpdate, background_tasks: BackgroundTasks, request: Request,
                      me: Consultant = Depends(current_freelancer), db: Session = Depends(get_db)):
    data = payload.model_dump(exclude_unset=True)
    if "links" in data and data["links"] is not None:
        data["links"] = [dict(label=l["label"], url=l["url"]) for l in data["links"]]
    for k, v in data.items():
        setattr(me, k, v)
    if "name" in data and me.user:
        me.user.name = me.name
    db.commit()
    db.refresh(me)
    background_tasks.add_task(matching.notify, matching.match_consultant(db, me))
    return freelancer_out(me, private=True, db=db)


@router.post("/me/cv", summary="Upload my CV (PDF): fills skills and experience, attaches the file")
async def upload_cv(background_tasks: BackgroundTasks, file: UploadFile = File(...),
                    me: Consultant = Depends(current_freelancer), db: Session = Depends(get_db)):
    data, name, ctype = await read_upload(file, {".pdf"})
    text = extract_pdf_text(data)
    if not text:
        raise HTTPException(status_code=422, detail="No text found in the PDF (it may be a scanned image). "
                                                    "Add your skills by hand instead.")
    parsed = parse_profile_text(text)
    added = [s for s in parsed["skills"] if s.lower() not in {x.lower() for x in (me.skills or [])}]
    me.skills = (me.skills or []) + added
    if parsed["experience_years"] and parsed["experience_years"] > (me.experience_years or 0):
        me.experience_years = parsed["experience_years"]
    if parsed["phone"] and not me.phone:
        me.phone = parsed["phone"]
    me.extracted_text = text[:10000]
    if me.source == "signup":
        me.source = "pdf"
    doc = Document(owner_type="consultant", owner_id=me.id, kind="file", title="CV", filename=name,
                   content_type=ctype, size_bytes=len(data), uploaded_by=me.user_id)
    doc.blob = DocumentBlob(data=data)
    db.add(doc)
    db.commit()
    db.refresh(me)
    events = matching.match_consultant(db, me)
    background_tasks.add_task(matching.notify, events)
    return {"profile": freelancer_out(me, private=True, db=db), "skills_added": added,
            "experience_years": me.experience_years, "new_matches": len(events), "document_id": doc.id}


def _payout_out(c: Consultant) -> dict:
    return {"mode": payouts.mode(), "status": c.payout_status, "method": c.payout_method,
            "masked": c.payout_masked, "beneficiary_name": c.payout_beneficiary, "note": c.payout_note,
            "account_id": c.payout_account_id}


@router.get("/me/payout", summary="My payout details (masked) and earnings")
def my_payout(me: Consultant = Depends(current_freelancer), db: Session = Depends(get_db)):
    orders = (db.query(Order).filter(Order.consultant_id == me.id, Order.paid_at.isnot(None))
              .order_by(Order.id.desc()).all())
    by_cur: dict = {}
    for o in orders:
        sums = by_cur.setdefault(o.currency or "INR", {"held": 0, "pending": 0, "released": 0, "failed": 0, "in_work": 0})
        key = o.payout_status if o.payout_status in sums else "in_work"
        sums[key] += o.amount_paise - o.platform_fee_paise
    by_cur = {c: {k: v / 100 for k, v in t.items()} for c, t in by_cur.items()}
    empty = {"held": 0, "pending": 0, "released": 0, "failed": 0, "in_work": 0}
    return {**_payout_out(me), "totals": by_cur.get("INR", empty),
            "other_currencies": {c: t for c, t in by_cur.items() if c != "INR"},
            "orders": [order_out(o) for o in orders]}


@router.put("/me/payout", summary="Add or change where I get paid (bank account or UPI)",
            dependencies=[Depends(limit("payout_setup", 10, 3600))])
def set_payout(payload: PayoutDetailsIn, request: Request, me: Consultant = Depends(current_freelancer),
               db: Session = Depends(get_db)):
    payouts.setup_account(db, me, method=payload.method, beneficiary_name=payload.beneficiary_name.strip(),
                          account_number=payload.account_number, ifsc=payload.ifsc, vpa=payload.vpa,
                          phone=payload.phone or me.phone)
    audit.log(db, "payout.details_set", me.user_id, "consultant", me.id,
              {"method": me.payout_method, "account": me.payout_masked, "status": me.payout_status}, request)
    paid = payouts.catch_up(db, me)
    return {**_payout_out(me), "orders_paid_now": paid}


@router.get("/me/recommended-jobs", summary="Open jobs that match my profile, best first")
def recommended_jobs(me: Consultant = Depends(current_freelancer), db: Session = Depends(get_db)):
    rows = (db.query(Match, Job).join(Job, Job.id == Match.job_id)
            .filter(Match.consultant_id == me.id, Job.status == "open")
            .order_by(Match.score.desc(), Job.id.desc()).all())
    return [{"score": m.score, "match_details": m.match_details, "job": job_out(db, j)} for m, j in rows]


@router.get("/{consultant_id}", summary="Public freelancer profile")
def get_profile(consultant_id: int, db: Session = Depends(get_db), user: Optional[User] = Depends(get_optional_user)):
    c = db.get(Consultant, consultant_id)
    if not c or (not c.is_public and not owns_consultant(user, c)):
        raise HTTPException(status_code=404, detail="Freelancer not found")
    out = freelancer_out(c, private=owns_consultant(user, c), db=db)
    out["services"] = [service_out(s) for s in db.query(Service).filter(
        Service.consultant_id == c.id, Service.status == "active").order_by(Service.id.desc()).all()]
    return out


# ---- admin -------------------------------------------------------------------------------------
@router.post("", summary="Admin: create a freelancer profile on someone's behalf")
def admin_create(payload: FreelancerAdminCreate, background_tasks: BackgroundTasks, request: Request,
                 admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    email = payload.email.lower()
    if db.query(Consultant).filter(Consultant.email == email).first():
        raise HTTPException(status_code=400, detail="A freelancer with this email already exists")
    c = Consultant(**{**payload.model_dump(), "email": email}, source="manual", links=[])
    db.add(c)
    db.commit()
    db.refresh(c)
    audit.log(db, "freelancer.admin_create", admin.id, "consultant", c.id, {"email": email}, request)
    background_tasks.add_task(matching.notify, matching.match_consultant(db, c))
    return freelancer_out(c, private=True, db=db)


@router.put("/{consultant_id}", summary="Admin: update any profile")
def admin_update(consultant_id: int, payload: FreelancerUpdate, background_tasks: BackgroundTasks,
                 admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    c = db.get(Consultant, consultant_id)
    if not c:
        raise HTTPException(status_code=404, detail="Freelancer not found")
    data = payload.model_dump(exclude_unset=True)
    if "links" in data and data["links"] is not None:
        data["links"] = [dict(label=l["label"], url=l["url"]) for l in data["links"]]
    for k, v in data.items():
        setattr(c, k, v)
    db.commit()
    background_tasks.add_task(matching.notify, matching.match_consultant(db, c))
    return freelancer_out(c, private=True, db=db)


@router.delete("/{consultant_id}", summary="Admin: delete a profile")
def admin_delete(consultant_id: int, request: Request, admin: User = Depends(require_admin),
                 db: Session = Depends(get_db)):
    c = db.get(Consultant, consultant_id)
    if not c:
        raise HTTPException(status_code=404, detail="Freelancer not found")
    db.query(Document).filter(Document.owner_type == "consultant", Document.owner_id == c.id).delete()
    db.delete(c)
    db.commit()
    audit.log(db, "freelancer.delete", admin.id, "consultant", consultant_id, None, request)
    return {"status": "deleted", "id": consultant_id}
