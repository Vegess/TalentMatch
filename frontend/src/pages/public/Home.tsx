import { Link } from "react-router-dom";
import { useApi, useTitle } from "../../lib/hooks";
import { ButtonLink, Card } from "../../components/ui";
import { JobCard, ServiceCard } from "../../components/Cards";
import { PlanCards } from "./Pricing";
import { CountUp, Reveal } from "../../components/Motion";

function HeroGraphic() {
  // A job in the middle, freelancers around it; lines draw in and the best fits light up.
  const people = [
    { x: 60, y: 60, s: 96 }, { x: 70, y: 200, s: 88 }, { x: 330, y: 50, s: 74 }, { x: 345, y: 210, s: 61 }, { x: 205, y: 250, s: 42 },
  ];
  return <svg viewBox="0 0 400 290" className="h-auto w-full max-w-md" role="img" aria-label="Freelancers ranked against a job by match score">
    {people.map((p, i) => <line key={"l" + i} x1={200} y1={135} x2={p.x} y2={p.y} stroke={p.s >= 50 ? "#2563eb" : "#cbd5e1"}
      strokeWidth={p.s >= 85 ? 2.6 : 1.6} strokeDasharray={p.s >= 50 ? undefined : "4 4"} className="anim-draw"
      style={{ ["--len" as any]: 220, animationDelay: `${i * 120}ms` }} />)}
    <g className="anim-fade-up"><rect x="140" y="102" width="120" height="66" rx="12" fill="#fff" stroke="#2563eb" strokeWidth="2" />
      <text x="200" y="128" textAnchor="middle" fontSize="12" fontWeight="600" fill="#0f172a">Backend role</text>
      <text x="200" y="148" textAnchor="middle" fontSize="10" fill="#64748b">Python · SQL · 5 yrs</text></g>
    <circle cx={people[0].x} cy={people[0].y} r="24" fill="none" stroke="#2563eb" strokeWidth="2" className="anim-pulse-ring" />
    {people.map((p, i) => <g key={"p" + i} className="anim-fade-up" style={{ animationDelay: `${300 + i * 120}ms` }}>
      <circle cx={p.x} cy={p.y} r="24" fill={p.s >= 85 ? "#2563eb" : p.s >= 50 ? "#dbeafe" : "#f1f5f9"} stroke="#fff" strokeWidth="3" />
      <text x={p.x} y={p.y + 4} textAnchor="middle" fontSize="11" fontWeight="700" fill={p.s >= 85 ? "#fff" : "#1e3a8a"}>{p.s}%</text>
    </g>)}
  </svg>;
}

export default function Home() {
  useTitle("Hire freelancers ranked by fit");
  const jobs = useApi<any>("/api/v1/jobs?limit=3");
  const services = useApi<any>("/api/v1/services?limit=3");
  const talent = useApi<any>("/api/v1/freelancers?limit=1");
  const steps = [
    ["Post a job description", "Scope, responsibilities, skills, budget and attachments — PDFs, Drive or Notion links."],
    ["Get a ranked shortlist", "Every freelancer is scored on skills (70%) and experience (30%), with matched and missing skills shown."],
    ["Hire and pay safely", "Accept a proposal or buy a fixed-price service. Pay with Razorpay; the freelancer is paid out after you approve the work."],
  ];
  return <>
    <section className="relative overflow-hidden border-b border-slate-200 bg-gradient-to-b from-brand-50 to-white">
      <div aria-hidden className="anim-drift pointer-events-none absolute -left-24 -top-24 h-72 w-72 rounded-full bg-brand-200/40 blur-3xl" />
      <div aria-hidden className="anim-drift pointer-events-none absolute -bottom-24 right-0 h-80 w-80 rounded-full bg-violet-200/40 blur-3xl" style={{ animationDelay: "-7s" }} />
      <div className="relative mx-auto grid max-w-6xl items-center gap-10 px-4 py-16 md:grid-cols-2 md:py-24">
        <div className="anim-fade-up">
          <p className="mb-3 inline-block rounded-full bg-white px-3 py-1 text-xs font-medium text-brand-700 ring-1 ring-brand-200">Freelance marketplace for Indian teams</p>
          <h1 className="text-4xl font-bold leading-tight text-slate-900 md:text-5xl">Hire freelancers ranked by how well they fit the job.</h1>
          <p className="mt-4 text-lg text-slate-600">Post a job description and see a scored shortlist in seconds. Or buy a fixed-price service. Pay with UPI or card through Razorpay.</p>
          <div className="mt-8 flex flex-wrap gap-3">
            <ButtonLink to="/register?role=client">Hire talent</ButtonLink>
            <ButtonLink to="/register?role=freelancer" variant="secondary">Join as a freelancer</ButtonLink>
          </div>
          <p className="mt-6 text-sm text-slate-500">
            {talent.data ? <><b className="text-slate-800"><CountUp value={talent.data.total} /></b> freelancers · </> : null}
            {jobs.data ? <><b className="text-slate-800"><CountUp value={jobs.data.total} /></b> open jobs · </> : null}
            {services.data ? <><b className="text-slate-800"><CountUp value={services.data.total} /></b> services</> : null}
          </p>
        </div>
        <div className="anim-float flex justify-center"><HeroGraphic /></div>
      </div>
    </section>

    <section className="mx-auto max-w-6xl px-4 py-16">
      <h2 className="text-2xl font-semibold">How it works</h2>
      <div className="mt-6 grid gap-4 md:grid-cols-3">{steps.map(([t, d], i) => <Reveal key={t} delay={i * 90}><Card className="lift h-full p-6">
        <span className="grid h-8 w-8 place-items-center rounded-full bg-brand-600 text-sm font-semibold text-white">{i + 1}</span>
        <h3 className="mt-4 font-semibold">{t}</h3><p className="mt-1 text-sm text-slate-600">{d}</p></Card></Reveal>)}</div>
    </section>

    {!!jobs.data?.items?.length && <section className="mx-auto max-w-6xl px-4 pb-16">
      <div className="flex items-end justify-between"><h2 className="text-2xl font-semibold">Latest jobs</h2><Link className="text-sm font-medium text-brand-700" to="/jobs">All jobs →</Link></div>
      <div className="mt-6 grid gap-4 md:grid-cols-3">{jobs.data.items.map((j: any, i: number) => <Reveal key={j.id} delay={i * 80}><JobCard job={j} to={`/jobs/${j.id}`} /></Reveal>)}</div>
    </section>}

    {!!services.data?.items?.length && <section className="mx-auto max-w-6xl px-4 pb-16">
      <div className="flex items-end justify-between"><h2 className="text-2xl font-semibold">Fixed-price services</h2><Link className="text-sm font-medium text-brand-700" to="/services">All services →</Link></div>
      <div className="mt-6 grid gap-4 md:grid-cols-3">{services.data.items.map((s: any, i: number) => <Reveal key={s.id} delay={i * 80}><ServiceCard s={s} /></Reveal>)}</div>
    </section>}

    <section className="border-t border-slate-200 bg-white"><div className="mx-auto max-w-6xl px-4 py-16">
      <h2 className="text-2xl font-semibold">Plans for hiring teams</h2>
      <p className="mt-1 text-slate-600">Freelancers join free. Clients pick a plan.</p>
      <Reveal className="mt-6"><PlanCards /></Reveal>
    </div></section>
  </>;
}
