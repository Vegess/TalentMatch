import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../lib/api";
import { useApi, useDebounced, useTitle } from "../../lib/hooks";
import { countryName, date, flag, label, money } from "../../lib/format";
import { CountUp } from "../../components/Motion";
import { AreaChart, BarList, moneyAxis } from "../../components/Charts";
import { useToast } from "../../components/Toast";
import { Badge, Button, Card, CardHeader, Empty, ErrorBox, Input, Loading, Notice, PageHeader, Select, Skills, Stat,
  StatusBadge, Table, Tabs, Td } from "../../components/ui";

export function Overview() {
  useTitle("Control room");
  const [days, setDays] = useState(30);
  const { data: d, error, loading, reload } = useApi<any>(`/api/v1/admin/overview?days=${days}`);
  const [metric, setMetric] = useState("revenue");
  const [cur, setCur] = useState("INR");
  const toast = useToast();
  if (loading && !d) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const mk = d.marketplace;
  const m = { ...d.money, ...(d.money_by_currency[cur] || d.money_by_currency.INR) };
  const fmt = (v: number) => money(v, cur);
  return <>
    <PageHeader title="Control room" subtitle={`Platform health at a glance · payments: ${d.payment_provider === "demo" ? "demo mode" : "Razorpay"} · match threshold ${d.match_threshold}%`}
      actions={<><select aria-label="Period" value={days} onChange={(e) => setDays(Number(e.target.value))} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"><option value={7}>7 days</option><option value={30}>30 days</option><option value={90}>90 days</option></select>
        <div className="flex rounded-lg border border-slate-300 bg-white p-0.5" role="radiogroup" aria-label="Currency">{d.currencies_in_use.map((c: string) =>
          <button key={c} role="radio" aria-checked={cur === c} onClick={() => setCur(c)} className={`rounded-md px-2.5 py-1.5 text-xs font-semibold ${cur === c ? "bg-brand-600 text-white" : "text-slate-600"}`}>{c}</button>)}</div>
        <Button variant="secondary" onClick={async () => { const r = await api("/api/v1/admin/rematch-all", { method: "POST" }); toast(`Re-matched ${r.jobs_rematched} jobs`, "success"); reload(); }}>Re-run matching</Button></>} />
    {d.payment_provider === "demo" && <div className="mb-6"><Notice tone="blue">Payments are in <b>demo mode</b>: checkouts are simulated. Set <code>RAZORPAY_KEY_ID</code> and <code>RAZORPAY_KEY_SECRET</code> on the server for real Razorpay.</Notice></div>}
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <Stat accent label={`Total collected (${cur})`} value={<CountUp value={m.total_collected} format={fmt} />} hint={`${fmt(m.subscription_revenue)} plans · ${fmt(m.order_gmv)} orders`} />
      <Stat label="Monthly recurring revenue" value={<CountUp value={m.mrr} format={fmt} />} hint={`from plans billed in ${cur}`} />
      <Stat label="Platform fees earned" value={<CountUp value={m.platform_fees} format={fmt} />} />
      <Stat label="Paid out to freelancers" value={<CountUp value={m.payouts_released} format={fmt} />} hint={<>{fmt(m.payouts_held)} on hold · {m.payouts_pending ? <Link className="text-amber-700 hover:underline" to="/control-room/orders?payout=pending">{fmt(m.payouts_pending)} need attention →</Link> : "nothing stuck"}</>} />
    </div>
    <div className="mt-6 grid gap-6 lg:grid-cols-[2fr_1fr]">
      <Card><CardHeader title={metric === "revenue" ? `Money collected (${cur})` : "New sign-ups"} subtitle={`Last ${days} days`}
        action={<div className="flex gap-1 rounded-lg bg-slate-100 p-1">{["revenue", "signups"].map((k) => <button key={k} onClick={() => setMetric(k)}
          className={`rounded-md px-2.5 py-1 text-xs font-medium ${metric === k ? "bg-white shadow-sm" : "text-slate-500"}`}>{k === "revenue" ? "Revenue" : "Sign-ups"}</button>)}</div>} />
        <div className="p-4"><AreaChart key={metric + days + cur} data={d.series} valueKey={metric === "revenue" ? `revenue_${cur}` : metric} format={metric === "revenue" ? (v) => (cur === "INR" ? moneyAxis(v) : money(v, cur)) : (v) => String(v)} /></div></Card>
      <Card><CardHeader title="Active plans" /><div className="p-5"><BarList items={Object.entries(d.plans).map(([k, v]: any) => ({ label: k, value: v,
        tone: k === "ENTERPRISE" ? "#7c3aed" : k === "PREMIUM" ? "#2563eb" : "#94a3b8" }))} /></div></Card>
    </div>
    <div className="mt-6 grid gap-4 sm:grid-cols-3 lg:grid-cols-6">
      {[["Users", d.users.total], ["Clients", d.users.clients], ["Freelancers", d.users.freelancers], ["Open jobs", mk.open_jobs], ["Services", mk.active_services], ["Proposals", mk.proposals]]
        .map(([k, v]) => <Card key={k} className="p-4"><p className="text-xs text-slate-500">{k}</p><p className="text-xl font-semibold">{v}</p></Card>)}
    </div>
    <div className="mt-6 grid gap-6 lg:grid-cols-3">
      <Card><CardHeader title="Where people are" subtitle="Clients and freelancers by country" /><div className="p-5">
        <BarList items={Object.entries(d.countries).map(([k, v]: any) => ({ label: k === "—" ? "Not set" : `${flag(k)} ${countryName(k)}`, value: v }))} /></div></Card>
      <Card><CardHeader title="Orders by status" /><div className="p-5">{Object.keys(d.orders_by_status).length ? <BarList items={Object.entries(d.orders_by_status).map(([k, v]: any) => ({ label: label(k), value: v }))} /> : <p className="text-sm text-slate-500">No orders yet.</p>}</div></Card>
      <Card><CardHeader title="Health" /><ul className="divide-y divide-slate-100 text-sm">
        <li className="flex justify-between px-5 py-3"><span>Payments by currency</span><span className="flex flex-wrap justify-end gap-1">{Object.entries(d.payment_providers).map(([c, p]: any) =>
          <Badge key={c} tone={p ? (p === "demo" ? "blue" : "green") : "red"}>{c}: {p || "off"}</Badge>)}</span></li>
        <li className="flex justify-between px-5 py-3"><span>Email</span><Badge tone={d.email === "smtp" ? "green" : "amber"}>{d.email === "smtp" ? "SMTP" : "server log only"}</Badge></li>
        <li className="flex justify-between px-5 py-3"><span>Automatic payouts</span><Badge tone={d.payout_mode === "off" ? "amber" : "green"}>{d.payout_mode === "razorpay" ? "Razorpay Route" : d.payout_mode === "demo" ? "demo" : "off (manual)"}</Badge></li>
        <li className="flex justify-between px-5 py-3"><span>Freelancers with payout details</span><Badge tone="blue">{d.freelancers_with_payouts}</Badge></li>
        <li className="flex justify-between px-5 py-3"><span>Failed payouts</span><Badge tone={m.payouts_failed ? "red" : "green"}>{m.payouts_failed}</Badge></li>
        <li className="flex justify-between px-5 py-3"><span>Failed payments</span><Badge tone={m.failed_payments ? "amber" : "green"}>{m.failed_payments}</Badge></li>
        <li className="flex justify-between px-5 py-3"><span>Disabled accounts</span><Badge>{d.users.disabled}</Badge></li>
        <li className="flex justify-between px-5 py-3"><span>Ranked matches stored</span><Badge tone="blue">{mk.matches}</Badge></li>
        <li className="flex justify-between px-5 py-3"><span>Documents stored</span><Badge>{mk.documents}</Badge></li>
        <li className="flex justify-between px-5 py-3"><span>Sign-ups</span><Badge tone={d.signup_mode === "open" ? "green" : "amber"}>{d.signup_mode}</Badge></li>
      </ul></Card>
    </div>
  </>;
}

