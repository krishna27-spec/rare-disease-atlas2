"""Milestone 6: an LLM reads each abstract and proposes facts; code keeps only facts with a verbatim quote.

Run locally (uses .env):  uv run python -m src.extract --limit 20      (add --spread to take turns between diseases)
Run on molab:             see notebooks/extract_molab.py (same functions)

Reads  data/cache/abstracts.jsonl                 (pmid, title, abstract, disease_ids)
Writes data/cache/extractions.jsonl               one line per abstract read (resumable: re-runs skip done PMIDs)
       data/cache/edges_text_mined.jsonl          the flat list of facts whose quote was found in the abstract

Only `src.llm` is needed besides the standard library, so it also runs on molab. Turning facts into graph
edges (resolving names to MONDO/HGNC/HP/Reactome IDs) happens later, locally: src/graph/text_mined.py.
"""
import argparse
import datetime
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from src.llm import chat_json, last_model

CACHE = Path("data/cache")
PREDICATES = ("gene_associated_with_disease", "has_phenotype", "participates_in_pathway")


class Fact(BaseModel):
    disease: str                      # the disease as named in the abstract
    predicate: Literal["gene_associated_with_disease", "has_phenotype", "participates_in_pathway"]
    object: str                       # gene symbol, symptom, or pathway, as named in the abstract
    certainty: Literal["stated", "suggested", "denied"]
    evidence_text: str                # one sentence copied exactly from the abstract


class Facts(BaseModel):
    facts: list[Fact]


SYSTEM = """You extract facts from one scientific abstract about rare neurological lysosomal storage diseases.
Return JSON {"facts": [...]}. Each fact has:
- disease: the human disease, as named in the abstract
- predicate: one of
    gene_associated_with_disease  (a gene whose mutations cause or are linked to the disease)
    has_phenotype                 (a symptom or clinical sign patients with the disease have)
    participates_in_pathway       (a biological pathway or process the disease's gene/protein works in)
- object: SHORT. For genes the official symbol (HEXB, HGSNAT). For symptoms a short standard clinical term
    ("seizure", "hepatomegaly", "intellectual disability"), never a sentence. For pathways a short process name
- certainty: "stated" if the abstract says it plainly, "suggested" if it only hints, proposes or speculates,
    "denied" if the abstract says plainly that it is NOT so for the disease in general (for example "seizures
    are not a feature of X"). A finding missing in one single patient is not "denied": leave it out
- evidence_text: ONE sentence copied EXACTLY, character for character, from the abstract

Rules: use only what the abstract says. Never use outside knowledge. Skip animal-only, yeast or cell-only
findings unless the sentence is about the human disease. If the abstract is not about one of these diseases
(for example CLN1 is also a yeast cyclin), return {"facts": []}. Return at most 8 facts. When unsure, leave it out."""


def norm(text: str) -> str:
    """Whitespace and case do not matter when checking a quote."""
    return re.sub(r"\s+", " ", text).strip().lower()


def read_abstract(rec: dict) -> dict:
    """Ask the LLM about one abstract. Returns {pmid, facts (verified), dropped, failed}."""
    text = f"{rec['title']}\n\n{rec['abstract']}"
    out = chat_json([{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}], Facts, effort="low")
    if out is None:
        return {"pmid": rec["pmid"], "facts": [], "dropped": 0, "failed": True, "model": ""}
    haystack = norm(text)
    kept, dropped = [], 0
    for f in out.facts:
        if f.evidence_text.strip() and norm(f.evidence_text) in haystack:  # hard rule 1: quote must be real
            kept.append(f.model_dump())
        else:
            dropped += 1
    return {"pmid": rec["pmid"], "facts": kept, "dropped": dropped, "failed": False, "model": last_model()}


def run(abstracts_path: Path, out_dir: Path, limit: int | None = None, workers: int = 1,
        spread: bool = False) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    done_path, flat_path = out_dir / "extractions.jsonl", out_dir / "edges_text_mined.jsonl"
    records = [json.loads(line) for line in abstracts_path.read_text().splitlines() if line.strip()]
    done = {json.loads(l)["pmid"] for l in done_path.read_text().splitlines()} if done_path.exists() else set()
    todo = [r for r in records if r["pmid"] not in done]
    if spread:   # take turns between diseases, so a short run still reads a few abstracts for every disease
        turn: dict[str, int] = {}
        order = []
        for r in todo:
            key = (r["disease_ids"] or [""])[0]
            turn[key] = turn.get(key, 0) + 1
            order.append(turn[key])
        todo = [r for _, r in sorted(zip(order, todo), key=lambda x: x[0])]
    todo = todo[:limit]
    print(f"{len(records)} abstracts, {len(done)} already done, reading {len(todo)} now")
    when = datetime.date.today().isoformat()
    with ThreadPoolExecutor(workers) as pool, done_path.open("a") as f:
        for i, (rec, res) in enumerate(zip(todo, pool.map(read_abstract, todo)), 1):
            if res["failed"]:
                print(f"  PMID {rec['pmid']}: invalid JSON, will retry on the next run")
                continue  # not written, so the next run tries again
            res.update(disease_ids=rec["disease_ids"], date=when)
            f.write(json.dumps(res) + "\n")
            f.flush()
            if i % 10 == 0:
                print(f"  {i}/{len(todo)}")
    rows = [json.loads(l) for l in done_path.read_text().splitlines()]
    with flat_path.open("w") as f:
        for r in rows:
            for fact in r["facts"]:
                f.write(json.dumps({**fact, "pmid": r["pmid"], "disease_ids": r["disease_ids"],
                                    "model": r["model"], "date": r["date"]}) + "\n")
    n_facts = sum(len(r["facts"]) for r in rows)
    print(f"Done: {len(rows)} abstracts read, {n_facts} verified facts, "
          f"{sum(r['dropped'] for r in rows)} dropped (quote not in abstract) -> {flat_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--input", default="abstracts_filtered.jsonl")  # from src.etl.filter_abstracts
    ap.add_argument("--spread", action="store_true")
    a = ap.parse_args()
    run(CACHE / a.input, CACHE, a.limit, a.workers, a.spread)
