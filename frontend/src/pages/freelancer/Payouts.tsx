import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api } from "../../lib/api";
import { useApi, useTitle } from "../../lib/hooks";
import { date, inr, money } from "../../lib/format";
import { useToast } from "../../components/Toast";
import { Button, Card, CardHeader, Empty, ErrorBox, Input, Loading, Notice, PageHeader, Stat, StatusBadge, Table, Td,
  cx } from "../../components/ui";

const STATUS_TEXT: Record<string, string> = {
  not_set: "Add where you want to be paid. Until then, approved earnings wait for you.",
  active: "Payouts are active. Your share of each order is sent to you automatically when the client approves.",
  under_review: "Razorpay is verifying your account (usually 10–15 minutes for bank accounts). Earnings are held safely meanwhile.",
  needs_clarification: "Razorpay couldn't verify these details. Check the name and number, then save again.",
  failed: "Setting up payouts failed. Check your details and save again.",
};

export const PAYOUT_EXPLAIN: Record<string, string> = {
  none: "Not paid yet.",
  held: "Your share is with Razorpay, on hold until the client approves the work.",
  pending: "Approved — waiting for payout details or a manual payout by the platform.",
  released: "Released to the freelancer's bank / UPI (arrives on Razorpay's settlement schedule).",
  failed: "The automatic payout failed. The platform team will retry it.",
};

