import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, onSession, refreshSession, setAccessToken } from "./api";

export type Role = "admin" | "client" | "freelancer";
export type User = {
  id: number; email: string; name: string; role: Role; client_id: number | null;
  consultant_id: number | null; plan: string | null; company_name?: string | null;
  currency?: string | null; preferred_language?: string; email_notifications?: boolean;
};

type Ctx = {
  user: User | null; ready: boolean;
  login: (email: string, password: string) => Promise<User>;
  register: (body: Record<string, unknown>) => Promise<User>;
  logout: () => Promise<void>;
  logoutAll: () => Promise<void>;
  reload: () => Promise<void>;
  setSession: (data: any) => void;
};

const AuthCtx = createContext<Ctx>(null as unknown as Ctx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  const setSession = useCallback((data: any) => {
    setAccessToken(data?.access_token ?? null);
    setUser(data?.user ?? null);
  }, []);

  useEffect(() => {
    onSession((data) => setUser(data?.user ?? null));
    refreshSession().finally(() => setReady(true));
    // keep the 30-minute access token fresh while the tab is open
    const t = setInterval(() => { refreshSession(); }, 25 * 60 * 1000);
    return () => clearInterval(t);
  }, []);

  const login = async (email: string, password: string) => {
    const data = await api("/api/v1/auth/login", { json: { email, password } });
    setSession(data);
    return data.user as User;
  };
  const register = async (body: Record<string, unknown>) => {
    const data = await api("/api/v1/auth/register", { json: body });
    setSession(data);
    return data.user as User;
  };
  const logout = async () => {
    await api("/api/v1/auth/logout", { method: "POST" }).catch(() => {});
    setSession(null);
  };
  const logoutAll = async () => {
    await api("/api/v1/auth/logout-all", { method: "POST" });
    setSession(null);
  };
  const reload = async () => {
    const me = await api<User>("/api/v1/auth/me");
    setUser(me);
  };
  return <AuthCtx.Provider value={{ user, ready, login, register, logout, logoutAll, reload, setSession }}>
    {children}
  </AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);

export const homeFor = (role?: Role | null) =>
  role === "admin" ? "/control-room" : role === "client" ? "/client" : role === "freelancer" ? "/freelancer" : "/";
