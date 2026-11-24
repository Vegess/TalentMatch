import { useState } from "react";
import { useApi, useDebounced, useTitle } from "../../lib/hooks";
import { Empty, ErrorBox, Input, Select } from "../../components/ui";
import { CardSkeletons, Reveal } from "../../components/Motion";
import { COUNTRY_CODES, countryName, flag } from "../../lib/format";
import { FreelancerCard, JobCard, ServiceCard } from "../../components/Cards";

function Toolbar({ children }: { children: React.ReactNode }) {
  return <div className="mb-6 grid gap-3 sm:grid-cols-[2fr_1fr_1fr]">{children}</div>;
}

function useCategories() { return useApi<string[]>("/api/v1/services/categories").data || []; }

export function Freelancers() {
  useTitle("Find talent");
  const [q, setQ] = useState(""); const [skill, setSkill] = useState(""); const [avail, setAvail] = useState("");
  const [country, setCountry] = useState(""); const [region, setRegion] = useState(""); const [lang, setLang] = useState("");
  const [sort, setSort] = useState("experience"); const [verified, setVerified] = useState(false);
  const dq = useDebounced(q), ds = useDebounced(skill), dl = useDebounced(lang);
  const qs = new URLSearchParams({ limit: "60", sort, ...(dq && { q: dq }), ...(ds && { skill: ds }), ...(avail && { available: avail }),
    ...(country && { country }), ...(region && { region }), ...(dl && { language: dl }), ...(verified && { verified: "true" }) });
  const { data, error, loading, reload } = useApi<any>(`/api/v1/freelancers?${qs}`);
  return <div className="mx-auto max-w-6xl px-4 py-10">
    <h1 className="text-3xl font-bold">Find talent</h1><p className="mt-1 text-slate-600">Browse freelancer profiles. Post a job to get them ranked for you.</p>
    <div className="mt-6"><Toolbar>
      <Input aria-label="Search" placeholder="Search name, headline, city…" value={q} onChange={(e) => setQ(e.target.value)} />
      <Input aria-label="Skill" placeholder="Skill, e.g. React" value={skill} onChange={(e) => setSkill(e.target.value)} />
      <Select aria-label="Availability" value={avail} onChange={(e) => setAvail(e.target.value)}><option value="">Any availability</option><option value="true">Available now</option><option value="false">Busy</option></Select>
    </Toolbar>
    <div className="-mt-3 mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
      <Select aria-label="Region" value={region} onChange={(e) => setRegion(e.target.value)}><option value="">Any region</option>
        <option value="asia">Asia</option><option value="europe">Europe</option><option value="americas">Americas</option><option value="africa">Africa</option><option value="oceania">Oceania</option></Select>
      <Select aria-label="Country" value={country} onChange={(e) => setCountry(e.target.value)}><option value="">Any country</option>
        {COUNTRY_CODES.map((c) => <option key={c} value={c}>{flag(c)} {countryName(c)}</option>)}</Select>
      <Input aria-label="Language" placeholder="Language, e.g. Spanish" value={lang} onChange={(e) => setLang(e.target.value)} />
      <Select aria-label="Sort" value={sort} onChange={(e) => setSort(e.target.value)}><option value="experience">Most experienced</option><option value="rating">Highest rated</option>
        <option value="rate_low">Lowest rate</option><option value="newest">Newest</option></Select>
      <label className="flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 text-sm"><input type="checkbox" checked={verified} onChange={(e) => setVerified(e.target.checked)} /> Verified only</label>
    </div></div>
    {error ? <ErrorBox message={error} onRetry={reload} /> : loading && !data ? <CardSkeletons /> : !data.items.length ? <Empty title="No freelancers match">Try a different skill or clear the filters.</Empty> :
      <><p className="mb-3 text-sm text-slate-500">{data.total} freelancer{data.total === 1 ? "" : "s"}</p>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{data.items.map((f: any, i: number) => <Reveal key={f.id} delay={Math.min(i, 8) * 50}><FreelancerCard f={f} /></Reveal>)}</div></>}
  </div>;
}

export function Services() {
  useTitle("Services");
  const cats = useCategories();
  const [q, setQ] = useState(""); const [cat, setCat] = useState(""); const [max, setMax] = useState("");
  const dq = useDebounced(q);
  const qs = new URLSearchParams({ limit: "60", ...(dq && { q: dq }), ...(cat && { category: cat }), ...(max && { max_price: max }) });
  const { data, error, loading, reload } = useApi<any>(`/api/v1/services?${qs}`);
  return <div className="mx-auto max-w-6xl px-4 py-10">
    <h1 className="text-3xl font-bold">Services</h1><p className="mt-1 text-slate-600">Fixed scope, fixed price, clear delivery time.</p>
    <div className="mt-6"><Toolbar>
      <Input aria-label="Search" placeholder="Search services…" value={q} onChange={(e) => setQ(e.target.value)} />
      <Select aria-label="Category" value={cat} onChange={(e) => setCat(e.target.value)}><option value="">All categories</option>{cats.map((c) => <option key={c}>{c}</option>)}</Select>
      <Select aria-label="Max price" value={max} onChange={(e) => setMax(e.target.value)}><option value="">Any price</option><option value="10000">Up to ₹10,000</option><option value="30000">Up to ₹30,000</option><option value="60000">Up to ₹60,000</option></Select>
    </Toolbar></div>
    {error ? <ErrorBox message={error} onRetry={reload} /> : loading && !data ? <CardSkeletons /> : !data.items.length ? <Empty title="No services found" /> :
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{data.items.map((s: any, i: number) => <Reveal key={s.id} delay={Math.min(i, 8) * 50}><ServiceCard s={s} /></Reveal>)}</div>}
  </div>;
}

export function Jobs() {
  useTitle("Jobs");
  const cats = useCategories();
  const [q, setQ] = useState(""); const [cat, setCat] = useState(""); const [mode, setMode] = useState("");
  const dq = useDebounced(q);
  const qs = new URLSearchParams({ limit: "60", ...(dq && { q: dq }), ...(cat && { category: cat }), ...(mode && { location_type: mode }) });
  const { data, error, loading, reload } = useApi<any>(`/api/v1/jobs?${qs}`);
  return <div className="mx-auto max-w-6xl px-4 py-10">
    <h1 className="text-3xl font-bold">Open jobs</h1><p className="mt-1 text-slate-600">Sign in as a freelancer to see your match score and apply.</p>
    <div className="mt-6"><Toolbar>
      <Input aria-label="Search" placeholder="Search jobs…" value={q} onChange={(e) => setQ(e.target.value)} />
      <Select aria-label="Category" value={cat} onChange={(e) => setCat(e.target.value)}><option value="">All categories</option>{cats.map((c) => <option key={c}>{c}</option>)}</Select>
      <Select aria-label="Work mode" value={mode} onChange={(e) => setMode(e.target.value)}><option value="">Any work mode</option><option value="remote">Remote</option><option value="hybrid">Hybrid</option><option value="onsite">On-site</option></Select>
    </Toolbar></div>
    {error ? <ErrorBox message={error} onRetry={reload} /> : loading && !data ? <CardSkeletons cols="md:grid-cols-2" /> : !data.items.length ? <Empty title="No open jobs match" /> :
      <div className="grid gap-4 md:grid-cols-2">{data.items.map((j: any, i: number) => <Reveal key={j.id} delay={Math.min(i, 8) * 50}><JobCard job={j} to={`/jobs/${j.id}`} /></Reveal>)}</div>}
  </div>;
}
