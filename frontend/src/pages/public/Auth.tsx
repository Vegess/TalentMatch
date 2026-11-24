import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { homeFor, useAuth } from "../../lib/auth";
import { useTitle } from "../../lib/hooks";
import { Button, Card, ErrorBox, Input, Notice, cx } from "../../components/ui";
import { api } from "../../lib/api";
import { browserCountry, browserTimezone } from "../../lib/format";
import { Logo } from "../../components/Layout";

function Shell({ title, children, footer }: { title: string; children: React.ReactNode; footer: React.ReactNode }) {
  return <div className="flex min-h-screen flex-col items-center justify-center bg-gradient-to-b from-brand-50 to-slate-50 px-4 py-10">
    <div className="mb-6"><Logo /></div>
    <Card className="anim-fade-up w-full max-w-md p-6 sm:p-8"><h1 className="mb-6 text-xl font-semibold">{title}</h1>{children}</Card>
    <p className="mt-6 text-sm text-slate-600">{footer}</p>
  </div>;
}

export function Login() {
  useTitle("Sign in");
  const { login } = useAuth();
  const nav = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setError(null);
    try {
      const u = await login(email, password);
      const next = params.get("next");
      nav(next && next.startsWith("/") && !next.startsWith("//") ? next : homeFor(u.role), { replace: true });
    } catch (err: any) { setError(err.message); } finally { setBusy(false); }
  };
  return <Shell title="Sign in to TalentMatch" footer={<>New here? <Link className="font-medium text-brand-700" to="/register">Create an account</Link></>}>
    <form onSubmit={submit} className="space-y-4">
      {error && <ErrorBox message={error} />}
      <Input label="Email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
      <Input label="Password" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
      <div className="-mt-2 text-right"><Link to="/forgot-password" className="text-xs font-medium text-brand-700 hover:underline">Forgot password?</Link></div>
      <Button type="submit" className="w-full" loading={busy}>Sign in</Button>
    </form>
  </Shell>;
}

export function Register() {
  useTitle("Create account");
  const { register } = useAuth();
  const nav = useNavigate();
  const [params] = useSearchParams();
  const [role, setRole] = useState<"client" | "freelancer">(params.get("role") === "freelancer" ? "freelancer" : "client");
  const [f, setF] = useState({ name: "", email: "", password: "", company_name: "", headline: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.value });
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setError(null);
    try {
      const u = await register({ role, name: f.name, email: f.email, password: f.password,
        company_name: role === "client" ? f.company_name : null, headline: role === "freelancer" ? f.headline : null,
        country: browserCountry() || null, timezone: browserTimezone() || null,
        language: (() => { try { return localStorage.getItem("tm_lang") || null; } catch { return null; } })() });
      nav(u.role === "freelancer" ? "/freelancer/profile?welcome=1" : "/client?welcome=1", { replace: true });
    } catch (err: any) { setError(err.message); } finally { setBusy(false); }
  };
  return <Shell title="Create your account" footer={<>Already have an account? <Link className="font-medium text-brand-700" to="/login">Sign in</Link></>}>
    <div className="mb-5 grid grid-cols-2 gap-2 rounded-lg bg-slate-100 p-1" role="radiogroup">
      {(["client", "freelancer"] as const).map((r) => <button key={r} type="button" role="radio" aria-checked={role === r} onClick={() => setRole(r)}
        className={cx("rounded-md py-2 text-sm font-medium transition", role === r ? "bg-white text-slate-900 shadow-sm" : "text-slate-500")}>
        {r === "client" ? "I want to hire" : "I'm a freelancer"}</button>)}
    </div>
    <form onSubmit={submit} className="space-y-4">
      {error && <ErrorBox message={error} />}
      <Input label="Your name" required autoComplete="name" value={f.name} onChange={set("name")} />
      {role === "client"
        ? <Input label="Company name" value={f.company_name} onChange={set("company_name")} placeholder="Optional" />
        : <Input label="Headline" value={f.headline} onChange={set("headline")} placeholder="e.g. React developer, 5 years" />}
      <Input label="Work email" type="email" required autoComplete="email" value={f.email} onChange={set("email")} />
      <Input label="Password" type="password" required minLength={8} autoComplete="new-password" value={f.password} onChange={set("password")}
        hint="At least 8 characters, mixing letters with numbers or symbols." />
      <Button type="submit" className="w-full" loading={busy}>{role === "client" ? "Create company account" : "Create freelancer account"}</Button>
      {role === "client" && <p className="text-center text-xs text-slate-500">You start on the Free plan. Upgrade any time.</p>}
    </form>
  </Shell>;
}


export function ForgotPassword() {
  useTitle("Reset password");
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setError(null);
    try { const r = await api("/api/v1/auth/forgot-password", { json: { email } }); setSent(r.message); }
    catch (err: any) { setError(err.message); } finally { setBusy(false); }
  };
  return <Shell title="Reset your password" footer={<Link className="font-medium text-brand-700" to="/login">Back to sign in</Link>}>
    {sent ? <Notice tone="green">{sent} The link works once and expires in 30 minutes.</Notice> :
      <form onSubmit={submit} className="space-y-4">
        {error && <ErrorBox message={error} />}
        <p className="text-sm text-slate-600">Enter your account email and we'll send you a link to choose a new password.</p>
        <Input label="Email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        <Button type="submit" className="w-full" loading={busy}>Send reset link</Button>
      </form>}
  </Shell>;
}

export function ResetPassword() {
  useTitle("Choose a new password");
  const { setSession } = useAuth();
  const nav = useNavigate();
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const [pw, setPw] = useState(""); const [pw2, setPw2] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (pw !== pw2) { setError("The passwords don't match."); return; }
    setBusy(true); setError(null);
    try {
      const d = await api("/api/v1/auth/reset-password", { json: { token, new_password: pw } });
      setSession(d); nav(homeFor(d.user.role), { replace: true });
    } catch (err: any) { setError(err.message); } finally { setBusy(false); }
  };
  return <Shell title="Choose a new password" footer={<Link className="font-medium text-brand-700" to="/forgot-password">Need a new link?</Link>}>
    <form onSubmit={submit} className="space-y-4">
      {!token && <ErrorBox message="This link is missing its token. Open the link from your email again." />}
      {error && <ErrorBox message={error} />}
      <Input label="New password" type="password" autoComplete="new-password" required minLength={8} value={pw} onChange={(e) => setPw(e.target.value)}
        hint="At least 8 characters, letters plus numbers or symbols. You'll be signed out of other devices." />
      <Input label="Confirm new password" type="password" autoComplete="new-password" required value={pw2} onChange={(e) => setPw2(e.target.value)} />
      <Button type="submit" className="w-full" loading={busy} disabled={!token}>Set password & sign in</Button>
    </form>
  </Shell>;
}
