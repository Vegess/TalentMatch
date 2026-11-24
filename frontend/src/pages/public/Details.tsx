import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { useApi, useTitle } from "../../lib/hooks";
import { budget, date, inr, label, lines, money } from "../../lib/format";
import { usePay } from "../../components/Checkout";
import { Documents } from "../../components/Documents";
import { ServiceCard } from "../../components/Cards";
import { Badges, Place, Rating, Stars } from "../../components/Trust";
import { MessageButton } from "../shared/Messages";
import { hour, flag, countryName, ago } from "../../lib/format";
import { useToast } from "../../components/Toast";
import { Avatar, Badge, Button, ButtonLink, Card, CardHeader, ErrorBox, Input, Loading, Notice, ScoreRing, Skills,
  StatusBadge, Textarea } from "../../components/ui";

export function JobDescription({ job }: { job: any }) {
  const resp = lines(job.responsibilities), req = lines(job.requirements);
  return <Card className="p-6">
    <div className="grid gap-4 border-b border-slate-100 pb-5 sm:grid-cols-4">
      {[["Budget", budget(job)], ["Work mode", `${label(job.location_type)}${job.location ? ` · ${job.location}` : ""}`],
        ["Experience", job.min_experience_years ? `${job.min_experience_years}+ years` : "Any"], ["Apply by", date(job.deadline)]]
        .map(([k, v]) => <div key={k}><p className="text-xs uppercase tracking-wide text-slate-500">{k}</p><p className="mt-1 font-medium">{v}</p></div>)}
    </div>
    <div className="prose-sm mt-5 space-y-5 text-slate-700">
      {job.description && <section><h3 className="mb-1 font-semibold text-slate-900">Overview</h3><p className="whitespace-pre-line" translate="no">{job.description}</p></section>}
      {resp.length > 0 && <section><h3 className="mb-1 font-semibold text-slate-900">Responsibilities</h3><ul className="list-disc space-y-1 pl-5" translate="no">{resp.map((r) => <li key={r}>{r}</li>)}</ul></section>}
      {req.length > 0 && <section><h3 className="mb-1 font-semibold text-slate-900">Requirements & nice-to-haves</h3><ul className="list-disc space-y-1 pl-5" translate="no">{req.map((r) => <li key={r}>{r}</li>)}</ul></section>}
      <section><h3 className="mb-2 font-semibold text-slate-900">Required skills</h3><Skills skills={job.required_skills} /></section>
    </div>
  </Card>;
}