export function Users() {
  useTitle("Users");
  const toast = useToast();
  const [q, setQ] = useState(""); const [role, setRole] = useState("");
  const dq = useDebounced(q);
  const { data, error, loading, reload } = useApi<any[]>(`/api/v1/admin/users?${new URLSearchParams({ ...(dq && { q: dq }), ...(role && { role }) })}`);
  const toggle = async (u: any) => {
    try { await api(`/api/v1/admin/users/${u.id}`, { method: "PATCH", json: { is_active: !u.is_active } }); toast(u.is_active ? "Account disabled and signed out" : "Account enabled", "success"); reload(); }
    catch (e: any) { toast(e.message, "error"); }
  };
  const verify = async (u: any) => {
    try { await api(`/api/v1/admin/users/${u.id}`, { method: "PATCH", json: { verified: !u.verified } }); toast(u.verified ? "Verified badge removed" : `${u.name} is now verified`, "success"); reload(); }
    catch (e: any) { toast(e.message, "error"); }
  };
  return <>
    <PageHeader title="Users" />
    <div className="mb-4 grid gap-3 sm:grid-cols-[2fr_1fr]"><Input aria-label="Search" placeholder="Search name or email" value={q} onChange={(e) => setQ(e.target.value)} />
      <Select aria-label="Role" value={role} onChange={(e) => setRole(e.target.value)}><option value="">All roles</option><option value="client">Clients</option><option value="freelancer">Freelancers</option><option value="admin">Admins</option></Select></div>
    <Card>{error ? <div className="p-4"><ErrorBox message={error} /></div> : loading && !data ? <Loading /> : !data!.length ? <Empty title="No users found" /> :
      <Table head={["User", "Role", "Country", "Joined", "Last sign-in", "Status", ""]}>{data!.map((u) => <tr key={u.id}>
        <Td><p className="font-medium">{u.name} {u.verified && <span title="Verified" className="text-brand-600">✓</span>}</p><p className="text-xs text-slate-500">{u.email}</p></Td><Td><StatusBadge status={u.role} /></Td>
        <Td className="whitespace-nowrap">{u.country ? `${flag(u.country)} ${u.country}` : "—"}</Td>
        <Td className="whitespace-nowrap">{date(u.created_at)}</Td><Td className="whitespace-nowrap">{date(u.last_login_at)}</Td>
        <Td>{u.is_active ? <Badge tone="green">Active</Badge> : <Badge tone="red">Disabled</Badge>}</Td>
        <Td>{u.role !== "admin" && <div className="flex gap-1">
          <Button size="sm" variant="secondary" onClick={() => verify(u)}>{u.verified ? "Unverify" : "Verify"}</Button>
          <Button size="sm" variant={u.is_active ? "danger" : "secondary"} onClick={() => toggle(u)}>{u.is_active ? "Disable" : "Enable"}</Button></div>}</Td></tr>)}</Table>}</Card>
  </>;
}

