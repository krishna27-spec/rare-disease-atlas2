"""Second mechanism source: Gene Ontology biological processes for our genes (curated, via the QuickGO API).

Run:  uv run python -m src.etl.go      (after src.etl.biology; before src.graph.similarity)
Why: Reactome has no specific pathway for some genes (CLN5, CLN6, CLN7, CLN8), so those diseases had no mechanism
evidence at all. GO annotates almost every gene with the processes it takes part in.

Adds Pathway nodes with GO IDs and Gene -> participates_in_pathway -> GO edges (replacing the earlier GO layer only).
Only annotations a curator made are kept: purely electronic ones (evidence code IEA) and negated ones (NOT) are
skipped. The evidence code and the paper behind each annotation are stored in `source_record`.
Every API answer is cached in data/cache/quickgo/, so re-runs download nothing.
"""
import json

import pandas as pd
import pyarrow.parquet as pq
import requests

from src.etl.download import RAW
from src.etl.research import HEADERS, TODAY, cached
from src.graph.schema import EDGE_SCHEMA, GRAPH_DIR, NODE_SCHEMA, make_edge, write_table

API = "https://www.ebi.ac.uk/QuickGO/services"
SOURCE = "Gene Ontology (QuickGO)"
# evidence code -> confidence. Experimental evidence is strongest; statements without a traceable experiment weakest.
EXPERIMENTAL = {"EXP", "IDA", "IMP", "IPI", "IGI", "IEP", "HDA", "HMP", "HGI", "HEP", "HTP"}
REVIEWED = {"IBA", "TAS", "IC", "ISS", "ISO", "ISA", "ISM", "IGC", "RCA", "IKR"}
CONF = {"experimental": 0.9, "reviewed": 0.8, "statement": 0.7}


def confidence(code: str) -> float:
    return CONF["experimental"] if code in EXPERIMENTAL else CONF["reviewed"] if code in REVIEWED else CONF["statement"]


def annotations(uniprot: str) -> list[dict]:
    params = {"geneProductId": uniprot, "aspect": "biological_process", "taxonId": 9606, "limit": 200}
    data = cached("quickgo", f"annotation|{uniprot}", lambda: requests.get(
        f"{API}/annotation/search", params=params, headers={**HEADERS, "Accept": "application/json"}, timeout=60))
    return data.get("results", [])


def term_names(go_ids: list[str]) -> dict[str, str]:
    names = {}
    for i in range(0, len(go_ids), 25):
        chunk = go_ids[i:i + 25]
        data = cached("quickgo", "terms|" + ",".join(chunk), lambda: requests.get(
            f"{API}/ontology/go/terms/{','.join(chunk)}", headers={**HEADERS, "Accept": "application/json"}, timeout=60))
        for t in data.get("results", []):
            if not t.get("isObsolete"):
                names[t["id"]] = t["name"]
    return names


def main() -> None:
    nodes = pq.read_table(GRAPH_DIR / "nodes.parquet").to_pylist()
    edges = pq.read_table(GRAPH_DIR / "edges.parquet").to_pylist()
    nodes = [n for n in nodes if not n["node_id"].startswith("GO:")]
    edges = [e for e in edges if e["source"] != SOURCE]
    genes = sorted(n["node_id"] for n in nodes if n["node_type"] == "Gene")
    uniprot = pd.read_csv(RAW / "hgnc_complete_set.txt", sep="\t", dtype=str,
                          usecols=["symbol", "uniprot_ids"]).set_index("symbol")["uniprot_ids"]

    best: dict[tuple[str, str], tuple[float, str, str]] = {}   # (gene, GO id) -> (confidence, record, url)
    skipped = {"electronic (IEA)": 0, "negated (NOT)": 0}
    for g in genes:
        up = uniprot.get(g)
        if not isinstance(up, str):
            print(f"  {g}: no UniProt ID in HGNC, skipped")
            continue
        up = up.split("|")[0]
        for a in annotations(up):
            if a["goEvidence"] == "IEA":
                skipped["electronic (IEA)"] += 1
                continue
            if "NOT" in a["qualifier"].upper() or a["qualifier"] != "involved_in":
                skipped["negated (NOT)"] += "NOT" in a["qualifier"].upper()
                continue
            conf = confidence(a["goEvidence"])
            key = (g, a["goId"])
            if key not in best or conf > best[key][0]:
                best[key] = (conf, f"UniProtKB:{up}|{a['goId']}|{a['goEvidence']}|{a.get('reference') or ''}",
                             f"https://www.ebi.ac.uk/QuickGO/annotations?geneProductId={up}&goId={a['goId']}")
    names = term_names(sorted({go for _, go in best}))
    new_edges = [make_edge(g, "participates_in_pathway", go, "curated", conf, SOURCE, rec, url, TODAY)
                 for (g, go), (conf, rec, url) in sorted(best.items()) if go in names]
    used = sorted({e["object"] for e in new_edges})
    new_nodes = [{"node_id": go, "node_type": "Pathway", "name": names[go],
                  "attrs": json.dumps({"source": "Gene Ontology", "aspect": "biological_process"})} for go in used]
    write_table(nodes + new_nodes, NODE_SCHEMA, "nodes")
    write_table(edges + new_edges, EDGE_SCHEMA, "edges")

    per_gene = pd.Series([e["subject"] for e in new_edges]).value_counts()
    print(f"{len(new_edges)} gene -> GO process edges, {len(new_nodes)} GO terms, for {per_gene.size} of {len(genes)} genes")
    print("skipped: " + ", ".join(f"{v} {k}" for k, v in skipped.items()))
    print("genes with no curated GO process: " + (", ".join(g for g in genes if g not in per_gene.index) or "none"))
    shared = pd.Series([e["object"] for e in new_edges]).value_counts()
    print("processes shared by the most genes: "
          + "; ".join(f"{names[go]} ({n})" for go, n in shared.head(8).items()))


if __name__ == "__main__":
    main()
