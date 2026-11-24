"""Matching between jobs and freelancer profiles.

Matches are kept in sync whenever a job or a profile is created or changed, so the ranked list
for a job is always complete (including freelancers who joined after the job was posted).
"""
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session

from app.core import config
from app.core.plugin_loader import PluginLoader
from app.models import Job, Consultant, Match, Client


def _plugin(name: Optional[str] = None):
    return PluginLoader().get_ranking_plugin(name or config.DEFAULT_RANKING_PLUGIN)


def score_pair(job: Job, consultant: Consultant, plugin_name: Optional[str] = None) -> Dict[str, Any]:
    plugin = _plugin(plugin_name)
    details = plugin.explain(
        {"skills": consultant.skills or [], "experience_years": consultant.experience_years or 0},
        {"skills": job.required_skills or [], "min_experience_years": job.min_experience_years or 0})
    details["plugin_used"] = (plugin_name or config.DEFAULT_RANKING_PLUGIN).rsplit(".", 1)[-1]
    return details


def upsert_match(db: Session, job: Job, consultant: Consultant, details: Dict[str, Any]) -> Tuple[Match, bool]:
    m = db.query(Match).filter(Match.job_id == job.id, Match.consultant_id == consultant.id).first()
    created = m is None
    if created:
        m = Match(job_id=job.id, consultant_id=consultant.id)
        db.add(m)
    m.score = details["score"]
    m.match_details = {k: v for k, v in details.items() if k != "score"}
    return m, created


def _eligible(job: Job, consultant: Consultant) -> bool:
    return job.status == "open" and bool(consultant.is_public) and bool(job.required_skills)


def _sync_pair(db: Session, job: Job, consultant: Consultant, events: List[Dict[str, Any]]):
    details = score_pair(job, consultant)
    if _eligible(job, consultant) and details["score"] >= config.MATCH_THRESHOLD:
        _, created = upsert_match(db, job, consultant, details)
        if created:
            client = db.get(Client, job.client_id)
            events.append({
                "type": "new_match", "job_id": job.id, "job_title": job.title,
                "consultant_id": consultant.id, "consultant_name": consultant.name, "score": details["score"],
                "user_ids": [u for u in (client.owner_user_id if client else None, consultant.user_id) if u],
            })
    else:
        db.query(Match).filter(Match.job_id == job.id, Match.consultant_id == consultant.id).delete()


def rematch_job(db: Session, job: Job) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for consultant in db.query(Consultant).all():
        _sync_pair(db, job, consultant, events)
    db.commit()
    return events


def match_consultant(db: Session, consultant: Consultant) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for job in db.query(Job).filter(Job.status == "open").all():
        _sync_pair(db, job, consultant, events)
    # profile hidden → drop matches on closed jobs too
    if not consultant.is_public:
        db.query(Match).filter(Match.consultant_id == consultant.id).delete()
    db.commit()
    return events


def rematch_all(db: Session) -> int:
    count = 0
    for job in db.query(Job).all():
        if job.status != "open":
            db.query(Match).filter(Match.job_id == job.id).delete()
            continue
        rematch_job(db, job)
        count += 1
    db.commit()
    return count


async def notify(events: List[Dict[str, Any]]):
    from app.services.realtime import manager
    for ev in events:
        await manager.publish(ev)
