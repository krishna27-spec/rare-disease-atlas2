"""Loading the graph files, searching them, and building the cited candidate actions. No LLM in here."""
import json
import re
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz, process

GRAPH = Path(__file__).resolve().parent.parent.parent / "data" / "graph"
MANUAL = Path(__file__).resolve().parent.parent.parent / "data" / "manual"
NEIGHBOUR_MIN = 0.15          # below this a "neighbour" is too weak to recommend
USEFUL_KINDS = {"natural history study", "registry", "observational study", "animal model", "biomarker"}
COLOURS = {"curated": "#1f77b4", "text_mined": "#ff7f0e", "inferred": "#8c8c8c"}   # used everywhere
EDGE_ID = re.compile(r"E[0-9a-f]{12}")


class Graph:
    def __init__(self):
        self.nodes = pd.read_parquet(GRAPH / "nodes.parquet")
        self.edges = pd.read_parquet(GRAPH / "edges.parquet")
        self.edge_by_id = self.edges.set_index("edge_id", drop=False)
        self.name = dict(zip(self.nodes.node_id, self.nodes.name))
        self.neighbours = pd.read_parquet(GRAPH / "neighbours.parquet")
        self.assets = pd.read_parquet(GRAPH / "cluster_assets.parquet")
        self.people = pd.read_parquet(GRAPH / "shared_people.parquet")
        self.clusters = pd.read_csv(GRAPH / "clusters.csv")
        self.cluster_of = dict(zip(self.clusters.mondo_id, self.clusters.cluster))
        self.diseases = self.nodes[self.nodes.node_type == "Disease"].set_index("node_id")
        orgs = MANUAL / "patient_orgs.csv"
        self.orgs = pd.read_csv(orgs) if orgs.exists() else pd.DataFrame()
        self.summary = json.loads((GRAPH / "connections_summary.json").read_text())
        self._index = self._build_index()

    # ---------- search
    def _build_index(self) -> list[tuple[str, str, str, str]]:
        """(search text, kind, node id, label)."""
        rows = []
        for r in self.diseases.itertuples():
            for s in [r.name, *list(r.synonyms)]:
                rows.append((s.lower(), "disease", r.Index, r.name))
        for r in self.nodes[self.nodes.node_type == "Gene"].itertuples():
            rows += [(r.node_id.lower(), "gene", r.node_id, r.node_id), (r.name.lower(), "gene", r.node_id, r.node_id)]
        for r in self.nodes[self.nodes.node_type == "Phenotype"].itertuples():
            rows.append((r.name.lower(), "symptom", r.node_id, r.name))
        return rows

    def search(self, q: str, limit: int = 6) -> list[dict]:
        q = q.strip().lower()
        if not q:
            return []
        texts = [r[0] for r in self._index]
        hits = process.extract(q, texts, scorer=fuzz.WRatio, limit=40, score_cutoff=88)
        best: dict[str, dict] = {}
        if len(q) >= 4:   # whole-word-ish substring ("sachs" finds Tay-Sachs) counts as a strong match
            hits += [(t, 90.0, i) for i, t in enumerate(texts) if q in t]
        for text, score, i in hits:
            _, kind, nid, label = self._index[i]
            if nid not in best or score > best[nid]["score"]:
                best[nid] = {"kind": kind, "id": nid, "label": label, "matched": text, "score": score}
        return sorted(best.values(), key=lambda h: -h["score"])[:limit]

    def diseases_for(self, kind: str, nid: str) -> list[str]:
        e = self.edges
        if kind == "gene":
            return e[(e.subject == nid) & (e.predicate == "gene_associated_with_disease")].object.tolist() or \
                e[(e.object == nid) & (e.predicate == "gene_associated_with_disease")].subject.tolist()
        return e[(e.object == nid) & (e.predicate == "has_phenotype")].subject.tolist()

    # ---------- one disease
    def facts(self, d: str) -> dict:
        e = self.edges
        genes = e[(e.object == d) & (e.predicate == "gene_associated_with_disease")]
        gset = set(genes.subject)
        paths = e[e.subject.isin(gset) & (e.predicate == "participates_in_pathway")]
        return {
            "genes": sorted(gset), "gene_edges": genes.edge_id.tolist(),
            "pathways": sorted(set(paths.object)),
            "n_phenotypes": int(((e.subject == d) & (e.predicate == "has_phenotype")).sum()),
            "n_trials": int(((e.subject == d) & (e.predicate == "studied_in_trial")).sum()),
            "n_grants": int(((e.subject == d) & (e.predicate == "funded_by")).sum()),
            "n_papers": int(((e.subject == d) & (e.evidence_type == "text_mined")).sum()),
            "cluster": int(self.cluster_of[d]),
            "cluster_members": [self.name[x] for x, c in self.cluster_of.items() if c == self.cluster_of[d]],
        }

    def neighbours_of(self, d: str) -> pd.DataFrame:
        return self.neighbours[self.neighbours.disease_id == d].sort_values("rank")

    def useful_assets(self, d: str) -> pd.DataFrame:
        a = self.assets
        return a[(a.disease_id == d) & a.kind.isin(USEFUL_KINDS)]

    def no_route(self, d: str) -> bool:
        strong = self.neighbours_of(d).query("score >= @NEIGHBOUR_MIN")
        return strong.empty and self.useful_assets(d).empty

    def searched_summary(self, d: str) -> list[str]:
        f = self.facts(d)
        return [f"ClinicalTrials.gov: {f['n_trials']} trials linked to this disease",
                f"NIH RePORTER: {f['n_grants']} grants",
                f"HPO / Orphadata / Reactome: {f['n_phenotypes']} phenotypes, {len(f['genes'])} gene(s), "
                f"{len(f['pathways'])} pathway(s)",
                f"PubMed text mining: {f['n_papers']} extracted facts",
                f"Similarity to the other {len(self.diseases) - 1} diseases: best score "
                f"{self.neighbours_of(d).score.max():.2f} (needs {NEIGHBOUR_MIN})"]

    # ---------- evidence
    def edge(self, eid: str) -> dict | None:
        return self.edge_by_id.loc[eid].to_dict() if eid in self.edge_by_id.index else None

    def comparison_note(self, d: str) -> str:
        """Plain-language reason a 'Contrast' disease is in the Atlas, built from graph data (no extra claims)."""
        if d not in self.diseases.index or self.diseases.loc[d, "group"] != "Contrast":
            return ""
        sanf = self.nodes[(self.nodes.node_type == "Disease") & (self.nodes.group == "Sanfilippo")].node_id
        rows = self.neighbours[(self.neighbours.disease_id == d) & self.neighbours.neighbour_id.isin(sanf)]
        n = int(rows.n_shared_pathways.max()) if len(rows) else 0
        return (f"Included as a comparison disease: it shares up to {n} specific Reactome pathways with the "
                "Sanfilippo (MPS III) diseases, so it shows what is similar and what differs.")

    def label(self, nid: str) -> str:
        return self.name.get(nid, nid)

    # ---------- candidate actions (code only; every one carries the edge IDs that support it)
    def candidates(self, d: str, limit: int = 8) -> list[dict]:
        out = []
        for a in self.useful_assets(d).itertuples():
            out.append({"text": f"Contact the team behind {a.kind} '{a.title}' ({a.asset_id.replace('ASSET:', '')}, "
                                f"sponsor {a.sponsor or 'unknown'}, status {a.status or 'unknown'}) for {self.label(d)}",
                        "edge_ids": [a.edge_id]})
        for n in self.neighbours_of(d).query("score >= @NEIGHBOUR_MIN").itertuples():
            assets = self.useful_assets(n.neighbour_id)
            assets = assets[assets.kind.isin(["natural history study", "registry"])].head(2)
            paths = json.loads(n.shared_pathways)[:1]
            why = f"shares the pathway '{paths[0]['name']}'" if paths else "has similar symptoms"
            for a in assets.itertuples():
                ids = [a.edge_id, n.similar_edge_id] + (paths[0]["edge_ids"][:2] if paths else [])
                out.append({"text": f"{self.label(n.neighbour_id)} {why} with {self.label(d)} "
                                    f"(similarity {n.score:.2f}). It has {a.kind} '{a.title}' "
                                    f"({a.asset_id.replace('ASSET:', '')}, sponsor {a.sponsor or 'unknown'}). "
                                    "Ask whether its protocol, outcome measures or registry could be reused",
                            "edge_ids": [i for i in ids if i]})
        ds = {d} | set(self.neighbours_of(d).query("score >= @NEIGHBOUR_MIN").neighbour_id)
        for p in self.people.itertuples():
            linked = [x for x in json.loads(p.diseases) if x[0] in ds]
            if len(linked) >= 2:
                out.append({"text": f"{p.person} ({p.affiliation or 'affiliation unknown'}) is listed on trials for "
                                    f"{', '.join(x[1] for x in linked)}, so could connect the groups",
                            "edge_ids": json.loads(p.edge_ids)[:4]})
        seen, uniq = set(), []
        for c in out:
            if c["text"] not in seen:
                seen.add(c["text"]); uniq.append(c)
        return uniq[:limit]


def validate_steps(text: str, allowed: set[str]) -> list[str]:
    """Keep only lines (one step per line) that cite at least one edge ID, and only if every ID was in the input."""
    kept = []
    for line in text.splitlines():
        ids = EDGE_ID.findall(line)
        if len(line.strip(" -*•0123456789.[]E,")) > 20 and ids and all(i in allowed for i in ids):
            kept.append(line.strip(" -*•"))
    return kept
