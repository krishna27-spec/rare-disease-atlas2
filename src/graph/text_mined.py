"""Milestone 6, last step: turn extracted facts into graph edges (evidence_type = text_mined).

Run:  uv run python -m src.graph.text_mined
Reads  data/cache/edges_text_mined.jsonl (from src.extract), data/cache/abstracts.jsonl, data/graph/*.parquet
Writes data/graph/{nodes,edges}.parquet  (replaces the previous text_mined edges, Paper nodes and paper authors only)

A fact becomes an edge only if every name resolves to a stable ID already in the graph AND the quote itself names it:
  disease   -> MONDO via src.etl.terms, and it must be one of the paper's own diseases. A family name
               ("Batten disease") counts only when exactly one of the paper's diseases belongs to that family;
               the edge is then marked "family-level wording" and gets a lower confidence
  gene      -> HGNC symbol (the symbol or its full name)
  phenotype -> HP term (name or HPO synonym)
Anything that does not resolve is dropped and counted. participates_in_pathway facts are dropped:
our pathway edges link genes (not diseases) to Reactome, so a disease->pathway claim has no valid home.

Direction matches the curated layer: Gene -> gene_associated_with_disease -> Disease, Disease -> has_phenotype -> HP.
A fact the abstract DENIES becomes an edge with the predicate prefixed by "not_" (not_has_phenotype, ...), so nothing
that counts phenotypes or genes picks it up by accident; src.graph.connections pairs it with the edges it contradicts.

Authors of the papers that gave an edge are added too (curated, from PubMed metadata): an author whose full name
equals exactly one investigator already in the graph is linked to that person (lower confidence, marked as a name
match); any other author becomes a new Investigator node.
"""
import json
import re
from collections import Counter
from pathlib import Path

import obonet
import pandas as pd
import pyarrow.parquet as pq

from src.etl.download import RAW
from src.etl.genes import gene_aliases
from src.etl.research import investigator_id, real_person
from src.etl.terms import match_diseases, normalise
from src.graph.schema import EDGE_SCHEMA, GRAPH_DIR, NODE_SCHEMA, make_edge, write_table

CACHE = Path("data/cache")
CONF = {"stated": 0.7, "suggested": 0.5, "denied": 0.7}
FAMILY_PENALTY = 0.1    # the abstract said "Sanfilippo syndrome", the paper was found for one subtype
NAME_MATCH_CONF = 0.6   # author linked to an existing investigator by full name only


def phenotype_lookup(hp_ids: set[str]) -> dict[str, str]:
    """normalised phenotype name or synonym -> HP id, for HP terms already in the graph (ambiguous names dropped)."""
    hp = obonet.read_obo(RAW / "hp.obo")
    seen: dict[str, set[str]] = {}
    for hid in hp_ids & set(hp.nodes):
        names = [hp.nodes[hid]["name"]]
        names += [m.group(1) for s in hp.nodes[hid].get("synonym", []) if (m := re.search(r'"(.*?)"', s))]
        for n in names:
            seen.setdefault(normalise(n), set()).add(hid)
    return {k: next(iter(v)) for k, v in seen.items() if len(v) == 1}


