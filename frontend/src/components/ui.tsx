import { useEffect, useId, useRef, useState, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode,
  type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";
import { Link } from "react-router-dom";
import { initials, label } from "../lib/format";
import { CountUp as CountUpLazy } from "./Motion";

const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");
export { cx };

type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger"; size?: "sm" | "md"; loading?: boolean;
};
const btnBase = "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition disabled:opacity-60 disabled:cursor-not-allowed whitespace-nowrap";
const btnVariants = {
  primary: "bg-brand-600 text-white hover:bg-brand-700 shadow-sm",
  secondary: "bg-white text-slate-800 border border-slate-300 hover:border-slate-400 hover:bg-slate-50",
  ghost: "text-slate-700 hover:bg-slate-100",
  danger: "bg-white text-red-600 border border-red-200 hover:bg-red-50",
};
const btnSizes = { sm: "px-3 py-1.5 text-sm", md: "px-4 py-2 text-sm" };

export function Button({ variant = "primary", size = "md", loading, className, children, disabled, ...rest }: BtnProps) {
  return (
    <button className={cx(btnBase, btnVariants[variant], btnSizes[size], className)} disabled={disabled || loading} {...rest}>
      {loading && <Spinner className="h-4 w-4" />}{children}
    </button>
  );
}

export function ButtonLink({ to, variant = "primary", size = "md", className, children }:
  { to: string; variant?: BtnProps["variant"]; size?: "sm" | "md"; className?: string; children: ReactNode }) {
  return <Link to={to} className={cx(btnBase, btnVariants[variant!], btnSizes[size], className)}>{children}</Link>;
}

export function Spinner({ className = "h-5 w-5" }: { className?: string }) {
  return <svg className={cx("animate-spin", className)} viewBox="0 0 24 24" fill="none" aria-hidden>
    <circle cx="12" cy="12" r="10" stroke="currentColor" strokeOpacity=".25" strokeWidth="3" />
    <path d="M22 12a10 10 0 0 0-10-10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
  </svg>;
}

export function Card({ className, children, ...rest }: { className?: string; children: ReactNode } & Record<string, any>) {
  return <div className={cx("rounded-xl border border-slate-200 bg-white shadow-sm", className)} {...rest}>{children}</div>;
}

export function CardHeader({ title, action, subtitle }: { title: ReactNode; action?: ReactNode; subtitle?: ReactNode }) {
  return <div className="flex items-start justify-between gap-4 border-b border-slate-100 px-5 py-4">
    <div><h3 className="font-semibold text-slate-900">{title}</h3>
      {subtitle && <p className="mt-0.5 text-sm text-slate-500">{subtitle}</p>}</div>
    {action}
  </div>;
}

export function Field({ label: l, hint, error, children, htmlFor }:
  { label: string; hint?: ReactNode; error?: string; children: ReactNode; htmlFor?: string }) {
  return <div className="space-y-1.5">
    <label htmlFor={htmlFor} className="block text-sm font-medium text-slate-700">{l}</label>
    {children}
    {error ? <p className="text-xs text-red-600">{error}</p> : hint ? <p className="text-xs text-slate-500">{hint}</p> : null}
  </div>;
}

const inputCls = "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100 disabled:bg-slate-50";

export function Input({ label: l, hint, className, ...rest }: InputHTMLAttributes<HTMLInputElement> & { label?: string; hint?: ReactNode }) {
  const id = useId();
  const el = <input id={id} className={cx(inputCls, className)} {...rest} />;
  return l ? <Field label={l} hint={hint} htmlFor={id}>{el}</Field> : el;
}

export function Textarea({ label: l, hint, className, ...rest }: TextareaHTMLAttributes<HTMLTextAreaElement> & { label?: string; hint?: ReactNode }) {
  const id = useId();
  const el = <textarea id={id} className={cx(inputCls, "min-h-[90px]", className)} {...rest} />;
  return l ? <Field label={l} hint={hint} htmlFor={id}>{el}</Field> : el;
}

export function Select({ label: l, hint, className, children, ...rest }: SelectHTMLAttributes<HTMLSelectElement> & { label?: string; hint?: ReactNode }) {
  const id = useId();
  const el = <select id={id} className={cx(inputCls, "pr-8", className)} {...rest}>{children}</select>;
  return l ? <Field label={l} hint={hint} htmlFor={id}>{el}</Field> : el;
}

