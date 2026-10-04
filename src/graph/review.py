"""Second opinion on every text-mined edge: a bigger model (gpt-oss-120b) checks the quote really supports the claim.

Run:  uv run python -m src.graph.review             (asks the LLM about edges not reviewed yet)
      uv run python -m src.graph.review --limit 0   (no LLM calls: only applies verdicts already cached; used by build)
Reads  data/graph/{nodes,edges}.parquet, data/cache/reviews.jsonl (the cache: one verdict per edge_id)
Writes data/graph/edges.parquet: `reviewer_verdict` = supported | partial | unsupported | not_reviewed, and for
       supported edges confidence +0.15 (capped at 0.95), as the confidence rules in the README say.

The reviewer sees only the claim, the quoted sentence, the paper title and the curated alias names, never the
first model's reasoning. Edge IDs are stable,
so a rebuild keeps its verdicts. Run after src.graph.text_mined and before src.graph.connections.
"""
import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal

import pandas as pd
from pydantic import BaseModel

from src.etl.genes import gene_aliases
from src.etl.terms import SPECIFIC
from src.graph.schema import EDGE_SCHEMA, GRAPH_DIR, write_table
from src.graph.text_mined import FAMILY_PENALTY, phenotype_lookup
from src.llm import chat_json, last_model

CACHE = Path("data/cache/reviews.jsonl")
BONUS, CAP = 0.15, 0.95
BASE = {"stated": 0.7, "suggested": 0.5, "denied": 0.7}
WORDING = {"gene_associated_with_disease": "Mutations in the gene {s} cause or are linked to the disease {o}.",
           "has_phenotype": "Patients with the disease {s} have the symptom or clinical sign: {o}.",
           "not_gene_associated_with_disease": "The gene {s} is NOT linked to the disease {o}.",
           "not_has_phenotype": "Patients with the disease {s} do NOT have the symptom or clinical sign: {o}."}

VERSION = 3   # raise when the claim wording or prompt changes: older verdicts are then asked again
MAX_NAMES = 14

SYSTEM = """You check one claim against one sentence quoted from a scientific abstract.
The claim lists other names for the gene, disease or symptom ("also called"): treat every listed name as the
same thing. That name list is the only outside knowledge you may use.
You also get the paper's title. A sentence that does not repeat the disease name is about the disease in the title,
unless the sentence itself is about something else (another disease, an animal model, a treatment).
Answer with JSON {"verdict": ..., "reason": ...}.
- "supported": the sentence, read on its own, clearly says the claim.
- "partial": the sentence is about the claim but is weaker, narrower or hedged (one patient, an animal model,
  "may", "suggests"), or it needs outside knowledge to connect the two.
- "unsupported": the sentence does not say the claim, or says something different.
Judge only from the sentence. Do not use outside knowledge. reason: one short sentence."""


class Verdict(BaseModel):
    verdict: Literal["supported", "partial", "unsupported"]
    reason: str


def review_one(job: dict) -> dict | None:
    out = chat_json([{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": f"Paper title: {job['title']}\nClaim: {job['claim']}\n"
                                                 f"Sentence: \"{job['quote']}\""}],
                    Verdict, tier="quality", effort="low")
    if out is None:
        return None
    return {"edge_id": job["edge_id"], "v": VERSION, "verdict": out.verdict, "reason": out.reason,
            "model": last_model(),
            "date": pd.Timestamp.today().date().isoformat()}


def certainty(method: str) -> str:
    return method.rsplit("certainty: ", 1)[-1] if "certainty: " in (method or "") else "stated"


