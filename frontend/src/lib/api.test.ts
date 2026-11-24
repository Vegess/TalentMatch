import { afterEach, describe, expect, it, vi } from "vitest";
import { api, errorMessage, refreshSession, setAccessToken } from "./api";

describe("errorMessage", () => {
  it("reads FastAPI string details", () => {
    expect(errorMessage({ detail: "Wrong email or password" }, "x")).toBe("Wrong email or password");
  });
  it("turns validation errors into readable text", () => {
    const d = { detail: [{ loc: ["body", "budget_max"], msg: "Value error, too small" }, { loc: ["body"], msg: "bad" }] };
    expect(errorMessage(d, "x")).toBe("budget max: too small · bad");
  });
  it("falls back when there is no detail", () => {
    expect(errorMessage(null, "Request failed")).toBe("Request failed");
  });
});

describe("api", () => {
  afterEach(() => { vi.unstubAllGlobals(); setAccessToken(null); });

  it("refreshes once on 401 and retries with the new token", async () => {
    setAccessToken("old");
    const calls: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init: any) => {
      calls.push(`${url} ${init.headers?.Authorization || ""}`);
      if (url.endsWith("/auth/refresh")) return new Response(JSON.stringify({ access_token: "new", user: {} }), { status: 200 });
      if (init.headers?.Authorization === "Bearer old") return new Response("{}", { status: 401 });
      return new Response(JSON.stringify({ ok: true }), { status: 200 });
    }));
    expect(await api("/api/v1/orders")).toEqual({ ok: true });
    expect(calls).toEqual(["/api/v1/orders Bearer old", "/api/v1/auth/refresh ", "/api/v1/orders Bearer new"]);
  });

  it("raises a readable error and does not loop when refresh fails", async () => {
    setAccessToken("old");
    const f = vi.fn(async (url: string) => new Response(JSON.stringify({ detail: url.endsWith("refresh") ? "Not signed in" : "Session expired" }), { status: 401 }));
    vi.stubGlobal("fetch", f);
    await expect(api("/api/v1/orders")).rejects.toThrow("Session expired");
    expect(f).toHaveBeenCalledTimes(2);
  });

  it("skips the refresh call for visitors who never signed in", async () => {
    const store: Record<string, string> = {};
    vi.stubGlobal("localStorage", { getItem: (k: string) => store[k] ?? null, setItem: (k: string, v: string) => { store[k] = v; }, removeItem: (k: string) => { delete store[k]; } });
    const f = vi.fn(); vi.stubGlobal("fetch", f);
    expect(await refreshSession()).toBe(false);
    expect(f).not.toHaveBeenCalled();
  });
});
