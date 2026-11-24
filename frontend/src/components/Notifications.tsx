import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { ago } from "../lib/format";
import { cx } from "./ui";

const ICON: Record<string, string> = { message: "✉", new_proposal: "📥", hired: "🎉", order_paid: "₹", delivered: "📦",
  approved: "✅", review: "★", plan_activated: "⭐", verified: "✓", changes_requested: "↺", proposal_declined: "–" };

export function NotificationBell({ align = "left" }: { align?: "left" | "right" }) {
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<{ unread: number; items: any[] }>({ unread: 0, items: [] });
  const [msgs, setMsgs] = useState(0);
  const ref = useRef<HTMLDivElement>(null);
  const load = useCallback(async () => {
    try {
      const [n, m] = await Promise.all([api("/api/v1/notifications?limit=20"), api("/api/v1/conversations/unread-count").catch(() => ({ unread: 0 }))]);
      setData(n); setMsgs(m.unread);
    } catch { /* signed out */ }
  }, []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const h = (e: Event) => { const t = (e as CustomEvent).detail?.type; if (t === "notification" || t === "message") load(); };
    window.addEventListener("tm:event", h);
    return () => window.removeEventListener("tm:event", h);
  }, [load]);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", close); document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", esc); };
  }, [open]);
  const openItem = async (n: any) => {
    setOpen(false);
    if (!n.read) api(`/api/v1/notifications/${n.id}/read`, { method: "POST" }).then(load).catch(() => {});
    if (n.link) nav(n.link);
  };
  return <div ref={ref} className="relative flex items-center gap-1">
    <button onClick={() => nav("/messages")} className="relative rounded-lg p-2 text-slate-600 hover:bg-slate-100" aria-label={`Messages${msgs ? `, ${msgs} unread` : ""}`}>
      <span aria-hidden>✉</span>{msgs > 0 && <span className="absolute -right-0.5 -top-0.5 grid h-4 min-w-4 place-items-center rounded-full bg-brand-600 px-1 text-[10px] font-semibold text-white">{msgs}</span>}
    </button>
    <button onClick={() => setOpen(!open)} className="relative rounded-lg p-2 text-slate-600 hover:bg-slate-100" aria-haspopup="true" aria-expanded={open}
      aria-label={`Notifications${data.unread ? `, ${data.unread} unread` : ""}`}>
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden className={cx(data.unread > 0 && "anim-ring")}><path d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9" /><path d="M10.3 21a1.9 1.9 0 0 0 3.4 0" /></svg>
      {data.unread > 0 && <span className="absolute -right-0.5 -top-0.5 grid h-4 min-w-4 place-items-center rounded-full bg-red-500 px-1 text-[10px] font-semibold text-white">{data.unread > 9 ? "9+" : data.unread}</span>}
    </button>
    {open && <div className={cx("anim-pop absolute top-11 z-50 w-[min(360px,calc(100vw-2rem))] overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl", align === "right" ? "right-0" : "left-0")}>
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-2.5">
        <p className="text-sm font-semibold">Notifications</p>
        {data.unread > 0 && <button className="text-xs font-medium text-brand-700 hover:underline" onClick={async () => { await api("/api/v1/notifications/read-all", { method: "POST" }); load(); }}>Mark all read</button>}
      </div>
      {!data.items.length ? <p className="px-4 py-8 text-center text-sm text-slate-500">You're all caught up.</p> :
        <ul className="max-h-96 divide-y divide-slate-100 overflow-y-auto">{data.items.map((n) => <li key={n.id}>
          <button onClick={() => openItem(n)} className={cx("flex w-full gap-3 px-4 py-3 text-left hover:bg-slate-50", !n.read && "bg-brand-50/50")}>
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-slate-100 text-sm" aria-hidden>{ICON[n.kind] || "•"}</span>
            <span className="min-w-0"><span className={cx("block text-sm", !n.read && "font-semibold")}>{n.title}</span>
              {n.body && <span className="line-clamp-2 block text-xs text-slate-500">{n.body}</span>}
              <span className="text-[11px] text-slate-400">{ago(n.created_at)}</span></span>
          </button></li>)}</ul>}
    </div>}
  </div>;
}
