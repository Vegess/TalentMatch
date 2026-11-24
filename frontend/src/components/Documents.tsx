import { useRef, useState } from "react";
import { api, openDocument } from "../lib/api";
import { useApi } from "../lib/hooks";
import { bytes, date } from "../lib/format";
import { useToast } from "./Toast";
import { Button, Card, CardHeader, Empty, ErrorBox, Input, Loading, Modal } from "./ui";

type Props = { ownerType: "job" | "consultant" | "service" | "order"; ownerId: number; canEdit: boolean;
  title?: string; subtitle?: string };

/** Files (stored by the platform) and links (Drive, Notion, Figma, GitHub…) attached to something. */
export function Documents({ ownerType, ownerId, canEdit, title = "Documents & links", subtitle }: Props) {
  const toast = useToast();
  const { data, error, loading, reload } = useApi<any[]>(`/api/v1/documents?owner_type=${ownerType}&owner_id=${ownerId}`);
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [linkOpen, setLinkOpen] = useState(false);
  const [link, setLink] = useState({ title: "", url: "" });
  const [saving, setSaving] = useState(false);

  const upload = async (f: File) => {
    const form = new FormData();
    form.append("owner_type", ownerType); form.append("owner_id", String(ownerId));
    form.append("title", f.name.replace(/\.[^.]+$/, "")); form.append("file", f);
    setUploading(true);
    try { await api("/api/v1/documents/upload", { form }); toast(`Uploaded ${f.name}`, "success"); reload(); }
    catch (e: any) { toast(e.message, "error"); }
    finally { setUploading(false); if (fileRef.current) fileRef.current.value = ""; }
  };
  const addLink = async () => {
    setSaving(true);
    try {
      await api("/api/v1/documents/link", { json: { owner_type: ownerType, owner_id: ownerId, ...link } });
      setLinkOpen(false); setLink({ title: "", url: "" }); toast("Link added", "success"); reload();
    } catch (e: any) { toast(e.message, "error"); } finally { setSaving(false); }
  };
  const remove = async (id: number) => {
    try { await api(`/api/v1/documents/${id}`, { method: "DELETE" }); reload(); } catch (e: any) { toast(e.message, "error"); }
  };

  return <Card>
    <CardHeader title={title} subtitle={subtitle} action={canEdit && <div className="flex gap-2">
      <input ref={fileRef} type="file" className="hidden" accept=".pdf,.doc,.docx,.txt,.md,.png,.jpg,.jpeg"
        onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
      <Button size="sm" variant="secondary" onClick={() => setLinkOpen(true)}>Add link</Button>
      <Button size="sm" onClick={() => fileRef.current?.click()} loading={uploading}>Upload file</Button>
    </div>} />
    {loading ? <Loading /> : error ? <div className="p-4"><ErrorBox message={error} onRetry={reload} /></div> :
      !data?.length ? <Empty title="Nothing attached yet" icon="📎">{canEdit ? "Upload a PDF or Word file (max 10 MB), or link to Google Drive, Notion, Figma or GitHub." : "No documents have been shared."}</Empty> :
        <ul className="divide-y divide-slate-100">{data.map((d) => <li key={d.id} className="flex items-center gap-3 px-5 py-3">
          <span className="grid h-9 w-9 place-items-center rounded-lg bg-slate-100 text-xs font-semibold text-slate-600">
            {d.kind === "url" ? "🔗" : (d.filename?.split(".").pop() || "file").toUpperCase().slice(0, 4)}</span>
          <div className="min-w-0 flex-1">
            {d.kind === "url"
              ? <a href={d.url} target="_blank" rel="noopener noreferrer nofollow" className="block truncate text-sm font-medium text-brand-700 hover:underline">{d.title}</a>
              : <button className="block truncate text-left text-sm font-medium text-brand-700 hover:underline" onClick={() => openDocument(d.download_url, d.filename).catch((e) => toast(e.message, "error"))}>{d.title}</button>}
            <p className="truncate text-xs text-slate-500">{d.kind === "url" ? new URL(d.url).hostname : `${d.filename} · ${bytes(d.size_bytes)}`} · {date(d.created_at)}</p>
          </div>
          {canEdit && <button onClick={() => remove(d.id)} className="rounded px-2 py-1 text-xs text-slate-400 hover:bg-red-50 hover:text-red-600">Remove</button>}
        </li>)}</ul>}
    <Modal open={linkOpen} onClose={() => setLinkOpen(false)} title="Add a link"
      footer={<><Button variant="ghost" onClick={() => setLinkOpen(false)}>Cancel</Button>
        <Button onClick={addLink} loading={saving} disabled={!link.title || !link.url}>Add link</Button></>}>
      <Input label="Title" value={link.title} onChange={(e) => setLink({ ...link, title: e.target.value })} placeholder="e.g. Full JD on Google Drive" />
      <Input label="URL" type="url" value={link.url} onChange={(e) => setLink({ ...link, url: e.target.value })} placeholder="https://…" hint="Must start with https:// or http://" />
    </Modal>
  </Card>;
}
