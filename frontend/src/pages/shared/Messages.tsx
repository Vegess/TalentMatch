import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../../lib/api";
import { useApi, useTitle } from "../../lib/hooks";
import { ago } from "../../lib/format";
import { useLiveReload } from "../../lib/realtime";
import { useToast } from "../../components/Toast";
import { Avatar, Button, Card, Empty, ErrorBox, Loading, PageHeader, cx } from "../../components/ui";

function Inbox({ activeId }: { activeId?: number }) {
  const { data, error, loading, reload } = useApi<any[]>("/api/v1/conversations");
  useLiveReload(["message"], reload);
  if (loading && !data) return <Loading />;
  if (error) return <div className="p-4"><ErrorBox message={error} /></div>;
  if (!data!.length) return <Empty title="No conversations yet" icon="✉">Message a freelancer from their profile or a proposal — or reply when a client writes to you.</Empty>;
  return <ul className="divide-y divide-slate-100">{data!.map((c) => <li key={c.id}>
    <Link to={`/messages/${c.id}`} className={cx("flex gap-3 px-4 py-3 transition hover:bg-slate-50", activeId === c.id && "bg-brand-50/60")}>
      <Avatar name={c.other.name} size={38} />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-2"><p className={cx("truncate text-sm", c.unread ? "font-semibold" : "font-medium")}>{c.other.name}</p>
          <span className="shrink-0 text-[11px] text-slate-400">{ago(c.last_message_at)}</span></div>
        {c.job && <p className="truncate text-[11px] text-brand-700">{c.job.title}</p>}
        <p className={cx("truncate text-xs", c.unread ? "text-slate-800" : "text-slate-500")}>{c.last_message ? `${c.last_message.mine ? "You: " : ""}${c.last_message.body}` : "No messages yet"}</p>
      </div>
      {c.unread > 0 && <span className="mt-1 grid h-5 min-w-5 place-items-center self-start rounded-full bg-brand-600 px-1.5 text-[11px] font-semibold text-white">{c.unread}</span>}
    </Link></li>)}</ul>;
}

function Thread({ id }: { id: number }) {
  const toast = useToast();
  const [conv, setConv] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [body, setBody] = useState("");
  const [sending, setSending] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const load = useCallback(async () => {
    try { setConv(await api(`/api/v1/conversations/${id}`)); setError(null); } catch (e: any) { setError(e.message); }
  }, [id]);
  useEffect(() => { setConv(null); load(); }, [load]);
  useEffect(() => {
    const h = (e: Event) => { const d = (e as CustomEvent).detail; if (d?.type === "message" && d.conversation_id === id) load(); };
    window.addEventListener("tm:event", h);
    return () => window.removeEventListener("tm:event", h);
  }, [id, load]);
  useEffect(() => { endRef.current?.scrollIntoView({ block: "end" }); }, [conv?.messages?.length]);
  const send = async (e: FormEvent) => {
    e.preventDefault();
    const text = body.trim();
    if (!text) return;
    setSending(true);
    try {
      const m = await api(`/api/v1/conversations/${id}/messages`, { json: { body: text } });
      setConv((c: any) => ({ ...c, messages: [...c.messages, m] })); setBody("");
    } catch (err: any) { toast(err.message, "error"); } finally { setSending(false); }
  };
  if (error) return <div className="p-4"><ErrorBox message={error} /></div>;
  if (!conv) return <Loading />;
  const otherLink = conv.other.type === "freelancer" ? `/freelancers/${conv.other.id}` : null;
  let lastDay = "";
  return <div className="flex h-full min-h-[60vh] flex-col">
    <div className="flex items-center gap-3 border-b border-slate-100 px-5 py-3">
      <Avatar name={conv.other.name} size={36} />
      <div className="min-w-0"><p className="font-semibold">{otherLink ? <Link className="hover:text-brand-700" to={otherLink}>{conv.other.name}</Link> : conv.other.name}</p>
        <p className="truncate text-xs text-slate-500">{conv.other.subtitle}{conv.job ? ` · re: ${conv.job.title}` : ""}</p></div>
    </div>
    <div className="flex-1 space-y-2 overflow-y-auto bg-slate-50/60 px-4 py-4" aria-live="polite" translate="no">
      {!conv.messages.length && <p className="py-10 text-center text-sm text-slate-500">Say hello 👋</p>}
      {conv.messages.map((m: any) => {
        const day = new Date(m.created_at + "Z").toDateString();
        const sep = day !== lastDay; lastDay = day;
        return <div key={m.id}>
          {sep && <p className="my-3 text-center text-[11px] uppercase tracking-wide text-slate-400">{new Date(m.created_at + "Z").toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" })}</p>}
          <div className={cx("flex", m.mine ? "justify-end" : "justify-start")}>
            <div className={cx("anim-pop max-w-[78%] whitespace-pre-wrap break-words rounded-2xl px-3.5 py-2 text-sm shadow-sm",
              m.mine ? "rounded-br-md bg-brand-600 text-white" : "rounded-bl-md bg-white text-slate-800 ring-1 ring-slate-200")}>
              {m.body}<span className={cx("ml-2 align-bottom text-[10px]", m.mine ? "text-brand-100" : "text-slate-400")}>
                {new Date(m.created_at + "Z").toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}</span></div>
          </div></div>;
      })}
      <div ref={endRef} />
    </div>
    <form onSubmit={send} className="flex items-end gap-2 border-t border-slate-100 p-3">
      <textarea aria-label="Message" rows={1} value={body} onChange={(e) => setBody(e.target.value)} maxLength={4000}
        onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); (e.currentTarget.form as HTMLFormElement).requestSubmit(); } }}
        placeholder="Write a message… (Enter to send, Shift+Enter for a new line)"
        className="max-h-40 min-h-[42px] flex-1 resize-y rounded-xl border border-slate-300 px-3 py-2.5 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100" />
      <Button type="submit" loading={sending} disabled={!body.trim()}>Send</Button>
    </form>
  </div>;
}

export default function Messages() {
  const { id } = useParams();
  const active = id ? Number(id) : undefined;
  useTitle("Messages");
  return <>
    <PageHeader title="Messages" subtitle="Private conversations between companies and freelancers." />
    <Card className="grid overflow-hidden md:grid-cols-[300px_1fr]">
      <div className={cx("max-h-[70vh] overflow-y-auto border-slate-100 md:border-r", !!active && "hidden md:block")}><Inbox activeId={active} /></div>
      <div className={cx(!active && "hidden md:block")}>
        {active ? <><Link to="/messages" className="block border-b border-slate-100 px-4 py-2 text-sm text-brand-700 md:hidden">← All conversations</Link><Thread id={active} /></>
          : <Empty title="Pick a conversation" icon="✉" />}
      </div>
    </Card>
  </>;
}

/** "Message" button used on profiles, proposals, matches and orders. */
export function MessageButton({ consultantId, clientId, jobId, label = "Message", size = "sm", variant = "secondary" }:
  { consultantId?: number; clientId?: number; jobId?: number; label?: string; size?: "sm" | "md"; variant?: "primary" | "secondary" | "ghost" }) {
  const nav = useNavigate();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  return <Button size={size} variant={variant} loading={busy} onClick={async () => {
    setBusy(true);
    try {
      const c = await api("/api/v1/conversations", { json: { consultant_id: consultantId, client_id: clientId, job_id: jobId } });
      nav(`/messages/${c.id}`);
    } catch (e: any) { toast(e.message, "error"); } finally { setBusy(false); }
  }}>✉ {label}</Button>;
}
