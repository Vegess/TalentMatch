import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";
import { api } from "../lib/api";
import { money } from "../lib/format";
import { Button, Modal, Notice } from "./ui";

/* One entry point for every payment:
 *   const pay = usePay();  await pay({ purpose: "order", order_id })
 * Uses Razorpay Checkout when the API has keys, otherwise a clearly-labelled demo checkout. */

type CheckoutBody = { purpose: "subscription" | "order"; plan_type?: string; months?: number; order_id?: number };
type Result = { status: "paid" | "failed" | "dismissed"; payment?: any };
const Ctx = createContext<(b: CheckoutBody) => Promise<Result>>(async () => ({ status: "dismissed" }));

let rzpLoading: Promise<void> | null = null;
function loadRazorpay(): Promise<void> {
  if ((window as any).Razorpay) return Promise.resolve();
  rzpLoading ??= new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = "https://checkout.razorpay.com/v1/checkout.js";
    s.onload = () => resolve();
    s.onerror = () => { rzpLoading = null; reject(new Error("Could not load Razorpay Checkout")); };
    document.body.appendChild(s);
  });
  return rzpLoading;
}

export function CheckoutProvider({ children }: { children: ReactNode }) {
  const [demo, setDemo] = useState<any | null>(null);
  const [busy, setBusy] = useState(false);
  const resolver = useRef<(r: Result) => void>(() => {});

  const pay = useCallback(async (body: CheckoutBody): Promise<Result> => {
    const co = await api("/api/v1/payments/checkout", { json: body });
    if (co.provider === "stripe") {
      // Stripe hosts the card form; it sends the client back to /payments/return.
      try { sessionStorage.setItem("tm_after_pay", window.location.pathname + window.location.search); } catch { /* ignore */ }
      window.location.assign(co.checkout_url);
      return new Promise<Result>(() => {});
    }
    if (co.provider === "razorpay") {
      await loadRazorpay();
      return new Promise<Result>((resolve) => {
        const rzp = new (window as any).Razorpay({
          key: co.key_id, amount: co.amount_paise, currency: co.currency, order_id: co.provider_order_id,
          name: "TalentMatch", description: co.description, prefill: co.prefill, theme: { color: "#2563eb" },
          handler: async (resp: any) => {
            try {
              const p = await api("/api/v1/payments/verify", { json: { payment_id: co.payment_id, ...resp } });
              resolve({ status: "paid", payment: p });
            } catch { resolve({ status: "failed" }); }
          },
          modal: { ondismiss: () => { api(`/api/v1/payments/${co.payment_id}/failed?reason=Checkout%20closed`, { method: "POST" }).catch(() => {}); resolve({ status: "dismissed" }); } },
        });
        rzp.on("payment.failed", (r: any) => {
          api(`/api/v1/payments/${co.payment_id}/failed?reason=${encodeURIComponent(r?.error?.description || "Payment failed")}`, { method: "POST" }).catch(() => {});
        });
        rzp.open();
      });
    }
    return new Promise<Result>((resolve) => { resolver.current = resolve; setDemo(co); });
  }, []);

  const finishDemo = async (outcome: "success" | "failure" | "dismiss") => {
    const co = demo;
    if (!co) return;
    if (outcome === "dismiss") {
      api(`/api/v1/payments/${co.payment_id}/failed?reason=Checkout%20closed`, { method: "POST" }).catch(() => {});
      setDemo(null); resolver.current({ status: "dismissed" }); return;
    }
    setBusy(true);
    try {
      const p = await api(`/api/v1/payments/${co.payment_id}/demo-complete`, { json: { outcome } });
      resolver.current({ status: p.status === "paid" ? "paid" : "failed", payment: p });
    } catch { resolver.current({ status: "failed" }); }
    finally { setBusy(false); setDemo(null); }
  };

  return <Ctx.Provider value={pay}>
    {children}
    <Modal open={!!demo} onClose={() => finishDemo("dismiss")} title="Checkout"
      footer={<>
        <Button variant="ghost" onClick={() => finishDemo("failure")} disabled={busy}>Simulate failure</Button>
        <Button onClick={() => finishDemo("success")} loading={busy}>Pay {demo && money(demo.amount_minor / 100, demo.currency)}</Button>
      </>}>
      <Notice tone="blue"><b>Demo mode.</b> No money moves. Add Razorpay (INR) or Stripe (USD / EUR / GBP) keys on the server for real payments.</Notice>
      <div className="rounded-lg border border-slate-200 p-4">
        <p className="text-sm text-slate-500">{demo?.description}</p>
        <p className="mt-1 text-3xl font-semibold">{demo && money(demo.amount_minor / 100, demo.currency)}</p>
        <p className="mt-2 text-xs text-slate-500">Billed to {demo?.prefill?.name} · {demo?.prefill?.email}</p>
      </div>
    </Modal>
  </Ctx.Provider>;
}

export const usePay = () => useContext(Ctx);
