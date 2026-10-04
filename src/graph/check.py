"""Check the built graph against the project's evidence rules. Exits with an error if any rule is broken.

Run:  uv run python -m src.graph.check      (last step of src.graph.build)
Checks: every edge has source, record, date, confidence and evidence type; text-mined edges carry a quote that
really is in the paper's abstract; inferred edges say how they were computed; every edge points at nodes that
exist; edge IDs are unique; and every edge ID the query layer hands to a UI exists in the graph.
"""
import json
import re
import sys
from pathlib import Path

import pandas as pd

from src.graph.schema import GRAPH_DIR

ABSTRACTS = Path("data/cache/abstracts.jsonl")
EDGE_ID = re.compile(r"E[0-9a-f]{12}")


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def main() -> None:
    nodes = pd.read_parquet(GRAPH_DIR / "nodes.parquet")
    edges = pd.read_parquet(GRAPH_DIR / "edges.parquet")
    problems: list[str] = []

    def rule(name: str, bad: pd.DataFrame) -> None:
        print(f"  {'ok ' if bad.empty else 'BAD'}  {name}" + ("" if bad.empty else f": {len(bad)} edges"))
        if not bad.empty:
            problems.append(f"{name}: e.g. {bad.edge_id.head(3).tolist()}")

    print(f"{len(nodes)} nodes, {len(edges)} edges")
    rule("edge IDs are unique", edges[edges.edge_id.duplicated()])
    rule("node IDs are unique", nodes[nodes.node_id.duplicated()].rename(columns={"node_id": "edge_id"}))
    rule("evidence type is curated, text_mined or inferred",
         edges[~edges.evidence_type.isin(["curated", "text_mined", "inferred"])])
    rule("source, record and retrieval date are filled",
         edges[(edges.source == "") | (edges.source_record == "") | (edges.retrieved == "")
               | edges.source.isna() | edges.retrieved.isna()])
    rule("confidence is between 0 and 1", edges[~edges.confidence.between(0, 1)])
    rule("inferred edges say how they were computed", edges[(edges.evidence_type == "inferred") & (edges.method == "")])
    tm = edges[edges.evidence_type == "text_mined"]
    rule("text-mined edges store the quoted sentence", tm[tm.evidence_text == ""])
    known = set(nodes.node_id)
    rule("both ends of every edge are nodes", edges[~edges.subject.isin(known) | ~edges.object.isin(known)])

    if ABSTRACTS.exists():   # the cache is not shipped with a deployed app; the check runs where the graph is built
        text = {}
        for l in ABSTRACTS.read_text().splitlines():
            r = json.loads(l)
            text[r["pmid"]] = norm(r["title"] + "\n\n" + r["abstract"])
        pub = tm[tm.source == "PubMed"]
        pmid = pub.source_record.str.split("|").str[0].str.replace("PMID:", "")
        found = [norm(q) in text.get(p, "") for q, p in zip(pub.evidence_text, pmid)]
        rule("every paper quote is found word for word in its abstract", pub[[not f for f in found]])

    pages = Path("data/cache/org_pages")
    if pages.exists():
        import hashlib

        from src.etl.org_scrape import page_text
        web = tm[tm.source == "Patient organisation website"]
        bad = []
        for e in web.itertuples():
            f = pages / (hashlib.sha1(e.source_url.encode()).hexdigest() + ".json")
            text = norm(" ".join(page_text(json.loads(f.read_text()).get("text", ""))[1])) if f.exists() else ""
            bad.append(norm(e.evidence_text) not in text)
        rule("every organisation quote is found on the cached page it cites", web[bad])

    from src.atlas.queries import Atlas
    A = Atlas()
    ids = set(edges.edge_id)
    missing = set()
    for d in A.G.diseases.index:
        blob = json.dumps([A.disease(d), A.neighbours(d), A.pathway_paths(d), A.connectors(disease=d), A.assets(d),
                           A.subgraph(d), A.next_steps(d, explain=False)])
        missing |= set(EDGE_ID.findall(blob)) - ids
    blob = json.dumps([A.clusters(), [A.cluster(c) for c in set(A.G.cluster_of.values())], A.contradictions()])
    missing |= set(EDGE_ID.findall(blob)) - ids
    print(f"  {'ok ' if not missing else 'BAD'}  every edge ID returned by the query layer exists"
          + ("" if not missing else f": {len(missing)} unknown, e.g. {sorted(missing)[:3]}"))
    if missing:
        problems.append("query layer returns unknown edge IDs (rebuild src.graph.connections)")

    if problems:
        sys.exit("Graph check FAILED:\n  " + "\n  ".join(problems))
    print("Graph check passed.")


if __name__ == "__main__":
    main()
