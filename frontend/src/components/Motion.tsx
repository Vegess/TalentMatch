/* Hand-built motion primitives. No animation library; everything respects prefers-reduced-motion. */
import { useEffect, useRef, useState, type ReactNode } from "react";
import { cx } from "./ui";

export const reducedMotion = () =>
  typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

/** Animated check mark for successful payments / actions. */
export function SuccessMark({ size = 64 }: { size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 52 52" className="mx-auto" role="img" aria-label="Success">
    <circle cx="26" cy="26" r="24" fill="#ecfdf5" stroke="#10b981" strokeWidth="2.5" className="anim-draw" style={{ ["--len" as any]: 151 }} />
    <path d="M15 27l7 7 15-15" fill="none" stroke="#059669" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round"
      className="anim-draw" style={{ ["--len" as any]: 40, animationDelay: "350ms" }} />
  </svg>;
}

/** Counts up to a number when it scrolls into view. `format` renders the in-between values. */
export function CountUp({ value, format = (n) => Math.round(n).toLocaleString(), duration = 900 }:
  { value: number; format?: (n: number) => string; duration?: number }) {
  const [shown, setShown] = useState(reducedMotion() ? value : 0);
  const ref = useRef<HTMLSpanElement>(null);
  const from = useRef(0);
  useEffect(() => {
    if (reducedMotion()) { setShown(value); return; }
    let raf = 0, started = false;
    const start = () => {
      if (started) return; started = true;
      const t0 = performance.now(), a = from.current;
      const tick = (t: number) => {
        const k = Math.min(1, (t - t0) / duration);
        const eased = 1 - Math.pow(1 - k, 3);
        setShown(a + (value - a) * eased);
        if (k < 1) raf = requestAnimationFrame(tick); else from.current = value;
      };
      raf = requestAnimationFrame(tick);
    };
    const el = ref.current;
    if (!el || !("IntersectionObserver" in window)) { start(); return () => cancelAnimationFrame(raf); }
    const io = new IntersectionObserver((es) => es.some((e) => e.isIntersecting) && start(), { threshold: 0.3 });
    io.observe(el);
    return () => { io.disconnect(); cancelAnimationFrame(raf); };
  }, [value, duration]);
  return <span ref={ref} className="tabular-nums">{format(shown)}</span>;
}

/** Fades + lifts children in when they scroll into view. Stagger with `delay`. */
export function Reveal({ children, delay = 0, className, as: Tag = "div" }:
  { children: ReactNode; delay?: number; className?: string; as?: any }) {
  const ref = useRef<HTMLElement>(null);
  const [visible, setVisible] = useState(reducedMotion());
  useEffect(() => {
    if (visible) return;
    const el = ref.current;
    if (!el || !("IntersectionObserver" in window)) { setVisible(true); return; }
    const io = new IntersectionObserver((es) => { if (es.some((e) => e.isIntersecting)) { setVisible(true); io.disconnect(); } },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.05 });
    io.observe(el);
    return () => io.disconnect();
  }, [visible]);
  return <Tag ref={ref} className={cx("reveal", visible && "reveal-in", className)} style={{ transitionDelay: `${delay}ms` }}>{children}</Tag>;
}

/** Grey shimmering placeholder blocks while data loads. */
export function Skeleton({ className }: { className?: string }) {
  return <div className={cx("skeleton rounded-md", className)} aria-hidden />;
}

export function CardSkeletons({ count = 6, cols = "sm:grid-cols-2 lg:grid-cols-3" }: { count?: number; cols?: string }) {
  return <div className={cx("grid gap-4", cols)} aria-busy="true" aria-label="Loading">
    {Array.from({ length: count }).map((_, i) => <div key={i} className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="flex items-center gap-3"><Skeleton className="h-11 w-11 rounded-full" /><div className="flex-1 space-y-2"><Skeleton className="h-3.5 w-2/3" /><Skeleton className="h-3 w-1/2" /></div></div>
      <div className="mt-5 flex gap-2"><Skeleton className="h-5 w-14" /><Skeleton className="h-5 w-16" /><Skeleton className="h-5 w-12" /></div>
      <Skeleton className="mt-5 h-3 w-1/3" /></div>)}
  </div>;
}