export function Payments() {
  useTitle("Payments");
  const [status, setStatus] = useState("");
  const { data, error, loading } = useApi<any[]>(`/api/v1/admin/payments${status ? `?status=${status}` : ""}`);
  const totals: Record<string, number> = {};
  (data || []).filter((p) => p.status === "paid").forEach((p) => { totals[p.currency] = (totals[p.currency] || 0) + p.amount; });
  const total = Object.entries(totals).map(([c, v]) => money(v, c)).join(" + ") || "nothing";
  return <>
    <PageHeader title="Payments" subtitle="Every checkout attempt, with the Razorpay order / payment reference." />
    <Tabs value={status} onChange={setStatus} tabs={[{ id: "", label: "All" }, { id: "paid", label: "Paid" }, { id: "created", label: "Started" }, { id: "failed", label: "Failed" }]} />
    <Card>{error ? <div className="p-4"><ErrorBox message={error} /></div> : loading && !data ? <Loading /> : !data!.length ? <Empty title="No payments" icon="₹" /> : <>
      <p className="px-5 pt-4 text-sm text-slate-500">{data!.length} payment(s) · {total} paid</p>
      <Table head={["Date", "Client", "For", "Amount", "Provider", "Status", "Reference"]}>{data!.map((p) => <tr key={p.id}>
        <Td className="whitespace-nowrap">{date(p.created_at)}</Td><Td>{p.client?.company_name}<p className="text-xs text-slate-500">{p.user?.email}</p></Td>
        <Td>{p.purpose === "subscription" ? `${p.plan_type} · ${p.months} mo` : `Order #${p.order_id}`}</Td><Td className="font-medium">{money(p.amount, p.currency)}</Td>
        <Td><Badge>{p.provider}</Badge></Td><Td><StatusBadge status={p.status} />{p.error && <p className="mt-1 text-xs text-red-600">{p.error}</p>}</Td>
        <Td className="font-mono text-xs text-slate-500">{p.provider_payment_id || p.provider_order_id}</Td></tr>)}</Table></>}</Card>
  </>;
}

