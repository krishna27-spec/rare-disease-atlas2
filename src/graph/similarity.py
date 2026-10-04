"""Milestone 4: how similar are our diseases? Phenotype + pathway similarity, then clusters.

Run:  uv run python -m src.graph.similarity
Reads data/graph/{nodes,edges}.parquet (from src.etl.biology). Writes:
  data/graph/similarity_pairs.csv   every disease pair with its scores and top shared phenotypes
  data/graph/clusters.csv           disease -> cluster
  data/graph/edges.parquet          adds/refreshes the inferred `similar_to` edges
"""
import datetime
import itertools
import math

import networkx as nx
import obonet
import pandas as pd

from src.etl.download import RAW
from src.graph.reactome import generic_pathways
from src.graph.schema import EDGE_SCHEMA, GRAPH_DIR, make_edge, write_table

W_PHENOTYPE, W_PATHWAY = 0.6, 0.4   # combined = 0.6 * phenotype + 0.4 * pathway
MIN_EDGE_SCORE = 0.15               # weaker pairs stay in similarity_pairs.csv but get no edge
SEED = 42                           # makes Louvain give the same answer every run
TOP_SHARED = 5


def information_content(sets: dict[str, set[str]]) -> dict[str, float]:
    """IC(term) = -ln(fraction of our diseases that have the term). Rare term -> high IC."""
    n = len(sets)
    counts: dict[str, int] = {}
    for terms in sets.values():
        for t in terms:
            counts[t] = counts.get(t, 0) + 1
    return {t: -math.log(c / n) for t, c in counts.items()}


def weighted_jaccard(a: set[str], b: set[str], ic: dict[str, float]) -> float:
    """Sum of IC of shared terms / sum of IC of all terms in either. 0 if either side is empty."""
    union = sum(ic[t] for t in a | b)
    return sum(ic[t] for t in a & b) / union if union and a and b else 0.0


def most_specific(shared: set[str], hp: nx.MultiDiGraph) -> list[str]:
    """Drop shared terms that are just a parent of another shared term (keep the specific ones)."""
    parents = set()
    for t in shared:
        parents |= nx.descendants(hp, t)   # obonet edges point child -> parent
    return [t for t in shared if t not in parents]


def main() -> None:
    nodes = pd.read_parquet(GRAPH_DIR / "nodes.parquet")
    edges = pd.read_parquet(GRAPH_DIR / "edges.parquet")
    edges = edges[edges["predicate"] != "similar_to"]          # re-runs replace old similar_to edges
    names = nodes.set_index("node_id")["name"]
    diseases = nodes[nodes["node_type"] == "Disease"]["node_id"].tolist()

    # --- phenotype sets, propagated up the HPO tree (a child term also counts as its parents)
    hp = obonet.read_obo(RAW / "hp.obo")
    pheno: dict[str, set[str]] = {}
    for d in diseases:
        direct = edges[(edges.subject == d) & (edges.predicate == "has_phenotype")]["object"]
        terms = set(direct)
        for t in direct:
            terms |= nx.descendants(hp, t)
        pheno[d] = terms
    ic_p = information_content(pheno)

    # --- pathway sets: a disease's pathways are those of its genes (Reactome file is already all-levels)
    causal = edges[(edges.predicate == "gene_associated_with_disease") & (edges.evidence_type == "curated")]
    genes = {d: set(causal[causal.object == d]["subject"]) for d in diseases}   # curated only: papers can be wrong
    # Reactome only. GO processes (src.etl.go) stay out of the score: they are annotated gene by gene with no shared
    # granularity, so two related genes rarely carry the same term and every pair would be penalised (tried: the NCL
    # cluster fell apart). GO edges are still used as cited mechanism links by the pathway navigator.
    reactome = edges[(edges.predicate == "participates_in_pathway") & edges.object.str.startswith("R-HSA-")]
    gene_paths = reactome.groupby("subject")["object"].apply(set)
    generic = generic_pathways()   # root-level pathways ('Metabolism', 'Disease', ...) fit every disease: skip them
    paths = {d: set().union(*[gene_paths.get(g, set()) for g in genes[d]]) - generic for d in diseases}
    ic_w = information_content(paths)

    # --- scores for every pair
    rows = []
    for a, b in itertools.combinations(diseases, 2):
        ps = weighted_jaccard(pheno[a], pheno[b], ic_p)
        ws = weighted_jaccard(paths[a], paths[b], ic_w)
        # if either disease has no pathway data, don't punish the pair: use phenotype alone
        combined = ps if not (paths[a] and paths[b]) else W_PHENOTYPE * ps + W_PATHWAY * ws
        shared = most_specific(pheno[a] & pheno[b], hp)
        shared = sorted(shared, key=lambda t: -ic_p[t])[:TOP_SHARED]
        shared_paths = sorted(paths[a] & paths[b], key=lambda p: -ic_w[p])[:3]
        rows.append({"disease_a": a, "disease_b": b, "name_a": names[a], "name_b": names[b],
                     "phenotype_score": round(ps, 4), "pathway_score": round(ws, 4),
                     "combined": round(combined, 4),
                     "top_shared_phenotypes": "; ".join(f"{hp.nodes[t]['name']} ({t})" for t in shared),
                     "top_shared_pathways": "; ".join(f"{nodes.set_index('node_id').loc[p, 'name']} ({p})"
                                                      for p in shared_paths)})
    pairs = pd.DataFrame(rows).sort_values("combined", ascending=False)
    pairs.to_csv(GRAPH_DIR / "similarity_pairs.csv", index=False)

    # --- Louvain clusters on the weighted similarity graph
    g = nx.Graph()
    g.add_nodes_from(diseases)
    for r in pairs[pairs["combined"] >= MIN_EDGE_SCORE].itertuples():
        g.add_edge(r.disease_a, r.disease_b, weight=r.combined)
    communities = nx.community.louvain_communities(g, weight="weight", seed=SEED)
    communities = sorted(communities, key=lambda c: -len(c))
    cluster_of = {d: i + 1 for i, c in enumerate(communities) for d in c}
    clusters = pd.DataFrame({"mondo_id": diseases, "name": [names[d] for d in diseases],
                             "cluster": [cluster_of[d] for d in diseases]}).sort_values(["cluster", "mondo_id"])
    clusters.to_csv(GRAPH_DIR / "clusters.csv", index=False)

    # --- inferred edges (every one says how it was computed)
    today = datetime.date.today().isoformat()
    method = (f"IC-weighted Jaccard: {W_PHENOTYPE} x phenotype (HPO, propagated) + "
              f"{W_PATHWAY} x pathway (Reactome); phenotype only if a disease has no pathways")
    new = [make_edge(r.disease_a, "similar_to", r.disease_b, "inferred", r.combined, "Atlas similarity",
                     f"{r.disease_a}|{r.disease_b}|phenotype={r.phenotype_score}|pathway={r.pathway_score}",
                     "", today, method=method)
           for r in pairs[pairs["combined"] >= MIN_EDGE_SCORE].itertuples()]
    write_table(edges.to_dict("records") + new, EDGE_SCHEMA, "edges")

    print(f"{len(pairs)} pairs scored, {len(new)} similar_to edges (score >= {MIN_EDGE_SCORE})")
    print(f"score range {pairs.combined.min():.3f} to {pairs.combined.max():.3f}, median {pairs.combined.median():.3f}")
    print("\nClusters:")
    for i, c in enumerate(communities, 1):
        print(f"  Cluster {i}: " + ", ".join(sorted(names[d] for d in c)))


if __name__ == "__main__":
    main()
