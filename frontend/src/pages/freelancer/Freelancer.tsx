import { useCallback, useRef, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { useApi, useTitle } from "../../lib/hooks";
import { useLiveReload } from "../../lib/realtime";
import { ago, inr, skillsFrom, money, COUNTRY_CODES, CURRENCIES, TIMEZONES, countryName, flag, hour, browserTimezone } from "../../lib/format";
import { Documents } from "../../components/Documents";
import { ServiceForm } from "../../components/Forms";
import { JobCard } from "../../components/Cards";
import { useToast } from "../../components/Toast";
import { Button, ButtonLink, Card, CardHeader, Empty, ErrorBox, Input, Loading, Modal, Notice, PageHeader, Select,
  Skills, Stat, StatusBadge, Table, Td, Textarea } from "../../components/ui";

export function FreelancerDashboard() {
  useTitle("Dashboard");
  const { user } = useAuth();
  const profile = useApi<any>("/api/v1/freelancers/me");
  const recs = useApi<any[]>("/api/v1/freelancers/me/recommended-jobs");
  const props = useApi<any[]>("/api/v1/proposals/mine");
  const orders = useApi<any[]>("/api/v1/orders");
  useLiveReload(["new_match", "proposal_accepted", "order_paid", "order_completed"], useCallback(() => { recs.reload(); props.reload(); orders.reload(); }, []));
  const p = profile.data;
  const completeness = p ? [p.headline, p.bio, p.skills?.length, p.experience_years, p.hourly_rate, p.location, p.links?.length].filter(Boolean).length : 0;
  const active = (orders.data || []).filter((o) => o.status === "in_progress");
  const earnedBy: Record<string, number> = {};
  (orders.data || []).filter((o) => o.status === "completed").forEach((o) => { earnedBy[o.currency] = (earnedBy[o.currency] || 0) + o.freelancer_earnings; });
  const earned = Object.entries(earnedBy).map(([c, v]) => money(v, c)).join(" + ") || money(0, p?.currency || "INR");
  return <>
    <PageHeader title={`Hi, ${user?.name.split(" ")[0]}`} subtitle="Jobs that match your profile, your proposals and your work in progress."
      actions={<ButtonLink to="/freelancer/jobs">Find work</ButtonLink>} />
    {p && p.payout_status === "not_set" && <div className="mb-4"><Notice>Add your bank or UPI details so approved work is paid to you automatically. <Link className="font-medium underline" to="/freelancer/payouts">Set up payouts</Link></Notice></div>}
    {p && completeness < 6 && <div className="mb-6"><Notice tone="blue">Your profile is {Math.round((completeness / 7) * 100)}% complete. Clients and matching use your skills and experience — <Link className="font-medium underline" to="/freelancer/profile">upload your CV or add them</Link>.</Notice></div>}
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <Stat label="Matching open jobs" value={recs.data?.length ?? "—"} accent />
      <Stat label="Proposals sent" value={props.data?.length ?? "—"} hint={`${(props.data || []).filter((x) => x.status === "shortlisted").length} shortlisted`} />
      <Stat label="Orders in progress" value={active.length} />
      <Stat label="Earned (approved work)" value={earned} hint="after the 10% platform fee" />
    </div>
    <div className="mt-6 grid gap-6 lg:grid-cols-[1.4fr_1fr]">
      <div><h2 className="mb-3 font-semibold">Best matches for you</h2>
        {recs.loading && !recs.data ? <Loading /> : !recs.data?.length ? <Card><Empty title="No matching jobs yet">Add more skills to your profile — you'll be notified when a job matches.</Empty></Card> :
          <div className="space-y-4">{recs.data.slice(0, 4).map((r) => <JobCard key={r.job.id} job={r.job} to={`/jobs/${r.job.id}`} score={r.score} />)}</div>}</div>
      <Card className="self-start"><CardHeader title="Work in progress" action={<Link to="/orders" className="text-sm font-medium text-brand-700">All orders</Link>} />
        {!active.length ? <Empty title="Nothing in progress" icon="⇄" /> :
          <ul className="divide-y divide-slate-100">{active.map((o) => <li key={o.id}><Link to={`/orders/${o.id}`} className="flex items-center justify-between gap-3 px-5 py-3 hover:bg-slate-50">
            <div className="min-w-0"><p className="truncate text-sm font-medium">{o.title}</p><p className="text-xs text-slate-500">{o.client?.company_name} · {money(o.freelancer_earnings, o.currency)} to you</p></div>
            <StatusBadge status={o.status} /></Link></li>)}</ul>}</Card>
    </div>
  </>;
}

export function Profile() {
  useTitle("Profile & CV");
  const toast = useToast();
  const { reload: reloadUser } = useAuth();
  const [params] = useSearchParams();
  const { data, error, loading, setData } = useApi<any>("/api/v1/freelancers/me");
  const [form, setForm] = useState<any | null>(null);
  const [saving, setSaving] = useState(false);
  const [cvBusy, setCvBusy] = useState(false);
  const cvRef = useRef<HTMLInputElement>(null);
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} />;
  const f = form || { ...data, skills: (data.skills || []).join(", "), links: data.links?.length ? data.links : [],
    languages: (data.languages || []).join(", "), timezone: data.timezone || browserTimezone() };
  const set = (k: string) => (e: any) => setForm({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  const save = async (e: FormEvent) => {
    e.preventDefault(); setSaving(true);
    try {
      const out = await api("/api/v1/freelancers/me", { method: "PUT", json: {
        name: f.name, phone: f.phone || null, headline: f.headline || null, bio: f.bio || null, location: f.location || null,
        hourly_rate: f.hourly_rate === "" || f.hourly_rate == null ? null : Number(f.hourly_rate), availability: f.availability,
        skills: skillsFrom(f.skills), experience_years: Number(f.experience_years) || 0, is_public: !!f.is_public,
        country: f.country || null, timezone: f.timezone || null, currency: f.currency || "INR",
        work_start_hour: f.work_start_hour === "" || f.work_start_hour == null ? null : Number(f.work_start_hour),
        work_end_hour: f.work_end_hour === "" || f.work_end_hour == null ? null : Number(f.work_end_hour),
        languages: skillsFrom(f.languages || ""),
        links: f.links.filter((l: any) => l.label && l.url) } });
      setData(out); setForm(null); reloadUser(); toast("Profile saved — matches updated", "success");
    } catch (err: any) { toast(err.message, "error"); } finally { setSaving(false); }
  };
  const uploadCv = async (file: File) => {
    const form = new FormData(); form.append("file", file);
    setCvBusy(true);
    try {
      const r = await api("/api/v1/freelancers/me/cv", { form });
      setData(r.profile); setForm(null);
      toast(`CV read: ${r.skills_added.length} new skill(s), ${r.experience_years} yrs, ${r.new_matches} new match(es).`, "success");
    } catch (err: any) { toast(err.message, "error"); } finally { setCvBusy(false); if (cvRef.current) cvRef.current.value = ""; }
  };
  const setLink = (i: number, k: string, v: string) => { const links = [...f.links]; links[i] = { ...links[i], [k]: v }; setForm({ ...f, links }); };
  return <>
    <PageHeader title="Profile & CV" subtitle="Your profile is what clients see and what jobs are matched against."
      actions={<ButtonLink variant="secondary" to={`/freelancers/${data.id}`}>View public profile</ButtonLink>} />
    {params.get("welcome") && <div className="mb-6"><Notice tone="blue"><b>Welcome!</b> The fastest start: upload your CV (PDF) and we'll fill in your skills and experience.</Notice></div>}
    <Card className="mb-6 flex flex-wrap items-center justify-between gap-4 border-brand-200 bg-brand-50/50 p-5">
      <div><p className="font-semibold">Upload your CV</p><p className="text-sm text-slate-600">PDF, text-based (not scanned). We read your skills, years of experience and phone number, and attach the file to your profile.</p></div>
      <input ref={cvRef} type="file" accept=".pdf,application/pdf" className="hidden" onChange={(e) => e.target.files?.[0] && uploadCv(e.target.files[0])} />
      <Button onClick={() => cvRef.current?.click()} loading={cvBusy}>Upload CV (PDF)</Button>
    </Card>
    <form onSubmit={save} className="space-y-6">
      <Card className="space-y-4 p-5">
        <div className="grid gap-4 sm:grid-cols-2"><Input label="Full name" required value={f.name} onChange={set("name")} /><Input label="Headline" value={f.headline || ""} onChange={set("headline")} placeholder="e.g. Senior React developer" /></div>
        <Textarea label="About you" rows={5} value={f.bio || ""} onChange={set("bio")} placeholder="What you do best, industries you know, how you work" />
        <div className="grid gap-4 sm:grid-cols-4">
          <Input label="City" value={f.location || ""} onChange={set("location")} />
          <Input label="Phone" value={f.phone || ""} onChange={set("phone")} hint="Shown only to paying clients" />
          <Input label={`Hourly rate (${f.currency || "INR"})`} type="number" min={0} value={f.hourly_rate ?? ""} onChange={set("hourly_rate")} />
          <Select label="Availability" value={f.availability} onChange={set("availability")}><option value="available">Available</option><option value="busy">Busy</option></Select>
        </div>
      </Card>
      <Card className="space-y-4 p-5"><h3 className="font-semibold">Location, hours & languages <span className="font-normal text-slate-500">— helps clients across timezones</span></h3>
        <div className="grid gap-4 sm:grid-cols-3">
          <Select label="Country" value={f.country || ""} onChange={set("country")}><option value="">Choose…</option>
            {COUNTRY_CODES.map((c) => <option key={c} value={c}>{flag(c)} {countryName(c)}</option>)}</Select>
          <Select label="Timezone" value={f.timezone || ""} onChange={set("timezone")}><option value="">Choose…</option>
            {TIMEZONES.map((z) => <option key={z}>{z}</option>)}</Select>
          <Select label="Currency for rates & services" value={f.currency || "INR"} onChange={set("currency")}>{CURRENCIES.map((c) => <option key={c}>{c}</option>)}</Select>
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          <Select label="Usually start work" value={f.work_start_hour ?? ""} onChange={set("work_start_hour")}><option value="">—</option>{Array.from({ length: 24 }, (_, h) => <option key={h} value={h}>{hour(h)}</option>)}</Select>
          <Select label="Usually finish" value={f.work_end_hour ?? ""} onChange={set("work_end_hour")}><option value="">—</option>{Array.from({ length: 24 }, (_, h) => <option key={h} value={h}>{hour(h)}</option>)}</Select>
          <Input label="Languages you work in" value={f.languages || ""} onChange={set("languages")} placeholder="English, Hindi" />
        </div>
      </Card>
      <Card className="space-y-4 p-5"><h3 className="font-semibold">Skills & experience <span className="font-normal text-slate-500">— used for matching</span></h3>
        <div className="grid gap-4 sm:grid-cols-[3fr_1fr]"><Input label="Skills" value={f.skills} onChange={set("skills")} hint="Comma-separated, e.g. Python, FastAPI, PostgreSQL" />
          <Input label="Years of experience" type="number" min={0} max={70} step={0.5} value={f.experience_years} onChange={set("experience_years")} /></div>
        <Skills skills={skillsFrom(f.skills)} /></Card>
      <Card className="space-y-3 p-5"><div className="flex items-center justify-between"><h3 className="font-semibold">Links</h3>
        <Button type="button" size="sm" variant="secondary" disabled={f.links.length >= 10} onClick={() => setForm({ ...f, links: [...f.links, { label: "", url: "" }] })}>Add link</Button></div>
        {!f.links.length && <p className="text-sm text-slate-500">GitHub, LinkedIn, Behance, a portfolio site, a hosted PDF…</p>}
        {f.links.map((l: any, i: number) => <div key={i} className="grid gap-2 sm:grid-cols-[1fr_3fr_auto]">
          <Input aria-label="Label" placeholder="Label" value={l.label} onChange={(e) => setLink(i, "label", e.target.value)} />
          <Input aria-label="URL" type="url" placeholder="https://" value={l.url} onChange={(e) => setLink(i, "url", e.target.value)} />
          <Button type="button" variant="ghost" onClick={() => setForm({ ...f, links: f.links.filter((_: any, j: number) => j !== i) })}>Remove</Button></div>)}
      </Card>
      <Card className="flex flex-wrap items-center justify-between gap-4 p-5">
        <label className="flex items-center gap-3 text-sm"><input type="checkbox" className="h-4 w-4" checked={!!f.is_public} onChange={set("is_public")} />
          <span><b>Public profile</b> — listed in Find talent and matched to jobs</span></label>
        <Button type="submit" loading={saving}>Save profile</Button></Card>
    </form>
    <div className="mt-6"><Documents ownerType="consultant" ownerId={data.id} canEdit title="CV, portfolio & certificates" subtitle="Visible to signed-in clients while your profile is public." /></div>
  </>;
}

export function MyServices() {
  useTitle("My services");
  const toast = useToast();
  const { data, error, loading, reload } = useApi<any[]>("/api/v1/services/mine");
  const [editing, setEditing] = useState<any | null>(null);
  const save = async (body: any) => {
    try {
      if (editing?.id) await api(`/api/v1/services/${editing.id}`, { method: "PUT", json: body });
      else await api("/api/v1/services", { json: body });
      toast("Service saved", "success"); setEditing(null); reload();
    } catch (e: any) { toast(e.message, "error"); }
  };
  const del = async (s: any) => {
    if (!confirm(`Delete “${s.title}”?`)) return;
    try { await api(`/api/v1/services/${s.id}`, { method: "DELETE" }); reload(); } catch (e: any) { toast(e.message, "error"); }
  };
  return <>
    <PageHeader title="My services" subtitle="Fixed-price packages clients can buy straight away." actions={<Button onClick={() => setEditing({})}>New service</Button>} />
    <Card>{error ? <div className="p-4"><ErrorBox message={error} /></div> : loading && !data ? <Loading /> : !data!.length ? <Empty title="No services yet" icon="◈" action={<Button size="sm" onClick={() => setEditing({})}>Create your first service</Button>}>Package what you do into a clear scope and price.</Empty> :
      <Table head={["Service", "Price", "Delivery", "Status", ""]}>{data!.map((s) => <tr key={s.id}>
        <Td><Link to={`/services/${s.id}`} className="font-medium hover:text-brand-700">{s.title}</Link><p className="text-xs text-slate-500">{s.category}</p></Td>
        <Td className="font-medium">{money(s.price, s.currency)}</Td><Td>{s.delivery_days} days</Td><Td><StatusBadge status={s.status} /></Td>
        <Td><div className="flex justify-end gap-1"><Button size="sm" variant="ghost" onClick={() => setEditing(s)}>Edit</Button><Button size="sm" variant="ghost" onClick={() => del(s)}>Delete</Button></div></Td></tr>)}</Table>}</Card>
    <Modal wide open={!!editing} onClose={() => setEditing(null)} title={editing?.id ? "Edit service" : "New service"}>
      {editing && <ServiceForm initial={editing} onSubmit={save} onCancel={() => setEditing(null)} />}
    </Modal>
    {editing?.id && null}
  </>;
}

export function FindWork() {
  useTitle("Find work");
  const { data, error, loading, reload } = useApi<any[]>("/api/v1/freelancers/me/recommended-jobs");
  useLiveReload(["new_match"], reload);
  return <>
    <PageHeader title="Find work" subtitle="Open jobs ranked against your profile (50%+ fit). Update your skills to improve matches."
      actions={<ButtonLink variant="secondary" to="/jobs">Browse all jobs</ButtonLink>} />
    {error ? <ErrorBox message={error} /> : loading && !data ? <Loading /> : !data!.length ? <Card><Empty title="No matching jobs right now" action={<ButtonLink size="sm" to="/freelancer/profile">Improve my profile</ButtonLink>}>We'll notify you when a job matches.</Empty></Card> :
      <div className="grid gap-4 md:grid-cols-2">{data!.map((r) => <JobCard key={r.job.id} job={r.job} to={`/jobs/${r.job.id}`} score={r.score}
        extra={r.match_details?.missing_skills?.length ? <span className="text-xs text-slate-500">Missing: {r.match_details.missing_skills.join(", ")}</span> : <span className="text-xs text-emerald-700">All skills matched</span>} />)}</div>}
  </>;
}

export function MyProposals() {
  useTitle("Proposals");
  const toast = useToast();
  const { data, error, loading, reload } = useApi<any[]>("/api/v1/proposals/mine");
  useLiveReload(["proposal_accepted"], reload);
  const withdraw = async (id: number) => {
    try { await api(`/api/v1/proposals/${id}/withdraw`, { method: "POST" }); reload(); } catch (e: any) { toast(e.message, "error"); }
  };
  return <>
    <PageHeader title="My proposals" />
    <Card>{error ? <div className="p-4"><ErrorBox message={error} /></div> : loading && !data ? <Loading /> : !data!.length ? <Empty title="No proposals yet" icon="✉" action={<ButtonLink size="sm" to="/freelancer/jobs">Find work</ButtonLink>} /> :
      <Table head={["Job", "Bid", "Status", "Sent", ""]}>{data!.map((p) => <tr key={p.id}>
        <Td><Link to={`/jobs/${p.job_id}`} className="font-medium hover:text-brand-700">{p.job?.title}</Link><p className="text-xs text-slate-500">{p.job?.client?.company_name}</p></Td>
        <Td className="font-medium">{money(p.bid_amount, p.currency)}</Td><Td><StatusBadge status={p.status} /></Td><Td className="text-slate-500">{ago(p.created_at)}</Td>
        <Td>{p.order_id ? <ButtonLink size="sm" variant="secondary" to={`/orders/${p.order_id}`}>View order</ButtonLink>
          : ["submitted", "shortlisted"].includes(p.status) && <Button size="sm" variant="ghost" onClick={() => withdraw(p.id)}>Withdraw</Button>}</Td></tr>)}</Table>}</Card>
  </>;
}