export function AdminOrders() {
  useTitle("Orders & payouts");
  const toast = useToast();
  const [tab, setTab] = useState(new URLSearchParams(location.search).get("payout") === "pending" ? "payout" : "all");
  const { data: raw, error, loading, reload } = useApi<any[]>(`/api/v1/admin/orders${tab === "held" ? "?payout_status=held" : !["all", "payout"].includes(tab) ? `?status=${tab}` : ""}`);
  const data = tab === "payout" ? (raw || []).filter((o) => ["pending", "failed"].includes(o.payout_status)) : raw;
  const release = async (o: any) => {
    if (!confirm(`Record that ${money(o.freelancer_earnings, o.currency)} was paid to ${o.freelancer?.name} outside the app?`)) return;
    try { await api(`/api/v1/admin/orders/${o.id}/release-payout`, { method: "POST" }); toast(`Manual payout of ${money(o.freelancer_earnings, o.currency)} to ${o.freelancer?.name} recorded`, "success"); reload(); }
    catch (e: any) { toast(e.message, "error"); }
  };
  const retry = async (o: any) => {
    try { await api(`/api/v1/admin/orders/${o.id}/retry-payout`, { method: "POST" }); toast(`Payout of ${money(o.freelancer_earnings, o.currency)} released via Razorpay Route`, "success"); reload(); }
    catch (e: any) { toast(e.message, "error"); reload(); }
  };
  return <>
    <PageHeader title="Orders & payouts" subtitle="Payouts go out automatically through Razorpay Route when a client approves. Anything stuck shows here: retry it, or pay manually and record it." />
    <Tabs value={tab} onChange={setTab} tabs={[{ id: "all", label: "All" }, { id: "payout", label: "Needs attention" }, { id: "held", label: "On hold" }, { id: "in_progress", label: "In progress" }, { id: "delivered", label: "Delivered" }, { id: "pending_payment", label: "Unpaid" }]} />
    <Card>{error ? <div className="p-4"><ErrorBox message={error} /></div> : loading && !data ? <Loading /> : !data!.length ? <Empty title="Nothing here" icon="⇄" /> :
      <Table head={["Order", "Client → Freelancer", "Amount", "Fee", "Status", "Payout", ""]}>{data!.map((o) => <tr key={o.id}>
        <Td><Link to={`/orders/${o.id}`} className="font-medium hover:text-brand-700">#{o.id} · {o.title}</Link><p className="text-xs text-slate-500">{date(o.created_at)}</p></Td>
        <Td>{o.client?.company_name} → {o.freelancer?.name}</Td><Td className="font-medium">{money(o.amount, o.currency)}</Td><Td>{money(o.platform_fee, o.currency)}</Td>
        <Td><StatusBadge status={o.status} /></Td>
        <Td><StatusBadge status={o.payout_status} />{o.transfer_id && <p className="mt-1 font-mono text-[11px] text-slate-500">{o.transfer_id}</p>}
          {o.payout_error && ["pending", "failed"].includes(o.payout_status) && <p className={`mt-1 max-w-[220px] text-xs ${o.payout_status === "failed" ? "text-red-600" : "text-amber-700"}`}>{o.payout_error}</p>}</Td>
        <Td>{["pending", "failed"].includes(o.payout_status) && <div className="flex flex-col gap-1">
          <Button size="sm" onClick={() => retry(o)}>Retry via Route</Button>
          <Button size="sm" variant="ghost" onClick={() => release(o)}>Paid manually</Button></div>}</Td></tr>)}</Table>}</Card>
  </>;
}

