import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import ConstellationGraph from "../components/ConstellationGraph.jsx";
import WorldMap from "../components/WorldMap.jsx";
import { Card, Gap, Limit, Skeletons, Why, pretty } from "../components/ui.jsx";
import { useApi, useEvidence } from "../hooks.js";

// One disease, seven views of the same Atlas. Overview says the least; each tab goes one step deeper.
const TABS = [["overview", "Overview"], ["biology", "Biology"], ["connections", "Connections"], ["research", "Research"], ["landscape", "Landscape"], ["communities", "Communities"], ["tenx", "10× route"], ["evidence", "Evidence"]];
const KIND_ORDER = ["natural history study", "registry", "observational study", "interventional trial"];
const LAYERS = ["mechanism", "related", "groups", "symptoms"];
const list = (xs, n = 3) => xs.slice(0, n).join(", ");
const plural = (n, one, many = one + "s") => `${n} ${n === 1 ? one : many}`;
const cut = (s, n = 200) => (s.length > n ? s.slice(0, n) + "…" : s);

const Head = ({ title, sub }) => <header className="view-head"><h2>{title}</h2>{sub && <p className="lead">{sub}</p>}</header>;
const Sec = ({ title, sub, children }) => <section className="sec"><h3>{title}</h3>{sub && <p className="sub">{sub}</p>}{children}</section>;

function Asset({ a, withDisease }) {
  return (
    <Card meta={`${withDisease ? a.disease.name + " · " : ""}${a.kind} · ${pretty(a.status) || "status unknown"}`} title={a.title}
      foot={<><a className="chip" href={a.source_url} target="_blank" rel="noreferrer">{a.asset_id.replace("ASSET:", "")} ↗</a><Why ids={a.edge_ids} title={a.title} /></>}>
      <p>{a.sponsor || "Sponsor not recorded"}</p>
    </Card>
  );
}

function Org({ o, disease }) {
  const reg = o.registry_mentions && o.registry_mentions[0];
  return (
    <Card meta={o.hand_checked ? "Checked by a person" : "Read from its website"} title={o.name}
      foot={<><a className="chip" href={o.url} target="_blank" rel="noreferrer">Visit site ↗</a><Why ids={o.edge_ids} title={`${o.name} and ${disease}`} /></>}>
      {reg ? <><p>From its own website:</p><div className="quote">“{cut(reg.quote)}”</div></>
        : o.quote ? <div className="quote">“{cut(o.quote)}”</div> : <p>{o.registry_or_study}</p>}
    </Card>
  );
}

/* ------------------------------------------------------------------ Overview */
function Overview({ d, nb, assets, conn, tenx, land, setTab }) {
  const strong = nb ? nb.neighbours.filter((n) => n.supported) : [];
  const genes = d.genes.map((g) => g.gene);
  const ev = d.counts.edges_by_evidence_type;
  const nh = assets ? assets.own.filter((a) => a.kind === "natural history study" || a.kind === "registry").length : 0;
  const tiles = [
    ["biology", "Biology", `How ${list(genes)} leads to ${plural(d.counts.phenotypes, "recorded symptom")}.`],
    ["connections", "Connections", strong.length ? `${plural(strong.length, "related disease")} on the map. The closest is ${strong[0].name}.` : "No disease is similar enough to recommend yet."],
    ["research", "Research", `${plural(d.counts.trials, "study", "studies")} and ${plural(d.counts.grants, "grant")}${nh ? `, including ${plural(nh, "natural history study or registry", "natural history studies and registries")}` : ""}.`],
    ["landscape", "Landscape", land ? `${land.milestones.reached} of ${land.milestones.of} milestones toward a treatment reached. Studies in ${plural(land.where.n_countries, "country", "countries")}.` : "How common, how far, how funded, and where."],
    ["communities", "Communities", `${plural(d.patient_orgs.length, "patient organisation")}${conn && conn.n_people ? ` and ${plural(conn.n_people, "researcher")} working across related diseases` : ""}.`],
    ["tenx", "10× route", tenx ? (tenx.supported ? `${plural(tenx.numbers.own, "natural history study", "natural history studies")} here, ${tenx.numbers.relatives} in close relatives to build on.` : "No study to build on yet. See what is missing.") : "A faster route to a natural history study."],
    ["evidence", "Evidence", `${(ev.curated || 0) + (ev.text_mined || 0) + (ev.inferred || 0)} facts: ${ev.curated || 0} verified, ${ev.text_mined || 0} from literature, ${ev.inferred || 0} Atlas-derived.`],
  ];
  return (
    <>
      <p className="lead wide">
        <b>{d.name}</b> is caused by variants in the gene <b>{list(genes)}</b>.
        The Atlas connects it to {plural(strong.length, "related disease")}, {plural(d.counts.trials, "registered study", "registered studies")} and {plural(d.patient_orgs.length, "patient organisation")}. {d.comparison_note}
      </p>
      <div className="chips" style={{ marginTop: 18 }}>
        <Why ids={d.genes.flatMap((g) => g.edge_ids)} title={`${list(genes)} and ${d.name}`} label="Why this gene?" />
        {d.synonyms.filter((s) => s.length < 34).slice(0, 3).map((s) => <span key={s} className="chip">{s}</span>)}
      </div>
      <KeyFacts k={d.key_facts} />
      <div className="stats" style={{ marginTop: 40 }}>
        <div className="stat"><b>{d.counts.phenotypes}</b><span>symptoms on record</span></div>
        <div className="stat"><b>{strong.length}</b><span>close relatives</span></div>
        <div className="stat"><b>{d.counts.trials}</b><span>clinical studies</span></div>
        <div className="stat"><b>{d.counts.grants}</b><span>research grants</span></div>
        <div className="stat"><b>{d.patient_orgs.length}</b><span>patient organisations</span></div>
      </div>
      <Sec title="Where would you like to go next?">
        <div className="tiles">
          {tiles.map(([id, label, text]) => (
            <button key={id} className="tile" onClick={() => setTab(id)}>
              <span className="tile-name">{label}</span><span className="tile-text">{text}</span><span className="tile-go" aria-hidden="true">→</span>
            </button>
          ))}
        </div>
      </Sec>
    </>
  );
}

