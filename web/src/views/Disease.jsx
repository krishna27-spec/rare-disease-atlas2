import { useEffect, useState } from "react";
import ConstellationGraph from "../components/ConstellationGraph.jsx";
import { Card, Chapter, Gap, Limit, Reveal, Skeletons, Why, pretty } from "../components/ui.jsx";
import { useApi, useEvidence } from "../hooks.js";

const CHAPTERS = [["understand", "Understand"], ["alike", "Who is like us"], ["exists", "What exists"], ["help", "Who can help"], ["next", "What to do next"]];
const list = (xs, n = 3) => xs.slice(0, n).join(", ");
const KIND_ORDER = ["natural history study", "registry", "observational study", "interventional trial"];

function Rail({ ids }) {
  const [on, setOn] = useState(ids[0][0]);
  useEffect(() => {
    const io = new IntersectionObserver((es) => es.forEach((e) => e.isIntersecting && setOn(e.target.id)), { rootMargin: "-40% 0px -55% 0px" });
    ids.forEach(([id]) => { const el = document.getElementById(id); el && io.observe(el); });
    return () => io.disconnect();
  }, [ids]);
  return (
    <nav className="rail" aria-label="Sections">
      {ids.map(([id, label]) => <button key={id} className={on === id ? "on" : ""} onClick={() => document.getElementById(id).scrollIntoView()}><span>{label}</span></button>)}
    </nav>
  );
}

function Org({ o, disease }) {
  return (
    <Card key={o.org_id} meta={o.hand_checked ? "Patient group · checked by a person" : "Patient group · read from its website"} title={o.name}
      foot={<><a className="chip" href={o.url} target="_blank" rel="noreferrer">Visit site ↗</a><Why ids={o.edge_ids} title={`${o.name} and ${disease}`} /></>}>
      {o.registry_mentions && o.registry_mentions[0]
        ? <><p>On its site, about a {o.registry_mentions[0].kind}:</p><div className="quote">“{o.registry_mentions[0].quote.slice(0, 190)}{o.registry_mentions[0].quote.length > 190 ? "…" : ""}”</div></>
        : o.quote ? <div className="quote">“{o.quote.slice(0, 190)}{o.quote.length > 190 ? "…" : ""}”</div> : <p>{o.registry_or_study}</p>}
    </Card>
  );
}

