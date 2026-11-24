import { countryName, flag, localTime } from "../lib/format";
import { cx } from "./ui";

export function Stars({ value, size = 14, className }: { value?: number | null; size?: number; className?: string }) {
  const v = Math.max(0, Math.min(5, value || 0));
  return <span className={cx("inline-flex", className)} aria-label={`${v.toFixed(1)} out of 5`} role="img">
    {[0, 1, 2, 3, 4].map((i) => {
      const fill = Math.max(0, Math.min(1, v - i));
      return <svg key={i} width={size} height={size} viewBox="0 0 20 20" aria-hidden>
        <defs><linearGradient id={`s${i}-${fill}`}><stop offset={fill} stopColor="#f59e0b" /><stop offset={fill} stopColor="#e2e8f0" /></linearGradient></defs>
        <path fill={`url(#s${i}-${fill})`} d="M10 1.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8L10 14.9l-5.2 2.7 1-5.8L1.5 7.7l5.9-.9z" />
      </svg>;
    })}
  </span>;
}

export function Rating({ avg, count, compact }: { avg?: number | null; count?: number; compact?: boolean }) {
  if (!count) return <span className="text-xs text-slate-400">No reviews yet</span>;
  return <span className="inline-flex items-center gap-1.5 text-sm">
    <Stars value={avg} />{!compact && <b className="text-slate-800">{(avg || 0).toFixed(1)}</b>}
    <span className="text-slate-500">({count})</span>
  </span>;
}

const BADGE: Record<string, { label: string; cls: string; icon: string; title: string }> = {
  verified: { label: "Verified", icon: "✓", cls: "bg-brand-50 text-brand-700 ring-brand-200", title: "Identity checked by the TalentMatch team" },
  payouts_verified: { label: "Payouts set up", icon: "₹", cls: "bg-emerald-50 text-emerald-700 ring-emerald-200", title: "Bank / UPI verified for payouts" },
  top_rated: { label: "Top rated", icon: "★", cls: "bg-amber-50 text-amber-800 ring-amber-200", title: "4.5+ average from at least 3 reviews" },
};

export function Badges({ badges, small }: { badges?: string[]; small?: boolean }) {
  if (!badges?.length) return null;
  return <span className="inline-flex flex-wrap gap-1">{badges.filter((b) => BADGE[b]).map((b) =>
    <span key={b} title={BADGE[b].title} className={cx("inline-flex items-center gap-1 rounded-full font-medium ring-1 ring-inset", BADGE[b].cls,
      small ? "px-1.5 py-0 text-[10px]" : "px-2 py-0.5 text-xs")}><span aria-hidden>{BADGE[b].icon}</span>{BADGE[b].label}</span>)}</span>;
}

export function Place({ country, timezone, city, showTime }: { country?: string | null; timezone?: string | null; city?: string | null; showTime?: boolean }) {
  const lt = showTime ? localTime(timezone) : null;
  const name = [city, countryName(country)].filter(Boolean).join(", ");
  if (!name && !lt) return null;
  return <span className="inline-flex flex-wrap items-center gap-x-1.5 text-slate-500">
    {country && <span aria-hidden>{flag(country)}</span>}{name}
    {lt && <span className="whitespace-nowrap">· {lt.time} local ({lt.diff})</span>}
  </span>;
}
