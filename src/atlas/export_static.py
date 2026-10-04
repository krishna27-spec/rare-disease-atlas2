"""Export every API answer as a static JSON file, so the website can be hosted with no server (GitHub Pages).

Run:  uv run python -m src.atlas.export_static        (then: cd web && npm run build:pages)
      add --no-llm to skip asking gpt-oss for the plain-language next steps
Writes web/static-api/. The site built in "pages" mode reads these files instead of calling the API
(see web/src/api.js). Search and the mechanism lookup run in the browser over an exported index.
The plain-language next steps are asked from gpt-oss once, here, and stored; without quota the cited candidates
are stored instead and the site says so.
"""
import json
import shutil
import sys
from pathlib import Path

from src.atlas.queries import Atlas, clean

OUT = Path("web/static-api")


def safe(s: str) -> str:
    return s.replace(":", "_")


def write(path: str, data) -> None:
    f = OUT / path
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))


def main(explain: bool = True) -> None:
    A = Atlas()
    shutil.rmtree(OUT, ignore_errors=True)
    ids = list(A.G.diseases.index)
    write("diseases.json", A.diseases())
    write("stats.json", A.stats())
    write("contradictions.json", A.contradictions())
    write("connectors.json", A.connectors(limit=60))
    write("connectors-cross.json", A.connectors(limit=60, cross_cluster_only=True))
    worded = 0
    for d in ids:
        p = f"disease/{safe(d)}"
        write(f"{p}.json", A.disease(d))
        write(f"{p}/graph.json", A.subgraph(d))
        write(f"{p}/neighbours.json", A.neighbours(d))
        write(f"{p}/pathways.json", A.pathway_paths(d, 12))
        write(f"{p}/assets.json", A.assets(d))
        write(f"{p}/biology.json", A.biology(d))
        write(f"{p}/ten-x.json", A.ten_x(d))
        write(f"{p}/landscape.json", A.landscape(d))
        write(f"{p}/connectors.json", A.connectors(disease=d, limit=60))
        steps = A.next_steps(d, explain=explain)
        worded += bool(steps["used_llm"])
        write(f"{p}/next-steps.json", steps)
    # every fact, for the evidence drawer (one file, fetched the first time a "Why?" is opened)
    write("edges.json", {eid: A.edge(eid) for eid in A.edges.edge_id})
    # search: the same index the API uses, plus where each non-disease hit leads
    leads = {nid: A._diseases_for(kind, nid) for _, kind, nid, _ in A._index if kind != "disease"}
    write("search-index.json", {"rows": [list(r) for r in A._index], "leads": clean(leads),
                                "searched": A.search("zzzzzzzzzz")["no_match"]["searched"]})
    t = A._tables()["outside_index"]
    write("outside.json", [[r.mondo_id, r.name, r.synonyms, r.genes, r.orpha] for r in t.itertuples()])
    # mechanisms: one answer per pathway and per gene
    targets = [p for p in A.pathways.index if not A.pathways.loc[p, "generic"]]
    targets += list(A.nodes[A.nodes.node_type == "Gene"].node_id)
    for x in targets:
        write(f"mechanism/{safe(x)}.json", A.clusters_for_mechanism(x))
    n = sum(1 for _ in OUT.rglob("*.json"))
    size = sum(f.stat().st_size for f in OUT.rglob("*.json")) / 1e6
    print(f"{n} files, {size:.1f} MB -> {OUT}; next steps worded by gpt-oss for {worded} of {len(ids)} diseases")


if __name__ == "__main__":
    main(explain="--no-llm" not in sys.argv)