const tones: Record<string, string> = {
  gray: "bg-slate-100 text-slate-700 ring-slate-200", blue: "bg-brand-50 text-brand-700 ring-brand-200",
  green: "bg-emerald-50 text-emerald-700 ring-emerald-200", amber: "bg-amber-50 text-amber-800 ring-amber-200",
  red: "bg-red-50 text-red-700 ring-red-200", violet: "bg-violet-50 text-violet-700 ring-violet-200",
};
export function Badge({ tone = "gray", children, className }: { tone?: keyof typeof tones | string; children: ReactNode; className?: string }) {
  return <span className={cx("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset", tones[tone] || tones.gray, className)}>{children}</span>;
}

const statusTone: Record<string, string> = {
  open: "green", active: "green", paid: "green", completed: "green", released: "green", accepted: "green", available: "green",
  in_progress: "blue", delivered: "violet", shortlisted: "violet", submitted: "gray", pending: "amber",
  pending_payment: "amber", created: "amber", busy: "amber", held: "violet", not_set: "gray",
  under_review: "amber", needs_clarification: "red", closed: "gray", paused: "gray", none: "gray",
  cancelled: "red", failed: "red", rejected: "red", withdrawn: "gray", expired: "red",
  FREE: "gray", PREMIUM: "blue", ENTERPRISE: "violet", admin: "violet", client: "blue", freelancer: "green",
};
export function StatusBadge({ status }: { status?: string | null }) {
  if (!status) return <Badge>No plan</Badge>;
  return <Badge tone={statusTone[status] || "gray"}>{/^[A-Z]+$/.test(status) ? status : label(status)}</Badge>;
}

export function Skills({ skills, matched, missing, max }: { skills?: string[]; matched?: string[]; missing?: string[]; max?: number }) {
  if (matched || missing) {
    return <div className="flex flex-wrap gap-1.5">
      {(matched || []).map((s) => <span key={"m" + s} className="rounded-md bg-emerald-50 px-2 py-0.5 text-xs text-emerald-700 ring-1 ring-emerald-200">✓ {s}</span>)}
      {(missing || []).map((s) => <span key={"x" + s} className="rounded-md bg-slate-50 px-2 py-0.5 text-xs text-slate-400 line-through ring-1 ring-slate-200">{s}</span>)}
    </div>;
  }
  const list = skills || [];
  const shown = max ? list.slice(0, max) : list;
  if (!list.length) return <span className="text-sm text-slate-400">No skills listed</span>;
  return <div className="flex flex-wrap gap-1.5">
    {shown.map((s) => <span key={s} className="rounded-md bg-slate-100 px-2 py-0.5 text-xs text-slate-700">{s}</span>)}
    {max && list.length > max && <span className="text-xs text-slate-500">+{list.length - max}</span>}
  </div>;
}

export function Avatar({ name, size = 40 }: { name: string; size?: number }) {
  const hue = [...name].reduce((a, c) => a + c.charCodeAt(0), 0) % 360;
  return <div aria-hidden className="grid shrink-0 place-items-center rounded-full font-semibold text-white"
    style={{ width: size, height: size, fontSize: size * 0.38, background: `hsl(${hue} 55% 48%)` }}>{initials(name)}</div>;
}

export function ScoreRing({ score, size = 52 }: { score: number; size?: number }) {
  const r = size / 2 - 4, c = 2 * Math.PI * r, pct = Math.max(0, Math.min(100, score));
  const color = pct >= 85 ? "#059669" : pct >= 65 ? "#2563eb" : "#d97706";
  return <div className="relative shrink-0" style={{ width: size, height: size }} title={`${pct.toFixed(0)}% match`}>
    <svg width={size} height={size} className="-rotate-90">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#e2e8f0" strokeWidth="4" />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth="4" strokeLinecap="round"
        className="anim-draw" style={{ ["--len" as any]: c, strokeDasharray: c, strokeDashoffset: c - (c * pct) / 100 }} />
    </svg>
    <span className="absolute inset-0 grid place-items-center text-xs font-semibold text-slate-800">{pct.toFixed(0)}%</span>
  </div>;
}

export function Empty({ title, children, action, icon = "◇" }: { title: string; children?: ReactNode; action?: ReactNode; icon?: string }) {
  return <div className="flex flex-col items-center justify-center px-6 py-12 text-center">
    <div className="mb-3 grid h-11 w-11 place-items-center rounded-full bg-brand-50 text-lg text-brand-600">{icon}</div>
    <p className="font-medium text-slate-800">{title}</p>
    {children && <div className="mt-1 max-w-sm text-sm text-slate-500">{children}</div>}
    {action && <div className="mt-4">{action}</div>}
  </div>;
}

export function Loading({ label: l = "Loading…" }: { label?: string }) {
  return <div className="flex items-center justify-center gap-2 py-16 text-sm text-slate-500"><Spinner /> {l}</div>;
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
    {message} {onRetry && <button className="ml-2 font-medium underline" onClick={onRetry}>Try again</button>}
  </div>;
}

