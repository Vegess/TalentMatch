/* Fetch wrapper.
 * - Access token lives in memory only (never localStorage).
 * - The refresh token is an httpOnly cookie; on a 401 we refresh once (single-flight) and retry.
 */
export const API_BASE = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

let accessToken: string | null = null;
let refreshing: Promise<boolean> | null = null;
let onSessionChange: ((data: any | null) => void) | null = null;

// Non-secret hint so signed-out visitors don't make a refresh call that is bound to fail.
const HINT = "tm_has_session";
const hint = {
  get: () => { try { return localStorage.getItem(HINT) === "1"; } catch { return true; } },
  set: (on: boolean) => { try { on ? localStorage.setItem(HINT, "1") : localStorage.removeItem(HINT); } catch { /* storage blocked */ } },
};
export const setAccessToken = (t: string | null) => { accessToken = t; hint.set(!!t); };
export const getAccessToken = () => accessToken;
export const onSession = (fn: (data: any | null) => void) => { onSessionChange = fn; };

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) { super(message); this.status = status; }
}

export function errorMessage(data: any, fallback: string): string {
  const d = data?.detail;
  if (Array.isArray(d)) {
    return d.map((e: any) => {
      const field = Array.isArray(e.loc) ? e.loc[e.loc.length - 1] : "";
      const msg = String(e.msg || "").replace(/^Value error, /, "");
      return field && field !== "body" ? `${String(field).replace(/_/g, " ")}: ${msg}` : msg;
    }).join(" · ");
  }
  return typeof d === "string" ? d : fallback;
}

export async function refreshSession(opts: { force?: boolean } = {}): Promise<boolean> {
  if (!opts.force && !accessToken && !hint.get()) return false;
  if (!refreshing) {
    refreshing = (async () => {
      try {
        const r = await fetch(`${API_BASE}/api/v1/auth/refresh`, { method: "POST", credentials: "include" });
        if (!r.ok) { setAccessToken(null); onSessionChange?.(null); return false; }
        const data = await r.json();
        setAccessToken(data.access_token);
        onSessionChange?.(data);
        return true;
      } catch { return false; }
      finally { setTimeout(() => { refreshing = null; }, 0); }
    })();
  }
  return refreshing;
}

type Opts = { method?: string; json?: unknown; form?: FormData; auth?: boolean; raw?: boolean };

export async function api<T = any>(path: string, opts: Opts = {}, retried = false): Promise<T> {
  const headers: Record<string, string> = {};
  let body: BodyInit | undefined;
  if (opts.json !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(opts.json); }
  if (opts.form) body = opts.form;
  if (accessToken) headers["Authorization"] = `Bearer ${accessToken}`;
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { method: opts.method || (body ? "POST" : "GET"), headers, body,
      credentials: "include" });
  } catch {
    throw new ApiError("Can't reach the server. If it was asleep, try again in a few seconds.", 0);
  }
  if (res.status === 401 && !retried && !path.startsWith("/api/v1/auth/")) {
    if (await refreshSession()) return api<T>(path, opts, true);
  }
  if (opts.raw) {
    if (!res.ok) throw new ApiError(errorMessage(await res.json().catch(() => null), res.statusText), res.status);
    return res as unknown as T;
  }
  const data = res.status === 204 ? null : await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(errorMessage(data, res.statusText || "Request failed"), res.status);
  return data as T;
}

/** Open an authenticated file download in a new tab. */
export async function openDocument(downloadUrl: string, filename?: string) {
  const res = await api<Response>(downloadUrl, { raw: true });
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const viewable = /pdf|image|text\/plain/.test(blob.type);
  if (viewable) window.open(url, "_blank", "noopener");
  else {
    const a = document.createElement("a");
    a.href = url; a.download = filename || "download"; a.click();
  }
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
