import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import { get, q } from "../api.js";

const KIND = { disease: "Disease", gene: "Gene", symptom: "Symptom", pathway: "Mechanism", patient_org: "Patient group" };

// One box for everything. A disease opens directly; a gene, symptom, mechanism or group lists the diseases it leads to.
export default function Search({ onDisease, autoFocus, placeholder = "Search a disease, gene, symptom or patient group" }) {
  const [text, setText] = useState("");
  const [res, setRes] = useState(null);
  const [on, setOn] = useState(0);
  const box = useRef(null);

  useEffect(() => {
    if (text.trim().length < 2) return setRes(null);
    let live = true;
    const t = setTimeout(() => get(`/search?q=${q(text.trim())}`).then((r) => live && (setRes(r), setOn(0))).catch(() => {}), 160);
    return () => { live = false; clearTimeout(t); };
  }, [text]);

  useEffect(() => {
    const out = (e) => box.current && !box.current.contains(e.target) && setRes(null);
    document.addEventListener("mousedown", out);
    return () => document.removeEventListener("mousedown", out);
  }, []);

  // flatten: disease hits open themselves; other hits offer each disease they lead to
  const rows = !res ? [] : res.hits.flatMap((h) =>
    h.kind === "disease"
      ? [{ id: h.id, label: h.label, kind: h.kind, sub: h.matched !== h.label.toLowerCase() ? `matched “${h.matched}”` : "" }]
      : (h.diseases || []).slice(0, 4).map((d) => ({ id: d.id, label: d.name, kind: h.kind, sub: `${KIND[h.kind].toLowerCase()}: ${h.label}` })));
  const go = (r) => { setRes(null); setText(""); onDisease(r.id); };
  const key = (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setOn((on + 1) % Math.max(rows.length, 1)); }
    if (e.key === "ArrowUp") { e.preventDefault(); setOn((on - 1 + rows.length) % Math.max(rows.length, 1)); }
    if (e.key === "Enter" && rows[on]) go(rows[on]);
    if (e.key === "Escape") setRes(null);
  };

  return (
    <div className="searchbox" ref={box}>
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>
      <input value={text} onChange={(e) => setText(e.target.value)} onKeyDown={key} placeholder={placeholder} autoFocus={autoFocus} aria-label="Search the Atlas" />
      <AnimatePresence>
        {res && (
          <motion.div className="results" initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.25 }}>
            {rows.map((r, i) => (
              <button key={r.id + r.sub} className={"result" + (i === on ? " on" : "")} onMouseEnter={() => setOn(i)} onClick={() => go(r)}>
                <span className="kind">{KIND[r.kind]}</span>
                <span><span>{r.label}</span>{r.sub && <span className="sub"><br />{r.sub}</span>}</span>
              </button>
            ))}
            {!rows.length && (
              <div className="empty">
                <b>Nothing in the Atlas matches “{res.query}”.</b><br />
                {res.no_match
                  ? <>That means it is outside what has been loaded, not that nothing is known. We searched {res.no_match.searched.diseases} diseases, {res.no_match.searched.genes} genes, {res.no_match.searched.symptoms} symptoms, {res.no_match.searched.specific_pathways} mechanisms and {res.no_match.searched.patient_organisations} patient groups.</>
                  : "It matched something that leads to no disease in the Atlas."}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
