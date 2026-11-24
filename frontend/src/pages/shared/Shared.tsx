import { useCallback, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { useApi, useTitle } from "../../lib/hooks";
import { useLiveReload } from "../../lib/realtime";
import { date, inr, money } from "../../lib/format";
import { usePay } from "../../components/Checkout";
import { Documents } from "../../components/Documents";
import { useToast } from "../../components/Toast";
import { PAYOUT_EXPLAIN } from "../freelancer/Payouts";
import { MessageButton } from "./Messages";
import { Stars } from "../../components/Trust";
import { COUNTRY_CODES, CURRENCIES, TIMEZONES, countryName, flag } from "../../lib/format";
import { Button, Card, CardHeader, Empty, ErrorBox, Input, Loading, Modal, Notice, PageHeader, Select, StatusBadge, Table, Tabs,
  Td, Textarea } from "../../components/ui";
import { LanguagePicker } from "../../lib/i18n";

const STEPS = ["pending_payment", "in_progress", "delivered", "completed"];
const STEP_LABEL: Record<string, string> = { pending_payment: "Payment", in_progress: "In progress", delivered: "Delivered", completed: "Approved" };

export function Orders() {
  useTitle("Orders");
  const { user } = useAuth();
  const [tab, setTab] = useState("all");
  const { data, error, loading, reload } = useApi<any[]>("/api/v1/orders");
  useLiveReload(["order_paid", "order_delivered", "order_completed", "proposal_accepted"], reload);
  const list = (data || []).filter((o) => tab === "all" || (tab === "active" ? ["pending_payment", "in_progress", "delivered"].includes(o.status) : o.status === tab));
  return <>
    <PageHeader title="Orders" subtitle={user?.role === "client" ? "Services you bought and freelancers you hired." : "Work clients have bought from you."} />
    <Tabs value={tab} onChange={setTab} tabs={[{ id: "all", label: "All" }, { id: "active", label: "Active" }, { id: "completed", label: "Completed" }, { id: "cancelled", label: "Cancelled" }]} />
    <Card>{error ? <div className="p-4"><ErrorBox message={error} onRetry={reload} /></div> : loading && !data ? <Loading /> : !list.length ? <Empty title="No orders here" icon="⇄" /> :
      <Table head={["Order", user?.role === "client" ? "Freelancer" : "Client", "Amount", "Status", "Created"]}>{list.map((o) => <tr key={o.id} className="hover:bg-slate-50">
        <Td><Link to={`/orders/${o.id}`} className="font-medium hover:text-brand-700">#{o.id} · {o.title}</Link></Td>
        <Td>{user?.role === "client" ? o.freelancer?.name : o.client?.company_name}</Td>
        <Td className="font-medium">{money(user?.role === "freelancer" ? o.freelancer_earnings : o.amount, o.currency)}</Td>
        <Td><StatusBadge status={o.status} /></Td><Td className="whitespace-nowrap text-slate-500">{date(o.created_at)}</Td></tr>)}</Table>}</Card>
  </>;
}

export function OrderDetail() {
  const { id } = useParams();
  const toast = useToast();
  const pay = usePay();
  const { data: o, error, loading, reload } = useApi<any>(`/api/v1/orders/${id}`);
  const [deliverOpen, setDeliverOpen] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  useLiveReload(["order_paid", "order_delivered", "order_completed"], useCallback(() => reload(), [reload]));
  useTitle(o ? `Order #${o.id}` : "Order");
  if (loading && !o) return <Loading />;
  if (error) return <ErrorBox message={error} />;
  const run = async (key: string, fn: () => Promise<any>, ok: string) => {
    setBusy(key);
    try { await fn(); toast(ok, "success"); reload(); } catch (e: any) { toast(e.message, "error"); } finally { setBusy(null); }
  };
  const payNow = async () => {
    setBusy("pay");
    try {
      const r = await pay({ purpose: "order", order_id: o.id });
      if (r.status === "paid") toast("Payment received — work can start.", "success");
      else if (r.status === "failed") toast("Payment failed. Nothing was charged; try again.", "error");
      reload();
    } catch (e: any) { toast(e.message, "error"); } finally { setBusy(null); }
  };
  const role = o.viewer_role;
  const stepIdx = STEPS.indexOf(o.status);
  return <>
    <PageHeader crumbs={[{ to: "/orders", label: "Orders" }]} title={`Order #${o.id}`} subtitle={o.title}
      actions={<StatusBadge status={o.status} />} />
    {o.status !== "cancelled" && <Card className="mb-6 p-5"><ol className="grid grid-cols-4 gap-2">{STEPS.map((s, i) =>
      <li key={s} className="text-center"><div className={`mx-auto h-1.5 rounded-full ${i <= stepIdx ? "bg-brand-600" : "bg-slate-200"}`} />
        <p className={`mt-2 text-xs font-medium ${i <= stepIdx ? "text-brand-700" : "text-slate-400"}`}>{STEP_LABEL[s]}</p></li>)}</ol></Card>}
    <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
      <div className="space-y-6">
        {role === "client" && o.status === "pending_payment" && <Notice>This order is waiting for payment. The freelancer starts once you pay.</Notice>}
        {role === "freelancer" && o.status === "pending_payment" && <Notice tone="blue">Waiting for the client's payment. You'll be notified when you can start.</Notice>}
        {role === "client" && o.status === "delivered" && <Notice tone="green">The work has been delivered. Review it and approve, or send it back for changes.</Notice>}
        {o.requirements && <Card className="p-5"><h3 className="mb-1 font-semibold">Client brief</h3><p className="whitespace-pre-line text-sm text-slate-700">{o.requirements}</p></Card>}
        {o.delivery_note && <Card className="p-5"><h3 className="mb-1 font-semibold">Delivery note</h3><p className="whitespace-pre-line text-sm text-slate-700">{o.delivery_note}</p>
          <p className="mt-2 text-xs text-slate-500">Delivered {date(o.delivered_at)}</p></Card>}
        {o.status === "completed" && role !== "admin" && <ReviewBox orderId={o.id} role={role} />}
        <Documents ownerType="order" ownerId={o.id} canEdit={o.status !== "cancelled"} title="Files & links" subtitle="Shared only between the client, the freelancer and platform admins." />
        {o.payments?.length > 0 && <Card><CardHeader title="Payments" /><Table head={["Date", "Amount", "Status", "Reference"]}>{o.payments.map((p: any) => <tr key={p.id}>
          <Td>{date(p.created_at)}</Td><Td>{money(p.amount, p.currency)}</Td><Td><StatusBadge status={p.status} /></Td><Td className="font-mono text-xs">{p.provider_payment_id || p.provider_order_id}</Td></tr>)}</Table></Card>}
      </div>
      <aside className="space-y-4">
        <Card className="p-5">
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between"><dt className="text-slate-500">Order value</dt><dd className="font-semibold">{money(o.amount, o.currency)}</dd></div>
            {role !== "client" && <><div className="flex justify-between"><dt className="text-slate-500">Platform fee</dt><dd>−{money(o.platform_fee, o.currency)}</dd></div>
              <div className="flex justify-between border-t border-slate-100 pt-2"><dt className="text-slate-500">Freelancer receives</dt><dd className="font-semibold">{money(o.freelancer_earnings, o.currency)}</dd></div>
              <div className="flex justify-between"><dt className="text-slate-500">Payout</dt><dd><StatusBadge status={o.payout_status} /></dd></div>
              {o.payout_status !== "none" && <p className="rounded-md bg-slate-50 p-2 text-xs text-slate-600">{PAYOUT_EXPLAIN[o.payout_status]}
                {o.transfer_id && <span className="mt-1 block font-mono text-[11px] text-slate-500">{o.transfer_id}{o.transfer_status ? ` · ${o.transfer_status}` : ""}</span>}
                {role === "admin" && o.payout_error && <span className="mt-1 block text-red-600">{o.payout_error}</span>}</p>}</>}
            <div className="flex justify-between border-t border-slate-100 pt-2"><dt className="text-slate-500">Client</dt><dd>{o.client?.company_name}</dd></div>
            <div className="flex justify-between"><dt className="text-slate-500">Freelancer</dt><dd><Link className="text-brand-700 hover:underline" to={`/freelancers/${o.freelancer?.id}`}>{o.freelancer?.name}</Link></dd></div>
            <div className="flex justify-between"><dt className="text-slate-500">Created</dt><dd>{date(o.created_at)}</dd></div>
            {o.paid_at && <div className="flex justify-between"><dt className="text-slate-500">Paid</dt><dd>{date(o.paid_at)}</dd></div>}
            {o.job_id && <div className="flex justify-between"><dt className="text-slate-500">Job</dt><dd><Link className="text-brand-700 hover:underline" to={`/jobs/${o.job_id}`}>View</Link></dd></div>}
            {o.service_id && <div className="flex justify-between"><dt className="text-slate-500">Service</dt><dd><Link className="text-brand-700 hover:underline" to={`/services/${o.service_id}`}>View</Link></dd></div>}
          </dl>
          <div className="mt-5 space-y-2">
            {role === "client" && <div className="[&>button]:w-full"><MessageButton consultantId={o.consultant_id} label={`Message ${o.freelancer?.name?.split(" ")[0] || "freelancer"}`} size="md" /></div>}
            {role === "freelancer" && <div className="[&>button]:w-full"><MessageButton clientId={o.client_id} label="Message client" size="md" /></div>}
            {(role === "client" || role === "admin") && o.status === "pending_payment" && <>
              {role === "client" && <Button className="w-full" onClick={payNow} loading={busy === "pay"}>Pay {money(o.amount, o.currency)}</Button>}
              <Button className="w-full" variant="ghost" loading={busy === "cancel"} onClick={() => run("cancel", () => api(`/api/v1/orders/${o.id}/cancel`, { method: "POST" }), "Order cancelled")}>Cancel order</Button></>}
            {(role === "freelancer" || role === "admin") && o.status === "in_progress" && <Button className="w-full" onClick={() => setDeliverOpen(true)}>Mark as delivered</Button>}
            {(role === "client" || role === "admin") && o.status === "delivered" && <>
              <Button className="w-full" loading={busy === "complete"} onClick={() => run("complete", () => api(`/api/v1/orders/${o.id}/complete`, { method: "POST" }), "Approved — the freelancer will be paid out")}>Approve & release payment</Button>
              <Button className="w-full" variant="secondary" loading={busy === "changes"} onClick={() => run("changes", () => api(`/api/v1/orders/${o.id}/request-changes`, { method: "POST" }), "Sent back for changes")}>Request changes</Button></>}
          </div>
        </Card>
      </aside>
    </div>
    <Modal open={deliverOpen} onClose={() => setDeliverOpen(false)} title="Deliver the work"
      footer={<><Button variant="ghost" onClick={() => setDeliverOpen(false)}>Cancel</Button>
        <Button disabled={note.trim().length < 5} loading={busy === "deliver"} onClick={() => run("deliver", async () => { await api(`/api/v1/orders/${o.id}/deliver`, { json: { delivery_note: note } }); setDeliverOpen(false); }, "Delivered — the client has been notified")}>Deliver</Button></>}>
      <Textarea label="Delivery note" rows={5} value={note} onChange={(e) => setNote(e.target.value)} placeholder="What you delivered, links, how to use it" />
      <p className="text-xs text-slate-500">Attach files or links in the “Files & links” panel before or after delivering.</p>
    </Modal>
  </>;
}

export function Settings() {
  useTitle("Account");
  const { user, logoutAll, setSession, reload } = useAuth();
  const toast = useToast();
  const nav = useNavigate();
  const [cur, setCur] = useState(""); const [next, setNext] = useState("");
  const [busy, setBusy] = useState(false);
  const company = useApi<any>(user?.role === "client" ? "/api/v1/clients/me" : null);
  const [c, setC] = useState<any | null>(null);
  const changePw = async () => {
    setBusy(true);
    try { const d = await api("/api/v1/auth/change-password", { json: { current_password: cur, new_password: next } }); setSession(d); setCur(""); setNext(""); toast("Password changed. Other devices were signed out.", "success"); }
    catch (e: any) { toast(e.message, "error"); } finally { setBusy(false); }
  };
  const cc = c || company.data;
  const savePref = async (body: any) => {
    try { await api("/api/v1/auth/me", { method: "PATCH", json: body }); toast("Saved", "success"); reload(); } catch (e: any) { toast(e.message, "error"); }
  };
  return <>
    <PageHeader title="Account" subtitle={`${user?.email} · ${user?.role}`} />
    <div className="grid gap-6 lg:grid-cols-2">
      {user?.role === "client" && cc && <Card><CardHeader title="Company" /><div className="space-y-3 p-5">
        <Input label="Contact name" value={cc.name || ""} onChange={(e) => setC({ ...cc, name: e.target.value })} />
        <Input label="Company name" value={cc.company_name || ""} onChange={(e) => setC({ ...cc, company_name: e.target.value })} />
        <div className="grid grid-cols-2 gap-3"><Input label="Industry" value={cc.industry || ""} onChange={(e) => setC({ ...cc, industry: e.target.value })} />
          <Input label="Website" type="url" value={cc.website || ""} onChange={(e) => setC({ ...cc, website: e.target.value })} placeholder="https://" /></div>
        <Textarea label="About" rows={3} value={cc.about || ""} onChange={(e) => setC({ ...cc, about: e.target.value })} />
        <div className="grid grid-cols-3 gap-3">
          <Select label="Country" value={cc.country || ""} onChange={(e) => setC({ ...cc, country: e.target.value })}><option value="">—</option>
            {COUNTRY_CODES.map((k) => <option key={k} value={k}>{flag(k)} {countryName(k)}</option>)}</Select>
          <Select label="Timezone" value={cc.timezone || ""} onChange={(e) => setC({ ...cc, timezone: e.target.value })}><option value="">—</option>{TIMEZONES.map((z) => <option key={z}>{z}</option>)}</Select>
          <Select label="Billing currency" value={cc.currency || "INR"} onChange={(e) => setC({ ...cc, currency: e.target.value })}>{CURRENCIES.map((k) => <option key={k}>{k}</option>)}</Select>
        </div>
        <p className="text-xs text-slate-500">Billing currency sets plan prices and the default for new jobs. INR is paid via Razorpay; USD / EUR / GBP by card via Stripe.</p>
        <Button onClick={async () => { try { await api("/api/v1/clients/me", { method: "PUT", json: { name: cc.name, company_name: cc.company_name || null, industry: cc.industry || null, website: cc.website || null, about: cc.about || null, country: cc.country || null, timezone: cc.timezone || null, currency: cc.currency || "INR" } }); toast("Company saved", "success"); setC(null); company.reload(); reload(); } catch (e: any) { toast(e.message, "error"); } }}>Save company</Button>
      </div></Card>}
      <Card><CardHeader title="Preferences" /><div className="space-y-4 p-5">
        <LanguagePicker onChange={(l) => savePref({ preferred_language: l })} />
        <label className="flex items-center gap-3 text-sm"><input type="checkbox" className="h-4 w-4" checked={!!user?.email_notifications}
          onChange={(e) => savePref({ email_notifications: e.target.checked })} />
          <span><b>Email notifications</b> — messages, proposals, payments, deliveries and reviews</span></label>
      </div></Card>
      <Card><CardHeader title="Password" /><div className="space-y-3 p-5">
        <Input label="Current password" type="password" autoComplete="current-password" value={cur} onChange={(e) => setCur(e.target.value)} />
        <Input label="New password" type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} hint="At least 8 characters, letters plus numbers or symbols." />
        <Button onClick={changePw} loading={busy} disabled={!cur || next.length < 8}>Change password</Button></div></Card>
      <Card><CardHeader title="Sessions" /><div className="space-y-3 p-5">
        <p className="text-sm text-slate-600">You stay signed in for up to 30 days of inactivity (90 days at most). Lost a device? Sign out everywhere.</p>
        <Button variant="danger" onClick={async () => { await logoutAll(); nav("/login"); }}>Sign out everywhere</Button></div></Card>
    </div>
  </>;
}


