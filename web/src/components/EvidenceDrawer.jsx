import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";
import { get } from "../api.js";
import { pretty } from "./ui.jsx";

const TYPE = {
  curated: ["From a database", "ok"],
  text_mined: ["Read from text, quote stored", "warn"],
  inferred: ["Computed by the Atlas, not an observation", ""],
};
const VERDICT = { supported: ["A second model agrees the quote supports this", "ok"], partial: ["A second model finds the quote only partly supports this", "warn"], unsupported: ["A second model did not find support in the quote", "bad"] };

const GENE_FIRST = new Set(["gene_associated_with_disease", "participates_in_pathway"]);
const SAY = { gene_associated_with_disease: "is the gene behind", participates_in_pathway: "works in the mechanism", has_phenotype: "has the symptom", similar_to: "is similar to", serves_disease: "serves", has_asset: "has the resource", studied_in_trial: "is studied in", funded_by: "is funded by", investigator_of: "works on" };

function Item({ id }) {
  const [e, setE] = useState(null);
  useEffect(() => { get(`/edge/${id}`).then(setE).catch(() => setE(false)); }, [id]);
  if (e === null) return <div className="ev"><div className="skeleton" style={{ height: 90 }} /></div>;
  if (e === false) return null;
  const [label, tone] = TYPE[e.evidence_type];
  const v = VERDICT[e.reviewer_verdict];
  return (
    <div className="ev">
      <div className="claim">{GENE_FIRST.has(e.predicate.replace("not_", "")) ? `${e.subject} (${e.subject_name})` : e.subject_name} <em>{SAY[e.predicate] || pretty(e.predicate)}</em> {e.object_name}</div>
      <div className="chips">
        <span className={"chip " + tone}>{label}</span>
        {v && <span className={"chip " + v[1]}>{v[0]}</span>}
      </div>
      {e.evidence_text && <div className="quote">“{e.evidence_text}”</div>}
      <div className="conf"><span>Confidence {Math.round(e.confidence * 100)}%</span><div className="bar-score"><i style={{ width: `${e.confidence * 100}%` }} /></div></div>
      <dl className="kv">
        <dt>Source</dt><dd>{e.source}</dd>
        <dt>Record</dt><dd style={{ wordBreak: "break-word" }}>{e.source_record}</dd>
        <dt>Retrieved</dt><dd>{e.retrieved}</dd>
        {e.method && <><dt>Method</dt><dd>{e.method}</dd></>}
      </dl>
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
