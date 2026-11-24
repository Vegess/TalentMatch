import { useState, type FormEvent } from "react";
import { CURRENCIES, skillsFrom } from "../lib/format";
import { useAuth } from "../lib/auth";
import { Button, Card, Input, Select, Textarea } from "./ui";

export const CATEGORIES = ["Engineering", "Design & Frontend", "Data & AI", "ERP & Operations", "Finance", "Marketing", "Other"];

export function JobForm({ initial, onSubmit, submitLabel }: { initial?: any; onSubmit: (body: any) => Promise<void>; submitLabel: string }) {
  const { user } = useAuth();
  const [f, setF] = useState(() => ({
    currency: initial?.currency || user?.currency || "INR",
    title: initial?.title || "", category: initial?.category || "", description: initial?.description || "",
    responsibilities: initial?.responsibilities || "", requirements: initial?.requirements || "",
    required_skills: (initial?.required_skills || []).join(", "), min_experience_years: initial?.min_experience_years ?? 0,
    budget_type: initial?.budget_type || "fixed", budget_min: initial?.budget_min ?? "", budget_max: initial?.budget_max ?? "",
    location_type: initial?.location_type || "remote", location: initial?.location || "", deadline: initial?.deadline || "",
  }));
  const [busy, setBusy] = useState(false);
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.value });
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await onSubmit({
        ...f, category: f.category || null, required_skills: skillsFrom(f.required_skills),
        min_experience_years: Number(f.min_experience_years) || 0,
        budget_min: f.budget_min === "" ? null : Number(f.budget_min), budget_max: f.budget_max === "" ? null : Number(f.budget_max),
        location: f.location || null, deadline: f.deadline || null,
        responsibilities: f.responsibilities || null, requirements: f.requirements || null,
      });
    } finally { setBusy(false); }
  };
  return <form onSubmit={submit} className="space-y-6">
    <Card className="space-y-4 p-5">
      <h3 className="font-semibold">The role</h3>
      <div className="grid gap-4 sm:grid-cols-[2fr_1fr]">
        <Input label="Job title" required minLength={3} maxLength={200} value={f.title} onChange={set("title")} placeholder="e.g. Senior Python Backend Consultant" />
        <Select label="Category" value={f.category} onChange={set("category")}>
          <option value="">Choose…</option>{CATEGORIES.map((c) => <option key={c}>{c}</option>)}</Select>
      </div>
      <Textarea label="Overview" rows={4} value={f.description} onChange={set("description")} placeholder="What the project is and why it matters" />
      <div className="grid gap-4 sm:grid-cols-2">
        <Textarea label="Responsibilities" hint="One per line" rows={5} value={f.responsibilities} onChange={set("responsibilities")} />
        <Textarea label="Requirements & nice-to-haves" hint="One per line" rows={5} value={f.requirements} onChange={set("requirements")} />
      </div>
    </Card>
    <Card className="space-y-4 p-5">
      <h3 className="font-semibold">Matching</h3>
      <div className="grid gap-4 sm:grid-cols-[2fr_1fr]">
        <Input label="Required skills" value={f.required_skills} onChange={set("required_skills")} placeholder="Python, FastAPI, PostgreSQL"
          hint="Comma-separated. Freelancers are ranked by these (70%) and experience (30%)." />
        <Input label="Minimum experience (years)" type="number" min={0} max={70} step={0.5} value={f.min_experience_years} onChange={set("min_experience_years")} />
      </div>
    </Card>
    <Card className="space-y-4 p-5">
      <h3 className="font-semibold">Budget, location & timing</h3>
      <div className="grid gap-4 sm:grid-cols-4">
        <Select label="Budget type" value={f.budget_type} onChange={set("budget_type")}><option value="fixed">Fixed price</option><option value="hourly">Hourly</option></Select>
        <Select label="Currency" value={f.currency} onChange={set("currency")}>{CURRENCIES.map((c) => <option key={c}>{c}</option>)}</Select>
        <Input label={`Minimum (${f.currency}${f.budget_type === "hourly" ? "/hr" : ""})`} type="number" min={0} value={f.budget_min} onChange={set("budget_min")} />
        <Input label={`Maximum (${f.currency}${f.budget_type === "hourly" ? "/hr" : ""})`} type="number" min={0} value={f.budget_max} onChange={set("budget_max")} />
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        <Select label="Work mode" value={f.location_type} onChange={set("location_type")}><option value="remote">Remote</option><option value="hybrid">Hybrid</option><option value="onsite">On-site</option></Select>
        <Input label="City" value={f.location} onChange={set("location")} placeholder={f.location_type === "remote" ? "Optional" : "e.g. Bengaluru"} />
        <Input label="Apply by" type="date" value={f.deadline} onChange={set("deadline")} />
      </div>
    </Card>
    <div className="flex justify-end"><Button type="submit" loading={busy}>{submitLabel}</Button></div>
  </form>;
}

export function ServiceForm({ initial, onSubmit, onCancel }: { initial?: any; onSubmit: (b: any) => Promise<void>; onCancel: () => void }) {
  const { user } = useAuth();
  const [f, setF] = useState(() => ({
    currency: initial?.currency || user?.currency || "INR",
    title: initial?.title || "", category: initial?.category || "", description: initial?.description || "",
    deliverables: initial?.deliverables || "", price: initial?.price ?? "", delivery_days: initial?.delivery_days ?? 7,
    skills: (initial?.skills || []).join(", "), status: initial?.status || "active",
  }));
  const [busy, setBusy] = useState(false);
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.value });
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true);
    try { await onSubmit({ ...f, category: f.category || null, price: Number(f.price), delivery_days: Number(f.delivery_days), skills: skillsFrom(f.skills), deliverables: f.deliverables || null }); }
    finally { setBusy(false); }
  };
  return <form onSubmit={submit} className="space-y-4">
    <Input label="Title" required minLength={5} value={f.title} onChange={set("title")} placeholder="I will build…" />
    <div className="grid gap-4 sm:grid-cols-4">
      <Select label="Category" value={f.category} onChange={set("category")}><option value="">Choose…</option>{CATEGORIES.map((c) => <option key={c}>{c}</option>)}</Select>
      <Select label="Currency" value={f.currency} onChange={set("currency")}>{CURRENCIES.map((c) => <option key={c}>{c}</option>)}</Select>
      <Input label={`Price (${f.currency})`} type="number" required min={5} value={f.price} onChange={set("price")} />
      <Input label="Delivery (days)" type="number" required min={1} max={365} value={f.delivery_days} onChange={set("delivery_days")} />
    </div>
    <Textarea label="Description" rows={4} value={f.description} onChange={set("description")} />
    <Textarea label="What's included" hint="One deliverable per line" rows={3} value={f.deliverables} onChange={set("deliverables")} />
    <Input label="Skills" value={f.skills} onChange={set("skills")} placeholder="React, TypeScript" />
    <Select label="Status" value={f.status} onChange={set("status")}><option value="active">Active — visible to clients</option><option value="paused">Paused — hidden</option></Select>
    <div className="flex justify-end gap-2 pt-2"><Button type="button" variant="ghost" onClick={onCancel}>Cancel</Button><Button type="submit" loading={busy}>Save service</Button></div>
  </form>;
}