export default function Disease({ id, mode, go }) {
  const simple = mode === "simple";
  const open = useEvidence();
  const [d] = useApi(`/disease/${id}`);
  const [graph] = useApi(`/disease/${id}/graph`);
  const [nb] = useApi(`/disease/${id}/neighbours`);
  const [paths] = useApi(`/disease/${id}/pathways?max_paths=4`);
  const [assets] = useApi(`/disease/${id}/assets`);
  const [conn] = useApi(`/connectors?disease=${id}&limit=12`);
  const [quick] = useApi(`/disease/${id}/next-steps?explain=false`);
  const [full] = useApi(`/disease/${id}/next-steps?explain=true`);
  const [showGraph, setShowGraph] = useState(!simple);
  useEffect(() => { window.scrollTo(0, 0); setShowGraph(!simple); }, [id, simple]);

  if (!d) return <div className="wrap page"><Skeletons /></div>;
  const genes = d.genes.map((g) => g.gene);
  const strong = nb ? nb.neighbours.filter((n) => n.supported) : [];
  const weak = nb ? nb.neighbours.filter((n) => !n.supported) : [];
  const own = assets ? [...assets.own].sort((a, b) => KIND_ORDER.indexOf(a.kind) - KIND_ORDER.indexOf(b.kind)) : [];
  const steps = full && full.steps.length ? full.steps : null;
  const next = full || quick;
  const chapters = simple ? CHAPTERS.filter(([c]) => ["understand", "help", "next"].includes(c)) : CHAPTERS;

  const onNode = (n, ids) => (n.type === "disease" ? go({ view: "disease", id: n.id, mode }) : open(n.label, ids));
  const onEdge = (e) => open("This connection", [e.id]);

  const Help = (
    <Chapter id="help" eyebrow={simple ? "Your community" : "Who can help"}
      title={d.patient_orgs.length ? `${d.patient_orgs.length} patient group${d.patient_orgs.length > 1 ? "s" : ""} work on ${d.name}.` : `No patient group is recorded for ${d.name} yet.`}
      lead={simple ? "These organisations name this disease on their own websites. They are the fastest way to reach other families." : "Organisations, and the researchers whose work already spans this disease and its neighbours."}>
      {d.patient_orgs.length
        ? <Limit items={d.patient_orgs} n={3} noun="groups" render={(o) => <Org key={o.org_id} o={o} disease={d.name} />} />
        : <Gap title="An honest gap"><p>We read the websites of 21 patient organisations and none names this disease more than in passing.</p></Gap>}
      {!simple && conn && conn.people.length > 0 && (
        <div style={{ marginTop: 32 }}>
          <Reveal><h3 style={{ marginBottom: 16 }}>People who already work across these diseases</h3></Reveal>
          <Limit items={conn.people} n={3} noun="people" render={(p) => (
            <Card key={p.person_id} meta={p.via.map((v) => `via a ${v}`).join(" · ")} title={p.name}
              foot={<Why ids={p.edge_ids} title={p.name} label="See the record" />}>
              <p>{p.affiliation || "Affiliation not recorded"}</p>
              <p className="small">Linked to {list(p.links.map((l) => l.name), 4)}{p.links.length > 4 ? ` and ${p.links.length - 4} more` : ""}.</p>
            </Card>
          )} />
        </div>
      )}
    </Chapter>
  );

  return (
    <div className="page">
      <Rail ids={chapters} />
      <div className="wrap">
        <Reveal className="titleblock">
          <span className="eyebrow">{d.group} · cluster of {d.cluster_members.length + 1}</span>
          <h1 style={{ fontSize: "clamp(40px, 5.4vw, 72px)" }}>{d.name}</h1>
          <p className="lead" style={{ margin: "0 auto" }}>
            Caused by variants in the gene <b style={{ color: "var(--text)" }}>{list(genes)}</b>.
            {strong.length > 0 && <> Its closest relatives in the Atlas are {list(strong.map((n) => n.name), 2)}.</>}
          </p>
          <div className="chips" style={{ justifyContent: "center" }}>
            <Why ids={d.genes.flatMap((g) => g.edge_ids)} title={`${list(genes)} and ${d.name}`} label="Why this gene?" />
            <button className="chip" onClick={() => go({ view: "disease", id, mode: simple ? "full" : "simple" })}>{simple ? "Show the full research view" : "Show the simple view"}</button>
          </div>
        </Reveal>
        {showGraph
          ? (graph ? <ConstellationGraph data={graph} onNode={onNode} onEdge={onEdge} /> : <div className="graphshell skeleton" />)
          : <div style={{ textAlign: "center", marginTop: 36 }}><button className="btn ghost" onClick={() => setShowGraph(true)}>See how this connects</button></div>}
      </div>

      <div className="narrow">
        <Chapter id="understand" eyebrow="Understand" title="What the Atlas knows about this disease."
          lead={`Also called ${list(d.synonyms.filter((s) => s.length < 40), 3)}.`}>
          <Reveal className="stats">
            <div className="stat"><b>{d.counts.phenotypes}</b><span>symptoms on record</span></div>
            <div className="stat"><b>{d.counts.trials}</b><span>clinical studies</span></div>
            <div className="stat"><b>{d.counts.grants}</b><span>research grants</span></div>
            <div className="stat"><b>{d.patient_orgs.length}</b><span>patient groups</span></div>
            <div className="stat"><b>{d.counts.facts_from_papers}</b><span>facts read from papers</span></div>
          </Reveal>
          {d.comparison_note && <p className="soft" style={{ marginTop: 24 }}>{d.comparison_note}</p>}
        </Chapter>
      </div>

      {simple && <div className="wrap">{Help}</div>}

      {!simple && (
        <div className="wrap">
          <Chapter id="alike" eyebrow="Who is like us"
            title={strong.length ? `${strong.length} disease${strong.length > 1 ? "s" : ""} share its biology.` : "No disease is similar enough to recommend."}
            lead="Ranked by shared mechanisms and by the symptoms that are unusual enough to be informative. Similarity is computed, so treat it as a lead to check, not a finding.">
            {!nb ? <Skeletons /> : strong.length ? (
              <Limit items={strong} n={3} noun="similar diseases" render={(n) => (
                <Card key={n.id} meta={`Similarity ${n.score.toFixed(2)}${n.same_cluster ? " · same cluster" : ""}`} title={n.name}
                  foot={<><Why ids={n.edge_ids.concat(n.shared_pathways.flatMap((p) => p.edge_ids)).slice(0, 12)} title={`${d.name} and ${n.name}`} /><button className="chip" onClick={() => go({ view: "disease", id: n.id, mode })}>Open →</button></>}>
                  <div className="bar-score"><i style={{ width: `${Math.min(100, n.score * 130)}%` }} /></div>
                  <dl className="kv">
                    <dt>Shares</dt><dd>{n.shared_pathways.length ? list(n.shared_pathways.map((p) => p.name), 2) : "no specific mechanism on record"}</dd>
                    <dt>Symptoms</dt><dd>{list(n.shared_phenotypes.map((p) => p.name), 3) || "none in common"}</dd>
                    <dt>Differs</dt><dd>Gene {list(n.genes_there)} instead of {list(n.genes_here)}{n.only_here.length ? `; only here: ${list(n.only_here.map((p) => p.name), 2)}` : ""}</dd>
                  </dl>
                </Card>
              )} />
            ) : <Gap title="An honest gap"><p>Every disease scored below {nb.threshold}. That means the Atlas cannot justify a comparison yet, not that none exists.</p></Gap>}
            {weak.length > 0 && <p className="small muted" style={{ marginTop: 18 }}>Too weak to recommend: {list(weak.map((n) => `${n.name} (${n.score.toFixed(2)})`), 4)}.</p>}

            {paths && paths.paths[0] && (
              <Reveal style={{ marginTop: 44 }}>
                <h3 style={{ marginBottom: 6 }}>The path that connects them</h3>
                <p className="soft small" style={{ marginBottom: 14 }}>Each arrow is one fact. Click it to see the source.</p>
                <div className="path">
                  {paths.paths[0].steps.map((s, i) => (
                    <div className="hop" key={i}>
                      {i === 0 && <div className="node"><small>Disease</small>{s.from_name}</div>}
                      <button className="link" onClick={() => open(`${s.from_name} ${s.relation} ${s.to_name}`, [s.edge_id])}>{s.relation}</button>
                      <div className="node"><small>{i === 1 ? "Mechanism" : i === 3 ? "Disease" : "Gene"}</small>{s.to_name}</div>
                    </div>
                  ))}
                </div>
                <p className="small muted" style={{ marginTop: 14 }}>{paths.paths[0].check_before_acting}</p>
              </Reveal>
            )}
            {paths && paths.no_route && <Gap title={paths.no_route.message}><p>{paths.no_route.why} What would change this: {paths.no_route.what_would_change_this}</p></Gap>}
          </Chapter>

          <Chapter id="exists" eyebrow="What exists"
            title={own.length ? `${own.length} studies and registries already exist.` : "No study or registry is registered for this disease."}
            lead="Natural history studies and registries first: they are the work a new group would otherwise rebuild.">
            {!assets ? <Skeletons /> : (
              <Limit items={own} n={3} noun="studies" render={(a) => (
                <Card key={a.asset_id} meta={`${a.kind} · ${pretty(a.status) || "status unknown"}`} title={a.title}
                  foot={<><a className="chip" href={a.source_url} target="_blank" rel="noreferrer">{a.asset_id.replace("ASSET:", "")} ↗</a><Why ids={a.edge_ids} title={a.title} /></>}>
                  <p>{a.sponsor || "Sponsor not recorded"}</p>
                </Card>
              )} />
            )}
            {assets && assets.cluster_reusable.length > 0 && (
              <div style={{ marginTop: 36 }}>
                <Reveal><h3 style={{ marginBottom: 16 }}>Built by sister diseases, possibly reusable</h3></Reveal>
                <Limit items={assets.cluster_reusable.filter((a) => a.kind !== "observational study")} n={3} noun="in this cluster" render={(a) => (
                  <Card key={a.asset_id + a.disease.id} meta={`${a.disease.name} · ${a.kind}`} title={a.title}
                    foot={<><a className="chip" href={a.source_url} target="_blank" rel="noreferrer">{a.asset_id.replace("ASSET:", "")} ↗</a><Why ids={a.edge_ids} title={a.title} /></>}>
                    <p>{a.sponsor || "Sponsor not recorded"} · {pretty(a.status)}</p>
                  </Card>
                )} />
              </div>
            )}
          </Chapter>
          {Help}
        </div>
      )}

      <div className="narrow">
        <Chapter id="next" eyebrow="What to do next" title={next && next.no_route ? "No supported next step was found." : "Steps you could take this week."}
          lead="Built only from facts in the graph. Every step names the evidence behind it.">
          {!next ? <Skeletons n={1} /> : next.no_route ? (
            <Gap title={next.no_route.message}>
              <p>What is missing: {next.no_route.what_is_missing.join("; ")}.</p>
              <p style={{ marginTop: 8 }}>{next.no_route.what_would_change_this}</p>
            </Gap>
          ) : (
            <div className="steps">
              {(steps || next.candidates.slice(0, 4).map((c) => `${c.text} [${c.edge_ids.join("][")}]`)).map((line, i) => {
                const ids = line.match(/E[0-9a-f]{12}/g) || [];
                return (
                  <Reveal className="step" key={i} delay={i * 0.06}>
                    <div><p>{line.replace(/\s*\[[^\]]*\]/g, "").trim().replace(/[.\s]+$/, "")}.</p><Why ids={ids} title={`Step ${i + 1}`} label={`Evidence (${ids.length})`} /></div>
                  </Reveal>
                );
              })}
            </div>
          )}
          {next && !next.no_route && (
            <>
              <p className="small muted" style={{ marginTop: 16 }}>{steps ? "Worded in plain language by gpt-oss from the cited facts; every line was checked to cite real evidence." : full ? "Shown as the Atlas found them. The plain-language wording is unavailable right now." : "Writing these in plain language…"}</p>
              <div className="note"><b style={{ color: "var(--text)" }}>Before acting, an expert should check</b><ul>{next.expert_must_check.map((x) => <li key={x}>{x}</li>)}</ul></div>
            </>
          )}
        </Chapter>
      </div>
      <p className="foot-note">Research exploration tool. Not medical advice. Always confirm with clinicians and researchers.</p>
    </div>
  );
}
