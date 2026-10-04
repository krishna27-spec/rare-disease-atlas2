import { useState } from "react";
import { q } from "../api.js";
import { Card, Gap, Reveal, Skeletons, Why } from "../components/ui.jsx";
import { useApi } from "../hooks.js";

const TRY = ["heparan sulfate", "lysosome organization", "glycosphingolipid", "cholesterol transport", "HEXB"];

// Priya's view: one mechanism in, every cluster it could reach out, ranked.
export default function Mechanism({ go }) {
  const [text, setText] = useState("heparan sulfate");
  const [query, setQuery] = useState("heparan sulfate");
  const [res] = useApi(`/mechanism?q=${q(query)}`);
  return (
    <div className="wrap page">
      <Reveal className="chapter-head">
        <span className="eyebrow">For therapy scouts</span>
        <h2>One mechanism. Every cluster it could reach.</h2>
        <p className="lead">Enter a pathway, a biological process or a gene. The Atlas ranks disease clusters by how many of their diseases run through it, with the groups, studies and contacts already in place.</p>
      </Reveal>
      <form className="field" onSubmit={(e) => { e.preventDefault(); setQuery(text.trim()); }}>
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Pathway, process or gene" aria-label="Mechanism" />
        <button className="btn" type="submit">Rank clusters</button>
      </form>
      <div className="chips" style={{ marginBottom: 40 }}>{TRY.map((t) => <button key={t} className="chip" onClick={() => { setText(t); setQuery(t); }}>{t}</button>)}</div>

      {!res ? <Skeletons /> : res.no_match ? <Gap title="Nothing matches that mechanism"><p>{res.no_match}</p></Gap> : (
        <>
          <p className="small muted" style={{ marginBottom: 20 }}>Matched {res.pathways.length} mechanism{res.pathways.length > 1 ? "s" : ""}: {res.pathways.slice(0, 4).map((p) => p.name).join(", ")}{res.pathways.length > 4 ? "…" : ""}</p>
          <div className="cards one">
            {res.clusters.map((c, i) => {
              const inf = c.infrastructure, gaps = c.unmet_need;
              return (
                <Card key={c.cluster} meta={`Rank ${i + 1} · cluster ${c.cluster}`} title={`${c.n_matching_diseases} of ${c.cluster_size} diseases run through it`}
                  foot={<Why ids={c.diseases.flatMap((d) => d.edge_ids).slice(0, 14)} title={`Cluster ${c.cluster} and ${query}`} />}>
                  <div className="chips">{c.diseases.map((d) => <button key={d.id} className="chip" onClick={() => go({ view: "disease", id: d.id, mode: "full" })}>{d.name} →</button>)}</div>
                  <dl className="kv" style={{ gridTemplateColumns: "150px 1fr", marginTop: 6 }}>
                    <dt>Patient groups</dt><dd>{c.patient_orgs.length ? c.patient_orgs.slice(0, 4).map((o) => o.name).join(", ") : "none recorded"}</dd>
                    <dt>Infrastructure</dt><dd>{Object.entries(inf).map(([k, v]) => `${v} ${k}${v > 1 ? "s" : ""}`).join(" · ").replace(/studys/g, "studies").replace(/registrys/g, "registries") || "none recorded"}</dd>
                    <dt>Unmet need</dt><dd>{gaps.diseases_with_no_active_interventional_trial.length ? `No active treatment trial for ${gaps.diseases_with_no_active_interventional_trial.join(", ")}` : "Every matching disease has an active treatment trial"}</dd>
                    <dt>Contacts</dt><dd>{c.contacts.length ? c.contacts.slice(0, 3).map((p) => `${p.name}${p.affiliation ? ` (${p.affiliation})` : ""}`).join("; ") : "none recorded"}</dd>
                  </dl>
                </Card>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