def labels(nodes: pd.DataFrame) -> dict[str, str]:
    """node id -> 'name (also called: ...)', from the curated dictionaries (HGNC, MONDO, HPO), not from the LLM."""
    genes = set(nodes[nodes.node_type == "Gene"].node_id)
    also: dict[str, list[str]] = {}
    for alias, sym in gene_aliases(genes).items():
        also.setdefault(sym, []).append(alias)
    for alias, hp_id in phenotype_lookup(set(nodes[nodes.node_type == "Phenotype"].node_id)).items():
        also.setdefault(hp_id, []).append(alias)
    for d in nodes[nodes.node_type == "Disease"].itertuples():
        also[d.node_id] = SPECIFIC.get(d.node_id, []) + list(d.synonyms)   # our own search terms first
    out = {}
    for n in nodes.itertuples():
        main_name = n.node_id if n.node_type == "Gene" else n.name
        others = [a for a in dict.fromkeys(also.get(n.node_id, [])) if a.lower() != main_name.lower()][:MAX_NAMES]
        out[n.node_id] = main_name + (f" (also called: {'; '.join(others)})" if others else "")
    return out


def main(limit: int | None = None, workers: int = 2, write: bool = True) -> None:
    nodes = pd.read_parquet(GRAPH_DIR / "nodes.parquet")
    edges = pd.read_parquet(GRAPH_DIR / "edges.parquet")
    older, done = {}, {}   # verdicts from an earlier prompt version are kept until the edge is asked again
    if CACHE.exists():
        for l in CACHE.read_text().splitlines():
            r = json.loads(l)
            (done if r.get("v", 1) == VERSION else older)[r["edge_id"]] = r
    name = labels(nodes) if limit != 0 else dict(zip(nodes.node_id, nodes.name))
    tm = edges[(edges.evidence_type == "text_mined") & (edges.source == "PubMed")]
    title = dict(zip(nodes.node_id, nodes.name))
    jobs = [{"edge_id": e.edge_id, "quote": e.evidence_text, "title": title.get(e.source_record.split("|")[0], ""),
             "claim": WORDING[e.predicate].format(s=name.get(e.subject, e.subject), o=name.get(e.object, e.object))}
            for e in tm.itertuples() if e.edge_id not in done and e.predicate in WORDING][:limit]
    print(f"{len(tm)} text-mined edges, {len(set(tm.edge_id) & set(done))} already reviewed, asking about {len(jobs)}")
    if jobs:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        try:
            with ThreadPoolExecutor(workers) as pool, CACHE.open("a") as f:
                for res in pool.map(review_one, jobs):
                    if res:                      # a failed call is simply asked again on the next run
                        done[res["edge_id"]] = res
                        f.write(json.dumps(res) + "\n")
                        f.flush()
        except RuntimeError as e:                # no provider available: keep what we have, the rest stays not_reviewed
            print(f"  stopped early: {e}")

    if not write:        # only fill the cache; a later build applies it (safe while other steps rewrite the graph)
        print(f"{len(done)} verdicts cached for the current prompt version")
        return
    verdicts, confs = [], []
    for e in edges.itertuples():
        if e.evidence_type != "text_mined" or e.source != "PubMed":
            verdicts.append(e.reviewer_verdict), confs.append(e.confidence)
            continue
        v = (done.get(e.edge_id) or older.get(e.edge_id, {})).get("verdict", "not_reviewed")
        base = BASE[certainty(e.method)] - (FAMILY_PENALTY if "family-level wording" in e.source_record else 0)
        verdicts.append(v)
        confs.append(min(base + BONUS, CAP) if v == "supported" else base)
    edges["reviewer_verdict"], edges["confidence"] = verdicts, confs
    edges["contradicts"] = [list(c) if c is not None else [] for c in edges["contradicts"]]
    write_table(edges.to_dict("records"), EDGE_SCHEMA, "edges")
    counts = edges[(edges.evidence_type == "text_mined") & (edges.source == "PubMed")].reviewer_verdict.value_counts().to_dict()
    (GRAPH_DIR / "review_summary.json").write_text(json.dumps(
        {"verdicts": counts, "models": sorted({r["model"] for r in {**older, **done}.values()})}, indent=1))
    print("Reviewer verdicts on text-mined edges:", counts)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--cache-only", action="store_true")
    a = ap.parse_args()
    main(a.limit, a.workers, not a.cache_only)
