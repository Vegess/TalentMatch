"""Turn ORM rows into API dicts. Public views never include private contact details."""
from typing import Optional
from sqlalchemy.orm import Session

from app.models import Consultant, Job, Service, Proposal, Order, Document, Client, Match, User, Payment


def rupees(paise: Optional[int]) -> Optional[float]:
    return None if paise is None else round(paise / 100, 2)


def badges(verified_at, rating_avg, rating_count, payout_status=None) -> list:
    b = []
    if verified_at:
        b.append("verified")
    if payout_status == "active":
        b.append("payouts_verified")
    if rating_avg is not None and (rating_count or 0) >= 3 and rating_avg >= 4.5:
        b.append("top_rated")
    return b


def freelancer_out(c: Consultant, private: bool = False, db: Optional[Session] = None) -> dict:
    from app.core.geo import region_of
    out = {
        "id": c.id, "name": c.name, "headline": c.headline, "bio": c.bio, "location": c.location,
        "hourly_rate": c.hourly_rate, "currency": c.currency or "INR", "availability": c.availability,
        "links": c.links or [], "skills": c.skills or [], "experience_years": c.experience_years or 0,
        "created_at": c.created_at, "has_account": c.user_id is not None,
        "country": c.country, "timezone": c.timezone, "region": region_of(c.timezone),
        "work_start_hour": c.work_start_hour, "work_end_hour": c.work_end_hour, "languages": c.languages or [],
        "rating_avg": round(c.rating_avg, 2) if c.rating_avg is not None else None, "rating_count": c.rating_count or 0,
        "badges": badges(c.verified_at, c.rating_avg, c.rating_count, c.payout_status),
    }
    if db is not None:
        out["active_services"] = db.query(Service).filter(Service.consultant_id == c.id,
                                                          Service.status == "active").count()
    if private:
        out.update({"email": c.email, "phone": c.phone, "is_public": c.is_public, "source": c.source,
                    "user_id": c.user_id, "payout_status": c.payout_status, "payout_masked": c.payout_masked})
    return out


def client_mini(c: Optional[Client]) -> Optional[dict]:
    if not c:
        return None
    return {"id": c.id, "company_name": c.company_name or c.name, "industry": c.industry, "website": c.website,
            "country": c.country, "rating_avg": round(c.rating_avg, 2) if c.rating_avg is not None else None,
            "rating_count": c.rating_count or 0, "verified": bool(c.verified_at)}


def client_out(db: Session, c: Client) -> dict:
    from app.services import subscriptions as subs
    return {"id": c.id, "name": c.name, "email": c.email, "company_name": c.company_name, "website": c.website,
            "industry": c.industry, "about": c.about, "created_at": c.created_at,
            "owner_user_id": c.owner_user_id, "current_plan": subs.current_plan(db, c.id),
            "country": c.country, "timezone": c.timezone, "currency": c.currency or "INR",
            "verified": bool(c.verified_at), "rating_avg": c.rating_avg, "rating_count": c.rating_count or 0,
            "open_jobs": subs.open_job_count(db, c.id)}


def job_out(db: Session, j: Job, owner_view: bool = False) -> dict:
    out = {
        "id": j.id, "client_id": j.client_id, "client": client_mini(j.client), "title": j.title,
        "category": j.category, "description": j.description or "", "responsibilities": j.responsibilities,
        "requirements": j.requirements, "required_skills": j.required_skills or [],
        "min_experience_years": j.min_experience_years or 0, "budget_type": j.budget_type,
        "budget_min": j.budget_min, "budget_max": j.budget_max, "currency": j.currency or "INR",
        "location_type": j.location_type,
        "location": j.location, "deadline": j.deadline, "status": j.status, "created_at": j.created_at,
        "proposal_count": db.query(Proposal).filter(Proposal.job_id == j.id).count(),
        "document_count": db.query(Document).filter(Document.owner_type == "job", Document.owner_id == j.id).count(),
    }
    if owner_view:
        out["match_count"] = db.query(Match).filter(Match.job_id == j.id).count()
    return out