// Three facts a family asks first, as Orphadata records them. Absent ones are simply not shown.
function KeyFacts({ k }) {
  if (!k) return null;
  const p = k.headline_prevalence, items = [
    p && ["How common", p.value.replace(/ /g, " "), `${p.where}, ${p.measure.toLowerCase()}`],
    k.onset.length && ["Usually starts in", k.onset.join(", "), "age of onset"],
    k.inheritance.length && ["Inherited as", k.inheritance.join(", "), "both parents carry it" ],
  ].filter(Boolean);
  if (!items.length) return null;
  if (items[2] && !/recessive/i.test(k.inheritance.join())) items[2][2] = "pattern of inheritance";
  return (
    <div className="facts">
      {items.map(([label, value, sub]) => <div className="fact" key={label}><span>{label}</span><b>{value}</b><small>{sub}</small></div>)}
      <a className="chip" href={k.source_url} target="_blank" rel="noreferrer">Orphanet ↗</a>
    </div>
  );
}

/* ------------------------------------------------------------------ Biology */
function Biology({ d, id }) {
  const [bio] = useApi(`/disease/${id}/biology`);
  const open = useEvidence();
  if (!bio) return <Skeletons />;
  const g = bio.genes[0], top = bio.pathways.find((p) => p.n_diseases > 1) || bio.pathways[0];
  return (
    <>
      <Head title="How does this disease work?" sub="From the disease to its gene, the biological mechanisms that gene takes part in, and the symptoms people experience." />
      <div className="chain">
        <div className="link-node"><small>Disease</small>{d.name}</div><span className="arrow">→</span>
        <button className="link-node" onClick={() => open(`${g.gene} and ${d.name}`, g.edge_ids)}><small>Gene{g.how_affected ? ` · ${g.how_affected}` : ""}</small>{bio.genes.map((x) => x.gene).join(", ")}</button><span className="arrow">→</span>
        {top && <><button className="link-node" onClick={() => open(top.name, top.edge_ids)}><small>Mechanism</small>{top.name}</button><span className="arrow">→</span></>}
        <div className="link-node"><small>Symptoms</small>{bio.n_symptoms} recorded</div>
      </div>
      <div className="two-col" style={{ marginTop: 8 }}>
        <div>
          <Sec title="Gene">
            <div className="rows">{bio.genes.map((x) => (
              <div className="row" key={x.gene}><div className="grow"><b>{x.gene}</b> <span className="soft">{x.name}</span><div className="sub">{x.how_affected ? `How it is affected: ${x.how_affected}. ` : ""}{x.clinvar_pathogenic_alleles ? `${x.clinvar_pathogenic_alleles} disease-causing variants recorded in ClinVar.` : ""}</div></div><Why ids={x.edge_ids} title={`${x.gene} and ${d.name}`} /></div>
            ))}</div>
          </Sec>
          <Sec title="Mechanisms" sub="The most specific first: a mechanism few diseases share says more than one most of them share.">
            {bio.pathways.length ? <Limit items={bio.pathways} n={6} className="rows" noun="mechanisms" render={(p) => (
              <div className="row" key={p.id + p.gene}><div className="grow">{p.name}<div className="sub">{p.source} · {p.n_diseases === 1 ? "only this disease" : `shared by ${p.n_diseases} diseases in the Atlas`}</div></div><Why ids={p.edge_ids} title={p.name} /></div>
            )} /> : <Gap title="No mechanism on record"><p>Neither Reactome nor Gene Ontology lists a specific process for this gene.</p></Gap>}
          </Sec>
        </div>
        <Sec title="Symptoms" sub="The most distinctive first. Symptoms shared with fewer diseases help tell this one apart.">
          <Limit items={bio.symptoms} n={10} className="rows" noun="symptoms" render={(s) => (
            <div className="row" key={s.id}><div className="grow">{s.name}<div className="sub">{s.n_diseases === 1 ? "only this disease" : `also in ${plural(s.n_diseases - 1, "other")}`}{s.stated_in_a_paper ? " · stated in a paper" : ""}</div></div><Why ids={s.edge_ids} title={`${d.name}: ${s.name}`} /></div>
          )} />
        </Sec>
      </div>
    </>
  );
}

