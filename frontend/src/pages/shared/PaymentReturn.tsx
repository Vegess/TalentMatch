import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../../lib/api";
import { useTitle } from "../../lib/hooks";
import { money } from "../../lib/format";
import { ButtonLink, Card, Spinner } from "../../components/ui";
import { SuccessMark } from "../../components/Motion";

/** Stripe sends the client back here after Checkout. We confirm with the server (which asks Stripe). */
export default function PaymentReturn() {
  useTitle("Payment");
  const [params] = useSearchParams();
  const pid = Number(params.get("pid"));
  const sessionId = params.get("session_id");
  const cancelled = params.get("cancelled");
  const [state, setState] = useState<"checking" | "paid" | "pending" | "failed" | "cancelled">("checking");
  const [payment, setPayment] = useState<any>(null);
  let back = "/";
  try { back = sessionStorage.getItem("tm_after_pay") || "/"; } catch { /* ignore */ }

  useEffect(() => {
    let stop = false;
    (async () => {
      if (!pid) { setState("failed"); return; }
      if (cancelled || !sessionId) {
        await api(`/api/v1/payments/${pid}/failed?reason=Checkout%20cancelled`, { method: "POST" }).catch(() => {});
        setState("cancelled"); return;
      }
      for (let i = 0; i < 6 && !stop; i++) {   // card payments confirm instantly; bank debits may take longer
        try {
          const p = await api("/api/v1/payments/stripe/confirm", { json: { payment_id: pid, session_id: sessionId } });
          setPayment(p);
          if (p.status === "paid") { setState("paid"); return; }
          if (p.status === "failed") { setState("failed"); return; }
        } catch { setState("failed"); return; }
        await new Promise((r) => setTimeout(r, 2000));
      }
      if (!stop) setState("pending");
    })();
    return () => { stop = true; };
  }, [pid, sessionId, cancelled]);

  return <div className="mx-auto max-w-md py-10">
    <Card className="p-8 text-center">
      {state === "checking" && <><Spinner className="mx-auto h-8 w-8 text-brand-600" /><p className="mt-4 font-medium">Confirming your payment…</p></>}
      {state === "paid" && <><SuccessMark /><p className="mt-4 text-lg font-semibold">Payment received</p>
        <p className="mt-1 text-sm text-slate-600">{payment && money(payment.amount, payment.currency)} · ref {payment?.provider_payment_id}</p></>}
      {state === "pending" && <><p className="text-lg font-semibold">Payment processing</p><p className="mt-1 text-sm text-slate-600">Your bank is still confirming it. We'll update your account automatically — you'll get a notification.</p></>}
      {state === "cancelled" && <><p className="text-lg font-semibold">Payment cancelled</p><p className="mt-1 text-sm text-slate-600">Nothing was charged. You can try again any time.</p></>}
      {state === "failed" && <><p className="text-lg font-semibold">Payment not completed</p><p className="mt-1 text-sm text-slate-600">Nothing was charged. Please try again.</p></>}
      {state !== "checking" && <ButtonLink className="mt-6" to={back}>Continue</ButtonLink>}
    </Card>
  </div>;
}