def service_out(s: Service) -> dict:
    c = s.consultant
    return {"id": s.id, "consultant_id": s.consultant_id, "title": s.title, "category": s.category,
            "description": s.description, "deliverables": s.deliverables, "price": s.price,
            "currency": s.currency or "INR",
            "delivery_days": s.delivery_days, "skills": s.skills or [], "status": s.status,
            "created_at": s.created_at,
            "freelancer": {"id": c.id, "name": c.name, "headline": c.headline, "location": c.location,
                           "country": c.country, "experience_years": c.experience_years,
                           "rating_avg": round(c.rating_avg, 2) if c.rating_avg is not None else None,
                           "rating_count": c.rating_count or 0,
                           "badges": badges(c.verified_at, c.rating_avg, c.rating_count, c.payout_status)} if c else None}


def proposal_out(p: Proposal, with_job: bool = False, with_freelancer: bool = False) -> dict:
    out = {"id": p.id, "job_id": p.job_id, "consultant_id": p.consultant_id, "cover_letter": p.cover_letter,
           "bid_amount": p.bid_amount, "currency": (p.job.currency if p.job else None) or "INR",
           "estimated_days": p.estimated_days, "status": p.status,
           "created_at": p.created_at}
    if with_job and p.job:
        out["job"] = {"id": p.job.id, "title": p.job.title, "status": p.job.status,
                      "client": client_mini(p.job.client)}
    if with_freelancer and p.consultant:
        c = p.consultant
        out["freelancer"] = {"id": c.id, "name": c.name, "headline": c.headline, "skills": c.skills or [],
                             "experience_years": c.experience_years, "hourly_rate": c.hourly_rate,
                             "currency": c.currency, "country": c.country,
                             "rating_avg": round(c.rating_avg, 2) if c.rating_avg is not None else None,
                             "rating_count": c.rating_count or 0,
                             "badges": badges(c.verified_at, c.rating_avg, c.rating_count, c.payout_status)}
    return out


def order_out(o: Order) -> dict:
    return {
        "id": o.id, "title": o.title, "status": o.status, "payout_status": o.payout_status,
        "amount": rupees(o.amount_paise), "platform_fee": rupees(o.platform_fee_paise),
        "freelancer_earnings": rupees(o.amount_paise - o.platform_fee_paise), "currency": o.currency,
        "requirements": o.requirements, "delivery_note": o.delivery_note,
        "client": client_mini(o.client), "client_id": o.client_id,
        "freelancer": {"id": o.consultant.id, "name": o.consultant.name, "user_id": o.consultant.user_id} if o.consultant else None,
        "consultant_id": o.consultant_id, "service_id": o.service_id, "job_id": o.job_id,
        "proposal_id": o.proposal_id, "created_at": o.created_at, "paid_at": o.paid_at,
        "delivered_at": o.delivered_at, "completed_at": o.completed_at,
        "payout_mode": o.payout_mode, "transfer_id": o.transfer_id, "transfer_status": o.transfer_status,
        "payout_error": o.payout_error, "payout_released_at": o.payout_released_at,
    }


def payment_out(p: Payment) -> dict:
    return {"id": p.id, "purpose": p.purpose, "plan_type": p.plan_type, "months": p.months, "order_id": p.order_id,
            "amount": rupees(p.amount_paise), "currency": p.currency, "provider": p.provider,
            "provider_order_id": p.provider_order_id, "provider_payment_id": p.provider_payment_id,
            "status": p.status, "error": p.error, "created_at": p.created_at, "paid_at": p.paid_at,
            "user": {"id": p.user.id, "name": p.user.name, "email": p.user.email} if p.user else None,
            "client": client_mini(p.client)}


def document_out(d: Document) -> dict:
    return {"id": d.id, "owner_type": d.owner_type, "owner_id": d.owner_id, "kind": d.kind, "title": d.title,
            "url": d.url if d.kind == "url" else None, "filename": d.filename, "content_type": d.content_type,
            "size_bytes": d.size_bytes, "created_at": d.created_at, "uploaded_by": d.uploaded_by,
            "download_url": f"/api/v1/documents/{d.id}/download" if d.kind == "file" else None}


def user_admin_out(u: User) -> dict:
    verified = None
    if u.role == "client" and u.client:
        verified = bool(u.client.verified_at)
    elif u.role == "freelancer" and u.consultant:
        verified = bool(u.consultant.verified_at)
    country = (u.client.country if u.role == "client" and u.client else
               u.consultant.country if u.role == "freelancer" and u.consultant else None)
    return {"id": u.id, "email": u.email, "name": u.name, "role": u.role, "is_active": u.is_active,
            "created_at": u.created_at, "last_login_at": u.last_login_at, "verified": verified, "country": country}
