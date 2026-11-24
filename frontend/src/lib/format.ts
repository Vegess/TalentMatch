export const inr = (n?: number | null, opts: { decimals?: boolean } = {}) =>
  n == null ? "—" : "₹" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: opts.decimals ? 2 : 0 });

export const SYMBOL: Record<string, string> = { INR: "₹", USD: "$", EUR: "€", GBP: "£" };
export const CURRENCIES = ["INR", "USD", "EUR", "GBP"] as const;

/** Money in any supported currency. INR uses the Indian grouping (1,50,000); others the international one. */
export function money(n?: number | null, currency: string = "INR", opts: { decimals?: boolean } = {}) {
  if (n == null) return "—";
  if (currency === "INR") return inr(n, opts);
  const frac = opts.decimals || !Number.isInteger(n) ? 2 : 0;
  return (SYMBOL[currency] || currency + " ") + Number(n).toLocaleString("en-US", { minimumFractionDigits: frac, maximumFractionDigits: 2 });
}

export const compactInr = (n: number) =>
  n >= 1e7 ? `₹${(n / 1e7).toFixed(1)}Cr` : n >= 1e5 ? `₹${(n / 1e5).toFixed(1)}L` : n >= 1e3 ? `₹${(n / 1e3).toFixed(0)}k` : `₹${n}`;

export function compactMoney(n: number, currency: string = "INR") {
  if (currency === "INR") return compactInr(n);
  const sym = SYMBOL[currency] || "";
  return n >= 1e6 ? `${sym}${(n / 1e6).toFixed(1)}M` : n >= 1e4 ? `${sym}${(n / 1e3).toFixed(0)}k` : `${sym}${n.toLocaleString("en-US")}`;
}

const asDate = (v: string | Date) => (v instanceof Date ? v : new Date(/[zZ]|[+-]\d\d:\d\d$/.test(v) || v.length <= 10 ? v : v + "Z"));

export const date = (v?: string | null) =>
  v ? asDate(v).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : "—";

export function ago(v?: string | null): string {
  if (!v) return "";
  const s = (Date.now() - asDate(v).getTime()) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  if (s < 86400 * 30) return `${Math.floor(s / 86400)} d ago`;
  return date(v);
}

export function budget(j: { budget_type: string; budget_min?: number | null; budget_max?: number | null; currency?: string }) {
  const unit = j.budget_type === "hourly" ? "/hr" : "";
  const c = (n: number) => compactMoney(n, j.currency || "INR");
  if (j.budget_min && j.budget_max) return `${c(j.budget_min)}–${c(j.budget_max)}${unit}`;
  if (j.budget_max) return `Up to ${c(j.budget_max)}${unit}`;
  if (j.budget_min) return `From ${c(j.budget_min)}${unit}`;
  return "Budget open";
}

export const label = (s?: string | null) => (s ? s.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase()) : "");

export const initials = (name = "") =>
  name.split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0]!.toUpperCase()).join("") || "?";

export const lines = (s?: string | null) => (s || "").split("\n").map((x) => x.trim()).filter(Boolean);

export const skillsFrom = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);

export const bytes = (n?: number | null) =>
  n == null ? "" : n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(0)} KB` : `${(n / 1048576).toFixed(1)} MB`;


// ---- countries & time ---------------------------------------------------------------------------
export const flag = (cc?: string | null) =>
  cc && /^[A-Z]{2}$/.test(cc) ? String.fromCodePoint(...[...cc].map((ch) => 0x1f1e6 + ch.charCodeAt(0) - 65)) : "";

let regionNames: Intl.DisplayNames | null = null;
export function countryName(cc?: string | null, locale = "en") {
  if (!cc) return "";
  try { regionNames ??= new Intl.DisplayNames([locale], { type: "region" }); return regionNames.of(cc) || cc; } catch { return cc; }
}

export const browserTimezone = () => { try { return Intl.DateTimeFormat().resolvedOptions().timeZone || ""; } catch { return ""; } };
export function browserCountry(): string {
  try {
    const loc = navigator.languages?.find((l) => /-[A-Z]{2}$/i.test(l)) || navigator.language || "";
    const m = loc.match(/-([A-Za-z]{2})$/);
    if (m) return m[1].toUpperCase();
  } catch { /* ignore */ }
  return browserTimezone() === "Asia/Kolkata" || browserTimezone() === "Asia/Calcutta" ? "IN" : "";
}

/** "3:42 PM" in a timezone, plus the offset from the viewer ("+5h 30m", "same time"). */
export function localTime(tz?: string | null): { time: string; diff: string } | null {
  if (!tz) return null;
  try {
    const now = new Date();
    const time = now.toLocaleTimeString("en-US", { timeZone: tz, hour: "numeric", minute: "2-digit" });
    const offset = (zone?: string) => {
      const parts = new Intl.DateTimeFormat("en-US", { timeZone: zone, hour12: false, year: "numeric", month: "2-digit",
        day: "2-digit", hour: "2-digit", minute: "2-digit" }).formatToParts(now);
      const g = (t: string) => Number(parts.find((p) => p.type === t)?.value);
      return (Date.UTC(g("year"), g("month") - 1, g("day"), g("hour") % 24, g("minute")) - now.getTime()) / 60000;
    };
    const d = Math.round(offset(tz) - offset(undefined));
    const h = Math.trunc(Math.abs(d) / 60), m = Math.abs(d) % 60;
    const diff = d === 0 ? "same time as you" : `${d > 0 ? "+" : "−"}${h ? `${h}h` : ""}${m ? ` ${m}m` : ""} from you`;
    return { time, diff };
  } catch { return null; }
}

export const hour = (h?: number | null) => (h == null ? "" : `${((h + 11) % 12) + 1} ${h < 12 ? "AM" : "PM"}`);

export const TIMEZONES: string[] = (() => {
  try { return (Intl as any).supportedValuesOf("timeZone") as string[]; } catch { return ["Asia/Kolkata", "Europe/London", "America/New_York"]; }
})();

export const COUNTRY_CODES = ("AE AR AT AU BD BE BG BR CA CH CL CN CO CZ DE DK EE EG ES FI FR GB GH GR HK HR HU ID IE IL IN IT JP KE KR LK LT LU LV " +
  "MA MX MY NG NL NO NP NZ PE PH PK PL PT QA RO RS SA SE SG SI SK TH TR TW UA US VN ZA").split(" ");
