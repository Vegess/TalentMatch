import { Link } from "react-router-dom";
import { ago, budget, inr, label, money } from "../lib/format";
import { Avatar, Badge, Card, Skills, StatusBadge } from "./ui";
import { Badges, Place, Rating } from "./Trust";
import { flag } from "../lib/format";

export function JobCard({ job, to, score, extra }: { job: any; to: string; score?: number; extra?: React.ReactNode }) {
  return <Card className="anim-fade-up lift p-5">
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0">
        <Link to={to} className="text-base font-semibold text-slate-900 hover:text-brand-700">{job.title}</Link>
        <p className="mt-0.5 text-sm text-slate-500">{job.client?.country && <span aria-hidden>{flag(job.client.country)} </span>}{job.client?.company_name}{job.client?.verified && <span className="text-brand-600" title="Verified company"> ✓</span>} · {label(job.location_type)}{job.location ? `, ${job.location}` : ""} · {ago(job.created_at)}</p>
      </div>
      {score != null ? <Badge tone={score >= 85 ? "green" : "blue"}>{Math.round(score)}% match</Badge> : job.status !== "open" && <StatusBadge status={job.status} />}
    </div>
    <p className="mt-3 line-clamp-2 text-sm text-slate-600">{job.description}</p>
    <div className="mt-3"><Skills skills={job.required_skills} max={6} /></div>
    <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-1 text-sm text-slate-600">
      <span className="font-medium text-slate-900">{budget(job)}</span>
      {job.min_experience_years > 0 && <span>{job.min_experience_years}+ yrs</span>}
      <span>{job.proposal_count} proposal{job.proposal_count === 1 ? "" : "s"}</span>
      {extra}
    </div>
  </Card>;
}

export function FreelancerCard({ f }: { f: any }) {
  return <Card className="anim-fade-up lift flex flex-col p-5">
    <div className="flex items-center gap-3">
      <Avatar name={f.name} size={46} />
      <div className="min-w-0">
        <Link to={`/freelancers/${f.id}`} className="font-semibold text-slate-900 hover:text-brand-700">{f.name}</Link>
        <p className="truncate text-sm text-slate-500">{f.headline || "Freelancer"}</p>
      </div>
    </div>
    <div className="mt-3 flex flex-wrap items-center gap-2"><Rating avg={f.rating_avg} count={f.rating_count} /><Badges badges={f.badges} small /></div>
    <div className="mt-3 flex-1"><Skills skills={f.skills} max={5} /></div>
    <div className="mt-4 flex items-center justify-between gap-2 text-sm">
      <span className="truncate text-slate-600">{f.experience_years} yrs · <Place country={f.country} city={f.location} /></span>
      <span className="font-medium">{f.hourly_rate ? `${money(f.hourly_rate, f.currency)}/hr` : ""}</span>
    </div>
  </Card>;
}

export function ServiceCard({ s }: { s: any }) {
  return <Card className="anim-fade-up lift flex flex-col p-5">
    {s.category && <p className="text-xs font-medium uppercase tracking-wide text-brand-700">{s.category}</p>}
    <Link to={`/services/${s.id}`} className="mt-1 font-semibold leading-snug text-slate-900 hover:text-brand-700">{s.title}</Link>
    <div className="mt-3 flex items-center gap-2 text-sm text-slate-600"><Avatar name={s.freelancer?.name || "?"} size={24} />{s.freelancer?.name}
      {s.freelancer?.country && <span aria-hidden>{flag(s.freelancer.country)}</span>}</div>
    {(s.freelancer?.rating_count > 0 || s.freelancer?.badges?.length > 0) && <div className="mt-2 flex flex-wrap items-center gap-2"><Rating avg={s.freelancer.rating_avg} count={s.freelancer.rating_count} compact /><Badges badges={s.freelancer.badges} small /></div>}
    <div className="mt-4 flex flex-1 items-end justify-between">
      <span className="text-sm text-slate-500">{s.delivery_days}-day delivery</span>
      <span className="text-lg font-semibold">{money(s.price, s.currency)}</span>
    </div>
  </Card>;
}