export function JobDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const toast = useToast();
  const { data: job, error, loading, reload } = useApi<any>(`/api/v1/jobs/${id}`, [user?.id]);
  const [cover, setCover] = useState(""); const [bid, setBid] = useState(""); const [days, setDays] = useState("");
  const [busy, setBusy] = useState(false);
  useTitle(job?.title || "Job");
  if (loading && !job) return <Loading />;
  if (error) return <div className="mx-auto max-w-4xl px-4 py-10"><ErrorBox message={error} /></div>;
  const apply = async () => {
    setBusy(true);
    try {
      await api(`/api/v1/jobs/${id}/proposals`, { json: { cover_letter: cover, bid_amount: Number(bid), estimated_days: days ? Number(days) : null } });
      toast("Proposal sent", "success"); reload();
    } catch (e: any) { toast(e.message, "error"); } finally { setBusy(false); }
  };
  return <div className="mx-auto max-w-6xl px-4 py-10">
    <Link to="/jobs" className="text-sm text-slate-500 hover:text-brand-700">← All jobs</Link>
    <div className="mt-3 grid gap-6 lg:grid-cols-[1fr_340px]">
      <div className="space-y-6">
        <div><div className="flex flex-wrap items-center gap-2">{job.category && <Badge tone="blue">{job.category}</Badge>}<StatusBadge status={job.status} /></div>
          <h1 className="mt-2 text-3xl font-bold">{job.title}</h1>
          <p className="mt-1 text-slate-600">{job.client?.company_name}{job.client?.industry ? ` · ${job.client.industry}` : ""} · posted {date(job.created_at)}</p></div>
        <JobDescription job={job} />
        {user ? <Documents ownerType="job" ownerId={job.id} canEdit={!!job.viewer_is_owner} title="Attachments" subtitle="Full JD, briefs and reference material" />
          : <Notice tone="blue"><Link className="font-medium underline" to={`/login?next=/jobs/${job.id}`}>Sign in</Link> to see attachments ({job.document_count}).</Notice>}
      </div>
      <aside className="space-y-4">
        {job.viewer_is_owner ? <Card className="p-5"><p className="text-sm text-slate-600">This is your job.</p>
          <ButtonLink className="mt-3 w-full" to={`/client/jobs/${job.id}`}>Manage job & see matches</ButtonLink></Card>
          : user?.role === "freelancer" ? <>
            {job.my_match && <Card className="flex items-center gap-4 p-5"><ScoreRing score={job.my_match.score} />
              <div><p className="font-medium">Your match</p><Skills matched={job.my_match.match_details?.matched_skills} missing={job.my_match.match_details?.missing_skills} /></div></Card>}
            {job.my_proposal ? <Card className="p-5"><p className="font-medium">You applied</p>
              <p className="mt-1 text-sm text-slate-600">Bid {money(job.my_proposal.bid_amount, job.currency)} · <StatusBadge status={job.my_proposal.status} /></p>
              <div className="mt-3 flex flex-wrap gap-2"><ButtonLink to="/freelancer/proposals" variant="secondary" size="sm">View my proposals</ButtonLink>
                <MessageButton clientId={job.client?.id} jobId={job.id} label="Message client" /></div></Card>
              : job.status === "open" && <Card><CardHeader title="Apply to this job" />
                <div className="space-y-3 p-5">
                  <Textarea label="Cover letter" rows={5} value={cover} onChange={(e) => setCover(e.target.value)} placeholder="Why you're a good fit (min 20 characters)" />
                  <div className="grid grid-cols-2 gap-3">
                    <Input label={`Your bid (${job.currency}${job.budget_type === "hourly" ? "/hr" : ""})`} type="number" min={5} value={bid} onChange={(e) => setBid(e.target.value)} />
                    <Input label="Days needed" type="number" min={1} value={days} onChange={(e) => setDays(e.target.value)} /></div>
                  <Button className="w-full" onClick={apply} loading={busy} disabled={cover.trim().length < 20 || !bid}>Send proposal</Button>
                </div></Card>}</>
            : !user ? <Card className="p-5"><p className="font-medium">Interested?</p><p className="mt-1 text-sm text-slate-600">Create a free freelancer account to see your match score and apply.</p>
              <ButtonLink className="mt-3 w-full" to="/register?role=freelancer">Join as a freelancer</ButtonLink>
              <ButtonLink className="mt-2 w-full" variant="ghost" to={`/login?next=/jobs/${job.id}`}>Sign in</ButtonLink></Card> : null}
        <Card className="p-5"><p className="text-xs uppercase tracking-wide text-slate-500">About the client</p>
          <p className="mt-1 font-medium">{job.client?.company_name}{job.client?.verified && <span className="ml-1 text-brand-600" title="Verified company">✓</span>}</p>
          {job.client?.country && <p className="text-sm text-slate-600">{flag(job.client.country)} {countryName(job.client.country)}</p>}
          <div className="mt-1"><Rating avg={job.client?.rating_avg} count={job.client?.rating_count} /></div>
          {job.client?.industry && <p className="text-sm text-slate-600">{job.client.industry}</p>}
          {job.client?.website && <a className="text-sm text-brand-700 hover:underline" href={job.client.website} target="_blank" rel="noopener noreferrer nofollow">{new URL(job.client.website).hostname}</a>}
          <p className="mt-2 text-sm text-slate-500">{job.proposal_count} proposal{job.proposal_count === 1 ? "" : "s"} so far</p></Card>
      </aside>
    </div>
  </div>;
}

