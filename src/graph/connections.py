"""Milestone 7: connections. Small tables for the app, computed from the graph only (no LLM).

Run:  uv run python -m src.graph.connections
Reads  data/graph/{nodes,edges}.parquet, clusters.csv, similarity_pairs.csv, data/manual/diseases.csv
Writes data/graph/{contradictions,shared_people,connectors,cluster_assets,neighbours}.parquet and
       connections_summary.json; fills the `contradicts` column of edges.parquet
Every row carries the edge IDs it came from, so the app can show the evidence behind each line.
"""
import json
from pathlib import Path

import networkx as nx
import obonet
import pandas as pd

from src.etl.download import RAW
from src.graph.reactome import generic_pathways
from src.graph.schema import EDGE_SCHEMA, GRAPH_DIR, write_table
from src.graph.similarity import information_content, most_specific

TOP_NEIGHBOURS, TOP_ITEMS = 5, 5


def edge_ids(edges: pd.DataFrame, **match) -> list[str]:
    m = pd.Series(True, index=edges.index)
    for col, val in match.items():
        m &= edges[col].isin(val) if isinstance(val, (set, list)) else edges[col] == val
    return edges.loc[m, "edge_id"].tolist()


def contradictions(edges: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    """A paper that DENIES a fact (predicate "not_...") contradicts every edge that asserts the same fact.

    Writes contradictions.parquet (one row per pair) and fills `contradicts` on both edges. If papers denied
    nothing, the table is empty and the note says so: we do not invent contradictions."""
    tm = edges[(edges.evidence_type == "text_mined") & (edges.source == "PubMed")]
    denied = tm[tm.predicate.str.startswith("not_")]
    edges = edges.copy()
    edges["contradicts"] = [[] for _ in range(len(edges))]
    pos = {eid: i for i, eid in enumerate(edges.edge_id)}
    col = edges.columns.get_loc("contradicts")
    rows = []
    for d in denied.itertuples():
        same = edges[(edges.subject == d.subject) & (edges.object == d.object) & (edges.predicate == d.predicate[4:])]
        for o in same.itertuples():
            rows.append({"edge_a": o.edge_id, "edge_b": d.edge_id, "subject": d.subject, "object": d.object,
                         "predicate": o.predicate,
                         "reason": f"{o.source} ({o.source_record}, {o.evidence_type}) asserts it; "
                                   f"{d.source_record} denies it"})
            edges.iat[pos[o.edge_id], col] = edges.iat[pos[o.edge_id], col] + [d.edge_id]
            edges.iat[pos[d.edge_id], col] = edges.iat[pos[d.edge_id], col] + [o.edge_id]
    pd.DataFrame(rows, columns=["edge_a", "edge_b", "subject", "object", "predicate", "reason"]).to_parquet(
        GRAPH_DIR / "contradictions.parquet", index=False)
    note = (f"{len(rows)} contradictions found among {len(tm)} text-mined facts "
            f"({len(denied)} facts were denials; {len(denied) - len({r['edge_b'] for r in rows})} of them deny "
            "something no other source asserts)")
    return {"contradictions": len(rows), "text_mined_facts": len(tm), "denied_facts": len(denied), "note": note}, edges


def connectors(nodes, edges, cluster_of, dname) -> pd.DataFrame:
    """People who link two or more of our diseases through ANY route: a trial, a grant or a paper.

    (shared_people below counts trials only and is kept as it was for the existing app.)"""
    dis = set(dname)
    trial = edges[edges.predicate == "studied_in_trial"][["object", "subject", "edge_id"]].assign(via="trial")
    grant = edges[edges.predicate == "funded_by"][["object", "subject", "edge_id"]].assign(via="grant")
    tm = edges[(edges.evidence_type == "text_mined") & (edges.source == "PubMed")
               & ~edges.predicate.str.startswith("not_")]
    paper = pd.DataFrame({"object": tm.source_record.str.split("|").str[0],
                          "subject": [s if s in dis else o for s, o in zip(tm.subject, tm.object)],
                          "edge_id": tm.edge_id, "via": "paper"})
    links = pd.concat([trial, grant, paper]).rename(columns={"object": "work", "subject": "disease"})
    by_work = {w: g for w, g in links.groupby("work")}
    people = nodes[nodes.node_type == "Investigator"].set_index("node_id")
    rows = []
    for pid, grp in edges[edges.predicate == "investigator_of"].groupby("subject"):
        if pid not in people.index or any(w in people.loc[pid, "name"].lower()
                                          for w in ("clinical sciences", "operations", "contact")):
            continue
        mine = pd.concat([by_work[w] for w in grp.object if w in by_work] or [links.iloc[:0]])
        ds = sorted(set(mine.disease) & dis)
        if len(ds) < 2:
            continue
        cl = sorted({int(cluster_of[d]) for d in ds})
        rows.append({"person_id": pid, "person": people.loc[pid, "name"],
                     "affiliation": json.loads(people.loc[pid, "attrs"] or "{}").get("affiliation", ""),
                     "n_diseases": len(ds), "clusters": json.dumps(cl), "cross_cluster": len(cl) > 1,
                     "via": json.dumps(sorted(set(mine.via))),
                     "diseases": json.dumps([{"id": d, "name": dname[d], "via": sorted(set(mine[mine.disease == d].via)),
                                              "works": sorted(set(mine[mine.disease == d].work))[:5]} for d in ds]),
                     "edge_ids": json.dumps(sorted(set(grp[grp.object.isin(mine.work)].edge_id) | set(mine.edge_id)))})
    df = pd.DataFrame(rows, columns=["person_id", "person", "affiliation", "n_diseases", "clusters", "cross_cluster",
                                     "via", "diseases", "edge_ids"])
    df = df.sort_values(["cross_cluster", "n_diseases"], ascending=False)
    df.to_parquet(GRAPH_DIR / "connectors.parquet", index=False)
    return df


def pathways(nodes, edges, dname) -> pd.DataFrame:
    """One row per Reactome pathway: its genes, the diseases those genes cause, and whether it is too generic.

    Saved so the query layer can navigate disease -> gene -> pathway -> gene -> disease without data/raw."""
    generic = generic_pathways()
    causal = edges[(edges.predicate == "gene_associated_with_disease") & (edges.evidence_type == "curated")]
    part = edges[edges.predicate == "participates_in_pathway"]
    pname = nodes.set_index("node_id")["name"]
    rows = []
    for pid, grp in part.groupby("object"):
        genes = sorted(set(grp.subject))
        ds = sorted(set(causal[causal.subject.isin(genes)].object))
        rows.append({"pathway_id": pid, "name": pname.get(pid, pid), "generic": pid in generic,
                     "n_genes": len(genes), "n_diseases": len(ds), "genes": json.dumps(genes),
                     "diseases": json.dumps([[d, dname[d]] for d in ds]),
                     "edge_ids": json.dumps(dict(zip(grp.subject, grp.edge_id)))})
    df = pd.DataFrame(rows).sort_values(["generic", "n_diseases"])
    df.to_parquet(GRAPH_DIR / "pathways.parquet", index=False)
    return df


def shared_people(nodes, edges, cluster_of, dname) -> pd.DataFrame:
    trial_dis = edges[edges.predicate == "studied_in_trial"]
    inv = edges[edges.predicate == "investigator_of"]
    people = nodes[nodes.node_type == "Investigator"].set_index("node_id")
    rows = []
    for pid, grp in inv.groupby("subject"):
        if any(w in people.loc[pid, "name"].lower() for w in ("clinical sciences", "operations", "contact")):
            continue   # a team/department label, not a person
        links = trial_dis[trial_dis.object.isin(grp.object)]
        ds = sorted(set(links.subject))
        if len(ds) < 2:
            continue
        cl = sorted({cluster_of[d] for d in ds})
        rows.append({"person_id": pid, "person": people.loc[pid, "name"],
                     "affiliation": json.loads(people.loc[pid, "attrs"] or "{}").get("affiliation", ""),
                     "n_diseases": len(ds), "diseases": json.dumps([[d, dname[d]] for d in ds]),
                     "clusters": json.dumps(cl), "cross_cluster": len(cl) > 1,
                     "edge_ids": json.dumps(sorted(set(grp.edge_id) | set(links.edge_id)))})
    df = pd.DataFrame(rows, columns=["person_id", "person", "affiliation", "n_diseases", "diseases",
                                     "clusters", "cross_cluster", "edge_ids"])
    df = df.sort_values(["cross_cluster", "n_diseases"], ascending=False)
    df.to_parquet(GRAPH_DIR / "shared_people.parquet", index=False)
    return df


def cluster_assets(nodes, edges, cluster_of, dname) -> pd.DataFrame:
    by_id = nodes.set_index("node_id")
    rows = []
    for e in edges[edges.predicate.isin(["has_asset", "studied_in_trial"])].itertuples():
        n = by_id.loc[e.object]
        a = json.loads(n["attrs"] or "{}")
        kind = a.get("asset_type") if e.predicate == "has_asset" else (
            "interventional trial" if a.get("study_type") == "INTERVENTIONAL" else "observational study")
        if e.predicate == "studied_in_trial" and a.get("study_type") == "OBSERVATIONAL":
            continue   # already listed as its Asset
        rows.append({"cluster": cluster_of[e.subject], "disease_id": e.subject, "disease": dname[e.subject],
                     "asset_id": e.object, "kind": kind, "title": n["name"], "status": a.get("status", ""),
                     "sponsor": a.get("sponsor", ""), "edge_id": e.edge_id, "source_url": e.source_url,
                     "confidence": e.confidence})
    df = pd.DataFrame(rows).sort_values(["cluster", "disease_id", "kind"])
    df.to_parquet(GRAPH_DIR / "cluster_assets.parquet", index=False)
    return df


def neighbours(nodes, edges, pairs, dname, diseases) -> pd.DataFrame:
    hp = obonet.read_obo(RAW / "hp.obo")
    ph_edges = edges[edges.predicate == "has_phenotype"]
    pheno, direct = {}, {}
    for d in diseases:
        direct[d] = ph_edges[ph_edges.subject == d]
        terms = set(direct[d].object)
        for t in list(terms):
            terms |= nx.descendants(hp, t)
        pheno[d] = terms
    ic = information_content(pheno)
    gene_e = edges[(edges.predicate == "gene_associated_with_disease") & (edges.evidence_type == "curated")]
    genes = {d: set(gene_e[gene_e.object == d].subject) for d in diseases}
    path_e = edges[edges.predicate == "participates_in_pathway"]
    pname = nodes.set_index("node_id")["name"]
    generic = generic_pathways()
    sim = edges[edges.predicate == "similar_to"].set_index(["subject", "object"])["edge_id"]

    def pheno_ids(d, term):  # direct edges of d whose term is `term` or one of its children
        sub = direct[d][direct[d].object.map(lambda o: o == term or term in nx.descendants(hp, o))]
        return sub.edge_id.tolist()

    def path_ids(d, p):
        return path_e[(path_e.subject.isin(genes[d])) & (path_e.object == p)].edge_id.tolist()

    def top(terms, d):
        ranked = sorted(most_specific(terms, hp), key=lambda t: -ic[t])[:TOP_ITEMS] if terms else []
        return [{"id": t, "name": hp.nodes[t]["name"], "ic": round(ic[t], 2), "edge_ids": pheno_ids(d, t)}
                for t in ranked]

    n_with: dict[str, int] = {}     # pathway -> how many of our diseases have a causal gene in it
    for d in diseases:
        for p in {p for g in genes[d] for p in path_e[path_e.subject == g].object}:
            n_with[p] = n_with.get(p, 0) + 1
    rows = []
    for d in diseases:
        mine = pairs[(pairs.disease_a == d) | (pairs.disease_b == d)].sort_values("combined", ascending=False)
        for rank, r in enumerate(mine.head(TOP_NEIGHBOURS).itertuples(), 1):
            o = r.disease_b if r.disease_a == d else r.disease_a
            paths_d = {p for g in genes[d] for p in path_e[path_e.subject == g].object} - generic
            paths_o = {p for g in genes[o] for p in path_e[path_e.subject == g].object} - generic
            # most specific first: a pathway few of our diseases share says more than one most of them share
            shared_p = sorted(paths_d & paths_o, key=lambda p: (n_with[p], pname.get(p, "")))
            shared_ph = [{"id": t, "name": hp.nodes[t]["name"], "ic": round(ic[t], 2),
                          "edge_ids": pheno_ids(d, t) + pheno_ids(o, t)}
                         for t in sorted(most_specific(pheno[d] & pheno[o], hp), key=lambda t: -ic[t])[:TOP_ITEMS]]
            rows.append({
                "disease_id": d, "disease": dname[d], "neighbour_id": o, "neighbour": dname[o], "rank": rank,
                "score": r.combined, "phenotype_score": r.phenotype_score, "pathway_score": r.pathway_score,
                "similar_edge_id": sim.get((d, o), sim.get((o, d), "")),
                "shared_pathways": json.dumps([{"id": p, "name": pname.get(p, p),
                                                "edge_ids": path_ids(d, p) + path_ids(o, p)}
                                               for p in shared_p[:TOP_ITEMS]]),
                "n_shared_pathways": len(shared_p),
                "shared_phenotypes": json.dumps(shared_ph),
                "shared_genes": json.dumps(sorted(genes[d] & genes[o])),
                "genes": json.dumps(sorted(genes[d])), "neighbour_genes": json.dumps(sorted(genes[o])),
                "only_here": json.dumps(top(pheno[d] - pheno[o], d)),
                "only_neighbour": json.dumps(top(pheno[o] - pheno[d], o)),
                "gene_edge_ids": json.dumps(edge_ids(gene_e, object={d, o})),
            })
    df = pd.DataFrame(rows)
    df.to_parquet(GRAPH_DIR / "neighbours.parquet", index=False)
    return df


def main() -> None:
    nodes = pd.read_parquet(GRAPH_DIR / "nodes.parquet")
    edges = pd.read_parquet(GRAPH_DIR / "edges.parquet")
    clusters = pd.read_csv(GRAPH_DIR / "clusters.csv")
    cluster_of = dict(zip(clusters.mondo_id, clusters.cluster))
    pairs = pd.read_csv(GRAPH_DIR / "similarity_pairs.csv")
    dname = dict(zip(nodes[nodes.node_type == "Disease"].node_id, nodes[nodes.node_type == "Disease"].name))
    diseases = list(dname)

    summary, edges = contradictions(edges)
    write_table(edges.to_dict("records"), EDGE_SCHEMA, "edges")   # saves the `contradicts` links
    conn = connectors(nodes, edges, cluster_of, dname)
    paths = pathways(nodes, edges, dname)
    people = shared_people(nodes, edges, cluster_of, dname)
    assets = cluster_assets(nodes, edges, cluster_of, dname)
    nb = neighbours(nodes, edges, pairs, dname, diseases)
    summary.update(shared_people=len(people), cross_cluster_people=int(people.cross_cluster.sum()),
                   assets=len(assets), neighbour_rows=len(nb), connectors=len(conn), specific_pathways=int((~paths.generic).sum()),
                   cross_cluster_connectors=int(conn.cross_cluster.sum()))
    (GRAPH_DIR / "connections_summary.json").write_text(json.dumps(summary, indent=2))
    print(summary["note"])
    print(f"{len(people)} investigators work across 2+ diseases ({summary['cross_cluster_people']} across clusters). Top 10:")
    print(people.head(10)[["person", "affiliation", "n_diseases", "cross_cluster"]].to_string(index=False))

    mps = "MONDO:0009657"
    print(f"\n== {dname[mps]} (cluster {cluster_of[mps]}) ==")
    for r in nb[nb.disease_id == mps].itertuples():
        print(f"{r.rank}. {r.neighbour} score {r.score}  shared genes {r.shared_genes}  "
              f"shared pathways {r.n_shared_pathways}")
        print("   shared phenotypes:", [x["name"] for x in json.loads(r.shared_phenotypes)][:3])
        print("   only in this disease:", [x["name"] for x in json.loads(r.only_here)][:3])
    mine = assets[assets.cluster == cluster_of[mps]]
    print(f"\nAssets in its cluster: {len(mine)}")
    print(mine.groupby(["disease", "kind"]).size().to_string())


if __name__ == "__main__":
    main()
