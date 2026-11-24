/* Lightweight i18n: the interface is written in English; this translates rendered UI text in place.
 *
 * - Exact-match dictionary (English → Hindi / Spanish) plus patterns for text with names or numbers.
 * - Only interface strings are translated: anything inside [translate="no"] (people's names, job descriptions,
 *   messages, reviews…) is left alone, and text that isn't in the dictionary stays as written.
 * - A MutationObserver re-applies translations as React renders; switching back restores the originals.
 */
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

export type Lang = "en" | "hi" | "es";
export const LANGS: { code: Lang; label: string }[] = [
  { code: "en", label: "English" }, { code: "hi", label: "हिन्दी" }, { code: "es", label: "Español" }];

type Pair = [hi: string, es: string];
let D: Record<string, Pair> = {};
let dictPromise: Promise<void> | null = null;
const loadDict = () => (dictPromise ??= import("./i18n-dict").then((m) => { D = m.default as Record<string, Pair>; }));

// Patterns: English template with {x} placeholders → translated templates.
const P: [string, string, string][] = [
  ["Welcome back, {name}", "वापसी पर स्वागत है, {name}", "Hola de nuevo, {name}"], ["Welcome, {name}", "स्वागत है, {name}", "Bienvenido, {name}"],
  ["Hi, {name}", "नमस्ते, {name}", "Hola, {name}"], ["Ranked matches ({n})", "रैंक किए गए मैच ({n})", "Coincidencias ({n})"],
  ["Proposals ({n})", "प्रस्ताव ({n})", "Propuestas ({n})"], ["Attachments ({n})", "संलग्नक ({n})", "Adjuntos ({n})"],
  ["{n} freelancers", "{n} फ्रीलांसर", "{n} freelancers"], ["{n} freelancer", "{n} फ्रीलांसर", "{n} freelancer"],
  ["{n} proposals", "{n} प्रस्ताव", "{n} propuestas"], ["{n} proposal", "{n} प्रस्ताव", "{n} propuesta"], ["{n} matches", "{n} मैच", "{n} coincidencias"],
  ["{n} yrs", "{n} वर्ष", "{n} años"], ["{n}+ yrs", "{n}+ वर्ष", "{n}+ años"], ["{n} years experience", "{n} वर्ष का अनुभव", "{n} años de experiencia"],
  ["{n}-day delivery", "{n} दिन में डिलीवरी", "Entrega en {n} días"], ["Delivered in {n} days", "{n} दिन में डिलीवर", "Entrega en {n} días"],
  ["{n} days", "{n} दिन", "{n} días"], ["Buy for {x}", "{x} में खरीदें", "Comprar por {x}"], ["Pay {x}", "{x} भुगतान करें", "Pagar {x}"],
  ["Upgrade to {x}", "{x} पर अपग्रेड करें", "Mejorar a {x}"], ["Choose {x}", "{x} चुनें", "Elegir {x}"], ["Message {x}", "{x} को संदेश", "Escribir a {x}"],
  ["Posted {x}", "पोस्ट किया {x}", "Publicado {x}"], ["{n} shortlisted", "{n} शॉर्टलिस्ट", "{n} preseleccionadas"],
  ["{n}% match", "{n}% मैच", "{n}% de encaje"], ["just now", "अभी", "ahora mismo"], ["{n} min ago", "{n} मिनट पहले", "hace {n} min"],
  ["{n} h ago", "{n} घंटे पहले", "hace {n} h"], ["{n} d ago", "{n} दिन पहले", "hace {n} d"], ["{n} open jobs", "{n} खुली नौकरियाँ", "{n} trabajos abiertos"],
  ["{n} matches", "{n} मैच", "{n} coincidencias"], ["{n} proposals so far", "अब तक {n} प्रस्ताव", "{n} propuestas hasta ahora"], ["{n} ranked matches", "{n} रैंक किए गए मैच", "{n} coincidencias ordenadas"],
];
const COMPILED = P.map(([en, hi, es]) => {
  const names: string[] = [];
  const src = "^" + en.replace(/[.*+?^$()|[\]\\]/g, "\\$&").replace(/\{(\w+)\}/g, (_, n) => { names.push(n); return n === "n" ? "([\\d.,]+)" : "(.+?)"; }) + "$";
  return { re: new RegExp(src), names, hi, es };
});