export function FreelancerDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const { data: f, error, loading } = useApi<any>(`/api/v1/freelancers/${id}`, [user?.id]);
  const reviews = useApi<any>(`/api/v1/reviews/freelancer/${id}`);
  useTitle(f?.name || "Freelancer");
  if (loading && !f) return <Loading />;
  if (error) return <div className="mx-auto max-w-4xl px-4 py-10"><ErrorBox message={error} /></div>;
  return <div className="mx-auto max-w-6xl px-4 py-10">
    <Link to="/freelancers" className="text-sm text-slate-500 hover:text-brand-700">← All freelancers</Link>
    <div className="mt-3 grid gap-6 lg:grid-cols-[1fr_320px]">
      <div className="space-y-6">
        <Card className="p-6"><div className="flex flex-wrap items-center gap-4"><Avatar name={f.name} size={72} />
          <div className="flex-1"><h1 className="flex flex-wrap items-center gap-2 text-2xl font-bold">{f.name}<Badges badges={f.badges} /></h1><p className="text-slate-600">{f.headline}</p>
            <p className="mt-1 text-sm"><Place country={f.country} city={f.location} timezone={f.timezone} showTime /></p>
            <div className="mt-1 flex flex-wrap items-center gap-3 text-sm text-slate-500"><Rating avg={f.rating_avg} count={f.rating_count} /><span>{f.experience_years} years experience</span></div></div>
          <StatusBadge status={f.availability} /></div>
          {f.bio && <p className="mt-5 whitespace-pre-line text-slate-700">{f.bio}</p>}
          <div className="mt-5"><Skills skills={f.skills} /></div></Card>
        <Card><div className="flex items-center justify-between border-b border-slate-100 px-5 py-4"><h2 className="font-semibold">Reviews</h2>
          {reviews.data?.rating_count > 0 && <span className="flex items-center gap-2 text-sm"><Stars value={reviews.data.rating_avg} /><b>{reviews.data.rating_avg.toFixed(1)}</b><span className="text-slate-500">from {reviews.data.rating_count}</span></span>}</div>
          {!reviews.data?.items?.length ? <p className="px-5 py-6 text-sm text-slate-500">No reviews yet. Reviews appear after completed orders.</p> :
            <ul className="divide-y divide-slate-100">{reviews.data.items.map((r: any) => <li key={r.id} className="px-5 py-4">
              <div className="flex flex-wrap items-center justify-between gap-2"><span className="flex items-center gap-2"><Stars value={r.rating} /><b className="text-sm">{r.reviewer_name}</b></span>
                <span className="text-xs text-slate-400">{ago(r.created_at)}</span></div>
              {r.comment && <p className="mt-2 text-sm text-slate-700">“{r.comment}”</p>}
              <p className="mt-1 text-xs text-slate-500">{r.order_title}</p></li>)}</ul>}</Card>
        {f.services?.length > 0 && <div><h2 className="mb-3 text-lg font-semibold">Services</h2>
          <div className="grid gap-4 sm:grid-cols-2">{f.services.map((s: any) => <ServiceCard key={s.id} s={s} />)}</div></div>}
        {user ? <Documents ownerType="consultant" ownerId={f.id} canEdit={user.consultant_id === f.id || user.role === "admin"} title="CV, portfolio & certificates" />
          : <Notice tone="blue"><Link className="font-medium underline" to={`/login?next=/freelancers/${f.id}`}>Sign in</Link> to see CV and portfolio documents.</Notice>}
      </div>
      <aside className="space-y-4">
        <Card className="p-5"><p className="text-xs uppercase tracking-wide text-slate-500">Rate</p>
          <p className="mt-1 text-2xl font-semibold">{f.hourly_rate ? `${money(f.hourly_rate, f.currency)}/hr` : "On request"}</p>
          {user?.role === "client" ? <div className="mt-4 space-y-2"><MessageButton consultantId={f.id} label={`Message ${f.name.split(" ")[0]}`} variant="primary" size="md" />
            <ButtonLink className="w-full" variant="secondary" to="/client/jobs/new">Post a job</ButtonLink></div>
            : !user && <ButtonLink className="mt-4 w-full" to="/register?role=client">Hire {f.name.split(" ")[0]}</ButtonLink>}</Card>
        {(f.work_start_hour != null || f.languages?.length > 0) && <Card className="space-y-2 p-5 text-sm">
          {f.work_start_hour != null && f.work_end_hour != null && <div><p className="text-xs uppercase tracking-wide text-slate-500">Working hours</p>
            <p className="mt-0.5">{hour(f.work_start_hour)} – {hour(f.work_end_hour)} <span className="text-slate-500">({f.timezone})</span></p></div>}
          {f.languages?.length > 0 && <div><p className="text-xs uppercase tracking-wide text-slate-500">Languages</p><p className="mt-0.5">{f.languages.join(", ")}</p></div>}
        </Card>}
        {f.links?.length > 0 && <Card className="p-5"><p className="mb-2 text-xs uppercase tracking-wide text-slate-500">Links</p>
          <ul className="space-y-1.5">{f.links.map((l: any) => <li key={l.url}><a href={l.url} target="_blank" rel="noopener noreferrer nofollow" className="text-sm font-medium text-brand-700 hover:underline">{l.label} ↗</a></li>)}</ul></Card>}
      </aside>
    </div>
  </div>;
}