/* ------------------------------------------------------------------ Connections */
function Connections({ d, id, nb, go }) {
  const open = useEvidence();
  const [graph] = useApi(`/disease/${id}/graph`);
  const [paths] = useApi(`/disease/${id}/pathways?max_paths=4`);
  const [layers, setLayers] = useState(() => new Set());
  useEffect(() => {      // the map reveals itself in calm stages: the disease, its mechanisms, then its relatives
    setLayers(new Set());
    const a = setTimeout(() => setLayers(new Set(["mechanism"])), 900), b = setTimeout(() => setLayers(new Set(["mechanism", "related"])), 2100);
    return () => { clearTimeout(a); clearTimeout(b); };
  }, [id]);
  const more = LAYERS.find((l) => !layers.has(l));
  const strong = nb ? nb.neighbours.filter((n) => n.supported) : [], weak = nb ? nb.neighbours.filter((n) => !n.supported) : [];
  const onNode = (n, ids) => (n.type === "disease" ? go({ view: "disease", id: n.id, mode: "connections" }) : open(n.type === "gene" ? n.id : n.label, ids));
  return (
    <>
      <Head title="What is connected to it?" sub="The map starts with the closest links. Expand it to add patient groups and symptoms, or click a line to see why it exists." />
      {graph ? <ConstellationGraph data={graph} show={layers} onNode={onNode} onEdge={(e) => open("This connection", [e.id])} onExpand={more && layers.has("related") ? () => setLayers(new Set([...layers, more])) : undefined} /> : <div className="graphshell skeleton" />}
      <Sec title="Related diseases" sub="Ranked by shared mechanisms and by the symptoms unusual enough to be informative. The Atlas computed these links, so treat them as leads to check.">
        {!nb ? <Skeletons /> : strong.length ? (
          <div className="cards">{strong.map((n) => (
            <Card key={n.id} meta={`Similarity ${n.score.toFixed(2)}${n.same_cluster ? " · same cluster" : ""}`} title={n.name}
              foot={<><Why ids={n.edge_ids.concat(n.shared_pathways.flatMap((p) => p.edge_ids)).slice(0, 12)} title={`${d.name} and ${n.name}`} /><button className="chip" onClick={() => go({ view: "disease", id: n.id, mode: "overview" })}>Open →</button></>}>
              <div className="bar-score"><i style={{ width: `${Math.min(100, n.score * 130)}%` }} /></div>
              <dl className="kv">
                <dt>Shares</dt><dd>{n.shared_pathways.length ? list(n.shared_pathways.map((p) => p.name), 2) : "no specific mechanism on record"}</dd>
                <dt>Symptoms</dt><dd>{list(n.shared_phenotypes.map((p) => p.name), 3) || "none in common"}</dd>
                <dt>Differs</dt><dd>Gene {list(n.genes_there)} instead of {list(n.genes_here)}{n.only_here.length ? `; only here: ${list(n.only_here.map((p) => p.name), 2)}` : ""}</dd>
              </dl>
            </Card>
          ))}</div>
        ) : <Gap title="No supported connection found"><p>Every disease scored below {nb.threshold}. The Atlas cannot justify a comparison yet; that does not mean none exists.</p></Gap>}
        {weak.length > 0 && <p className="small muted" style={{ marginTop: 16 }}>Too weak to recommend: {list(weak.map((n) => `${n.name} (${n.score.toFixed(2)})`), 4)}.</p>}
      </Sec>
      {paths && paths.paths[0] && (
        <Sec title="The path that connects them" sub="Each arrow is one fact. Click it to see the source.">
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
        </Sec>
      )}
      {paths && paths.no_route && <Sec title="Shared mechanism"><Gap title={paths.no_route.message}><p>{paths.no_route.why} What would change this: {paths.no_route.what_would_change_this}</p></Gap></Sec>}
    </>
  );
}

