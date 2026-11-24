import { useRef, useState, type ReactNode } from "react";
import { Link, NavLink, Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import { homeFor, useAuth, type Role } from "../lib/auth";
import { useRealtime } from "../lib/realtime";
import { inr } from "../lib/format";
import { useToast } from "./Toast";
import { Avatar, ButtonLink, Loading, StatusBadge, cx } from "./ui";
import { NotificationBell } from "./Notifications";
import { LanguagePicker, useLang } from "../lib/i18n";
import { useEffect } from "react";

export function Logo({ light }: { light?: boolean }) {
  return <Link to="/" className="flex items-center gap-2 font-semibold">
    <svg width="28" height="28" viewBox="0 0 32 32" aria-hidden><rect width="32" height="32" rx="8" fill="#2563eb" />
      <path d="M9 11h14M16 11v12" stroke="#fff" strokeWidth="3.2" strokeLinecap="round" /><circle cx="23" cy="22" r="2.6" fill="#93c5fd" /></svg>
    <span className={light ? "text-white" : "text-slate-900"}>TalentMatch</span>
  </Link>;
}

export function PublicLayout() {
  const { user } = useAuth();
  const loc = useLocation();
  const [open, setOpen] = useState(false);
  const links = [["/freelancers", "Find talent"], ["/services", "Services"], ["/jobs", "Jobs"], ["/pricing", "Pricing"]];
  return <div className="flex min-h-screen flex-col">
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/90 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4">
        <div className="flex items-center gap-8"><Logo />
          <nav className="hidden gap-1 md:flex">{links.map(([to, l]) =>
            <NavLink key={to} to={to} className={({ isActive }) => cx("rounded-md px-3 py-2 text-sm font-medium", isActive ? "text-brand-700" : "text-slate-600 hover:text-slate-900")}>{l}</NavLink>)}</nav>
        </div>
        <div className="hidden items-center gap-2 md:flex">
          <LanguagePicker compact />
          {user ? <ButtonLink to={homeFor(user.role)}>Go to dashboard</ButtonLink> : <>
            <ButtonLink to="/login" variant="ghost">Sign in</ButtonLink>
            <ButtonLink to="/register">Get started</ButtonLink></>}
        </div>
        <button className="rounded p-2 md:hidden" onClick={() => setOpen(!open)} aria-label="Menu">☰</button>
      </div>
      {open && <nav className="border-t border-slate-100 px-4 py-2 md:hidden" onClick={() => setOpen(false)}>
        <div className="py-2" onClick={(e) => e.stopPropagation()}><LanguagePicker compact /></div>
        {links.map(([to, l]) => <Link key={to} to={to} className="block py-2 text-sm">{l}</Link>)}
        <Link to={user ? homeFor(user.role) : "/login"} className="block py-2 text-sm font-medium text-brand-700">{user ? "Dashboard" : "Sign in"}</Link>
      </nav>}
    </header>
    <main className="flex-1"><div key={loc.pathname} className="anim-page"><Outlet /></div></main>
    <footer className="border-t border-slate-200 bg-white">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-4 py-6 text-sm text-slate-500">
        <Logo /><p>Payments secured by Razorpay &amp; Stripe · © {new Date().getFullYear()} TalentMatch</p>
      </div>
    </footer>
  </div>;
}

type Item = { to: string; label: string; icon: string; end?: boolean };
const NAV: Record<Role, Item[]> = {
  client: [
    { to: "/client", label: "Dashboard", icon: "◧", end: true }, { to: "/client/jobs/new", label: "Post a job", icon: "＋" },
    { to: "/client/jobs", label: "My jobs", icon: "▤", end: true }, { to: "/messages", label: "Messages", icon: "✉" },
    { to: "/orders", label: "Orders", icon: "⇄" },
    { to: "/client/billing", label: "Plan & billing", icon: "₹" }, { to: "/freelancers", label: "Browse talent", icon: "☺" },
    { to: "/services", label: "Browse services", icon: "◈" }],
  freelancer: [
    { to: "/freelancer", label: "Dashboard", icon: "◧", end: true }, { to: "/freelancer/jobs", label: "Find work", icon: "⌕" },
    { to: "/freelancer/proposals", label: "Proposals", icon: "✎" }, { to: "/messages", label: "Messages", icon: "✉" },
    { to: "/orders", label: "Orders", icon: "⇄" },
    { to: "/freelancer/services", label: "My services", icon: "◈" }, { to: "/freelancer/payouts", label: "Payouts", icon: "₹" },
    { to: "/freelancer/profile", label: "Profile & CV", icon: "☺" }],
  admin: [
    { to: "/control-room", label: "Overview", icon: "◧", end: true }, { to: "/control-room/users", label: "Users", icon: "☺" },
    { to: "/control-room/payments", label: "Payments", icon: "₹" }, { to: "/control-room/orders", label: "Orders & payouts", icon: "⇄" },
    { to: "/control-room/jobs", label: "Jobs", icon: "▤" }, { to: "/control-room/services", label: "Services", icon: "◈" },
    { to: "/control-room/audit", label: "Audit log", icon: "≡" }],
};

export function AppShell() {
  const { user, logout } = useAuth();
  const { lang, setLang } = useLang();
  const loc = useLocation();
  useEffect(() => {   // apply the language saved on the account (other device / first sign-in)
    const pref = user?.preferred_language as any;
    if (pref && pref !== lang) setLang(pref);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id]);
  const toast = useToast();
  const nav = useNavigate();
  const [mobile, setMobile] = useState(false);
  const queue = useRef<any[]>([]);
  const timer = useRef<any>(null);
  useRealtime(!!user, (e) => {
    if (user?.role === "admin") {
      if (e.type === "plan_activated" || e.type === "order_paid") toast(e.type === "plan_activated" ? `A client activated ${e.plan}` : `Order #${e.order_id} was paid`, "info");
      return;
    }
    if (e.type !== "notification" || e.kind === "message" && location.pathname.startsWith("/messages")) return;
    queue.current.push(e); clearTimeout(timer.current);
    timer.current = setTimeout(() => {   // group bursts into one toast
      const batch = queue.current.splice(0);
      toast(batch.length === 1 ? batch[0].title : `${batch.length} new notifications`, "info");
    }, 400);
  });
  if (!user) return null;
  const items = NAV[user.role];
  const side = <nav className="space-y-0.5 p-3">
    {items.map((i) => <NavLink key={i.to} to={i.to} end={i.end} onClick={() => setMobile(false)}
      className={({ isActive }) => cx("flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition",
        isActive ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900")}>
      <span className="w-4 text-center opacity-70" aria-hidden>{i.icon}</span>{i.label}</NavLink>)}
    <NavLink to="/settings" onClick={() => setMobile(false)} className={({ isActive }) => cx("flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium",
      isActive ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100")}><span className="w-4 text-center opacity-70">⚙</span>Account</NavLink>
  </nav>;
  return <div className="min-h-screen lg:grid lg:grid-cols-[240px_1fr]">
    <aside className="hidden border-r border-slate-200 bg-white lg:sticky lg:top-0 lg:flex lg:h-screen lg:flex-col">
      <div className="flex h-16 items-center justify-between pl-5 pr-2"><Logo /><NotificationBell /></div>
      {user.role === "admin" && <p className="px-6 pb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-400">Control room</p>}
      <div className="flex-1 overflow-y-auto">{side}</div>
      <div className="border-t border-slate-100 p-3">
        <div className="flex items-center gap-3 rounded-lg px-2 py-2">
          <Avatar name={user.name} size={34} />
          <div className="min-w-0 flex-1"><p className="truncate text-sm font-medium">{user.name}</p>
            <p className="truncate text-xs text-slate-500">{user.role === "client" ? user.company_name || "Client" : user.role}</p></div>
          {user.role === "client" && <StatusBadge status={user.plan} />}
        </div>
        <button className="mt-1 w-full rounded-lg px-3 py-2 text-left text-sm text-slate-600 hover:bg-slate-100" onClick={async () => { await logout(); nav("/"); }}>Sign out</button>
      </div>
    </aside>
    <div className="min-w-0">
      <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-slate-200 bg-white/90 px-4 backdrop-blur lg:hidden">
        <Logo /><div className="flex items-center"><NotificationBell align="right" /><button onClick={() => setMobile(!mobile)} className="rounded p-2" aria-label="Menu">☰</button></div>
      </header>
      {mobile && <div className="border-b border-slate-200 bg-white lg:hidden">{side}
        <button className="mb-3 ml-6 text-sm text-slate-600" onClick={async () => { await logout(); nav("/"); }}>Sign out</button></div>}
      <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8"><div key={loc.pathname} className="anim-page"><Outlet /></div></main>
    </div>
  </div>;
}

export function RequireRole({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const { user, ready } = useAuth();
  const loc = useLocation();
  if (!ready) return <Loading label="Signing you in…" />;
  if (!user) return <Navigate to={`/login?next=${encodeURIComponent(loc.pathname + loc.search)}`} replace />;
  if (!roles.includes(user.role)) return <Navigate to={homeFor(user.role)} replace />;
  return <>{children}</>;
}

export const money = inr;
