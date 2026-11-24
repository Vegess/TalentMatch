import { useCallback, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { useApi, useTitle } from "../../lib/hooks";
import { useLiveReload } from "../../lib/realtime";
import { ago, date, inr, money } from "../../lib/format";
import { usePay } from "../../components/Checkout";
import { Documents } from "../../components/Documents";
import { JobForm } from "../../components/Forms";
import { JobDescription } from "../public/Details";
import { MessageButton } from "../shared/Messages";
import { Badges, Place, Rating } from "../../components/Trust";
import { PlanCards } from "../public/Pricing";
import { useToast } from "../../components/Toast";
import { Avatar, Badge, Button, ButtonLink, Card, CardHeader, Empty, ErrorBox, Loading, Modal, Notice, PageHeader,
  ScoreRing, Skills, Stat, StatusBadge, Table, Tabs, Td } from "../../components/ui";

export function ClientDashboard() {
  useTitle("Dashboard");
  const { user } = useAuth();
  const [params] = useSearchParams();
  const jobs = useApi<any[]>("/api/v1/jobs/mine");
  const orders = useApi<any[]>("/api/v1/orders");
  const sub = useApi<any>("/api/v1/subscriptions/me");
  useLiveReload(["new_match", "new_proposal", "order_delivered", "plan_activated"], useCallback(() => { jobs.reload(); orders.reload(); sub.reload(); }, []));
  const open = (jobs.data || []).filter((j) => j.status === "open");
  const matches = open.reduce((a, j) => a + (j.match_count || 0), 0);
  const proposals = open.reduce((a, j) => a + (j.proposal_count || 0), 0);
  const toReview = (orders.data || []).filter((o) => o.status === "delivered");
  const unpaid = (orders.data || []).filter((o) => o.status === "pending_payment");
  const limits = sub.data?.limits;
  return <>
    <PageHeader title={`Welcome${params.get("welcome") ? "" : " back"}, ${user?.name.split(" ")[0]}`} subtitle={user?.company_name || undefined}
      actions={<ButtonLink to="/client/jobs/new">Post a job</ButtonLink>} />
    {params.get("welcome") && <div className="mb-6"><Notice tone="blue">You're on the <b>Free</b> plan: post up to 2 jobs and see the top 3 matches for each. Start by posting your first job description.</Notice></div>}
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <Stat label="Open jobs" value={limits ? `${sub.data.open_jobs}${limits.max_open_jobs != null ? ` / ${limits.max_open_jobs}` : ""}` : open.length} hint={sub.data?.active ? `${sub.data.active.plan_type} plan` : "No active plan"} accent />
      <Stat label="Ranked matches" value={matches} hint="across open jobs" />
      <Stat label="Proposals received" value={proposals} />
      <Stat label="Orders to review" value={toReview.length} hint={unpaid.length ? `${unpaid.length} awaiting payment` : undefined} />
    </div>
    <div className="mt-6 grid gap-6 lg:grid-cols-[1.4fr_1fr]">
      <Card><CardHeader title="Your open jobs" action={<Link to="/client/jobs" className="text-sm font-medium text-brand-700">All jobs</Link>} />
        {jobs.loading && !jobs.data ? <Loading /> : !open.length ? <Empty title="No open jobs" action={<ButtonLink to="/client/jobs/new" size="sm">Post a job</ButtonLink>}>Post a job description and we'll rank freelancers for it straight away.</Empty> :
          <ul className="divide-y divide-slate-100">{open.slice(0, 6).map((j) => <li key={j.id}><Link to={`/client/jobs/${j.id}`} className="flex items-center justify-between gap-4 px-5 py-3 hover:bg-slate-50">
            <div className="min-w-0"><p className="truncate font-medium">{j.title}</p><p className="text-xs text-slate-500">Posted {ago(j.created_at)}</p></div>
            <div className="flex shrink-0 gap-2"><Badge tone="blue">{j.match_count} matches</Badge><Badge>{j.proposal_count} proposals</Badge></div></Link></li>)}</ul>}
      </Card>
      <Card><CardHeader title="Needs your attention" />
        {!toReview.length && !unpaid.length ? <Empty title="All caught up" icon="✓" /> :
          <ul className="divide-y divide-slate-100">{[...toReview, ...unpaid].map((o) => <li key={o.id}><Link to={`/orders/${o.id}`} className="flex items-center justify-between gap-3 px-5 py-3 hover:bg-slate-50">
            <div className="min-w-0"><p className="truncate text-sm font-medium">{o.title}</p><p className="text-xs text-slate-500">{o.freelancer?.name} · {money(o.amount, o.currency)}</p></div>
            <StatusBadge status={o.status} /></Link></li>)}</ul>}
      </Card>
    </div>
  </>;
}

export function MyJobs() {
  useTitle("My jobs");
  const { data, error, loading, reload } = useApi<any[]>("/api/v1/jobs/mine");
  return <>
    <PageHeader title="My jobs" actions={<ButtonLink to="/client/jobs/new">Post a job</ButtonLink>} />
    <Card>{error ? <div className="p-4"><ErrorBox message={error} onRetry={reload} /></div> : loading && !data ? <Loading /> : !data!.length ? <Empty title="No jobs yet" action={<ButtonLink to="/client/jobs/new" size="sm">Post your first job</ButtonLink>} /> :
      <Table head={["Job", "Status", "Matches", "Proposals", "Posted"]}>{data!.map((j) => <tr key={j.id} className="hover:bg-slate-50">
        <Td><Link to={`/client/jobs/${j.id}`} className="font-medium text-slate-900 hover:text-brand-700">{j.title}</Link><div className="mt-1"><Skills skills={j.required_skills} max={4} /></div></Td>
        <Td><StatusBadge status={j.status} /></Td><Td>{j.match_count}</Td><Td>{j.proposal_count}</Td><Td className="whitespace-nowrap text-slate-500">{date(j.created_at)}</Td></tr>)}</Table>}</Card>
  </>;
}

export function NewJob() {
  useTitle("Post a job");
  const nav = useNavigate();
  const toast = useToast();
  return <>
    <PageHeader title="Post a job" subtitle="A clear job description gets better matches and proposals. You can attach files after posting." crumbs={[{ to: "/client/jobs", label: "My jobs" }]} />
    <JobForm submitLabel="Post job & find matches" onSubmit={async (body) => {
      try {
        const j = await api("/api/v1/jobs", { json: body });
        toast(`Job posted — ${j.match_count} freelancer${j.match_count === 1 ? "" : "s"} matched.`, "success");
        nav(`/client/jobs/${j.id}?tab=matches`);
      } catch (e: any) { toast(e.message, "error"); }
    }} />
  </>;
}

function Matches({ jobId }: { jobId: number }) {
  const { data, error, loading, reload } = useApi<any>(`/api/v1/jobs/${jobId}/matches`);
  const toast = useToast();
  useLiveReload(["new_match"], reload);
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const rematch = async () => { await api(`/api/v1/jobs/${jobId}/rematch`, { method: "POST" }); toast("Matches recomputed", "success"); reload(); };
  return <div className="space-y-4">
    {!data.plan && <Notice>You have no active plan, so matches are hidden. <Link className="font-medium underline" to="/client/billing">Choose a plan</Link>.</Notice>}
    {data.plan && data.hidden_matches > 0 && <Notice>{data.hidden_matches} more match{data.hidden_matches === 1 ? " is" : "es are"} hidden on the {data.plan} plan. <Link className="font-medium underline" to="/client/billing">Upgrade</Link> to see everyone.</Notice>}
    {data.plan && !data.contact_details_visible && <Notice tone="blue">Contact details are masked on the Free plan. Invite matches by asking them to apply, or upgrade.</Notice>}
    <Card><CardHeader title={`${data.total_matches} ranked match${data.total_matches === 1 ? "" : "es"}`} subtitle="Skills 70% · experience 30% · only 50%+ shown" action={<Button size="sm" variant="secondary" onClick={rematch}>Recompute</Button>} />
      {!data.matches.length ? <Empty title={data.job_status === "closed" ? "This job is closed" : "No matches yet"}>{data.job_status === "closed" ? "Reopen it to match again." : "We'll notify you as soon as a freelancer with these skills joins."}</Empty> :
        <ul className="divide-y divide-slate-100">{data.matches.map((m: any) => <li key={m.match_id} className="flex flex-wrap items-center gap-4 px-5 py-4">
          <span className="w-5 text-sm font-semibold text-slate-400">{m.rank}</span>
          <ScoreRing score={m.score} />
          <div className="min-w-[220px] flex-1">
            <div className="flex flex-wrap items-center gap-2"><Link to={`/freelancers/${m.consultant_id}`} className="font-semibold hover:text-brand-700">{m.name}</Link>
              <StatusBadge status={m.availability} />{m.proposal_status && <Badge tone="violet">Applied · {m.proposal_status}</Badge>}</div>
            <p className="text-sm text-slate-500">{m.headline} · {m.experience_years} yrs{m.hourly_rate ? ` · ${money(m.hourly_rate, m.currency)}/hr` : ""}</p>
            <div className="mt-0.5 flex flex-wrap items-center gap-2 text-xs"><Place country={m.country} timezone={m.timezone} showTime /><Rating avg={m.rating_avg} count={m.rating_count} compact /><Badges badges={m.badges} small /></div>
            <p className="text-xs text-slate-500">{m.email}{m.phone ? ` · ${m.phone}` : ""}</p>
            <div className="mt-2"><Skills matched={m.match_details?.matched_skills} missing={m.match_details?.missing_skills} /></div>
          </div>
          <MessageButton consultantId={m.consultant_id} jobId={jobId} />
        </li>)}</ul>}
    </Card>
  </div>;
}

function Proposals({ jobId, onHired }: { jobId: number; onHired: (orderId: number) => void }) {
  const { data, error, loading, reload } = useApi<any[]>(`/api/v1/jobs/${jobId}/proposals`);
  const toast = useToast();
  const pay = usePay();
  const [hire, setHire] = useState<any | null>(null);
  const [busy, setBusy] = useState(false);
  useLiveReload(["new_proposal"], reload);
  const act = async (id: number, action: "shortlist" | "reject") => {
    try { await api(`/api/v1/proposals/${id}/${action}`, { method: "POST" }); reload(); } catch (e: any) { toast(e.message, "error"); }
  };
  const confirmHire = async () => {
    setBusy(true);
    try {
      const order = await api(`/api/v1/proposals/${hire.id}/accept`, { method: "POST" });
      setHire(null);
      const r = await pay({ purpose: "order", order_id: order.id });
      toast(r.status === "paid" ? "Paid — work can start." : "Hired. Pay from the order page to start the work.", r.status === "paid" ? "success" : "info");
      onHired(order.id);
    } catch (e: any) { toast(e.message, "error"); } finally { setBusy(false); }
  };
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  return <Card>
    {!data!.length ? <Empty title="No proposals yet" icon="✉">Freelancers who apply will appear here with their match score.</Empty> :
      <ul className="divide-y divide-slate-100">{data!.map((p) => <li key={p.id} className="px-5 py-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-center gap-3"><Avatar name={p.freelancer.name} />
            <div><Link to={`/freelancers/${p.freelancer.id}`} className="font-semibold hover:text-brand-700">{p.freelancer.name}</Link>
              <p className="text-sm text-slate-500">{p.freelancer.headline} · {p.freelancer.experience_years} yrs</p>
              <div className="flex flex-wrap items-center gap-2 text-xs"><Place country={p.freelancer.country} /><Rating avg={p.freelancer.rating_avg} count={p.freelancer.rating_count} compact /><Badges badges={p.freelancer.badges} small /></div></div></div>
          <div className="text-right"><p className="text-lg font-semibold">{money(p.bid_amount, p.currency)}</p>
            <p className="text-xs text-slate-500">{p.estimated_days ? `${p.estimated_days} days · ` : ""}{ago(p.created_at)}</p></div>
        </div>
        <p className="mt-3 whitespace-pre-line text-sm text-slate-700">{p.cover_letter}</p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <StatusBadge status={p.status} />{p.match_score != null && <Badge tone="blue">{Math.round(p.match_score)}% match</Badge>}
          <span className="flex-1" />
          <MessageButton consultantId={p.freelancer.id} jobId={jobId} />
          {["submitted", "shortlisted"].includes(p.status) && <>
            {p.status === "submitted" && <Button size="sm" variant="secondary" onClick={() => act(p.id, "shortlist")}>Shortlist</Button>}
            <Button size="sm" variant="ghost" onClick={() => act(p.id, "reject")}>Decline</Button>
            <Button size="sm" onClick={() => setHire(p)}>Hire</Button></>}
        </div>
      </li>)}</ul>}
    <Modal open={!!hire} onClose={() => setHire(null)} title={`Hire ${hire?.freelancer?.name}`}
      footer={<><Button variant="ghost" onClick={() => setHire(null)}>Cancel</Button><Button onClick={confirmHire} loading={busy}>Hire & pay {hire && money(hire.bid_amount, hire.currency)}</Button></>}>
      <p className="text-sm text-slate-600">This creates an order for <b>{hire && money(hire.bid_amount, hire.currency)}</b>. You pay now; the platform holds the money and pays the freelancer after you approve the delivered work.</p>
    </Modal>
  </Card>;
}

export function ManageJob() {
  const { id } = useParams();
  const [params, setParams] = useSearchParams();
  const nav = useNavigate();
  const toast = useToast();
  const { data: job, error, loading, reload } = useApi<any>(`/api/v1/jobs/${id}`);
  const [confirmDelete, setConfirmDelete] = useState(false);
  useTitle(job?.title || "Job");
  const tab = params.get("tab") || "matches";
  if (loading && !job) return <Loading />;
  if (error) return <ErrorBox message={error} />;
  const toggle = async () => {
    try { await api(`/api/v1/jobs/${id}`, { method: "PUT", json: { status: job.status === "open" ? "closed" : "open" } }); reload(); toast(job.status === "open" ? "Job closed" : "Job reopened", "success"); }
    catch (e: any) { toast(e.message, "error"); }
  };
  const del = async () => { await api(`/api/v1/jobs/${id}`, { method: "DELETE" }); toast("Job deleted", "success"); nav("/client/jobs"); };
  return <>
    <PageHeader crumbs={[{ to: "/client/jobs", label: "My jobs" }]} title={<span className="flex flex-wrap items-center gap-3">{job.title}<StatusBadge status={job.status} /></span>}
      subtitle={`Posted ${date(job.created_at)} · ${job.proposal_count} proposals`}
      actions={<><Button variant="secondary" onClick={toggle}>{job.status === "open" ? "Close job" : "Reopen job"}</Button>
        <ButtonLink variant="secondary" to={`/jobs/${job.id}`}>Public view</ButtonLink></>} />
    <Tabs value={tab} onChange={(t) => setParams({ tab: t })} tabs={[{ id: "matches", label: `Ranked matches (${job.match_count})` },
      { id: "proposals", label: `Proposals (${job.proposal_count})` }, { id: "description", label: "Job description" },
      { id: "files", label: `Attachments (${job.document_count})` }, { id: "edit", label: "Edit" }]} />
    {tab === "matches" && <Matches jobId={job.id} />}
    {tab === "proposals" && <Proposals jobId={job.id} onHired={(oid) => nav(`/orders/${oid}`)} />}
    {tab === "description" && <JobDescription job={job} />}
    {tab === "files" && <Documents ownerType="job" ownerId={job.id} canEdit title="Attachments" subtitle="Freelancers can see these while the job is open. Upload the full JD as PDF/Word or link to Drive / Notion." />}
    {tab === "edit" && <><JobForm initial={job} submitLabel="Save changes" onSubmit={async (body) => {
      try { await api(`/api/v1/jobs/${id}`, { method: "PUT", json: body }); toast("Saved — matches updated", "success"); reload(); setParams({ tab: "matches" }); }
      catch (e: any) { toast(e.message, "error"); } }} />
      <Card className="mt-6 flex flex-wrap items-center justify-between gap-3 border-red-200 p-5"><div><p className="font-medium">Delete this job</p><p className="text-sm text-slate-500">Removes matches, proposals and attachments. Orders are kept.</p></div>
        <Button variant="danger" onClick={() => setConfirmDelete(true)}>Delete job</Button></Card>
      <Modal open={confirmDelete} onClose={() => setConfirmDelete(false)} title="Delete job?" footer={<><Button variant="ghost" onClick={() => setConfirmDelete(false)}>Cancel</Button><Button variant="danger" onClick={del}>Delete</Button></>}>
        <p className="text-sm text-slate-600">This can't be undone.</p></Modal></>}
  </>;
}

export function Billing() {
  useTitle("Plan & billing");
  const { user, reload: reloadUser } = useAuth();
  const toast = useToast();
  const pay = usePay();
  const sub = useApi<any>("/api/v1/subscriptions/me");
  const payments = useApi<any[]>("/api/v1/payments/mine");
  const [busy, setBusy] = useState<string | null>(null);
  const [months, setMonths] = useState(1);
  const choose = async (plan: string) => {
    setBusy(plan);
    try {
      if (plan === "FREE") { await api("/api/v1/subscriptions/downgrade", { method: "POST" }); toast("Switched to Free", "success"); }
      else {
        const r = await pay({ purpose: "subscription", plan_type: plan, months });
        if (r.status === "paid") toast(`${plan} plan active`, "success");
        else if (r.status === "failed") toast("Payment failed — your plan wasn't changed.", "error");
      }
      sub.reload(); payments.reload(); reloadUser();
    } catch (e: any) { toast(e.message, "error"); } finally { setBusy(null); }
  };
  const active = sub.data?.active;
  return <>
    <PageHeader title="Plan & billing" subtitle="Upgrade to post more jobs and see every ranked match with contact details." />
    {sub.loading && !sub.data ? <Loading /> : <>
      <Card className="mb-6 flex flex-wrap items-center justify-between gap-4 p-5">
        <div><p className="text-sm text-slate-500">Current plan</p>
          <p className="mt-1 flex items-center gap-2 text-xl font-semibold">{active ? active.plan_type : "None"} <StatusBadge status={active?.status} /></p>
          <p className="text-sm text-slate-500">{active?.end_date ? `Renews / ends ${date(active.end_date)}` : active ? "No end date" : "Choose a plan to post jobs"} · {sub.data.open_jobs} open job(s)</p></div>
        <label className="flex items-center gap-2 text-sm text-slate-600">Billing period
          <select className="rounded-lg border border-slate-300 px-2 py-1.5" value={months} onChange={(e) => setMonths(Number(e.target.value))}>
            {[1, 3, 6, 12].map((m) => <option key={m} value={m}>{m} month{m > 1 ? "s" : ""}</option>)}</select></label>
      </Card>
      <PlanCards current={active?.plan_type} onChoose={choose} busy={busy} currency={user?.currency || "INR"} />
      <p className="mt-3 text-xs text-slate-500">Prices in {user?.currency || "INR"} — change your billing currency in <Link className="underline" to="/settings">Account</Link>. {user?.currency === "INR" ? "Paid with Razorpay (UPI, cards, netbanking)." : "Paid by card with Stripe."}</p>
    </>}
    <Card className="mt-6"><CardHeader title="Payment history" />
      {!payments.data?.length ? <Empty title="No payments yet" icon="₹" /> :
        <Table head={["Date", "For", "Amount", "Status", "Reference"]}>{payments.data.map((p) => <tr key={p.id}>
          <Td className="whitespace-nowrap">{date(p.created_at)}</Td>
          <Td>{p.purpose === "subscription" ? `${p.plan_type} plan · ${p.months} mo` : <Link className="text-brand-700 hover:underline" to={`/orders/${p.order_id}`}>Order #{p.order_id}</Link>}</Td>
          <Td className="font-medium">{money(p.amount, p.currency)}</Td><Td><StatusBadge status={p.status} /></Td>
          <Td className="font-mono text-xs text-slate-500">{p.provider_payment_id || p.provider_order_id}</Td></tr>)}</Table>}
    </Card>
  </>;
}
