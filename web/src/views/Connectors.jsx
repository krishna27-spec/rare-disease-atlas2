import { useState } from "react";
import { Card, Gap, Limit, Reveal, Skeletons, Why } from "../components/ui.jsx";
import { useApi } from "../hooks.js";

// Dr. Osei's view: who already links diseases, and through what.
export default function Connectors({ go }) {
  const [scope, setScope] = useState("");
  const [cross, setCross] = useState(true);
  const [diseases] = useApi("/diseases");
  const [res] = useApi(`/connectors?limit=60${scope ? `&disease=${scope}` : ""}${cross && !scope ? "&cross_cluster_only=true" : ""}`);
  return (
    <div className="wrap page">
      <Reveal className="chapter-head">
        <span className="eyebrow">For researchers</span>
        <h2>Who else works on your mechanism.</h2>
        <p className="lead">People and organisations whose trials, grants or papers already span two or more diseases. They are the shortest route between communities that do not know they overlap.</p>
      </Reveal>
      <div className="field">
        <select value={scope} onChange={(e) => setScope(e.target.value)} aria-label="Disease">
          <option value="">All diseases in the Atlas</option>
          {(diseases || []).map((d) => <option key={d.id} value={d.id}>{d.name} and its neighbours</option>)}
        </select>
        {!scope && <button className={"chip" + (cross ? " ok" : "")} onClick={() => setCross(!cross)}>{cross ? "Only links between clusters" : "All links"}</button>}
      </div>
      {!res ? <Skeletons /> : res.no_connector ? <Gap title="No connector found"><p>{res.no_connector}</p></Gap> : (
        <>
          <p className="small muted" style={{ margin: "8px 0 20px" }}>{res.n_people} people</p>
          <Limit items={res.people} n={9} noun="people" render={(p) => (
            <Card key={p.person_id} meta={`${p.n_diseases_in_scope} diseases · via ${p.via.join(", ")}${p.cross_cluster ? " · across clusters" : ""}`} title={p.name}
              foot={<Why ids={p.edge_ids} title={p.name} label="See the records" />}>
              <p>{p.affiliation || "Affiliation not recorded"}</p>
              <div className="chips">{p.links.slice(0, 5).map((l) => <button key={l.id} className="chip" onClick={() => go({ view: "disease", id: l.id, mode: "full" })}>{l.name}</button>)}{p.links.length > 5 && <span className="chip">+{p.links.length - 5}</span>}</div>
            </Card>
          )} />
          {res.organisations.length > 0 && (
            <div style={{ marginTop: 56 }}>
              <Reveal><h3 style={{ marginBottom: 16 }}>Organisations that serve several of these diseases</h3></Reveal>
              <Limit items={res.organisations} n={6} noun="organisations" render={(o) => (
                <Card key={o.org_id} meta={`${o.serves.length} diseases`} title={o.name}
                  foot={<><a className="chip" href={o.url} target="_blank" rel="noreferrer">Visit site ↗</a><Why ids={o.edge_ids} title={o.name} /></>}>
                  <p className="small">{o.serves.slice(0, 5).map((s) => s.name).join(", ")}{o.serves.length > 5 ? "…" : ""}</p>
                </Card>
              )} />
            </div>
          )}
        </>
      )}
    </div>
  );
}