export default function Payouts() {
  useTitle("Payouts");
  const toast = useToast();
  const { data, error, loading, reload } = useApi<any>("/api/v1/freelancers/me/payout");
  const [method, setMethod] = useState<"bank_account" | "upi">("upi");
  const [f, setF] = useState({ beneficiary_name: "", account_number: "", confirm: "", ifsc: "", vpa: "" });
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.value });
  const mismatch = method === "bank_account" && f.confirm && f.confirm !== f.account_number;
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (mismatch) return;
    setBusy(true);
    try {
      const r = await api("/api/v1/freelancers/me/payout", { method: "PUT", json: method === "upi"
        ? { method, beneficiary_name: f.beneficiary_name, vpa: f.vpa }
        : { method, beneficiary_name: f.beneficiary_name, account_number: f.account_number, ifsc: f.ifsc } });
      toast(r.orders_paid_now?.length ? `Saved — ${r.orders_paid_now.length} waiting payout(s) sent now.` : "Payout details saved", "success");
      setF({ beneficiary_name: "", account_number: "", confirm: "", ifsc: "", vpa: "" }); setEditing(false); reload();
    } catch (err: any) { toast(err.message, "error"); } finally { setBusy(false); }
  };
  const t = data.totals;
  const showForm = data.mode !== "off" && (editing || data.status === "not_set");
  return <>
    <PageHeader title="Payouts" subtitle="Where your earnings go, and the status of every paid order." />
    {data.mode === "off" && <div className="mb-6"><Notice>Automatic payouts aren't switched on for this platform. After each approved order the team pays you manually (bank / UPI).</Notice></div>}
    {data.mode === "demo" && <div className="mb-6"><Notice tone="blue"><b>Demo mode:</b> payouts are simulated with Razorpay Route test IDs. No money moves.</Notice></div>}
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <Stat accent label="Paid out" value={inr(t.released)} hint="released to your account" />
      <Stat label="On hold" value={inr(t.held)} hint="released when the client approves" />
      <Stat label="Waiting" value={inr(t.pending + t.failed)} hint={t.failed ? "includes a failed payout being retried" : "approved, not yet paid out"} />
      <Stat label="In progress" value={inr(t.in_work)} hint="paid orders not yet secured" />
    </div>
    {Object.keys(data.other_currencies || {}).length > 0 && <div className="mt-4"><Notice tone="blue">International orders: {Object.entries(data.other_currencies).map(([c, v]: any) =>
      `${money(v.released, c)} paid out · ${money(v.pending + v.failed + v.held + v.in_work, c)} to come`).join(" · ")}. Automatic payouts cover INR orders; international ones are paid out by the platform team.</Notice></div>}

    <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_1.1fr]">
      <Card>
        <CardHeader title="Payout account" action={<StatusBadge status={data.status} />} />
        <div className="space-y-4 p-5">
          <p className="text-sm text-slate-600">{STATUS_TEXT[data.status] || ""}</p>
          {data.note && <Notice>{data.note}</Notice>}
          {data.masked && !showForm && <div className="rounded-lg border border-slate-200 p-4">
            <p className="text-xs uppercase tracking-wide text-slate-500">{data.method === "upi" ? "UPI" : "Bank account"}</p>
            <p className="mt-1 font-mono text-sm">{data.masked}</p>
            <p className="text-sm text-slate-600">{data.beneficiary_name}</p>
            {data.mode !== "off" && <Button size="sm" variant="secondary" className="mt-3" onClick={() => setEditing(true)}>Change</Button>}
          </div>}
          {showForm && <form onSubmit={submit} className="space-y-4">
            <div className="grid grid-cols-2 gap-2 rounded-lg bg-slate-100 p-1" role="radiogroup">
              {([["upi", "UPI"], ["bank_account", "Bank account"]] as const).map(([k, l]) => <button key={k} type="button" role="radio" aria-checked={method === k}
                onClick={() => setMethod(k)} className={cx("rounded-md py-2 text-sm font-medium", method === k ? "bg-white shadow-sm" : "text-slate-500")}>{l}</button>)}
            </div>
            <Input label="Name exactly as on the account" required minLength={4} value={f.beneficiary_name} onChange={set("beneficiary_name")} autoComplete="name" />
            {method === "upi"
              ? <Input label="UPI ID" required value={f.vpa} onChange={set("vpa")} placeholder="yourname@okhdfcbank" />
              : <>
                <Input label="Account number" required inputMode="numeric" autoComplete="off" value={f.account_number} onChange={set("account_number")} />
                <Input label="Confirm account number" required inputMode="numeric" autoComplete="off" value={f.confirm} onChange={set("confirm")}
                  hint={mismatch ? <span className="text-red-600">Numbers don't match</span> : undefined} />
                <Input label="IFSC" required value={f.ifsc} onChange={(e) => setF({ ...f, ifsc: e.target.value.toUpperCase() })} placeholder="HDFC0000317" maxLength={11} />
              </>}
            <p className="text-xs text-slate-500">Sent securely to Razorpay to create your payout account. TalentMatch keeps only a masked copy (last 4 digits).</p>
            <div className="flex gap-2">
              <Button type="submit" loading={busy} disabled={!!mismatch}>Save payout details</Button>
              {data.status !== "not_set" && <Button type="button" variant="ghost" onClick={() => setEditing(false)}>Cancel</Button>}
            </div>
          </form>}
        </div>
      </Card>

      <Card><CardHeader title="How you get paid" /><ol className="space-y-3 p-5 text-sm text-slate-600">
        <li><b className="text-slate-900">1. Client pays</b> the full order amount through Razorpay.</li>
        <li><b className="text-slate-900">2. Your share is secured</b> — the amount minus the platform fee moves to your Razorpay payout account, on hold.</li>
        <li><b className="text-slate-900">3. You deliver</b>, and the client approves.</li>
        <li><b className="text-slate-900">4. Released automatically</b> — Razorpay settles it to your bank / UPI on its settlement schedule.</li>
      </ol></Card>
    </div>

    <Card className="mt-6"><CardHeader title="Paid orders" />
      {!data.orders.length ? <Empty title="No paid orders yet" icon="₹">Earnings appear here once a client pays.</Empty> :
        <Table head={["Order", "Client", "Your share", "Order status", "Payout", ""]}>{data.orders.map((o: any) => <tr key={o.id}>
          <Td><Link to={`/orders/${o.id}`} className="font-medium hover:text-brand-700">#{o.id} · {o.title}</Link><p className="text-xs text-slate-500">Paid {date(o.paid_at)}</p></Td>
          <Td>{o.client?.company_name}</Td><Td className="font-medium">{money(o.freelancer_earnings, o.currency)}</Td>
          <Td><StatusBadge status={o.status} /></Td><Td><StatusBadge status={o.payout_status} /></Td>
          <Td className="max-w-[260px] text-xs text-slate-500">{o.payout_status === "released" && o.payout_released_at ? `Released ${date(o.payout_released_at)}` : PAYOUT_EXPLAIN[o.payout_status]}</Td></tr>)}</Table>}
    </Card>
  </>;
}