/* ------------------------------------------------------------------ Research */
function Research({ d, id, assets, conn }) {
  const [quick] = useApi(`/disease/${id}/next-steps?explain=false`);
  const [full] = useApi(`/disease/${id}/next-steps?explain=true`);
  if (!assets) return <Skeletons />;
  const own = [...assets.own].sort((a, b) => KIND_ORDER.indexOf(a.kind) - KIND_ORDER.indexOf(b.kind));
  const reuse = own.filter((a) => a.kind === "natural history study" || a.kind === "registry");
  const sister = assets.cluster_reusable.filter((a) => a.kind !== "observational study");
  const rest = own.filter((a) => !reuse.includes(a));
  const steps = full && full.steps.length ? full.steps : null, next = full || quick;
  const people = conn ? conn.people : [];
  return (
    <>
      <Head title="What work already exists?" sub="Studies, resources and people around this disease, with the most reusable first." />
      <div className="stats">
        <div className="stat"><b>{d.counts.trials}</b><span>clinical studies</span></div>
        <div className="stat"><b>{reuse.length}</b><span>natural history studies and registries</span></div>
        <div className="stat"><b>{d.counts.grants}</b><span>research grants</span></div>
        <div className="stat"><b>{d.counts.facts_from_papers}</b><span>facts read from papers</span></div>
      </div>
      <Sec title="Research opportunities" sub="Existing studies and registries this community might join or reuse. Each one needs expert validation before acting.">
        {reuse.length ? <div className="cards">{reuse.slice(0, 6).map((a) => <Asset key={a.asset_id} a={a} />)}</div>
          : <Gap title="No natural history study or registry is registered for this disease"><p>That is the gap a patient group would close first. Sister diseases below may offer a protocol to adapt.</p></Gap>}
      </Sec>
      {sister.length > 0 && <Sec title="Built by related diseases" sub="Possibly reusable: protocols, outcome measures and teams to ask."><Limit items={sister} n={3} noun="in this cluster" render={(a) => <Asset key={a.asset_id + a.disease.id} a={a} withDisease />} /></Sec>}
      <Sec title="Suggested next steps" sub="Built only from facts in the graph. Every step names the evidence behind it.">
        {!next ? <Skeletons n={1} /> : next.no_route ? (
          <Gap title={next.no_route.message}><p>What is missing: {next.no_route.what_is_missing.join("; ")}.</p><p style={{ marginTop: 8 }}>{next.no_route.what_would_change_this}</p></Gap>
        ) : (
          <>
            <div className="steps">
              {(steps || next.candidates.slice(0, 3).map((c) => `${c.text} [${c.edge_ids.join("][")}]`)).map((line, i) => {
                const ids = line.match(/E[0-9a-f]{12}/g) || [];
                return <div className="step" key={i}><div><p>{line.replace(/\s*\[[^\]]*\]/g, "").trim().replace(/[.\s]+$/, "")}.</p><Why ids={ids} title={`Step ${i + 1}`} label={`Evidence (${ids.length})`} /></div></div>;
              })}
            </div>
            <p className="small muted" style={{ marginTop: 14 }}>{steps ? "Worded in plain language by gpt-oss from the cited facts; every line was checked to cite real evidence." : full ? "Shown as the Atlas found them. The plain-language wording is unavailable right now." : "Writing these in plain language…"}</p>
            <div className="note"><b style={{ color: "var(--text)" }}>Before acting, an expert should check</b><ul>{next.expert_must_check.map((x) => <li key={x}>{x}</li>)}</ul></div>
          </>
        )}
      </Sec>
      {rest.length > 0 && (
        <Sec title="Other studies for this disease">
          <Limit items={rest} n={6} className="rows" noun="studies" render={(a) => (
            <div className="row" key={a.asset_id}><div className="grow">{a.title}<div className="sub">{a.kind} · {pretty(a.status) || "status unknown"} · {a.sponsor || "sponsor not recorded"}</div></div><a className="chip" href={a.source_url} target="_blank" rel="noreferrer">{a.asset_id.replace("ASSET:", "")} ↗</a><Why ids={a.edge_ids} title={a.title} /></div>
          )} />
        </Sec>
      )}
      {people.length > 0 && (
        <Sec title="Researchers" sub="People whose trials, grants or papers span this disease and its relatives.">
          <Limit items={people} n={6} className="rows" noun="researchers" render={(p) => (
            <div className="row" key={p.person_id}><div className="grow">{p.name}<div className="sub">{p.affiliation || "Affiliation not recorded"} · via {p.via.join(", ")} · {list(p.links.map((l) => l.name), 3)}{p.links.length > 3 ? ` +${p.links.length - 3}` : ""}</div></div><Why ids={p.edge_ids} title={p.name} label="Records" /></div>
          )} />
        </Sec>
      )}
    </>
  );
}

