import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";
import { get } from "../api.js";
import { pretty } from "./ui.jsx";

// Plain labels first; the technical name stays in the tooltip.
const TYPE = {
  curated: ["Verified source", "ok", "Taken from a curated database or registry (curated)."],
  text_mined: ["Research literature", "info", "Read from text; the exact sentence is stored and was checked to be there (text-mined)."],
  inferred: ["Atlas-derived", "warn", "Computed by the Atlas, not an observation (inferred). A lead to check."],
};
const WEB = ["Organisation website", "info", "Read from the organisation's own web page; the sentence naming the disease is stored."];
const VERDICT = { supported: ["Second model agrees with the quote", "ok"], partial: ["Second model: the quote only partly supports this", "warn"], unsupported: ["Second model found no support in the quote", "bad"] };
const strength = (c) => (c >= 0.85 ? "Strong" : c >= 0.65 ? "Moderate" : "Tentative");

const GENE_FIRST = new Set(["gene_associated_with_disease", "participates_in_pathway"]);
const SAY = { gene_associated_with_disease: "is the gene behind", participates_in_pathway: "works in the mechanism", has_phenotype: "has the symptom", similar_to: "is similar to", serves_disease: "serves", has_asset: "has the resource", studied_in_trial: "is studied in", funded_by: "is funded by", investigator_of: "works on" };

function Item({ id }) {
  const [e, setE] = useState(null);
  useEffect(() => { get(`/edge/${id}`).then(setE).catch(() => setE(false)); }, [id]);
  if (e === null) return <div className="ev"><div className="skeleton" style={{ height: 90 }} /></div>;
  if (e === false) return null;
  const [label, tone, tip] = e.source === "Patient organisation website" && e.evidence_type === "text_mined" ? WEB : TYPE[e.evidence_type];
  const v = VERDICT[e.reviewer_verdict];
  return (
    <div className="ev">
      <div className="claim">{GENE_FIRST.has(e.predicate.replace("not_", "")) ? `${e.subject} (${e.subject_name})` : e.subject_name} <em>{SAY[e.predicate] || pretty(e.predicate)}</em> {e.object_name}</div>
      <div className="chips">
        <span className={"chip " + tone} title={tip}>{label}</span>
        {v && <span className={"chip " + v[1]}>{v[0]}</span>}
      </div>
      {e.evidence_text && <div className="quote">“{e.evidence_text}”</div>}
      <div className="conf" title={`Confidence ${e.confidence.toFixed(2)}`}><span>{strength(e.confidence)} evidence</span><div className="bar-score"><i style={{ width: `${e.confidence * 100}%` }} /></div></div>
      <dl className="kv">
        <dt>Source</dt><dd>{e.source}</dd>
        <dt>Retrieved</dt><dd>{e.retrieved}</dd>
      </dl>
      <details className="small soft">
        <summary style={{ cursor: "pointer", color: "var(--muted)" }}>Evidence details</summary>
        <dl className="kv" style={{ marginTop: 10 }}>
          <dt>Record</dt><dd style={{ wordBreak: "break-word" }}>{e.source_record}</dd>
          <dt>Confidence</dt><dd>{e.confidence.toFixed(2)} ({e.evidence_type.replace("_", "-")})</dd>
          {e.method && <><dt>Method</dt><dd>{e.method}</dd></>}
          <dt>Fact ID</dt><dd>{e.edge_id}</dd>
        </dl>
      </details>
      {e.contradicted_by && e.contradicted_by.length > 0 && <span className="chip bad">Contradicted by {e.contradicted_by.length} other finding(s)</span>}
      {e.source_url && <a href={e.source_url} target="_blank" rel="noreferrer">Open the source ↗</a>}
    </div>
  );
}

// Level 3 of "simple to depth": the proof behind any claim, always in the same place.
export default function EvidenceDrawer({ state, close }) {
  const [n, setN] = useState(5);
  useEffect(() => setN(5), [state]);
  useEffect(() => {
    const esc = (e) => e.key === "Escape" && close();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [close]);
  return (
    <AnimatePresence>
      {state && (
        <>
          <motion.div className="scrim" onClick={close} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} />
          <motion.aside className="drawer" role="dialog" aria-label="Evidence" initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }} transition={{ type: "spring", stiffness: 260, damping: 32 }}>
            <button className="close" onClick={close} aria-label="Close">×</button>
            <span className="eyebrow">Why is this connected?</span>
            <h3>{state.title}</h3>
            <p className="soft small">{state.ids.length} fact{state.ids.length > 1 ? "s" : ""} in the graph support this. Each one names its source.</p>
            <div style={{ marginTop: 18 }}>{state.ids.slice(0, n).map((id) => <Item key={id} id={id} />)}</div>
            {state.ids.length > n && <button className="more" onClick={() => setN(n + 10)}>Show more ({state.ids.length - n} left)</button>}
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
