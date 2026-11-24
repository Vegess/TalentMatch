from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request, Query
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_optional_user, current_freelancer
from app.core.plans import plan_limits
from app.models import Job, Client, Consultant, Match, Proposal, Document, User
from app.schemas.marketplace import JobIn, JobUpdate, ProposalIn
from app.services import matching, subscriptions as subs, audit
from app.services.access import owns_job, is_admin
from app.services.realtime import publish_all
from app.services.serializers import job_out, proposal_out

router = APIRouter()


def _get(db: Session, job_id: int) -> Job:
    j = db.get(Job, job_id)
    if not j:
        raise HTTPException(status_code=404, detail="Job not found")
    return j


def _get_owned(db: Session, job_id: int, user: User) -> Job:
    j = _get(db, job_id)
    if not owns_job(db, user, j):
        raise HTTPException(status_code=404, detail="Job not found")  # don't reveal other tenants' jobs
    return j


def _mask_email(email: Optional[str]) -> Optional[str]:
    if not email or "@" not in email:
        return email
    user, domain = email.split("@", 1)
    return (user[:1] + "***@" + domain) if user else "***@" + domain


@router.get("", summary="Browse open jobs (public)")
def browse(q: Optional[str] = None, skill: Optional[str] = None, category: Optional[str] = None,
           location_type: Optional[str] = None, limit: int = Query(24, ge=1, le=100),
           offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    query = db.query(Job).filter(Job.status == "open")
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(or_(Job.title.ilike(like), Job.description.ilike(like), Job.category.ilike(like)))
    if category:
        query = query.filter(Job.category == category)
    if location_type:
        query = query.filter(Job.location_type == location_type)
    rows = query.order_by(Job.id.desc()).all()
    if skill:
        s = skill.strip().lower()
        rows = [j for j in rows if any(s in (x or "").lower() for x in (j.required_skills or []))]
    return {"total": len(rows), "items": [job_out(db, j) for j in rows[offset:offset + limit]]}


@router.get("/mine", summary="My company's jobs (all statuses)")
def my_jobs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "client":
        raise HTTPException(status_code=403, detail="Only client accounts have jobs")
    c = db.query(Client).filter(Client.owner_user_id == user.id).first()
    if not c:
        return []
    return [job_out(db, j, owner_view=True) for j in db.query(Job).filter(Job.client_id == c.id)
            .order_by(Job.id.desc()).all()]


@router.post("", summary="Post a job description (runs matching)",
             description="Clients post for their own company. Admins must pass `client_id` as a query parameter.")
def create_job(payload: JobIn, background_tasks: BackgroundTasks, request: Request,
               client_id: Optional[int] = Query(None, description="Admin only"),
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role == "client":
        client = db.query(Client).filter(Client.owner_user_id == user.id).first()
    elif is_admin(user):
        if not client_id:
            raise HTTPException(status_code=400, detail="client_id is required for admins")
        client = db.get(Client, client_id)
    else:
        raise HTTPException(status_code=403, detail="Only clients can post jobs")
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    subs.ensure_can_open_job(db, client.id)
    data = payload.model_dump()
    data["currency"] = data.get("currency") or client.currency or "INR"
    job = Job(**data, client_id=client.id, status="open")
    db.add(job)
    db.commit()
    db.refresh(job)
    audit.log(db, "job.create", user.id, "job", job.id, {"title": job.title}, request)
    background_tasks.add_task(matching.notify, matching.rematch_job(db, job))
    return job_out(db, job, owner_view=True)


@router.get("/{job_id}", summary="Job description")
def get_job(job_id: int, db: Session = Depends(get_db), user: Optional[User] = Depends(get_optional_user)):
    j = _get(db, job_id)
    owner = owns_job(db, user, j)
    if j.status != "open" and not owner:
        raise HTTPException(status_code=404, detail="Job not found")
    out = job_out(db, j, owner_view=owner)
    out["viewer_is_owner"] = owner
    if user and user.role == "freelancer" and user.consultant:
        p = db.query(Proposal).filter(Proposal.job_id == j.id, Proposal.consultant_id == user.consultant.id).first()
        out["my_proposal"] = proposal_out(p) if p else None
        m = db.query(Match).filter(Match.job_id == j.id, Match.consultant_id == user.consultant.id).first()
        out["my_match"] = {"score": m.score, "match_details": m.match_details} if m else None
    return out


@router.put("/{job_id}", summary="Edit / close / reopen a job (re-matches)")
def update_job(job_id: int, payload: JobUpdate, background_tasks: BackgroundTasks, request: Request,
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    j = _get_owned(db, job_id, user)
    data = payload.model_dump(exclude_unset=True)
    if data.get("status") == "open" and j.status != "open":
        subs.ensure_can_open_job(db, j.client_id, exclude_job_id=j.id)
    bmin = data.get("budget_min", j.budget_min)
    bmax = data.get("budget_max", j.budget_max)
    if bmin is not None and bmax is not None and bmax < bmin:
        raise HTTPException(status_code=400, detail="budget_max must be greater than or equal to budget_min")
    for k, v in data.items():
        setattr(j, k, v)
    db.commit()
    db.refresh(j)
    if "status" in data:
        audit.log(db, f"job.{data['status']}", user.id, "job", j.id, None, request)
    background_tasks.add_task(matching.notify, matching.rematch_job(db, j))
    return job_out(db, j, owner_view=True)


@router.delete("/{job_id}", summary="Delete a job")
def delete_job(job_id: int, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    j = _get_owned(db, job_id, user)
    db.query(Document).filter(Document.owner_type == "job", Document.owner_id == j.id).delete()
    db.delete(j)
    db.commit()
    audit.log(db, "job.delete", user.id, "job", job_id, None, request)
    return {"status": "deleted", "id": job_id}


@router.post("/{job_id}/rematch", summary="Recompute matches for a job")
def rematch(job_id: int, background_tasks: BackgroundTasks, user: User = Depends(get_current_user),
            db: Session = Depends(get_db)):
    j = _get_owned(db, job_id, user)
    background_tasks.add_task(matching.notify, matching.rematch_job(db, j))
    return job_out(db, j, owner_view=True)


@router.get("/{job_id}/matches", summary="Ranked freelancers for a job (limited by plan)")
def job_matches(job_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = _get_owned(db, job_id, user)
    sub = subs.get_active(db, job.client_id)
    plan = sub.plan_type if sub else None
    limits = plan_limits(plan)
    rows = (db.query(Match, Consultant).join(Consultant, Consultant.id == Match.consultant_id)
            .filter(Match.job_id == job_id)
            .order_by(Match.score.desc(), Consultant.experience_years.desc(), Match.id).all())
    total = len(rows)
    admin = is_admin(user)
    cap = None if admin else (0 if sub is None else limits["max_visible_matches"])
    visible = rows if cap is None else rows[:cap]
    show_contact = admin or (bool(sub) and limits["show_contact_details"])
    proposals = {p.consultant_id: p.status for p in db.query(Proposal).filter(Proposal.job_id == job_id).all()}
    items = []
    for rank, (m, c) in enumerate(visible, start=1):
        items.append({
            "rank": rank, "match_id": m.id, "consultant_id": c.id, "name": c.name, "headline": c.headline,
            "email": c.email if show_contact else _mask_email(c.email),
            "phone": c.phone if show_contact else None, "skills": c.skills or [],
            "experience_years": c.experience_years or 0, "hourly_rate": c.hourly_rate, "currency": c.currency,
            "country": c.country, "timezone": c.timezone, "rating_avg": c.rating_avg, "rating_count": c.rating_count or 0,
            "badges": __import__("app.services.serializers", fromlist=["badges"]).badges(
                c.verified_at, c.rating_avg, c.rating_count, c.payout_status),
            "availability": c.availability, "score": m.score, "match_details": m.match_details,
            "proposal_status": proposals.get(c.id),
        })
    return {"job_id": job.id, "job_title": job.title, "job_status": job.status, "plan": plan,
            "total_matches": total, "visible_matches": len(items), "hidden_matches": total - len(items),
            "contact_details_visible": show_contact, "matches": items}


# ---- proposals on a job -----------------------------------------------------------------------
@router.post("/{job_id}/proposals", summary="Apply to a job (freelancer)")
async def apply(job_id: int, payload: ProposalIn, request: Request, me: Consultant = Depends(current_freelancer),
                db: Session = Depends(get_db)):
    job = _get(db, job_id)
    if job.status != "open":
        raise HTTPException(status_code=400, detail="This job is closed")
    p = Proposal(job_id=job.id, consultant_id=me.id, **payload.model_dump())
    db.add(p)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="You have already applied to this job")
    db.refresh(p)
    audit.log(db, "proposal.create", me.user_id, "proposal", p.id, {"job_id": job.id}, request)
    from app.services.notify import notify
    events = [{"type": "new_proposal", "job_id": job.id, "job_title": job.title, "freelancer_name": me.name,
               "user_ids": [], "admins": True}]
    events += notify(db, job.client.owner_user_id if job.client else None, "new_proposal",
                     f"New proposal from {me.name}", f"{me.name} applied to “{job.title}” with a bid of "
                     f"{p.bid_amount:,} {job.currency}.", f"/client/jobs/{job.id}?tab=proposals")
    await publish_all(events)
    return proposal_out(p, with_job=True)


@router.get("/{job_id}/proposals", summary="Proposals received for a job (job owner)")
def job_proposals(job_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = _get_owned(db, job_id, user)
    rows = db.query(Proposal).filter(Proposal.job_id == job.id).order_by(Proposal.id.desc()).all()
    scores = {m.consultant_id: m.score for m in db.query(Match).filter(Match.job_id == job.id).all()}
    out = []
    for p in rows:
        d = proposal_out(p, with_freelancer=True)
        d["match_score"] = scores.get(p.consultant_id)
        out.append(d)
    return out