export function Notice({ tone = "amber", children }: { tone?: "amber" | "blue" | "green"; children: ReactNode }) {
  const t = { amber: "border-amber-200 bg-amber-50 text-amber-900", blue: "border-brand-200 bg-brand-50 text-brand-900",
    green: "border-emerald-200 bg-emerald-50 text-emerald-900" }[tone];
  return <div className={cx("rounded-lg border px-4 py-3 text-sm", t)}>{children}</div>;
}

export function PageHeader({ title, subtitle, actions, crumbs }:
  { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode; crumbs?: { to: string; label: string }[] }) {
  return <div className="mb-6">
    {crumbs && <nav className="mb-2 flex gap-1 text-sm text-slate-500">
      {crumbs.map((c) => <span key={c.to}><Link className="hover:text-brand-700" to={c.to}>{c.label}</Link> <span className="mx-1">/</span></span>)}
    </nav>}
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div><h1 className="text-2xl font-semibold text-slate-900">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}</div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  </div>;
}

export function Stat({ label: l, value, hint, accent }: { label: string; value: ReactNode; hint?: ReactNode; accent?: boolean }) {
  return <Card className={cx("p-5 anim-fade-up", accent && "border-brand-200 bg-gradient-to-br from-brand-50 to-white")}>
    <p className="text-sm text-slate-500">{l}</p>
    <p className="mt-1 text-2xl font-semibold tabular-nums text-slate-900">{typeof value === "number" ? <CountUpLazy value={value} /> : value}</p>
    {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
  </Card>;
}

export function Tabs({ tabs, value, onChange }: { tabs: { id: string; label: ReactNode }[]; value: string; onChange: (id: string) => void }) {
  const wrap = useRef<HTMLDivElement>(null);
  const [bar, setBar] = useState<{ left: number; width: number } | null>(null);
  useEffect(() => {
    const el = wrap.current?.querySelector<HTMLElement>(`[data-tab="${CSS.escape(value)}"]`);
    if (el) setBar({ left: el.offsetLeft, width: el.offsetWidth });
  }, [value, tabs.length]);
  return <div ref={wrap} className="relative mb-5 flex gap-1 overflow-x-auto border-b border-slate-200" role="tablist">
    {tabs.map((t) => <button key={t.id} data-tab={t.id} role="tab" aria-selected={value === t.id} onClick={() => onChange(t.id)}
      className={cx("whitespace-nowrap px-3 py-2 text-sm font-medium transition-colors",
        value === t.id ? "text-brand-700" : "text-slate-500 hover:text-slate-800")}>{t.label}</button>)}
    {bar && <span aria-hidden className="absolute bottom-0 h-0.5 rounded-full bg-brand-600 transition-all duration-300 ease-out" style={{ left: bar.left, width: bar.width }} />}
  </div>;
}

export function Modal({ open, onClose, title, children, footer, wide }:
  { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode; footer?: ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const prev = document.activeElement as HTMLElement | null;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    setTimeout(() => ref.current?.querySelector<HTMLElement>("input,textarea,select,button")?.focus(), 30);
    return () => { document.removeEventListener("keydown", onKey); prev?.focus?.(); };
  }, [open, onClose]);
  if (!open) return null;
  return <div className="anim-backdrop fixed inset-0 z-50 flex items-end justify-center bg-slate-900/40 p-4 backdrop-blur-[2px] sm:items-center" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
    <div ref={ref} role="dialog" aria-modal="true" className={cx("anim-pop max-h-[90vh] w-full overflow-y-auto rounded-xl bg-white shadow-xl", wide ? "max-w-2xl" : "max-w-lg")}>
      <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
        <h2 className="font-semibold">{title}</h2>
        <button onClick={onClose} className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700" aria-label="Close">✕</button>
      </div>
      <div className="space-y-4 px-5 py-4">{children}</div>
      {footer && <div className="flex justify-end gap-2 border-t border-slate-100 bg-slate-50 px-5 py-3">{footer}</div>}
    </div>
  </div>;
}

export function Table({ head, children, empty }: { head: ReactNode[]; children: ReactNode; empty?: ReactNode }) {
  return <div className="overflow-x-auto">
    <table className="w-full text-left text-sm">
      <thead><tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
        {head.map((h, i) => <th key={i} className="whitespace-nowrap px-4 py-2.5 font-medium">{h}</th>)}
      </tr></thead>
      <tbody className="divide-y divide-slate-100">{children}</tbody>
    </table>
    {empty}
  </div>;
}

export const Td = ({ children, className }: { children?: ReactNode; className?: string }) =>
  <td className={cx("px-4 py-3 align-top", className)}>{children}</td>;