/* ------------------------------------------------------------------ Landscape */
const usd = (n) => (n >= 1e6 ? `$${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `$${Math.round(n / 1e3)}K` : `$${n}`);
function Landscape({ d, land }) {
  const open = useEvidence();
  const [mode, setMode] = useState("sites");
  if (!land) return <Skeletons />;
  const { milestones: m, trials: t, funding: f, where: w, key_facts: k } = land;
  const maxPhase = Math.max(...t.phases.map((p) => p.n), 1), maxFund = Math.max(...f.in_cluster.map((c) => c.amount), 1);
  const hasPrev = k.prevalence.some((p) => p.per_100k && !["Europe", "Worldwide", "Specific population"].includes(p.where));
  const regions = k.prevalence.filter((p) => ["Europe", "Worldwide"].includes(p.where));
  return (
    <>
      <Head title="Where does this disease stand?" sub="How far it has come on the way to a treatment, what the trials so far show, the public funding on record, and where in the world the work happens. Every figure is a count of registry records." />

      <section className="sec" style={{ marginTop: 0 }}>
        <h3>The road to a treatment</h3>
        <p className="sub">{m.reached} of {m.of} milestones are on record.{m.next_missing ? ` The first one missing: ${m.next_missing.toLowerCase()}.` : " None is missing."} {m.note}</p>
        <div className="road">
          {m.steps.map((s, i) => (
            <button key={s.step} className={"mile" + (s.reached ? " on" : "")} onClick={() => s.reached && open(s.step, s.edge_ids)} title={s.why_it_matters} disabled={!s.reached}>
              <span className="dot">{s.reached ? "✓" : i + 1}</span><b>{s.step}</b><small>{s.reached ? "on record" : "not on record"}</small>
            </button>
          ))}
        </div>
      </section>

      <Sec title="Where in the world" sub={mode === "sites" ? `${w.n_sites} study sites in ${plural(w.n_countries, "country", "countries")}. Larger glows mean more studies in that city; green means one is recruiting now.` : "Countries with a reported figure. Brighter means more common. A dark country has no reported figure, which is not the same as no patients."}>
        <div className="chips" style={{ marginBottom: 14 }}>
          <button className={"chip" + (mode === "sites" ? " sel" : "")} onClick={() => setMode("sites")}>Where studies run</button>
          {hasPrev && <button className={"chip" + (mode === "prevalence" ? " sel" : "")} onClick={() => setMode("prevalence")}>Where it is more common</button>}
        </div>
        <WorldMap cities={w.cities} prevalence={k.prevalence} mode={mode} />
        {mode === "sites" ? (
          <div className="chips" style={{ marginTop: 14 }}>{Object.entries(w.countries).slice(0, 10).map(([c, n]) => <span key={c} className="chip">{c} · {n}</span>)}{w.n_countries > 10 && <span className="chip">+{w.n_countries - 10} more</span>}</div>
        ) : (
          <div className="rows" style={{ marginTop: 14 }}>{k.prevalence.filter((p) => p.per_100k).slice(0, 8).map((p, i) => (
            <div className="row" key={i}><div className="grow">{p.where}<div className="sub">{p.measure}{p.validated ? "" : " · not yet validated"}{p.pmid ? ` · ${/^\d+$/.test(p.pmid) ? "PMID " + p.pmid : p.pmid.replace(/\[.*\]/, "")}` : ""}</div></div><span className="soft">{p.value}</span></div>
          ))}</div>
        )}
        {regions.length > 0 && mode === "prevalence" && <p className="small muted" style={{ marginTop: 10 }}>Regional figures: {regions.map((p) => `${p.where} ${p.value}`).join("; ")}.</p>}
      </Sec>

      {w.recruiting_now.length > 0 && (
        <Sec title="Taking part now" sub="Studies with at least one site recruiting. Check eligibility with the study team.">
          <div className="rows">{w.recruiting_now.map((r) => (
            <div className="row" key={r.nct}><div className="grow">{r.title}<div className="sub">{r.places.join(" · ")}{r.n_sites > r.places.length ? ` · +${r.n_sites - r.places.length} more sites` : ""}</div></div><a className="chip" href={r.source_url} target="_blank" rel="noreferrer">{r.nct} ↗</a><Why ids={r.edge_ids} title={r.title} /></div>
          ))}</div>
        </Sec>
      )}

      <Sec title="How far treatment trials have gone" sub={t.n_interventional ? `${plural(t.n_interventional, "treatment trial")} registered, ${t.participants_enrolled} participants planned or enrolled in total. The furthest stage reached is ${(t.furthest_phase || "not stated").toLowerCase()}.` : "No treatment trial is registered for this disease."}>
        {t.n_interventional > 0 && (
          <div className="two-col">
            <div className="bars">{t.phases.filter((p) => p.phase !== "Early phase 1" || p.n).map((p) => (
              <button className="hbar" key={p.phase} onClick={() => p.n && open(`${p.phase} trials for ${d.name}`, p.edge_ids)} disabled={!p.n}>
                <span>{p.phase}</span><i><em style={{ width: `${(p.n / maxPhase) * 100}%` }} /></i><b>{p.n}</b>
              </button>
            ))}</div>
            <div className="card">
              <span className="meta">Of the trials that have ended</span>
              <h3>{t.finished.ended ? `${t.finished.completed} of ${t.finished.ended} ran to completion` : "None has ended yet"}</h3>
              <p>{t.finished.note}</p>
              <div className="chips">{Object.entries(t.what_was_tested).map(([kind, n]) => <span key={kind} className="chip">{pretty(kind)} · {n}</span>)}<span className="chip">{t.posted_results} posted results</span></div>
            </div>
          </div>
        )}
      </Sec>

      {t.why_stopped.length > 0 && (
        <Sec title="Why trials stopped" sub="In the sponsors' own words, from the registry. Worth reading before designing the next one.">
          <div className="rows">{t.why_stopped.map((x) => (
            <div className="row top" key={x.nct}><div className="grow">{x.title}<div className="quote" style={{ marginTop: 8 }}>“{x.why_stopped}”</div><div className="sub" style={{ marginTop: 6 }}>{pretty(x.status)}{x.phases.length ? ` · ${x.phases.map((ph) => pretty(ph).replace(/phase(\d)/, "phase $1")).join(", ")}` : ""}</div></div><a className="chip" href={x.source_url} target="_blank" rel="noreferrer">{x.nct} ↗</a><Why ids={x.edge_ids} title={x.title} /></div>
          ))}</div>
        </Sec>
      )}

      <Sec title="Public funding on record" sub={f.note}>
        <div className="two-col">
          <div>
            <div className="stats"><div className="stat"><b>{usd(f.total_usd)}</b><span>across {plural(f.n_grants, "NIH grant")}</span></div></div>
            <div className="rows" style={{ marginTop: 20 }}>{f.top.slice(0, 4).map((g) => (
              <div className="row" key={g.grant}><div className="grow">{g.title}<div className="sub">{g.organization} · {g.fiscal_year}</div></div><span className="soft">{usd(g.amount)}</span><Why ids={g.edge_ids} title={g.title} /></div>
            ))}</div>
          </div>
          <div>
            <p className="small soft" style={{ marginBottom: 12 }}>Compared with the diseases in its cluster</p>
            <div className="bars">{f.in_cluster.map((c) => (
              <div className={"hbar" + (c.is_this ? " this" : "")} key={c.id}><span>{c.name}</span><i><em style={{ width: `${(c.amount / maxFund) * 100}%` }} /></i><b>{usd(c.amount)}</b></div>
            ))}</div>
          </div>
        </div>
      </Sec>
    </>
  );
}

/* ------------------------------------------------------------------ Communities */
function Communities({ d, id, nb, conn, go }) {
  const [paths] = useApi(`/disease/${id}/pathways?max_paths=12`);
  const strong = nb ? nb.neighbours.filter((n) => n.supported) : [];
  const mine = new Set(d.patient_orgs.map((o) => o.org_id));
  const theirs = Object.fromEntries((paths ? paths.paths : []).map((p) => [p.to_disease.id, p.what_is_there.patient_orgs]));
  const bridges = conn ? conn.organisations.filter((o) => o.serves.length > 1) : [];
  return (
    <>
      <Head title="Who else is working on this?" sub="Patient organisations for this disease, communities with shared biology, and the groups that already bridge them." />
      <Sec title={`Patient organisations for ${d.name}`} sub="Each one names this disease on its own website. The quote is theirs.">
        {d.patient_orgs.length ? <div className="cards">{d.patient_orgs.map((o) => <Org key={o.org_id} o={o} disease={d.name} />)}</div>
          : <Gap title="No patient organisation on file for this disease"><p>We read the websites of 21 patient organisations and none names it more than in passing. The related communities below may be the closest partners.</p></Gap>}
      </Sec>
      <Sec title="Related communities" sub="Diseases with shared biology. Their families, researchers and studies may be natural partners. These links are Atlas-derived: leads, not conclusions.">
        {strong.length ? <div className="rows">{strong.map((n) => {
          const orgs = theirs[n.id] || [], other = orgs.filter((o) => !mine.has(o.org_id)), same = orgs.filter((o) => mine.has(o.org_id));
          const why = [n.shared_pathways.length && "shares a biological mechanism", n.shared_phenotypes.length && "has similar symptoms"].filter(Boolean).join(" · ");
          return (
            <div className="row" key={n.id}>
              <div className="grow"><b>{n.name}</b><div className="sub">{why || "similar overall"}</div>
                <div className="sub" style={{ color: "var(--text-2)", marginTop: 2 }}>{other.length ? `Their patient groups: ${list(other.map((o) => o.name), 3)}` : same.length ? `Served by the same organisation${same.length > 1 ? "s" : ""}: ${list(same.map((o) => o.name), 3)}` : "No separate patient group on file"}</div></div>
              <Why ids={n.edge_ids.slice(0, 6)} title={`${d.name} and ${n.name}`} /><button className="chip" onClick={() => go({ view: "disease", id: n.id, mode: "communities" })}>Open →</button>
            </div>
          );
        })}</div> : <Gap title="No related community found"><p>No disease in the Atlas is similar enough to suggest a partner community.</p></Gap>}
      </Sec>
      {bridges.length > 0 && (
        <Sec title="Organisations that already bridge these diseases" sub="They serve more than one disease in this neighbourhood, so they are the shortest route between communities.">
          <div className="rows">{bridges.map((o) => (
            <div className="row" key={o.org_id}><div className="grow"><b>{o.name}</b><div className="sub">{list(o.serves.map((s) => s.name), 5)}{o.serves.length > 5 ? "…" : ""}</div></div><a className="chip" href={o.url} target="_blank" rel="noreferrer">Visit site ↗</a><Why ids={o.edge_ids.slice(0, 8)} title={o.name} /></div>
          ))}</div>
        </Sec>
      )}
    </>
  );
}

/* ------------------------------------------------------------------ 10x route */
function TenX({ t }) {
  const open = useEvidence();
  if (!t) return <Skeletons n={2} />;
  const n = t.numbers, r = Math.round;
  const study = (s) => (
    <div className="row" key={s.nct}><div className="grow">{s.title}<div className="sub">{s.disease} · {pretty(s.status)} · {s.start || "?"} to {s.completion || "?"}{s.months ? ` · ${r(s.months)} months` : ""}{s.enrollment ? ` · ${s.enrollment} enrolled` : ""} · {s.sponsor}</div></div><a className="chip" href={s.source_url} target="_blank" rel="noreferrer">{s.nct} ↗</a><button className="chip why" onClick={() => open(s.title, s.edge_ids)}>Why?</button></div>
  );
  return (
    <>
      <Head title="A faster route to a natural history study" sub={`${t.why_it_matters} It is the milestone most patient groups must reach first. This is what building it from zero looks like for ${t.disease.name}, against what could be reused.`} />
      <div className="stats">
        <div className="stat"><b>{n.own}</b><span>registered for this disease</span></div>
        <div className="stat"><b>{n.relatives}</b><span>in close relatives</span></div>
        <div className="stat"><b>{n.median_months ? r(n.median_months) : "–"}</b><span>months, median of {n.completed} completed</span></div>
        <div className="stat"><b>{n.median_enrollment ? r(n.median_enrollment) : "–"}</b><span>participants, median</span></div>
      </div>
      <p className="small muted" style={{ marginTop: 12 }}>Durations cover {n.basis}.</p>
      <div className="two-col" style={{ marginTop: 32 }}>
        <div className="card"><span className="meta">Usual route</span><h3>Build it from scratch</h3>
          <ul>{t.usual_route.map((x) => <li key={x}>{x}</li>)}{n.completed > 0 && <li>Completed studies ran {r(n.min_months)} to {r(n.max_months)} months.</li>}</ul>
          <div className="foot"><a className="chip" href={t.usual_route_source.url} target="_blank" rel="noreferrer">FDA guidance ↗</a></div>
        </div>
        <div className={"card" + (t.supported ? " accent" : "")}><span className="meta">Atlas route</span><h3>{t.supported ? "Reuse what already exists" : "Nothing to reuse yet"}</h3>
          <ul>{t.atlas_route.map((x) => <li key={x}>{x}</li>)}</ul>
        </div>
      </div>
      {t.own_studies.length > 0 && <Sec title="Already registered for this disease" sub="Check these first."><div className="rows">{t.own_studies.map(study)}</div></Sec>}
      {t.relative_studies.length > 0 && <Sec title="In close relatives" sub="Protocols and outcome measures to learn from."><Limit items={t.relative_studies} n={5} className="rows" noun="studies" render={study} /></Sec>}
      <div className="two-col" style={{ marginTop: 40 }}>
        <div className="note" style={{ marginTop: 0 }}><b style={{ color: "var(--text)" }}>Assumptions</b><ul>{t.assumptions.map((x) => <li key={x}>{x}</li>)}</ul></div>
        <div className="note" style={{ marginTop: 0, borderColor: "rgba(103,198,214,.4)" }}><b style={{ color: "var(--text)" }}>What must be validated next</b><ul>{t.validate_next.map((x) => <li key={x}>{x}</li>)}</ul></div>
      </div>
      <p className="small muted" style={{ marginTop: 14 }}>Durations are registered start to completion on ClinicalTrials.gov, retrieved {t.retrieved}. No time or cost saving is claimed, because there is no cited figure for one.</p>
    </>
  );
}

/* ------------------------------------------------------------------ Evidence */
const VERDICT = { supported: ["Second model agrees", "ok"], partial: ["Partly supported", "warn"], unsupported: ["Not supported by the quote", "bad"], not_reviewed: ["Not yet reviewed", ""] };
function EvidenceView({ d, go }) {
  const ev = d.counts.edges_by_evidence_type, facts = d.facts_from_papers;
  return (
    <>
      <Head title="Why trust this?" sub="Every statement about this disease is a fact in the graph with its source, date and strength. Nothing is shown without one." />
      <div className="cards">
        <Card meta="Verified source" title={`${ev.curated || 0} facts`}><p>Copied from a curated database or registry.</p><span className="chip ok">Solid line on the map</span></Card>
        <Card meta="Research literature" title={`${ev.text_mined || 0} facts`}><p>Read from a paper or an organisation's website. Kept only if the exact sentence is in the source.</p><span className="chip info">Dotted line</span></Card>
        <Card meta="Atlas-derived" title={`${ev.inferred || 0} links`}><p>Computed similarity to other diseases. A lead to check, not an observation.</p><span className="chip warn">Dashed line</span></Card>
      </div>
      <Sec title="What papers say about this disease" sub="Read by gpt-oss, then checked by a second model against the quoted sentence.">
        {facts.length ? <Limit items={facts} n={6} className="rows" noun="facts" render={(f) => {
          const [label, tone] = VERDICT[f.reviewer_verdict] || VERDICT.not_reviewed;
          return (
            <div className="row top" key={f.edge_id}><div className="grow"><b>{f.predicate.startsWith("gene") ? `${f.subject} is linked to ${f.object_name}` : `${f.subject_name}: ${f.object_name}`}</b><div className="quote" style={{ marginTop: 8 }}>“{cut(f.evidence_text, 260)}”</div></div><span className={"chip " + tone}>{label}</span><Why ids={[f.edge_id]} title={f.object_name} label="Source" /></div>
          );
        }} /> : <Gap title="No paper has been read for this disease yet"><p>The abstracts are collected; reading them is limited by the free model quota. The verified facts above do not depend on it.</p></Gap>}
      </Sec>
      <div className="deeper"><button className="chip" onClick={() => go({ view: "about" })}>How the whole Atlas checks its evidence →</button></div>
    </>
  );
}

export default function Disease({ id, mode, go }) {
  const tab = TABS.some(([t]) => t === mode) ? mode : "overview";
  const setTab = (t) => go({ view: "disease", id, mode: t });
  const [d] = useApi(`/disease/${id}`);
  const [nb] = useApi(`/disease/${id}/neighbours`);
  const [assets] = useApi(`/disease/${id}/assets`);
  const [conn] = useApi(`/connectors?disease=${id}&limit=12`);
  const [tenx] = useApi(`/disease/${id}/ten-x`);
  const [land] = useApi(`/disease/${id}/landscape`);
  useEffect(() => { window.scrollTo(0, 0); }, [id]);
  useEffect(() => {      // changing tab keeps the tab bar where it is instead of jumping to the top of the page
    const head = document.querySelector(".dhead");
    if (!head) return;
    const y = head.getBoundingClientRect().bottom + window.scrollY + 30 - 64;
    if (window.scrollY > y) window.scrollTo(0, y);
  }, [tab]);
  if (!d) return <div className="wrap page"><Skeletons /></div>;
  return (
    <div className="page disease">
      <div className="wrap dhead">
        <span className="eyebrow">Rare disease · {d.group}</span>
        <h1>{d.name}</h1>
        <span className="gene-tag"><b>{d.genes.map((g) => g.gene).join(", ")}</b> causal gene</span>
      </div>
      <nav className="tabs" aria-label="Views of this disease">
        <div className="wrap tabs-in">
          {TABS.map(([t, label]) => (
            <button key={t} className={"tab" + (t === tab ? " on" : "")} onClick={() => setTab(t)} aria-current={t === tab ? "page" : undefined}>
              {label}{t === tab && <motion.span layoutId="tab-line" className="tab-line" transition={{ type: "spring", stiffness: 420, damping: 36 }} />}
            </button>
          ))}
        </div>
      </nav>
      <motion.div key={tab} className="wrap view" initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}>
        {tab === "overview" && <Overview d={d} nb={nb} assets={assets} conn={conn} tenx={tenx} land={land} setTab={setTab} />}
        {tab === "biology" && <Biology d={d} id={id} />}
        {tab === "connections" && <Connections d={d} id={id} nb={nb} go={go} />}
        {tab === "research" && <Research d={d} id={id} assets={assets} conn={conn} />}
        {tab === "landscape" && <Landscape d={d} land={land} />}
        {tab === "communities" && <Communities d={d} id={id} nb={nb} conn={conn} go={go} />}
        {tab === "tenx" && <TenX t={tenx} />}
        {tab === "evidence" && <EvidenceView d={d} go={go} />}
      </motion.div>
      <p className="foot-note">Research exploration tool. Not medical advice. Always confirm with clinicians and researchers.</p>
    </div>
  );
}
