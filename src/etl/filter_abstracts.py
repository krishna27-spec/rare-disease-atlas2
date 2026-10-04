"""Keep only abstracts that mention one of our diseases or genes, so the LLM never reads off-topic papers.

Run:  uv run python -m src.etl.filter_abstracts
Reads data/cache/abstracts.jsonl and the graph's genes; writes data/cache/abstracts_filtered.jsonl
(Sanfilippo/MPS III papers first, since they are Maria's story and Groq's free tier only reads ~150 a day).

CLN1..CLN8 are also yeast cyclin genes, so a bare "CLN1" counts only if the abstract also has
lysosomal/Batten context."""
import json
import re
from pathlib import Path

import pandas as pd

from src.etl.genes import gene_aliases
from src.etl.terms import _has, match_diseases, normalise

CACHE = Path("data/cache")
BARE_CLN = re.compile(r"^cln\d$")
CONTEXT = ["lipofuscinosis", "batten", "lysosom", "neurodegenerat", "storage disease"]
SANFILIPPO = {"MONDO:0009655", "MONDO:0009656", "MONDO:0009657", "MONDO:0009658"}


def keep(text: str, aliases: dict[str, str]) -> bool:
    t = normalise(text)
    hits = {p for p in aliases if _has(t, [p])}
    diseases = match_diseases(text)
    bare_only = all(BARE_CLN.match(h) for h in hits) and not any(
        d for d, _ in diseases if not _has(t, ["cln1", "cln2", "cln3", "cln5", "cln6", "cln7", "cln8"]))
    ok_context = any(c in t for c in CONTEXT)
    if (hits or diseases) and (ok_context or not bare_only):
        return True
    return False


def main() -> None:
    nodes = pd.read_parquet("data/graph/nodes.parquet")
    aliases = gene_aliases(set(nodes[nodes.node_type == "Gene"].node_id))
    recs = [json.loads(l) for l in (CACHE / "abstracts.jsonl").read_text().splitlines()]
    kept = [r for r in recs if keep(r["title"] + " " + r["abstract"], aliases)]
    kept.sort(key=lambda r: not (set(r["disease_ids"]) & SANFILIPPO))
    (CACHE / "abstracts_filtered.jsonl").write_text("".join(json.dumps(r) + "\n" for r in kept))
    print(f"{len(recs)} abstracts -> {len(kept)} kept, {len(recs) - len(kept)} off-topic removed")
    print("yeast Cln1 paper (PMID 10213692) kept?", any(r["pmid"] == "10213692" for r in kept))


if __name__ == "__main__":
    main()
