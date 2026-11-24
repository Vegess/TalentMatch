import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

type Toast = { id: number; text: string; tone: "info" | "success" | "error" };
const Ctx = createContext<(text: string, tone?: Toast["tone"]) => void>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const push = useCallback((text: string, tone: Toast["tone"] = "info") => {
    const id = Date.now() + Math.random();
    setItems((x) => [...x.slice(-3), { id, text, tone }]);
    setTimeout(() => setItems((x) => x.filter((t) => t.id !== id)), tone === "error" ? 6500 : 4000);
  }, []);
  const color = { info: "border-l-brand-500", success: "border-l-emerald-500", error: "border-l-red-500" };
  return <Ctx.Provider value={push}>
    {children}
    <div className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-[min(380px,calc(100vw-2rem))] flex-col gap-2" aria-live="polite">
      {items.map((t) => <div key={t.id} className={`anim-slide-in pointer-events-auto rounded-lg border border-l-4 border-slate-200 bg-white px-4 py-3 text-sm shadow-lg ${color[t.tone]}`}>{t.text}</div>)}
    </div>
  </Ctx.Provider>;
}

export const useToast = () => useContext(Ctx);