export function ServiceDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const toast = useToast();
  const pay = usePay();
  const nav = useNavigate();
  const { data: s, error, loading } = useApi<any>(`/api/v1/services/${id}`, [user?.id]);
  const [brief, setBrief] = useState("");
  const [busy, setBusy] = useState(false);
  useTitle(s?.title || "Service");
  if (loading && !s) return <Loading />;
  if (error) return <div className="mx-auto max-w-4xl px-4 py-10"><ErrorBox message={error} /></div>;
  const buy = async () => {
    setBusy(true);
    try {
      const order = await api(`/api/v1/services/${id}/order`, { json: { requirements: brief || null } });
      const r = await pay({ purpose: "order", order_id: order.id });
      if (r.status === "paid") toast("Payment received — the freelancer can start.", "success");
      else toast("Payment not completed. You can pay later from Orders.", "info");
      nav(`/orders/${order.id}`);
    } catch (e: any) { toast(e.message, "error"); } finally { setBusy(false); }
  };
  return <div className="mx-auto max-w-6xl px-4 py-10">
    <Link to="/services" className="text-sm text-slate-500 hover:text-brand-700">← All services</Link>
    <div className="mt-3 grid gap-6 lg:grid-cols-[1fr_340px]">
      <div className="space-y-6">
        <div>{s.category && <Badge tone="blue">{s.category}</Badge>}<h1 className="mt-2 text-3xl font-bold">{s.title}</h1>
          <Link to={`/freelancers/${s.freelancer?.id}`} className="mt-3 flex items-center gap-2 text-slate-700 hover:text-brand-700"><Avatar name={s.freelancer?.name || "?"} size={30} />{s.freelancer?.name} · {s.freelancer?.headline}</Link>
          <div className="mt-2 flex flex-wrap items-center gap-2"><Rating avg={s.freelancer?.rating_avg} count={s.freelancer?.rating_count} /><Badges badges={s.freelancer?.badges} small /></div></div>
        <Card className="space-y-5 p-6">
          {s.description && <p className="whitespace-pre-line text-slate-700">{s.description}</p>}
          {lines(s.deliverables).length > 0 && <section><h3 className="mb-1 font-semibold">What's included</h3>
            <ul className="space-y-1 text-slate-700">{lines(s.deliverables).map((d) => <li key={d}>✓ {d}</li>)}</ul></section>}
          <Skills skills={s.skills} /></Card>
        {user && <Documents ownerType="service" ownerId={s.id} canEdit={!!s.viewer_is_owner} title="Samples & attachments" />}
      </div>
      <aside><Card className="sticky top-20 p-5">
        <p className="text-3xl font-bold">{money(s.price, s.currency)}</p><p className="mt-1 text-sm text-slate-500">Delivered in {s.delivery_days} days</p>
        {s.viewer_is_owner ? <Notice tone="blue">This is your service. Edit it from My services.</Notice>
          : user?.role === "client" ? <div className="mt-4 space-y-3">
            <Textarea label="Your brief (optional)" rows={4} value={brief} onChange={(e) => setBrief(e.target.value)} />
            <Button className="w-full" onClick={buy} loading={busy}>Buy for {money(s.price, s.currency)}</Button>
            <p className="text-xs text-slate-500">Paid securely via Razorpay. The freelancer is paid after you approve the delivery.</p></div>
            : !user ? <ButtonLink className="mt-4 w-full" to={`/login?next=/services/${s.id}`}>Sign in to buy</ButtonLink>
              : <p className="mt-4 text-sm text-slate-500">Only client accounts can buy services.</p>}
      </Card></aside>
    </div>
  </div>;
}

export function NotFound() {
  useTitle("Not found");
  return <div className="mx-auto max-w-lg px-4 py-24 text-center"><p className="text-6xl font-bold text-brand-600">404</p>
    <p className="mt-3 text-slate-600">This page doesn't exist.</p><ButtonLink to="/" className="mt-6">Go home</ButtonLink></div>;
}