def main() -> None:
    facts = [json.loads(l) for l in (CACHE / "edges_text_mined.jsonl").read_text().splitlines()]
    papers = {}
    for l in (CACHE / "abstracts.jsonl").read_text().splitlines():
        r = json.loads(l)
        papers[r["pmid"]] = r
    nodes = pq.read_table(GRAPH_DIR / "nodes.parquet").to_pylist()
    edges = pq.read_table(GRAPH_DIR / "edges.parquet").to_pylist()
    is_author = lambda n: n["node_type"] == "Investigator" and n["node_id"].startswith("AUTHOR:")
    nodes = [n for n in nodes if n["node_type"] != "Paper" and not is_author(n)]
    edges = [e for e in edges if e["source"] != "PubMed"]   # this layer's own edges: paper facts and authorships

    genes = gene_aliases({n["node_id"] for n in nodes if n["node_type"] == "Gene"})
    hp_nodes = {n["node_id"] for n in nodes if n["node_type"] == "Phenotype"}
    phenos = phenotype_lookup(hp_nodes)
    curated = {(e["subject"], e["predicate"], e["object"]) for e in edges}

    stats, new_edges, paper_ids = Counter(), [], set()
    for f in facts:
        stats["facts"] += 1
        if f["predicate"] == "participates_in_pathway":
            stats["dropped: pathway predicate has no disease->pathway home"] += 1
            continue
        matches = match_diseases(f["disease"])
        mondo = [d for d, kind in matches if kind == "specific" and d in f["disease_ids"]]
        family = False
        # The abstract uses a family name ("Batten disease"): accept only if exactly one of the paper's diseases
        # fits, and only for symptoms. Each subtype has its own gene, so a family-level gene statement
        # ("Sanfilippo is caused by SGSH, NAGLU, ...") must never be pinned on one subtype.
        if not mondo and f["predicate"] == "has_phenotype":
            fam = [d for d, kind in matches if kind == "broad" and d in f["disease_ids"]]
            if len(fam) == 1:
                mondo, family = fam, True
        if len(mondo) != 1:
            stats["dropped: out of scope (disease not one of ours / not this paper's)"] += 1
            continue
        key = normalise(f["object"])
        obj = genes.get(key) if f["predicate"] == "gene_associated_with_disease" else phenos.get(key)
        if obj is None:
            stats["dropped: unresolved (name not in graph)"] += 1
            continue
        # the quote must itself name the object (or a known alias), else the quote does not support this edge
        names = [k for k, v in (genes if f["predicate"] == "gene_associated_with_disease" else phenos).items() if v == obj]
        q = normalise(f["evidence_text"])
        if not (key in q or any(re.search(rf"\b{re.escape(n)}\b", q) for n in names)):
            stats["dropped: quote does not name the gene/symptom"] += 1
            continue
        pmid = f["pmid"]
        denied = f["certainty"] == "denied"
        subj, o = (obj, mondo[0]) if f["predicate"] == "gene_associated_with_disease" else (mondo[0], obj)
        new_edges.append(make_edge(
            subj, ("not_" if denied else "") + f["predicate"], o, "text_mined",
            CONF[f["certainty"]] - (FAMILY_PENALTY if family else 0), "PubMed",
            f"PMID:{pmid}" + ("|family-level wording" if family else ""), f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            f["date"], evidence_text=f["evidence_text"]))
        stats["of which: the abstract named the disease family, not the subtype"] += family
        new_edges[-1]["method"] = f"LLM extraction ({f.get('model') or 'model not recorded'}), certainty: {f['certainty']}"
        paper_ids.add(pmid)
        stats["denied by the paper" if denied else
              "also curated" if (subj, f["predicate"], o) in curated else "new to the graph"] += 1
    paper_nodes = [{"node_id": f"PMID:{p}", "node_type": "Paper", "name": papers[p]["title"],
                    "attrs": json.dumps({"pmid": p, "year": papers[p].get("year", ""),
                                         "journal": papers[p].get("journal", "")})} for p in sorted(paper_ids)]

    # ---- authors of those papers -> investigators
    meta = {}
    for l in (CACHE / "papers.jsonl").read_text().splitlines():
        r = json.loads(l)
        meta[r["pmid"]] = r
    by_name: dict[str, set[str]] = {}
    for n in nodes:
        if n["node_type"] == "Investigator":
            by_name.setdefault(normalise(n["name"]), set()).add(n["node_id"])
    author_nodes: dict[str, dict] = {}
    for p in sorted(paper_ids):
        m = meta.get(p, {})
        url = f"https://pubmed.ncbi.nlm.nih.gov/{p}/"
        for a in m.get("authors", []):
            name, aff = a.get("name", ""), a.get("affiliation") or ""
            if not real_person(name) or len(normalise(name).split()[0]) < 2:   # skip "D Skowyra": initials only
                continue
            known = by_name.get(normalise(name), set())
            if len(known) == 1:
                iid, conf, rec = next(iter(known)), NAME_MATCH_CONF, f"PMID:{p}|author|matched by full name"
                stats["authors linked to a known investigator (name match)"] += 1
            else:
                iid, conf, rec = "AUTHOR:" + investigator_id(name, "").split(":")[1], 0.9, f"PMID:{p}|author"
                author_nodes.setdefault(iid, {"node_id": iid, "node_type": "Investigator", "name": name,
                                              "attrs": json.dumps({"affiliation": aff, "source": "PubMed"})})
            new_edges.append(make_edge(iid, "investigator_of", f"PMID:{p}", "curated", conf, "PubMed", rec, url,
                                       m.get("retrieved") or f["date"]))
    write_table(nodes + paper_nodes + list(author_nodes.values()), NODE_SCHEMA, "nodes")
    write_table(edges + new_edges, EDGE_SCHEMA, "edges")
    n_tm = sum(e["evidence_type"] == "text_mined" for e in new_edges)
    print(f"{stats['facts']} facts read -> {n_tm} text_mined edges, {len(paper_nodes)} Paper nodes, "
          f"{len(author_nodes)} new author nodes")
    for k, v in stats.items():
        if k != "facts":
            print(f"  {v:5d}  {k}")
    drops = {k.replace("dropped: ", ""): v for k, v in stats.items() if k.startswith("dropped")}
    (GRAPH_DIR / "text_mined_drops.json").write_text(json.dumps(drops, indent=1))


if __name__ == "__main__":
    main()
