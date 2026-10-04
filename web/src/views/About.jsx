import { Card, Reveal, Skeletons } from "../components/ui.jsx";
import { useApi } from "../hooks.js";

const n = (o, k) => (o && o[k]) || 0;

// What is in the Atlas and how far each kind of evidence can be trusted.
export default function About() {
  const [s] = useApi("/stats");
  const [c] = useApi("/contradictions");
  if (!s) return <div className="wrap page"><Skeletons /></div>;
  const ev = s.edges_by_evidence_type, v = s.reviewer_verdicts, nodes = s.nodes_by_type;
  return (
    <div className="wrap page">
      <Reveal className="chapter-head">
        <span className="eyebrow">About the evidence</span>
        <h2>Every link names its source.</h2>
        <p className="lead">The Atlas holds {Object.values(ev).reduce((a, b) => a + b, 0).toLocaleString()} facts about {n(nodes, "Disease")} diseases. Each one records where it came from, when, and how far it can be trusted.</p>
      </Reveal>
      <div className="cards">
        <Card meta={`${n(ev, "curated").toLocaleString()} facts`} title="Verified source"><p>Copied from a curated database or registry: Orphadata, HPO, Reactome, Gene Ontology, ClinicalTrials.gov, NIH RePORTER.</p><span className="chip ok">Solid line</span></Card>
        <Card meta={`${n(ev, "text_mined").toLocaleString()} facts`} title="Research literature"><p>Read from a paper by gpt-oss, or from a patient organisation's own website. Kept only if the exact sentence is found in the source. A second model then checks each paper fact.</p><span className="chip info">Dotted line</span></Card>
        <Card meta={`${n(ev, "inferred").toLocaleString()} facts`} title="Atlas-derived"><p>Computed by the Atlas: disease similarity from shared mechanisms and informative symptoms. A lead to check, never an observation.</p><span className="chip warn">Dashed line</span></Card>
      </div>
      <div className="two-col" style={{ marginTop: 16 }}>
        <Card title="Second-model review of paper facts">
          <div className="chips"><span className="chip ok">{n(v, "supported")} supported</span><span className="chip warn">{n(v, "partial")} partial</span><span className="chip bad">{n(v, "unsupported")} unsupported</span><span className="chip">{n(v, "not_reviewed")} not yet reviewed</span></div>
          <p>The reviewer sees only the claim, the quoted sentence and the paper title. "Supported" raises a fact's strength; nothing is hidden.</p>
        </Card>
        <Card title="Contradictions"><p>{c ? c.note : "…"}</p><p>A fact that a paper denies is stored and paired with whatever asserts it.</p></Card>
      </div>
      <Reveal style={{ marginTop: 56 }}><h3 style={{ marginBottom: 14 }}>How evidence strength is set</h3>
        <div className="rows">{Object.entries(s.confidence_rules).map(([k, val]) => <div className="row" key={k}><div className="grow">{k}</div><span className="soft">{String(val)}</span></div>)}</div>
      </Reveal>
      <Reveal style={{ marginTop: 56 }}><h3 style={{ marginBottom: 14 }}>What is in the Atlas</h3>
        <div className="stats">{Object.entries(nodes).map(([k, val]) => <div className="stat" key={k}><b>{val}</b><span>{k === "PatientOrg" ? "patient groups" : k.toLowerCase() + "s"}</span></div>)}</div>
      </Reveal>
      <p className="foot-note">Research exploration tool. Not medical advice.</p>
    </div>
  );
}