function ReviewBox({ orderId, role }: { orderId: number; role: string }) {
  const toast = useToast();
  const { data, reload } = useApi<any>(`/api/v1/reviews/order/${orderId}`);
  const [rating, setRating] = useState(0);
  const [hover, setHover] = useState(0);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  if (!data) return null;
  const submit = async () => {
    setBusy(true);
    try { await api("/api/v1/reviews", { json: { order_id: orderId, rating, comment: comment || null } }); toast("Thanks for your review!", "success"); reload(); }
    catch (e: any) { toast(e.message, "error"); } finally { setBusy(false); }
  };
  const who = role === "client" ? "the freelancer" : "the client";
  return <Card><CardHeader title="Reviews" subtitle="Each side can review once after the work is approved." />
    <div className="space-y-4 p-5">
      {data.items.map((r: any) => <div key={r.id} className="rounded-lg bg-slate-50 p-3 text-sm">
        <div className="flex items-center gap-2"><Stars value={r.rating} /><b>{r.reviewer_name}</b><span className="text-xs text-slate-500">on {r.reviewee_role === "freelancer" ? "the freelancer" : "the client"}</span></div>
        {r.comment && <p className="mt-1 text-slate-700">“{r.comment}”</p>}</div>)}
      {data.can_review && <div className="space-y-3">
        <p className="text-sm font-medium">How was working with {who}?</p>
        <div className="flex gap-1" role="radiogroup" aria-label="Rating" onMouseLeave={() => setHover(0)}>
          {[1, 2, 3, 4, 5].map((n) => <button key={n} role="radio" aria-checked={rating === n} aria-label={`${n} star${n > 1 ? "s" : ""}`}
            onMouseEnter={() => setHover(n)} onClick={() => setRating(n)}
            className={`text-3xl leading-none transition-transform hover:scale-110 ${(hover || rating) >= n ? "text-amber-400" : "text-slate-300"}`}>★</button>)}
        </div>
        <Textarea label="Comment (optional, public)" rows={3} value={comment} onChange={(e) => setComment(e.target.value)} maxLength={2000} />
        <Button onClick={submit} loading={busy} disabled={!rating}>Submit review</Button>
      </div>}
      {!data.can_review && !data.items.length && <p className="text-sm text-slate-500">No reviews yet.</p>}
    </div></Card>;
}
