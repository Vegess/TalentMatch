import { useEffect } from "react";
import { API_BASE, getAccessToken, refreshSession } from "./api";

/** Connect to /ws with the current access token; calls onEvent for every message. Reconnects. */
export function useRealtime(enabled: boolean, onEvent: (e: any) => void) {
  useEffect(() => {
    if (!enabled) return;
    let ws: WebSocket | null = null, stop = false, timer: any;
    const connect = async () => {
      if (stop) return;
      let token = getAccessToken();
      if (!token && (await refreshSession())) token = getAccessToken();
      if (!token) return;
      const base = (import.meta.env.VITE_WS_URL || API_BASE || window.location.origin).replace(/\/$/, "");
      const url = base.replace(/^http/, "ws") + "/ws?token=" + encodeURIComponent(token);
      ws = new WebSocket(url);
      ws.onmessage = (m) => { try { const e = JSON.parse(m.data); onEvent(e); window.dispatchEvent(new CustomEvent("tm:event", { detail: e })); } catch { /* ignore */ } };
      ws.onclose = async (ev) => {
        if (stop) return;
        if (ev.code === 4401) await refreshSession();
        timer = setTimeout(connect, 5000);
      };
    };
    connect();
    return () => { stop = true; clearTimeout(timer); ws?.close(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled]);
}

/** Re-run `fn` when a live event of one of these types arrives. */
export function useLiveReload(types: string[], fn: () => void) {
  useEffect(() => {
    let t: any;
    const h = (e: Event) => {
      const d = (e as CustomEvent).detail;
      if (types.includes(d?.type)) { clearTimeout(t); t = setTimeout(fn, 400); }
    };
    window.addEventListener("tm:event", h);
    return () => { window.removeEventListener("tm:event", h); clearTimeout(t); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [types.join(","), fn]);
}
