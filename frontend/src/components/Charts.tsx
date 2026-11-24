/* Hand-built SVG charts (no chart library). Animated draw-in, disabled for reduced-motion users. */
import { useId, useState } from "react";
import { compactInr } from "../lib/format";

export function AreaChart({ data, valueKey, format = (v) => String(v), height = 180 }:
  { data: any[]; valueKey: string; format?: (v: number) => string; height?: number }) {
  const id = useId().replace(/:/g, "");
  const [hover, setHover] = useState<number | null>(null);
  const W = 640, H = height, P = 28, L = 52;
  const vals = data.map((d) => Number(d[valueKey]) || 0);
  const max = Math.max(1, ...vals);
  const x = (i: number) => L + (i * (W - L - P)) / Math.max(1, data.length - 1);
  const y = (v: number) => H - P - (v / max) * (H - P * 2);
  const line = vals.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const area = `${line} L${x(vals.length - 1)},${H - P} L${x(0)},${H - P} Z`;
  return <div className="relative">
    <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label={`${valueKey} over time`}
      onMouseLeave={() => setHover(null)}
      onMouseMove={(e) => {
        const r = (e.currentTarget as SVGElement).getBoundingClientRect();
        const rel = ((e.clientX - r.left) / r.width) * W;
        setHover(Math.max(0, Math.min(data.length - 1, Math.round(((rel - L) / (W - L - P)) * (data.length - 1)))));
      }}>
      <defs><linearGradient id={`g${id}`} x1="0" x2="0" y1="0" y2="1">
        <stop offset="0" stopColor="#2563eb" stopOpacity=".25" /><stop offset="1" stopColor="#2563eb" stopOpacity="0" /></linearGradient></defs>
      {[0, 0.5, 1].map((t) => <g key={t}>
        <line x1={L} x2={W - P} y1={y(max * t)} y2={y(max * t)} stroke="#e2e8f0" strokeDasharray="3 4" />
        <text x={L - 6} y={y(max * t) + 4} textAnchor="end" fontSize="10" fill="#94a3b8">{format(Math.round(max * t))}</text></g>)}
      <path d={area} fill={`url(#g${id})`} className="anim-fade-up" />
      <path d={line} fill="none" stroke="#2563eb" strokeWidth="2.2" strokeLinejoin="round" className="anim-draw" style={{ ["--len" as any]: 2000 }} />
      {hover != null && <g><line x1={x(hover)} x2={x(hover)} y1={P} y2={H - P} stroke="#94a3b8" />
        <circle cx={x(hover)} cy={y(vals[hover])} r="4" fill="#2563eb" stroke="#fff" strokeWidth="2" /></g>}
      {data.length > 1 && [0, data.length - 1].map((i) => <text key={i} x={x(i)} y={H - 8} fontSize="10" fill="#94a3b8" textAnchor={i ? "end" : "start"}>{String(data[i].date).slice(5)}</text>)}
    </svg>
    {hover != null && <div className="pointer-events-none absolute top-1 rounded-md bg-slate-900 px-2 py-1 text-xs text-white"
      style={{ left: `${(x(hover) / W) * 100}%`, transform: "translateX(-50%)" }}>{data[hover].date}: <b>{format(vals[hover])}</b></div>}
  </div>;
}

export function BarList({ items, total }: { items: { label: string; value: number; tone?: string }[]; total?: number }) {
  const max = total ?? Math.max(1, ...items.map((i) => i.value));
  return <ul className="space-y-3">{items.map((i, idx) => <li key={i.label}>
    <div className="mb-1 flex justify-between text-sm"><span className="text-slate-600">{i.label}</span><span className="font-medium tabular-nums">{i.value}</span></div>
    <div className="h-2 overflow-hidden rounded-full bg-slate-100">
      <div className="h-full rounded-full anim-fade-up" style={{ width: `${(i.value / (max || 1)) * 100}%`, background: i.tone || "#2563eb", animationDelay: `${idx * 60}ms` }} /></div>
  </li>)}</ul>;
}

export const moneyAxis = (v: number) => (v ? compactInr(v) : "₹0");
