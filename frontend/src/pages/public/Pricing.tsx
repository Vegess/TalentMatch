import { useNavigate } from "react-router-dom";
import { useApi, useTitle } from "../../lib/hooks";
import { useAuth } from "../../lib/auth";
import { browserCountry, money } from "../../lib/format";
import { useState } from "react";
import { Button, Card, Loading, cx } from "../../components/ui";

const guessCurrency = () => { const c = browserCountry(); return c === "IN" || !c ? "INR" : c === "GB" ? "GBP" : ["DE", "FR", "ES", "IT", "NL", "IE", "PT", "AT", "BE", "FI", "GR"].includes(c) ? "EUR" : "USD"; };

export function PlanCards({ current, onChoose, busy, currency: fixed }: { current?: string | null; onChoose?: (plan: string) => void; busy?: string | null; currency?: string }) {
  const [picked, setPicked] = useState(guessCurrency);
  const currency = fixed || picked;
  const { data } = useApi<any[]>("/api/v1/subscriptions/plans");
  const { user } = useAuth();
  const nav = useNavigate();
  if (!data) return <Loading />;
  return <div>
    {!fixed && <div className="mb-4 flex justify-end"><div className="flex rounded-lg border border-slate-300 bg-white p-0.5" role="radiogroup" aria-label="Currency">
      {["INR", "USD", "EUR", "GBP"].map((c) => <button key={c} role="radio" aria-checked={currency === c} onClick={() => setPicked(c)}
        className={cx("rounded-md px-2.5 py-1 text-xs font-semibold", currency === c ? "bg-brand-600 text-white" : "text-slate-600")}>{c}</button>)}</div></div>}
    <div className="grid gap-4 md:grid-cols-3">{data.map((p) => {
    const highlight = p.plan_type === "PREMIUM";
    const isCurrent = current === p.plan_type;
    return <Card key={p.plan_type} className={cx("flex flex-col p-6", highlight && "border-brand-300 ring-2 ring-brand-100")}>
      <div className="flex items-center justify-between"><h3 className="font-semibold">{p.name}</h3>{highlight && <span className="rounded-full bg-brand-600 px-2 py-0.5 text-xs text-white">Popular</span>}</div>
      <p className="mt-3"><span className="text-3xl font-bold">{money(p.prices?.[currency] ?? p.price_monthly, currency)}</span><span className="text-sm text-slate-500"> / month</span></p>
      <ul className="mt-5 flex-1 space-y-2 text-sm text-slate-600">
        <li>✓ {p.max_open_jobs == null ? "Unlimited" : p.max_open_jobs} open job{p.max_open_jobs === 1 ? "" : "s"}</li>
        <li>✓ {p.max_visible_matches == null ? "Every" : `Top ${p.max_visible_matches}`} ranked matches per job</li>
        <li>{p.show_contact_details ? "✓ Freelancer contact details" : "– Contact details hidden"}</li>
        <li>{p.can_message_any ? "✓ Message any freelancer" : "– Message freelancers who applied"}</li>
        <li>✓ Proposals, orders and secure payments</li>
      </ul>
      <div className="mt-6">
        {onChoose ? <Button className="w-full" variant={isCurrent ? "secondary" : highlight ? "primary" : "secondary"} disabled={isCurrent}
          loading={busy === p.plan_type} onClick={() => onChoose(p.plan_type)}>{isCurrent ? "Current plan" : p.price_monthly ? `Upgrade to ${p.name}` : "Switch to Free"}</Button>
          : <Button className="w-full" variant={highlight ? "primary" : "secondary"}
            onClick={() => nav(user?.role === "client" ? "/client/billing" : "/register?role=client")}>{p.price_monthly ? `Choose ${p.name}` : "Start free"}</Button>}
      </div>
    </Card>;
  })}</div></div>;
}

export default function Pricing() {
  useTitle("Pricing");
  return <div className="mx-auto max-w-6xl px-4 py-12">
    <h1 className="text-3xl font-bold">Simple pricing for hiring teams</h1>
    <p className="mt-2 text-slate-600">Freelancers always join free. On orders, the platform keeps a 10% fee from the freelancer's payout. Pay in INR (UPI, cards via Razorpay) or USD / EUR / GBP (cards via Stripe).</p>
    <div className="mt-8"><PlanCards /></div>
  </div>;
}