export function AdminJobs() {
  useTitle("Jobs");
  const toast = useToast();
  const { data, error, loading, reload } = useApi<any[]>("/api/v1/admin/jobs");
  const toggle = async (j: any) => {
    try { await api(`/api/v1/jobs/${j.id}`, { method: "PUT", json: { status: j.status === "open" ? "closed" : "open" } }); reload(); } catch (e: any) { toast(e.message, "error"); }
  };
  return <>
    <PageHeader title="Jobs" subtitle="All job descriptions on the platform." />
    <Card>{error ? <div className="p-4"><ErrorBox message={error} /></div> : loading && !data ? <Loading /> : !data!.length ? <Empty title="No jobs" /> :
      <Table head={["Job", "Client", "Skills", "Matches", "Proposals", "Status", ""]}>{data!.map((j) => <tr key={j.id}>
        <Td><Link to={`/jobs/${j.id}`} className="font-medium hover:text-brand-700">{j.title}</Link><p className="text-xs text-slate-500">{date(j.created_at)}</p></Td>
        <Td>{j.client?.company_name}</Td><Td><Skills skills={j.required_skills} max={3} /></Td><Td>{j.match_count}</Td><Td>{j.proposal_count}</Td>
        <Td><StatusBadge status={j.status} /></Td><Td><Button size="sm" variant="ghost" onClick={() => toggle(j)}>{j.status === "open" ? "Close" : "Reopen"}</Button></Td></tr>)}</Table>}</Card>
  </>;
}

export function AdminServices() {
  useTitle("Services");
  const toast = useToast();
  const { data, error, loading, reload } = useApi<any[]>("/api/v1/admin/services");
  const setStatus = async (s: any, status: string) => {
    try { await api(`/api/v1/services/${s.id}`, { method: "PUT", json: { status } }); reload(); } catch (e: any) { toast(e.message, "error"); }
  };
  return <>
    <PageHeader title="Services" subtitle="Pause anything that breaks the rules." />
    <Card>{error ? <div className="p-4"><ErrorBox message={error} /></div> : loading && !data ? <Loading /> : !data!.length ? <Empty title="No services" /> :
      <Table head={["Service", "Freelancer", "Price", "Status", ""]}>{data!.map((s) => <tr key={s.id}>
        <Td><Link to={`/services/${s.id}`} className="font-medium hover:text-brand-700">{s.title}</Link><p className="text-xs text-slate-500">{s.category}</p></Td>
        <Td>{s.freelancer?.name}</Td><Td>{money(s.price, s.currency)}</Td><Td><StatusBadge status={s.status} /></Td>
        <Td><Button size="sm" variant="ghost" onClick={() => setStatus(s, s.status === "active" ? "paused" : "active")}>{s.status === "active" ? "Pause" : "Activate"}</Button></Td></tr>)}</Table>}</Card>
  </>;
}

export function Audit() {
  useTitle("Audit log");
  const [action, setAction] = useState("");
  const { data, error, loading } = useApi<any[]>(`/api/v1/admin/audit${action ? `?action=${action}` : ""}`);
  return <>
    <PageHeader title="Audit log" subtitle="Sign-ins, payments, payouts, deletions and admin actions — newest first." />
    <Tabs value={action} onChange={setAction} tabs={[{ id: "", label: "Everything" }, { id: "payment", label: "Payments" }, { id: "payout", label: "Payouts" }, { id: "user", label: "Accounts" }, { id: "job", label: "Jobs" }, { id: "order", label: "Orders" }, { id: "document", label: "Documents" }]} />
    <Card>{error ? <div className="p-4"><ErrorBox message={error} /></div> : loading && !data ? <Loading /> : !data!.length ? <Empty title="No events" icon="≡" /> :
      <Table head={["When", "Action", "Who", "Target", "Details", "IP"]}>{data!.map((a) => <tr key={a.id}>
        <Td className="whitespace-nowrap text-slate-500">{new Date(a.created_at + "Z").toLocaleString("en-IN")}</Td>
        <Td><code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs">{a.action}</code></Td><Td>{a.actor || (a.actor_user_id ? `#${a.actor_user_id}` : "system")}</Td>
        <Td>{a.target_type ? `${a.target_type} #${a.target_id}` : "—"}</Td>
        <Td className="max-w-xs truncate font-mono text-xs text-slate-500">{a.details ? JSON.stringify(a.details) : ""}</Td><Td className="text-xs text-slate-500">{a.ip}</Td></tr>)}</Table>}</Card>
  </>;
}