export function translate(text: string, lang: Lang): string {
  if (lang === "en" || !text) return text;
  const lead = text.match(/^\s*/)![0], trail = text.match(/\s*$/)![0];
  const core = text.trim();
  if (!core) return text;
  const hit = D[core];
  if (hit) return lead + hit[lang === "hi" ? 0 : 1] + trail;
  for (const p of COMPILED) {
    const m = core.match(p.re);
    if (m) {
      let out = lang === "hi" ? p.hi : p.es;
      p.names.forEach((n, i) => { out = out.replace(`{${n}}`, m[i + 1]); });
      return lead + out + trail;
    }
  }
  return text;
}

export const t = (s: string) => translate(s, currentLang);

// ---- DOM translator -------------------------------------------------------------------------------
let currentLang: Lang = "en";
const textState = new WeakMap<Node, { orig: string; written: string }>();
const attrState = new WeakMap<Element, Record<string, { orig: string; written: string }>>();
const ATTRS = ["placeholder", "title", "aria-label"];
const SKIP = "script,style,textarea,code,pre,[translate='no'],[contenteditable='true']";

function doText(node: Text) {
  const parent = node.parentElement;
  if (!parent || parent.closest(SKIP)) return;
  const cur = node.nodeValue || "";
  const st = textState.get(node);
  const orig = st && st.written === cur ? st.orig : cur;   // React changed it → new original
  const next = translate(orig, currentLang);
  if (next !== cur) node.nodeValue = next;
  if (next !== orig || st) textState.set(node, { orig, written: next });
}

function doAttrs(el: Element) {
  if (el.closest(SKIP)) return;
  for (const a of ATTRS) {
    if (!el.hasAttribute(a)) continue;
    const cur = el.getAttribute(a) || "";
    const map = attrState.get(el) || {};
    const st = map[a];
    const orig = st && st.written === cur ? st.orig : cur;
    const next = translate(orig, currentLang);
    if (next !== cur) el.setAttribute(a, next);
    map[a] = { orig, written: next };
    attrState.set(el, map);
  }
}

function walk(root: Node) {
  if (root.nodeType === Node.TEXT_NODE) { doText(root as Text); return; }
  if (root.nodeType !== Node.ELEMENT_NODE) return;
  doAttrs(root as Element);
  const tw = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
  let n: Node | null;
  while ((n = tw.nextNode())) {
    if (n.nodeType === Node.TEXT_NODE) doText(n as Text); else doAttrs(n as Element);
  }
}

let observer: MutationObserver | null = null;
function startObserver() {
  if (observer || typeof MutationObserver === "undefined") return;
  observer = new MutationObserver((muts) => {
    for (const m of muts) {
      if (m.type === "characterData") doText(m.target as Text);
      else if (m.type === "attributes") doAttrs(m.target as Element);
      else m.addedNodes.forEach(walk);
    }
  });
  observer.observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ATTRS });
}

// ---- React glue -----------------------------------------------------------------------------------
const Ctx = createContext<{ lang: Lang; setLang: (l: Lang) => void }>({ lang: "en", setLang: () => {} });

const stored = (): Lang => { try { const l = localStorage.getItem("tm_lang"); return l === "hi" || l === "es" ? l : "en"; } catch { return "en"; } };

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(stored);
  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try { localStorage.setItem("tm_lang", l); } catch { /* ignore */ }
  }, []);
  useEffect(() => {
    let live = true;
    const apply = () => { if (!live) return; currentLang = lang; document.documentElement.lang = lang; startObserver(); walk(document.body); };
    if (lang === "en") apply(); else loadDict().then(apply);
    return () => { live = false; };
  }, [lang]);
  return <Ctx.Provider value={{ lang, setLang }}>{children}</Ctx.Provider>;
}

export const useLang = () => useContext(Ctx);

export function LanguagePicker({ onChange, compact }: { onChange?: (l: Lang) => void; compact?: boolean }) {
  const { lang, setLang } = useLang();
  return <label className="flex items-center gap-2 text-sm">
    {!compact && <span className="font-medium text-slate-700">Language</span>}
    <span aria-hidden className={compact ? "text-slate-500" : "hidden"}>🌐</span>
    <select translate="no" aria-label="Language" value={lang} onChange={(e) => { const l = e.target.value as Lang; setLang(l); onChange?.(l); }}
      className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm">
      {LANGS.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
    </select>
  </label>;
}
