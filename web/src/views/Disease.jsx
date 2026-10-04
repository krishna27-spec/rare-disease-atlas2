import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";
import ConstellationGraph from "../components/ConstellationGraph.jsx";
import { Card, Gap, Limit, Reveal, Skeletons, Why, pretty } from "../components/ui.jsx";
import { useApi, useEvidence } from "../hooks.js";

// The page starts minimal: the disease, its gene, and the brief's questions with a one-line answer each.
// Opening a question reveals its depth and grows the matching layer of the map. Nothing else appears unasked.
const list = (xs, n = 3) => xs.slice(0, n).join(", ");
const KIND_ORDER = ["natural history study", "registry", "observational study", "interventional trial"];
const LAYERS = ["mechanism", "related", "groups", "symptoms"];
const GROWS = { alike: ["mechanism", "related"], help: ["groups"], biology: ["mechanism", "symptoms"] };
const plural = (n, one, many = one + "s") => `${n} ${n === 1 ? one : many}`;
const cut = (s, n = 190) => (s.length > n ? s.slice(0, n) + "…" : s);

function Question({ id, eyebrow, title, answer, openSet, toggle, children }) {
  const open = openSet.has(id);
  return (
    <section id={id} className={"q" + (open ? " open" : "")}>
      <button className="q-head" onClick={() => toggle(id)} aria-expanded={open}>
        <span className="eyebrow">{eyebrow}</span>
        <h3>{title}</h3>
        <p>{answer}</p>
        <span className="plus" aria-hidden="true">+</span>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}>
            <div className="q-body">{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}

function Org({ o, disease }) {
  const reg = o.registry_mentions && o.registry_mentions[0];
  return (
    <Card meta={o.hand_checked ? "Patient group · checked by a person" : "Patient group · read from its website"} title={o.name}
      foot={<><a className="chip" href={o.url} target="_blank" rel="noreferrer">Visit site ↗</a><Why ids={o.edge_ids} title={`${o.name} and ${disease}`} /></>}>
      {reg ? <><p>On its site, about a {reg.kind}:</p><div className="quote">“{cut(reg.quote)}”</div></>
        : o.quote ? <div className="quote">“{cut(o.quote)}”</div> : <p>{o.registry_or_study}</p>}
    </Card>
  );
}

function Asset({ a, withDisease }) {
  return (
    <Card meta={`${withDisease ? a.disease.name + " · " : ""}${a.kind} · ${pretty(a.status) || "status unknown"}`} title={a.title}
      foot={<><a className="chip" href={a.source_url} target="_blank" rel="noreferrer">{a.asset_id.replace("ASSET:", "")} ↗</a><Why ids={a.edge_ids} title={a.title} /></>}>
      <p>{a.sponsor || "Sponsor not recorded"}</p>
    </Card>
  );
}

function TenX() {
  const [t] = useApi("/ten-x");
  const open = useEvidence();
  if (!t) return <Skeletons n={2} />;
  const n = t.numbers;
  return (
    <>
      <p className="soft">{t.why_it_matters}</p>
      <div className="stats" style={{ margin: "24px 0 28px" }}>
        <div className="stat"><b>{n.studies}</b><span>Sanfilippo natural history studies</span></div>
        <div className="stat"><b>{n.completed}</b><span>completed</span></div>
        <div className="stat"><b>{Math.round(n.median_months)}</b><span>months, median duration</span></div>
        <div className="stat"><b>{n.already_for_mps_iiic}</b><span>already for MPS IIIC</span></div>
      </div>
      <div className="two-col">
        <div className="card"><span className="meta">Usual route</span><h3>Build it from scratch</h3>
          <ul>{t.usual_route.map((x) => <li key={x}>{x}</li>)}<li>Completed studies ran {Math.round(n.min_months)} to {Math.round(n.max_months)} months, with a median of {Math.round(n.median_enrollment)} children enrolled.</li></ul>
          <div className="foot"><a className="chip" href={t.usual_route_source.url} target="_blank" rel="noreferrer">FDA guidance ↗</a></div>
        </div>
        <div className="card accent"><span className="meta">Atlas route</span><h3>Reuse what sister diseases built</h3>
          <ul>{t.atlas_route.map((x) => <li key={x}>{x}</li>)}</ul>
          <div className="foot">{t.own_studies.map((s) => <button key={s.nct} className="chip why" onClick={() => open(s.title, s.edge_ids)}>{s.nct} · {pretty(s.status)}</button>)}</div>
        </div>
      </div>
      <div className="two-col" style={{ marginTop: 16 }}>
        <div className="note" style={{ marginTop: 0 }}><b style={{ color: "var(--text)" }}>Assumptions</b><ul>{t.assumptions.map((x) => <li key={x}>{x}</li>)}</ul></div>
        <div className="note" style={{ marginTop: 0, borderColor: "rgba(103,198,214,.4)" }}><b style={{ color: "var(--text)" }}>What must be validated next</b><ul>{t.validate_next.map((x) => <li key={x}>{x}</li>)}</ul></div>
      </div>
      <p className="small muted" style={{ marginTop: 14 }}>Durations are registered start to completion on ClinicalTrials.gov, retrieved {t.retrieved}. No time or cost saving is claimed.</p>
    </>
  );
}

export default function Disease({ id, mode, go }) {
  const simple = mode === "simple";
  const openEvidence = useEvidence();
  const [open, setOpen] = useState(() => new Set(simple ? ["help", "next"] : []));
  const [layers, setLayers] = useState(() => new Set());
  useEffect(() => { setOpen(new Set(simple ? ["help", "next"] : [])); setLayers(new Set()); window.scrollTo(0, 0); }, [id, simple]);

  const [d] = useApi(`/disease/${id}`);
  const [graph] = useApi(`/disease/${id}/graph`);
  const [nb] = useApi(`/disease/${id}/neighbours`);
  const [paths] = useApi(`/disease/${id}/pathways?max_paths=4`);
  const [assets] = useApi(`/disease/${id}/assets`);
  const [conn] = useApi(`/connectors?disease=${id}&limit=12`);
  const [bio] = useApi(open.has("biology") ? `/disease/${id}/biology` : null);
  const [quick] = useApi(`/disease/${id}/next-steps?explain=false`);
  const [full] = useApi(open.has("next") ? `/disease/${id}/next-steps?explain=true` : null);

  const toggle = (sec) => {
    const was = open.has(sec), next = new Set(open);
    was ? next.delete(sec) : next.add(sec);
    setOpen(next);
    if (!was) {
      if (GROWS[sec]) setLayers(new Set([...layers, ...GROWS[sec]]));
      setTimeout(() => document.getElementById(sec)?.scrollIntoView({ behavior: "smooth", block: "start" }), 80);
    }
  };
  const nextLayer = LAYERS.find((l) => !layers.has(l));
  const show = useMemo(() => layers, [layers]);

  if (!d) return <div className="wrap page"><Skeletons /></div>;
  const genes = d.genes.map((g) => g.gene);
  const strong = nb ? nb.neighbours.filter((n) => n.supported) : [];
  const weak = nb ? nb.neighbours.filter((n) => !n.supported) : [];
  const own = assets ? [...assets.own].sort((a, b) => KIND_ORDER.indexOf(a.kind) - KIND_ORDER.indexOf(b.kind)) : [];
  const nh = own.filter((a) => a.kind === "natural history study" || a.kind === "registry").length;
  const reusable = assets ? assets.cluster_reusable.filter((a) => a.kind !== "observational study") : [];
  const steps = full && full.steps.length ? full.steps : null;
  const next = full || quick;
  const people = conn ? conn.people : [];

  const onNode = (n, ids) => (n.type === "disease" ? go({ view: "disease", id: n.id, mode }) : openEvidence(n.type === "gene" ? n.id : n.label, ids));
  const onEdge = (e) => openEvidence("This connection", [e.id]);

  return (
    <div className="page">
      <div className="wrap">
        <Reveal className="titleblock">
          <span className="eyebrow">{d.group} · cluster of {d.cluster_members.length + 1}</span>
          <h1 style={{ fontSize: "clamp(40px, 5.4vw, 72px)" }}>{d.name}</h1>
          <p className="lead" style={{ margin: "0 auto" }}>Caused by variants in the gene <b style={{ color: "var(--text)" }}>{list(genes)}</b>. {d.comparison_note || "Open a question below and the map grows with it."}</p>
          <div className="chips" style={{ justifyContent: "center" }}>
            <Why ids={d.genes.flatMap((g) => g.edge_ids)} title={`${list(genes)} and ${d.name}`} label="Why this gene?" />
            <button className="chip" onClick={() => go({ view: "disease", id, mode: simple ? "full" : "simple" })}>{simple ? "Show the full research view" : "Show the family view"}</button>
          </div>
        </Reveal>
        {graph ? <ConstellationGraph data={graph} show={show} onNode={onNode} onEdge={onEdge} onExpand={nextLayer ? () => setLayers(new Set([...layers, nextLayer])) : undefined} /> : <div className="graphshell skeleton" />}
      </div>

      <div className="wrap questions">
        {!simple && (
          <Question openSet={open} toggle={toggle} id="alike" eyebrow="Question 1" title="Who shares our disease characteristics?"
            answer={!nb ? "Looking…" : strong.length ? `${plural(strong.length, "disease")} share its biology. The closest is ${strong[0].name}.` : "No disease is similar enough to recommend. That is an honest gap."}>
            <p className="soft small">Ranked by shared mechanisms and by the symptoms unusual enough to be informative. Similarity is Atlas-derived: a lead to check, not a finding.</p>
            {strong.length > 0 ? (
              <div style={{ marginTop: 20 }}>
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
              </div>
            ) : nb && <Gap title="An honest gap"><p>Every disease scored below {nb.threshold}. The Atlas cannot justify a comparison yet; that does not mean none exists.</p></Gap>}
            {weak.length > 0 && <p className="small muted" style={{ marginTop: 16 }}>Too weak to recommend: {list(weak.map((n) => `${n.name} (${n.score.toFixed(2)})`), 4)}.</p>}
            {paths && paths.paths[0] && (
              <>
                <h4>The path that connects them</h4>
                <p className="soft small" style={{ marginBottom: 12 }}>Each arrow is one fact. Click it to see the source.</p>
                <div className="path">
                  {paths.paths[0].steps.map((s, i) => (
                    <div className="hop" key={i}>
                      {i === 0 && <div className="node"><small>Disease</small>{s.from_name}</div>}
                      <button className="link" onClick={() => openEvidence(`${s.from_name} ${s.relation} ${s.to_name}`, [s.edge_id])}>{s.relation}</button>
                      <div className="node"><small>{i === 1 ? "Mechanism" : i === 3 ? "Disease" : "Gene"}</small>{s.to_name}</div>
                    </div>
                  ))}
                </div>
                <p className="small muted" style={{ marginTop: 14 }}>{paths.paths[0].check_before_acting}</p>
              </>
            )}
            {paths && paths.no_route && <div style={{ marginTop: 20 }}><Gap title={paths.no_route.message}><p>{paths.no_route.why} What would change this: {paths.no_route.what_would_change_this}</p></Gap></div>}
          </Question>
        )}

        {!simple && (
          <Question openSet={open} toggle={toggle} id="exists" eyebrow="Question 2" title="What useful work already exists?"
            answer={!assets ? "Looking…" : own.length ? `${plural(own.length, "study", "studies")} for this disease, ${nh} of them natural history studies or registries. ${reusable.length} more in sister diseases.` : "No study or registry is registered for this disease."}>
            <p className="soft small">Natural history studies and registries first: they are the work a new group would otherwise rebuild.</p>
            <div style={{ marginTop: 20 }}><Limit items={own} n={3} noun="studies" render={(a) => <Asset key={a.asset_id} a={a} />} /></div>
            {reusable.length > 0 && <><h4>Built by sister diseases, possibly reusable</h4><Limit items={reusable} n={3} noun="in this cluster" render={(a) => <Asset key={a.asset_id + a.disease.id} a={a} withDisease />} /></>}
          </Question>
        )}

        <Question openSet={open} toggle={toggle} id="help" eyebrow={simple ? "Your community" : "Who can help"} title={simple ? "Who is already working on this?" : "Who could we work with?"}
          answer={`${plural(d.patient_orgs.length, "patient group")}${people.length ? ` and ${plural(conn.n_people, "researcher")} whose work spans these diseases` : ""}.`}>
          {d.patient_orgs.length
            ? <Limit items={d.patient_orgs} n={3} noun="groups" render={(o) => <Org key={o.org_id} o={o} disease={d.name} />} />
            : <Gap title="An honest gap"><p>We read the websites of 21 patient organisations and none names this disease more than in passing.</p></Gap>}
          {!simple && people.length > 0 && (
            <>
              <h4>People who already work across these diseases</h4>
              <Limit items={people} n={3} noun="people" render={(p) => (
                <Card key={p.person_id} meta={p.via.map((v) => `via a ${v}`).join(" · ")} title={p.name} foot={<Why ids={p.edge_ids} title={p.name} label="See the record" />}>
                  <p>{p.affiliation || "Affiliation not recorded"}</p>
                  <p className="small">Linked to {list(p.links.map((l) => l.name), 4)}{p.links.length > 4 ? ` and ${p.links.length - 4} more` : ""}.</p>
                </Card>
              )} />
            </>
          )}
        </Question>

        <Question openSet={open} toggle={toggle} id="next" eyebrow={simple ? "What you can do" : "Question 3"} title="What should we do together next?"
          answer={!next ? "Looking…" : next.no_route ? "No supported next step was found. See what is missing." : `${Math.min(next.candidates.length, 3)} steps you could take this week, each with its evidence.`}>
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
        </Question>

        {!simple && (
          <Question openSet={open} toggle={toggle} id="biology" eyebrow="Go deeper" title="The biology"
            answer={`Gene ${list(genes)}, ${plural(d.counts.phenotypes, "symptom")} on record, ${plural(d.counts.facts_from_papers, "fact")} read from papers.`}>
            {!bio ? <Skeletons n={2} /> : (
              <div className="two-col">
                <div>
                  <h4 style={{ marginTop: 8 }}>Gene</h4>
                  <div className="rows">{bio.genes.map((g) => (
                    <div className="row" key={g.gene}><div className="grow"><b>{g.gene}</b> <span className="soft">{g.name}</span><div className="sub">{g.how_affected ? `How it is affected: ${g.how_affected}. ` : ""}{g.clinvar_pathogenic_alleles ? `${g.clinvar_pathogenic_alleles} disease-causing variants recorded in ClinVar.` : ""}</div></div><Why ids={g.edge_ids} title={`${g.gene} and ${d.name}`} /></div>
                  ))}</div>
                  <h4>Mechanisms, most specific first</h4>
                  <Limit items={bio.pathways} n={5} className="rows" noun="mechanisms" render={(p) => (
                    <div className="row" key={p.id + p.gene}><div className="grow">{p.name}<div className="sub">{p.source} · shared by {plural(p.n_diseases, "disease")} in the Atlas</div></div><Why ids={p.edge_ids} title={p.name} /></div>
                  )} />
                </div>
                <div>
                  <h4 style={{ marginTop: 8 }}>Symptoms, most distinctive first</h4>
                  <Limit items={bio.symptoms} n={8} className="rows" noun="symptoms" render={(s) => (
                    <div className="row" key={s.id}><div className="grow">{s.name}<div className="sub">{s.n_diseases === 1 ? "only this disease" : `also in ${s.n_diseases - 1} other${s.n_diseases > 2 ? "s" : ""}`}{s.stated_in_a_paper ? " · stated in a paper" : ""}</div></div><Why ids={s.edge_ids} title={`${d.name}: ${s.name}`} /></div>
                  )} />
                </div>
              </div>
            )}
          </Question>
        )}

        {!simple && d.group === "Sanfilippo" && (
          <Question openSet={open} toggle={toggle} id="tenx" eyebrow="Go deeper" title="The 10× route" answer="A worked case: starting a natural history study for MPS IIIC without starting from zero.">
            <TenX />
          </Question>
        )}

        <div className="deeper">
          {simple && <button className="chip" onClick={() => go({ view: "disease", id, mode: "full" })}>See the research view: similar diseases, studies, biology →</button>}
          <button className="chip" onClick={() => go({ view: "about" })}>How the evidence is checked →</button>
        </div>
      </div>
      <p className="foot-note">Research exploration tool. Not medical advice. Always confirm with clinicians and researchers.</p>
    </div>
  );
}
