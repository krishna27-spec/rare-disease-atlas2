"""The Atlas query layer: everything a UI needs, as plain functions that return JSON-ready dicts and lists.

No Streamlit, no HTTP: `Atlas()` loads data/graph/ once, then answers questions. src/atlas/server.py wraps the
same methods as HTTP endpoints. Only `next_steps(..., explain=True)` calls the LLM; everything else is graph lookups.

The four capabilities of the brief:
  Search engine      search(q)
  Clustering         clusters(), cluster(id), clusters_for_mechanism(q)
  Pathway navigator  pathway_paths(disease)
  Connector          connectors(disease= / pathway= ...)
plus disease(id), neighbours(id), assets(id), edge(id), subgraph(id), next_steps(id), contradictions(), stats().

Rule kept everywhere: every item carries `edge_ids`, the graph edges that support it. A UI shows the evidence by
calling edge(edge_id). When nothing is supported, the answer says so and says what was searched.
"""
import json
import math
import re

import pandas as pd
from rapidfuzz import fuzz, process

from src.webapp.data import GRAPH, NEIGHBOUR_MIN, USEFUL_KINDS, Graph

MIN_SEARCH_SCORE = 88
ACTIVE = ["RECRUITING", "ACTIVE_NOT_RECRUITING", "NOT_YET_RECRUITING", "ENROLLING_BY_INVITATION"]
EDGE_FIELDS = ["edge_id", "subject", "predicate", "object", "evidence_type", "confidence", "source", "source_record",
               "source_url", "retrieved", "evidence_text", "method", "contradicts", "reviewer_verdict"]


def clean(x):
    """Make pandas/numpy values safe for JSON (NaN -> None, numpy numbers -> Python numbers, arrays -> lists)."""
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, set)) or hasattr(x, "tolist"):
        return [clean(v) for v in (x.tolist() if hasattr(x, "tolist") else x)] if not _scalar(x) else clean(x.item())
    if isinstance(x, float) and math.isnan(x):
        return None
    if hasattr(x, "item"):
        return clean(x.item())
    return x


def _scalar(x) -> bool:
    return hasattr(x, "ndim") and x.ndim == 0


def _attrs(text) -> dict:
    return json.loads(text) if isinstance(text, str) and text else {}


class Atlas:
    def __init__(self):
        self.G = Graph()                       # nodes, edges, neighbours, assets, clusters, fuzzy search (reused)
        g = self.G
        self.nodes = g.nodes.set_index("node_id", drop=False)
        self.edges = g.edges
        self.pathways = pd.read_parquet(GRAPH / "pathways.parquet").set_index("pathway_id", drop=False)
        self.people = pd.read_parquet(GRAPH / "connectors.parquet")
        self.contra = pd.read_parquet(GRAPH / "contradictions.parquet")
        e = self.edges
        self.causal = e[(e.predicate == "gene_associated_with_disease") & (e.evidence_type == "curated")]
        self.in_pathway = e[e.predicate == "participates_in_pathway"]
        self.serves = e[e.predicate == "serves_disease"]
        self._index = list(g._index)           # (text, kind, id, label) for diseases, genes, symptoms
        for p in self.pathways[~self.pathways.generic].itertuples():
            self._index.append((p.name.lower(), "pathway", p.pathway_id, p.name))
        for o in self.nodes[self.nodes.node_type == "PatientOrg"].itertuples():
            self._index.append((o.name.lower(), "patient_org", o.node_id, o.name))

    # ------------------------------------------------------------------ helpers
    def name(self, nid: str) -> str:
        return self.G.label(nid)

    def is_disease(self, nid: str) -> bool:
        return nid in self.G.diseases.index

    def _need_disease(self, d: str) -> None:
        if not self.is_disease(d):
            raise KeyError(f"{d} is not one of the {len(self.G.diseases)} diseases in the Atlas")

    def genes_of(self, d: str) -> list[dict]:
        rows = self.causal[self.causal.object == d]
        return [{"gene": r.subject, "name": self.name(r.subject), "confidence": r.confidence,
                 "clinvar_pathogenic_alleles": self.nodes.loc[r.subject, "clinvar_pathogenic_alleles"]
                 if r.subject in self.nodes.index else None, "edge_ids": [r.edge_id]} for r in rows.itertuples()]

    def orgs_of(self, d: str) -> list[dict]:
        """Patient organisations for a disease, one entry each (hand-checked and website-read edges merged)."""
        out: dict[str, dict] = {}
        for r in self.serves[self.serves.object == d].sort_values("confidence", ascending=False).itertuples():
            a = _attrs(self.nodes.loc[r.subject, "attrs"])
            o = out.setdefault(r.subject, {
                "org_id": r.subject, "name": self.name(r.subject), "url": a.get("url", ""),
                "registry_or_study": a.get("registry_or_study", ""),
                "registry_mentions": a.get("registry_mentions", []),     # sentences from its own pages, with URLs
                "date_checked": a.get("date_checked", ""), "hand_checked": False, "confidence": r.confidence,
                "quote": "", "edge_ids": []})
            o["edge_ids"].append(r.edge_id)
            o["hand_checked"] = o["hand_checked"] or (r.evidence_type == "curated" and a.get("scope_verified", False))
            if r.evidence_text and not o["quote"]:
                o["quote"] = r.evidence_text
        return sorted(out.values(), key=lambda o: (-o["hand_checked"], -o["confidence"]))

    def _diseases_for(self, kind: str, nid: str) -> list[dict]:
        """The diseases a non-disease search hit leads to, each with the edges that make the link."""
        e = self.edges
        if kind == "gene":
            rows = e[(e.subject == nid) & (e.predicate == "gene_associated_with_disease")]
            pairs = [(r.object, [r.edge_id]) for r in rows.itertuples()]
        elif kind == "symptom":
            rows = e[(e.object == nid) & (e.predicate == "has_phenotype")]
            pairs = [(r.subject, [r.edge_id]) for r in rows.itertuples()]
        elif kind == "patient_org":
            rows = self.serves[self.serves.subject == nid]
            pairs = [(r.object, [r.edge_id]) for r in rows.itertuples()]
        elif kind == "pathway":
            p = self.pathways.loc[nid]
            ids = json.loads(p.edge_ids)
            pairs = []
            for d, _ in json.loads(p.diseases):
                gs = [g["gene"] for g in self.genes_of(d) if g["gene"] in ids]
                pairs.append((d, [ids[g] for g in gs] + [x for g in self.genes_of(d) if g["gene"] in gs
                                                         for x in g["edge_ids"]]))
        else:
            return []
        merged: dict[str, list[str]] = {}
        for d, ids in pairs:
            merged.setdefault(d, []).extend(ids)
        return [{"id": d, "name": self.name(d), "edge_ids": sorted(set(ids))} for d, ids in merged.items()]

    # ------------------------------------------------------------------ 1. search engine
    def search(self, q: str, limit: int = 8) -> dict:
        """One box for a disease, synonym, gene, symptom, pathway or patient group (typos tolerated)."""
        text = q.strip().lower()
        hits: dict[str, dict] = {}
        if text:
            texts = [r[0] for r in self._index]
            found = process.extract(text, texts, scorer=fuzz.WRatio, limit=60, score_cutoff=MIN_SEARCH_SCORE)
            if len(text) >= 4:
                found += [(t, 90.0, i) for i, t in enumerate(texts) if text in t]
            for matched, score, i in found:
                _, kind, nid, label = self._index[i]
                if nid not in hits or score > hits[nid]["score"]:
                    hits[nid] = {"kind": kind, "id": nid, "label": label, "matched": matched, "score": round(score, 1)}
        ranked = sorted(hits.values(), key=lambda h: (-h["score"], h["kind"] != "disease"))[:limit]
        for h in ranked:
            if h["kind"] != "disease":
                h["diseases"] = self._diseases_for(h["kind"], h["id"])
        out = {"query": q, "hits": ranked}
        if not ranked:
            out["known_elsewhere"] = self.outside(q)   # real rare diseases the Atlas has not loaded yet
            n = self.nodes.node_type.value_counts()
            out["no_match"] = {
                "message": f"Nothing in the Atlas matches '{q}'. That means it is outside what was loaded, "
                           "not that nothing is known about it.",
                "searched": {"diseases": int(n.get("Disease", 0)), "genes": int(n.get("Gene", 0)),
                             "symptoms": int(n.get("Phenotype", 0)),
                             "specific_pathways": int((~self.pathways.generic).sum()),
                             "patient_organisations": int(n.get("PatientOrg", 0))},
                "what_would_change_this": "Add the disease (MONDO ID and causal gene) to data/manual/diseases.csv "
                                          "and rebuild the graph."}
        return clean(out)

    def diseases(self) -> list[dict]:
        return clean([{"id": d, "name": r["name"], "group": r["group"], "cluster": self.G.cluster_of[d],
                       "genes": [g["gene"] for g in self.genes_of(d)]} for d, r in self.G.diseases.iterrows()])

    def disease(self, d: str) -> dict:
        """The summary card for one disease. Every count is a count of graph edges."""
        self._need_disease(d)
        r, e = self.G.diseases.loc[d], self.edges
        mine = e[(e.subject == d) | (e.object == d)]
        tm = mine[(mine.evidence_type == "text_mined") & (mine.source == "PubMed")]
        return clean({
            "id": d, "name": r["name"], "synonyms": list(r["synonyms"]), "xrefs": list(r["xrefs"]),
            "group": r["group"], "cluster": self.G.cluster_of[d],
            "cluster_members": [{"id": x, "name": self.name(x)} for x, c in self.G.cluster_of.items()
                                if c == self.G.cluster_of[d] and x != d],
            "genes": self.genes_of(d), "patient_orgs": self.orgs_of(d),
            "counts": {"phenotypes": int(((e.subject == d) & (e.predicate == "has_phenotype")
                                          & (e.evidence_type == "curated")).sum()),
                       "trials": int(((e.subject == d) & (e.predicate == "studied_in_trial")).sum()),
                       "grants": int(((e.subject == d) & (e.predicate == "funded_by")).sum()),
                       "assets": int(((e.subject == d) & (e.predicate == "has_asset")).sum()),
                       "facts_from_papers": len(tm),
                       "edges_by_evidence_type": mine.evidence_type.value_counts().to_dict()},
            "comparison_note": self.G.comparison_note(d),
            "key_facts": self.key_facts(d),
            "facts_from_papers": [self.edge(x, brief=True) for x in tm.edge_id],
        })

    # ------------------------------------------------------------------ 2. clustering
    def neighbours(self, d: str) -> dict:
        """'Who is like us': the most similar diseases, why (shared), and what differs. Weak ones are flagged."""
        self._need_disease(d)
        out = []
        for r in self.G.neighbours_of(d).itertuples():
            out.append({"id": r.neighbour_id, "name": r.neighbour, "rank": r.rank, "score": r.score,
                        "phenotype_score": r.phenotype_score, "pathway_score": r.pathway_score,
                        "supported": r.score >= NEIGHBOUR_MIN, "same_cluster":
                            self.G.cluster_of[d] == self.G.cluster_of[r.neighbour_id],
                        "shared_pathways": json.loads(r.shared_pathways), "n_shared_pathways": r.n_shared_pathways,
                        "shared_phenotypes": json.loads(r.shared_phenotypes),
                        "genes_here": json.loads(r.genes), "genes_there": json.loads(r.neighbour_genes),
                        "only_here": json.loads(r.only_here), "only_there": json.loads(r.only_neighbour),
                        "edge_ids": [x for x in [r.similar_edge_id] if x] + json.loads(r.gene_edge_ids)})
        return clean({"disease": {"id": d, "name": self.name(d)}, "threshold": NEIGHBOUR_MIN,
                      "method": "IC-weighted Jaccard: 0.6 x phenotype (HPO) + 0.4 x pathway (Reactome)",
                      "neighbours": out})

    def _cluster_profile(self, cid: int) -> dict:
        members = [d for d, c in self.G.cluster_of.items() if c == cid]
        e = self.edges
        # shared specific pathways: carried by the genes of at least two members
        paths = []
        for p in self.pathways[~self.pathways.generic].itertuples():
            ds = [d for d, _ in json.loads(p.diseases) if d in members]
            if len(ds) >= 2:
                paths.append({"id": p.pathway_id, "name": p.name, "members": [self.name(d) for d in ds],
                              "n_members": len(ds), "n_diseases_total": p.n_diseases,
                              "edge_ids": sorted(json.loads(p.edge_ids).values())})
        paths.sort(key=lambda x: (-x["n_members"], x["n_diseases_total"]))
        # shared symptoms: curated phenotypes held by at least two members; rarer across the Atlas ranks higher
        ph = e[(e.predicate == "has_phenotype") & (e.evidence_type == "curated")]
        total = ph.groupby("object").subject.nunique()
        mine = ph[ph.subject.isin(members)]
        phenos = []
        for hp_id, grp in mine.groupby("object"):
            if grp.subject.nunique() >= 2:
                phenos.append({"id": hp_id, "name": self.name(hp_id), "n_members": grp.subject.nunique(),
                               "n_diseases_total": int(total[hp_id]), "edge_ids": grp.edge_id.tolist()})
        phenos.sort(key=lambda x: (-(x["n_members"] / len(members)) + x["n_diseases_total"] / 100, x["name"]))
        return {"shared_pathways": paths, "shared_phenotypes": phenos}

    def clusters(self) -> list[dict]:
        out = []
        for cid in sorted(set(self.G.cluster_of.values())):
            members = [d for d, c in self.G.cluster_of.items() if c == cid]
            prof = self._cluster_profile(cid)
            a = self.G.assets[self.G.assets.disease_id.isin(members)]
            out.append({"cluster": cid, "size": len(members),
                        "members": [{"id": d, "name": self.name(d), "genes": [g["gene"] for g in self.genes_of(d)]}
                                    for d in members],
                        "top_shared_pathways": prof["shared_pathways"][:3],
                        "top_shared_phenotypes": prof["shared_phenotypes"][:5],
                        "asset_counts": a.kind.value_counts().to_dict(),
                        "n_patient_orgs": self.serves[self.serves.object.isin(members)].subject.nunique(),
                        "singleton": len(members) == 1})
        return clean(out)

    def cluster(self, cid: int) -> dict:
        members = [d for d, c in self.G.cluster_of.items() if c == cid]
        if not members:
            raise KeyError(f"no cluster {cid}")
        prof = self._cluster_profile(cid)
        a = self.G.assets[self.G.assets.disease_id.isin(members) & self.G.assets.kind.isin(USEFUL_KINDS)]
        orgs: dict[str, dict] = {}
        for d in members:
            for o in self.orgs_of(d):
                x = orgs.setdefault(o["org_id"], {**o, "serves": [], "edge_ids": []})
                x["serves"].append(self.name(d))
                x["edge_ids"] += o["edge_ids"]
        sim = self.edges[(self.edges.predicate == "similar_to") & self.edges.subject.isin(members)
                         & self.edges.object.isin(members)]
        return clean({
            "cluster": cid, "members": [self.disease_brief(d) for d in members],
            "why_together": {"method": "Louvain communities on the similarity graph (similar_to edges, score >= "
                                       f"{NEIGHBOUR_MIN})", "similarity_edge_ids": sim.edge_id.tolist(), **prof},
            "reusable_assets": [self._asset(r) for r in a.itertuples()],
            "patient_orgs": list(orgs.values()),
            "connectors": self.connectors(cluster=cid)["people"][:15],
            "note": "A cluster of one means no other disease scored above the threshold: an honest gap, not an error."
                    if len(members) == 1 else ""})

    def disease_brief(self, d: str) -> dict:
        return {"id": d, "name": self.name(d), "genes": [g["gene"] for g in self.genes_of(d)],
                "edge_ids": [x for g in self.genes_of(d) for x in g["edge_ids"]]}

    def clusters_for_mechanism(self, q: str) -> dict:
        """Priya's view: given a mechanism (a pathway name/ID or a gene), rank the clusters it touches."""
        targets = {}
        if q in self.pathways.index:
            targets[q] = "pathway"
        else:
            for h in self.search(q, limit=12)["hits"]:
                if h["kind"] == "pathway":
                    targets[h["id"]] = "pathway"
                elif h["kind"] == "gene":
                    for p in self.in_pathway[self.in_pathway.subject == h["id"]].object:
                        if p in self.pathways.index and not self.pathways.loc[p, "generic"]:
                            targets[p] = f"pathway of gene {h['id']}"
        if not targets:
            return {"query": q, "pathways": [], "clusters": [],
                    "no_match": f"No specific Reactome pathway or gene in the Atlas matches '{q}'. "
                                f"{int((~self.pathways.generic).sum())} pathways and "
                                f"{(self.nodes.node_type == 'Gene').sum()} genes were searched."}
        by_cluster: dict[int, dict] = {}
        for pid in targets:
            p = self.pathways.loc[pid]
            for hit in self._diseases_for("pathway", pid):
                c = by_cluster.setdefault(self.G.cluster_of[hit["id"]], {"diseases": {}, "pathways": set()})
                d = c["diseases"].setdefault(hit["id"], {"id": hit["id"], "name": hit["name"], "via_pathways": [],
                                                         "edge_ids": []})
                d["via_pathways"].append(p["name"])
                d["edge_ids"] = sorted(set(d["edge_ids"]) | set(hit["edge_ids"]))
                c["pathways"].add(pid)
        out = []
        for cid, c in by_cluster.items():
            size = sum(1 for x in self.G.cluster_of.values() if x == cid)
            ds = list(c["diseases"])
            a = self.G.assets[self.G.assets.disease_id.isin(ds)]
            orgs = {o["org_id"]: o for d in ds for o in self.orgs_of(d)}
            active = a[(a.kind == "interventional trial") & a.status.isin(["RECRUITING", "ACTIVE_NOT_RECRUITING",
                                                                           "NOT_YET_RECRUITING", "ENROLLING_BY_INVITATION"])]
            out.append({"cluster": cid, "cluster_size": size, "n_matching_diseases": len(ds),
                        "coverage": round(len(ds) / size, 2), "n_matching_pathways": len(c["pathways"]),
                        "diseases": list(c["diseases"].values()),
                        "patient_orgs": list(orgs.values()),
                        "infrastructure": a.kind.value_counts().to_dict(),
                        "unmet_need": {"diseases_with_no_active_interventional_trial":
                                       [self.name(d) for d in ds if d not in set(active.disease_id)],
                                       "diseases_with_no_patient_org_recorded":
                                       [self.name(d) for d in ds if not self.orgs_of(d)]},
                        "contacts": self.connectors(diseases=ds, min_diseases=1)["people"][:8]})
        out.sort(key=lambda x: (-x["n_matching_diseases"], -x["n_matching_pathways"], -x["coverage"]))
        return clean({"query": q, "pathways": [{"id": p, "name": self.pathways.loc[p, "name"], "matched_as": how}
                                               for p, how in targets.items()],
                      "ranking": "by number of diseases in the cluster whose causal gene is in a matching pathway",
                      "clusters": out})

    # ------------------------------------------------------------------ 3. pathway navigator
    def pathway_paths(self, d: str, max_paths: int = 12) -> dict:
        """Disease -> its gene -> a specific pathway -> another gene -> another disease -> who and what is there.

        Paths through the most specific pathways (fewest diseases) come first. Every hop names its edge."""
        self._need_disease(d)
        my_genes = {g["gene"]: g["edge_ids"][0] for g in self.genes_of(d)}
        paths, no_pathway_genes = [], []
        for gene, gene_edge in my_genes.items():
            mine = self.in_pathway[self.in_pathway.subject == gene]
            specific = [p for p in mine.object if p in self.pathways.index and not self.pathways.loc[p, "generic"]]
            if not specific:
                no_pathway_genes.append(gene)
            for pid in specific:
                p = self.pathways.loc[pid]
                p_edges = json.loads(p.edge_ids)
                for other, other_name in json.loads(p.diseases):
                    if other == d:
                        continue
                    for og in self.genes_of(other):
                        if og["gene"] not in p_edges:
                            continue
                        a = self.G.useful_assets(other)
                        sim = self.G.neighbours[(self.G.neighbours.disease_id == d)
                                                & (self.G.neighbours.neighbour_id == other)]
                        steps = [
                            {"from": d, "from_name": self.name(d), "relation": "is caused by variants in",
                             "to": gene, "to_name": gene, "edge_id": gene_edge},
                            {"from": gene, "from_name": gene, "relation": "works in the pathway",
                             "to": pid, "to_name": p["name"], "edge_id": p_edges[gene]},
                            {"from": pid, "from_name": p["name"], "relation": "also involves",
                             "to": og["gene"], "to_name": og["gene"], "edge_id": p_edges[og["gene"]]},
                            {"from": og["gene"], "from_name": og["gene"], "relation": "whose variants cause",
                             "to": other, "to_name": other_name, "edge_id": og["edge_ids"][0]}]
                        paths.append({
                            "to_disease": {"id": other, "name": other_name},
                            "pathway": {"id": pid, "name": p["name"],
                                        "source": "Gene Ontology" if pid.startswith("GO:") else "Reactome"},
                            "pathway_specificity": {"n_diseases": p.n_diseases, "n_genes": p.n_genes},
                            "same_gene": og["gene"] == gene,
                            "similarity": sim.score.iloc[0] if len(sim) else None,
                            "same_cluster": self.G.cluster_of[d] == self.G.cluster_of[other],
                            "steps": steps, "edge_ids": [s["edge_id"] for s in steps],
                            "what_is_there": {"patient_orgs": self.orgs_of(other),
                                              "reusable_assets": [self._asset(r) for r in a.head(5).itertuples()],
                                              "n_reusable_assets": len(a)},
                            "check_before_acting": "Sharing a pathway does not mean a study design or a therapy "
                                                   "transfers. An expert must check the mechanism and eligibility."})
        paths.sort(key=lambda x: (x["pathway_specificity"]["n_diseases"], -(x["similarity"] or 0)))
        seen, best = set(), []
        for p in paths:                       # for the short list keep the most specific path to each disease
            if p["to_disease"]["id"] not in seen:
                seen.add(p["to_disease"]["id"])
                best.append(p)
        # then show the closest diseases first: same cluster, then overall similarity, then pathway specificity
        best.sort(key=lambda x: (not x["same_cluster"], -(x["similarity"] or 0), x["pathway_specificity"]["n_diseases"]))
        out = {"disease": {"id": d, "name": self.name(d)}, "genes": list(my_genes),
               "n_paths_total": len(paths), "paths": best[:max_paths]}
        if not paths:
            nb = [n for n in self.neighbours(d)["neighbours"] if n["supported"]]
            out["no_route"] = {
                "message": "No disease in the Atlas shares a specific Reactome pathway with this one.",
                "why": (f"Reactome records no specific pathway for {', '.join(no_pathway_genes)}."
                        if no_pathway_genes else "Its pathways are not shared by any other disease gene loaded."),
                "searched": f"{int((~self.pathways.generic).sum())} specific Reactome pathways across "
                            f"{(self.nodes.node_type == 'Gene').sum()} genes",
                "what_would_change_this": "A curated or published link between this gene and a biological process "
                                          "(for example Gene Ontology annotations or a paper stating the pathway).",
                "symptom_based_alternatives": [{"id": n["id"], "name": n["name"], "score": n["score"],
                                                "edge_ids": n["edge_ids"]} for n in nb]}
        return clean(out)

    # ------------------------------------------------------------------ 4. connector
    def connectors(self, disease: str | None = None, pathway: str | None = None, cluster: int | None = None,
                   diseases: list[str] | None = None, cross_cluster_only: bool = False, min_diseases: int = 2,
                   limit: int = 50) -> dict:
        """People and organisations that link diseases: 'who else works on my mechanism, and how do I reach them'.

        Scope: one disease (it plus its supported neighbours), a pathway (the diseases whose gene is in it),
        a cluster, or an explicit list. With no scope, everyone who links 2+ diseases in the Atlas."""
        scope, focus = None, None
        if disease:
            self._need_disease(disease)
            nb = self.G.neighbours_of(disease)
            scope, focus = {disease} | set(nb[nb.score >= NEIGHBOUR_MIN].neighbour_id), disease
        elif pathway:
            if pathway not in self.pathways.index:
                raise KeyError(f"unknown pathway {pathway}")
            scope = {d for d, _ in json.loads(self.pathways.loc[pathway, "diseases"])}
        elif cluster is not None:
            scope = {d for d, c in self.G.cluster_of.items() if c == cluster}
        elif diseases is not None:
            scope = set(diseases)
        people = []
        for r in self.people.itertuples():
            ds = json.loads(r.diseases)
            linked = [x for x in ds if scope is None or x["id"] in scope]
            if len(linked) < min_diseases or (focus and focus not in {x["id"] for x in linked}):
                continue
            if cross_cluster_only and not r.cross_cluster:
                continue
            people.append({"person_id": r.person_id, "name": r.person, "affiliation": r.affiliation,
                           "links": linked, "n_diseases_in_scope": len(linked), "n_diseases_total": r.n_diseases,
                           "via": json.loads(r.via), "cross_cluster": r.cross_cluster,
                           "how_to_reach": "Through the listed trial, grant or paper record (open any edge to get "
                                           "its source link); the graph stores no private contact details.",
                           "edge_ids": json.loads(r.edge_ids)})
        people.sort(key=lambda p: (-p["n_diseases_in_scope"], -p["cross_cluster"], -p["n_diseases_total"]))
        orgs: dict[str, dict] = {}
        for d in (scope if scope is not None else list(self.G.diseases.index)):
            for o in self.orgs_of(d):
                x = orgs.setdefault(o["org_id"], {**o, "serves": [], "edge_ids": []})
                x["serves"].append({"id": d, "name": self.name(d)})
                x["edge_ids"] += o["edge_ids"]
        bridging = [o for o in orgs.values() if len(o["serves"]) >= min(2, min_diseases)]
        out = {"scope": [{"id": d, "name": self.name(d)} for d in sorted(scope)] if scope is not None else "all",
               "people": people[:limit], "n_people": len(people),
               "organisations": sorted(bridging, key=lambda o: -len(o["serves"]))}
        if not people and not bridging:
            out["no_connector"] = ("No person or organisation in the graph links these diseases. Searched: "
                                   "investigators on ClinicalTrials.gov studies, NIH RePORTER grant leaders, authors "
                                   "of the papers that were read, and the hand-checked patient organisations.")
        return clean(out)

    # ------------------------------------------------------------------ what exists
    def _asset(self, r) -> dict:
        return {"asset_id": r.asset_id, "kind": r.kind, "title": r.title, "status": r.status, "sponsor": r.sponsor,
                "disease": {"id": r.disease_id, "name": r.disease}, "source_url": r.source_url,
                "confidence": r.confidence, "edge_ids": [r.edge_id]}

    def assets(self, d: str, include_cluster: bool = True) -> dict:
        """'What useful work already exists': this disease's assets, then its cluster's reusable ones."""
        self._need_disease(d)
        a = self.G.assets
        cid = self.G.cluster_of[d]
        own = a[a.disease_id == d]
        out = {"disease": {"id": d, "name": self.name(d)},
               "own": [self._asset(r) for r in own.itertuples()],
               "own_counts": own.kind.value_counts().to_dict(), "patient_orgs": self.orgs_of(d)}
        if include_cluster:
            sib = a[(a.cluster == cid) & (a.disease_id != d) & a.kind.isin(USEFUL_KINDS)]
            out["cluster_reusable"] = [self._asset(r) for r in sib.itertuples()]
        return clean(out)

    # ------------------------------------------------------------------ evidence
    def edge(self, eid: str, brief: bool = False) -> dict:
        """Everything known about one edge: source, date, confidence, quote, reviewer verdict, contradictions."""
        e = self.G.edge(eid)
        if e is None:
            raise KeyError(f"unknown edge {eid}")
        out = {k: e[k] for k in EDGE_FIELDS}
        out["contradicts"] = list(out["contradicts"]) if out["contradicts"] is not None else []
        out["subject_name"], out["object_name"] = self.name(e["subject"]), self.name(e["object"])
        out["kind"] = {"curated": "from a database or registry",
                       "text_mined": "read from a paper by an LLM; the quoted sentence was verified to be in the "
                       "abstract" if e["source"] == "PubMed" else "read from the organisation's own web page by code; "
                       "the sentence naming the disease is stored",
                       "inferred": "computed by the Atlas, not an observation"}[e["evidence_type"]]
        if not brief:
            out["contradicted_by"] = [self.edge(x, brief=True) for x in out["contradicts"]]
        return clean(out)

    def contradictions(self) -> dict:
        tm = self.edges[(self.edges.evidence_type == "text_mined") & (self.edges.source == "PubMed")]
        rows = [{**r._asdict(), "subject_name": self.name(r.subject), "object_name": self.name(r.object),
                 "edge_ids": [r.edge_a, r.edge_b]} for r in self.contra.itertuples(index=False)]
        return clean({"contradictions": rows, "n_text_mined_facts": len(tm),
                      "n_denials": int(tm.predicate.str.startswith("not_").sum()),
                      "note": self.G.summary.get("note", "")})

    def subgraph(self, d: str, max_symptoms: int = 4, max_pathways: int = 6) -> dict:
        """Nodes and edges to draw around one disease: neighbours, genes, shared pathways, paper symptoms, orgs."""
        self._need_disease(d)
        nodes: dict[str, dict] = {}
        edges: dict[str, dict] = {}

        def node(nid, kind):
            nodes.setdefault(nid, {"id": nid, "label": self.name(nid), "type": kind})

        def link(eid):
            e = self.G.edge(eid)
            if e:
                edges[eid] = {"id": eid, "source": e["subject"], "target": e["object"], "predicate": e["predicate"],
                              "evidence_type": e["evidence_type"], "confidence": e["confidence"]}

        node(d, "centre")
        nb = [n for n in self.neighbours(d)["neighbours"] if n["supported"]][:4]
        shown = [d] + [n["id"] for n in nb]
        for n in nb:
            node(n["id"], "disease")
            link(n["edge_ids"][0])
        for x in shown:
            for g in self.genes_of(x):
                node(g["gene"], "gene")
                link(g["edge_ids"][0])
            for o in self.orgs_of(x):
                node(o["org_id"], "patient_org")
                link(o["edge_ids"][0])
        e = self.edges
        tm = e[(e.subject == d) & (e.predicate == "has_phenotype") & (e.evidence_type == "text_mined")]
        for r in tm.sort_values("confidence", ascending=False).drop_duplicates("object").head(max_symptoms).itertuples():
            node(r.object, "symptom")
            link(r.edge_id)
        tmg = e[(e.object.isin(shown)) & (e.predicate == "gene_associated_with_disease") & (e.evidence_type == "text_mined")]
        for r in tmg.drop_duplicates(["subject", "object"]).itertuples():
            node(r.subject, "gene")
            link(r.edge_id)
        n_paths = 0
        for n in nb:
            for p in n["shared_pathways"]:
                if p["id"] in nodes or n_paths >= max_pathways:
                    continue
                n_paths += 1
                node(p["id"], "pathway")
                for eid in p["edge_ids"]:
                    x = self.G.edge(eid)
                    if x and x["subject"] in nodes:
                        link(eid)
        return clean({"centre": d, "nodes": list(nodes.values()), "edges": list(edges.values()),
                      "legend": {"curated": "database", "text_mined": "paper quote", "inferred": "computed similarity"}})

    # ------------------------------------------------------------------ what to do next
    def next_steps(self, d: str, explain: bool = True) -> dict:
        """Cited candidate actions built by code; optionally 1-3 plain-language steps written by gpt-oss.

        The LLM only rewrites the candidates. Any line citing no edge ID, or one that was not given, is discarded.
        If nothing is supported the answer is the no-route account: what was searched and what would change it."""
        self._need_disease(d)
        cands = self.G.candidates(d, limit=6) + self._org_candidates(d)
        out = {"disease": {"id": d, "name": self.name(d)}, "candidates": cands, "steps": [], "used_llm": False,
               "llm_note": "", "searched": self.G.searched_summary(d),
               "expert_must_check": ["Whether the shared pathway means the same disease mechanism in both diseases.",
                                     "Whether the other study's eligibility criteria and outcome measures fit this "
                                     "disease.", "Whether the listed team and study are still active."],
               "disclaimer": "Research exploration tool. Not medical advice."}
        if not cands:
            out["no_route"] = {
                "message": "No supported next step was found for this disease.",
                "what_is_missing": [f"A disease with similarity of at least {NEIGHBOUR_MIN} to this one",
                                    "A natural history study, registry or observational study for it or a neighbour",
                                    "An investigator who links it to another disease"],
                "what_would_change_this": "A registered natural history study or registry, or new evidence linking "
                                          "its gene to a pathway shared with another disease."}
            return clean(out)
        if explain:
            from src.webapp.explain import next_steps as write_steps
            res = write_steps(self.name(d), cands)
            out.update(steps=res["steps"], used_llm=res["used_llm"], llm_note=res["error"])
        return clean(out)

    def _org_candidates(self, d: str, limit: int = 3) -> list[dict]:
        """Cited actions that involve a patient organisation: this disease's own, then its closest neighbour's."""
        out = []
        for o in self.orgs_of(d)[:2]:
            reg = o["registry_mentions"][0]["quote"] if o["registry_mentions"] else ""
            out.append({"text": f"Contact {o['name']} ({o['url']}), a patient organisation for {self.name(d)}"
                                + (f". Its website says: \"{reg[:200]}\"" if reg else ""),
                        "edge_ids": o["edge_ids"][:2]})
        nb = self.G.neighbours_of(d)
        for n in nb[nb.score >= NEIGHBOUR_MIN].head(2).itertuples():
            mine = {o["org_id"] for o in self.orgs_of(d)}
            for o in self.orgs_of(n.neighbour_id):
                if o["org_id"] not in mine and o["registry_mentions"]:
                    out.append({"text": f"{o['name']} ({o['url']}) serves {n.neighbour}, which is similar to "
                                        f"{self.name(d)} (similarity {n.score:.2f}). Its website mentions a "
                                        f"{o['registry_mentions'][0]['kind']}: ask whether it could be shared",
                                "edge_ids": o["edge_ids"][:1] + ([n.similar_edge_id] if n.similar_edge_id else [])})
                    break
        return out[:limit]

    # ------------------------------------------------------------------ biology and the 10x case
    def biology(self, d: str) -> dict:
        """The disease's biology, most informative first: gene (and how it is affected), mechanisms, symptoms."""
        self._need_disease(d)
        e = self.edges
        genes = []
        for g in self.genes_of(d):
            rec = self.G.edge(g["edge_ids"][0])["source_record"]
            m = re.search(r"\(([^)]*function[^)]*)\)", rec)       # Orphadata: "... mutation(s) (loss of function) in"
            genes.append({**g, "how_affected": m.group(1) if m else "", "via_parent_disease": "via parent" in rec})
        mine = self.in_pathway[self.in_pathway.subject.isin([g["gene"] for g in genes])]
        paths = []
        for r in mine.itertuples():
            if r.object in self.pathways.index and not self.pathways.loc[r.object, "generic"]:
                p = self.pathways.loc[r.object]
                paths.append({"id": r.object, "name": p["name"], "gene": r.subject,
                              "source": "Gene Ontology" if r.object.startswith("GO:") else "Reactome",
                              "n_diseases": p.n_diseases, "n_genes": p.n_genes, "edge_ids": [r.edge_id]})
        paths.sort(key=lambda x: (x["n_diseases"], x["name"]))
        ph = e[e.predicate == "has_phenotype"]
        spread = ph[ph.evidence_type == "curated"].groupby("object").subject.nunique()
        symptoms = []
        for hp_id, grp in ph[ph.subject == d].groupby("object"):
            symptoms.append({"id": hp_id, "name": self.name(hp_id), "n_diseases": int(spread.get(hp_id, 1)),
                             "stated_in_a_paper": bool((grp.evidence_type == "text_mined").any()),
                             "in_database": bool((grp.evidence_type == "curated").any()),
                             "confidence": grp.confidence.max(), "edge_ids": grp.edge_id.tolist()})
        symptoms.sort(key=lambda x: (x["n_diseases"], -x["stated_in_a_paper"], x["name"]))
        return clean({"disease": {"id": d, "name": self.name(d)}, "genes": genes, "pathways": paths,
                      "symptoms": symptoms, "n_symptoms": len(symptoms), "n_diseases_in_atlas": len(self.G.diseases),
                      "ordering": "mechanisms and symptoms shared by the fewest diseases come first"})

    def ten_x(self, d: str = "MONDO:0009657") -> dict:
        """The 10x case for one disease: a natural history study from scratch versus reusing what relatives built.

        Every number is computed from registered ClinicalTrials.gov studies. No saving is claimed without a source."""
        self._need_disease(d)
        tl = pd.read_csv(GRAPH / "nhs_timelines.csv", dtype={"start": str, "completion": str})
        name = self.name(d)
        nb = self.G.neighbours_of(d)
        rel = list(nb[nb.score >= NEIGHBOUR_MIN].neighbour_id)
        own = tl[tl.disease_id == d]
        sister = tl[tl.disease_id.isin(rel)].drop_duplicates("nct")
        sister = sister[~sister.nct.isin(own.nct)]
        family = pd.concat([own, sister]).drop_duplicates("nct")
        scope, basis = family, f"{name} and its close relatives"
        if not len(family[(family.status == "COMPLETED") & family.months.notna()]):
            scope, basis = tl.drop_duplicates("nct"), "all diseases in the Atlas"     # nothing completed nearby: say so
        done = scope[(scope.status == "COMPLETED") & scope.months.notna()]
        row = lambda r: {"nct": r.nct, "disease": r.disease, "title": r.title, "status": r.status, "start": r.start,
                         "completion": r.completion, "months": r.months, "enrollment": r.enrollment,
                         "sponsor": r.sponsor, "source_url": r.source_url, "edge_ids": [r.edge_id]}
        sister_names = sorted({self.name(x) for x in sister.disease_id})
        if len(own):
            route = [f"{name} already has {len(own)} natural history stud{'y' if len(own) == 1 else 'ies'} registered. "
                     "Check these first: joining may beat starting a new one."]
        else:
            route = [f"No natural history study is registered for {name}. That is the gap to close."]
        if len(sister):
            route.append(f"{len(sister)} more exist for {', '.join(sister_names[:4])}"
                         f"{' and others' if len(sister_names) > 4 else ''}: protocols, outcome measures and teams to "
                         "learn from and ask to collaborate with.")
        elif not rel:
            route.append("No disease in the Atlas is similar enough to borrow from, so there is no supported shortcut yet.")
        else:
            route.append("Its close relatives have no registered natural history study either, so there is nothing "
                         "to reuse yet. A shared study across these diseases would be new ground.")
        return clean({
            "disease": {"id": d, "name": name},
            "milestone": f"Starting a natural history study for {name}",
            "why_it_matters": "A natural history study records how a disease progresses without treatment. "
                              "Regulators ask for it before trials.",
            "numbers": {"own": len(own), "relatives": len(sister), "completed": len(done), "basis": basis,
                        "median_months": done.months.median() if len(done) else None,
                        "min_months": done.months.min() if len(done) else None,
                        "max_months": done.months.max() if len(done) else None,
                        "median_enrollment": done.enrollment.median() if len(done) else None},
            "usual_route": ["FDA draft guidance says prospective natural history studies generally take more time than "
                            "reusing existing data, and longitudinal ones can be lengthy and costly.",
                            "No published figure was found for the time to set up such a study (protocol, ethics "
                            "approval, sites, funding), so none is stated."],
            "usual_route_source": {"label": "FDA, Rare Diseases: Natural History Studies for Drug Development (2019)",
                                   "url": "https://www.fda.gov/media/122425/download"},
            "atlas_route": route,
            "supported": bool(len(own) or len(sister)),
            "own_studies": [row(r) for r in own.itertuples()],
            "relative_studies": [row(r) for r in sister.sort_values("status").itertuples()],
            "assumptions": [f"A study for {name} could reuse outcome measures from its relatives. Not yet validated: "
                            "clinicians must confirm the diseases are close enough (shared mechanism, different genes).",
                            "Durations are those of the registered studies; a new study could be shorter or longer.",
                            "No time or cost saving is stated, because there is no cited figure for one."],
            "validate_next": [f"Whether each existing study is still enrolling and open to families with {name}.",
                              "Whether relatives' protocols and registries can be shared (ask the sponsors).",
                              "Expert review of how well outcome measures transfer between these diseases."],
            "retrieved": str(tl.retrieved.iloc[0])})

    # ------------------------------------------------------------------ landscape: how common, how far, how funded, where
    def _tables(self):
        if not hasattr(self, "_land"):
            read = lambda f: pd.read_parquet(GRAPH / f) if (GRAPH / f).exists() else pd.DataFrame()
            self._land = {k: read(f"{k}.parquet") for k in ("disease_facts", "trial_facts", "trial_sites", "outside_index")}
        return self._land

    def key_facts(self, d: str) -> dict:
        """Prevalence by place, age of onset and inheritance, as Orphadata records them (each with its reference)."""
        f = self._tables()["disease_facts"]
        f = f[f.disease_id == d] if len(f) else f
        prev = f[f.kind == "prevalence"] if len(f) else f
        rows = [{"where": r.where, "value": r.value, "per_100k": r.per_100k, "measure": r.measure,
                 "validated": r.validated, "pmid": r.reference, "source": r.source, "source_url": r.source_url}
                for r in prev.sort_values(["validated", "per_100k"], ascending=False).itertuples()]
        world = next((r for r in rows if r["where"] == "Worldwide"), None) or next((r for r in rows if r["where"] == "Europe"), None)
        return {"prevalence": rows, "headline_prevalence": world,
                "onset": sorted(set(f[f.kind == "onset"].value)) if len(f) else [],
                "inheritance": sorted(set(f[f.kind == "inheritance"].value)) if len(f) else [],
                "source": "Orphadata product 9", "source_url": prev.source_url.iloc[0] if len(prev) else
                (f.source_url.iloc[0] if len(f) else "")}

    def landscape(self, d: str) -> dict:
        """Beyond the brief: how common the disease is and where, how far its trials got, what stopped them,
        how much public funding is on record, where the work happens, and which milestones are still missing.

        Every number is a count of registry records. Nothing is estimated and no success probability is claimed."""
        self._need_disease(d)
        T, e, name = self._tables(), self.edges, self.name(d)
        mine = e[(e.subject == d) & (e.predicate == "studied_in_trial")]
        edge_of = dict(zip(mine.object, mine.edge_id))
        tf = T["trial_facts"]
        tf = tf[tf.nct.isin(edge_of)].copy() if len(tf) else tf
        title = lambda nct: self.name(nct)
        trial = lambda r: {"nct": r.nct, "title": title(r.nct), "status": r.status, "phases": r.phases.split("|") if r.phases else [],
                           "enrollment": r.enrollment, "start": r.start, "completion": r.completion,
                           "why_stopped": r.why_stopped, "has_results": r.has_results,
                           "interventions": r.interventions.split("|")[:3] if r.interventions else [],
                           "source_url": r.source_url, "edge_ids": [edge_of[r.nct]]}
        # ---- how far have treatment trials gone
        iv = tf[tf.study_type == "INTERVENTIONAL"] if len(tf) else tf
        order = [("EARLY_PHASE1", "Early phase 1"), ("PHASE1", "Phase 1"), ("PHASE2", "Phase 2"), ("PHASE3", "Phase 3"), ("PHASE4", "Phase 4")]
        phases = []
        for key, label in order:
            rows = iv[iv.phases.str.split("|").map(lambda ps: key in ps)] if len(iv) else iv
            phases.append({"phase": label, "n": len(rows), "completed": int((rows.status == "COMPLETED").sum()) if len(rows) else 0,
                           "active": int(rows.status.isin(ACTIVE).sum()) if len(rows) else 0,
                           "edge_ids": [edge_of[x] for x in rows.nct][:12] if len(rows) else []})
        ended = iv[iv.status.isin(["COMPLETED", "TERMINATED", "WITHDRAWN"])] if len(iv) else iv
        done = int((ended.status == "COMPLETED").sum()) if len(ended) else 0
        stopped = iv[(iv.why_stopped != "") & iv.status.isin(["TERMINATED", "WITHDRAWN", "SUSPENDED"])] if len(iv) else iv
        kinds = pd.Series([k for ks in iv.intervention_types for k in ks.split("|") if k]).value_counts().to_dict() if len(iv) else {}
        furthest = next((p["phase"] for p in reversed(phases) if p["n"]), None)
        # ---- funding on record
        gr = e[(e.subject == d) & (e.predicate == "funded_by")]
        grants = []
        for r in gr.itertuples():
            a = _attrs(self.nodes.loc[r.object, "attrs"])
            grants.append({"grant": r.object, "title": self.name(r.object), "amount": a.get("award_amount"),
                           "fiscal_year": a.get("fiscal_year"), "organization": a.get("organization", ""),
                           "source_url": f"https://reporter.nih.gov/project-details/{r.object}", "edge_ids": [r.edge_id]})
        total = sum(g["amount"] or 0 for g in grants)
        compare = []
        for x in [d] + [m for m, c in self.G.cluster_of.items() if c == self.G.cluster_of[d] and m != d]:
            gx = e[(e.subject == x) & (e.predicate == "funded_by")]
            amt = sum((_attrs(self.nodes.loc[o, "attrs"]).get("award_amount") or 0) for o in gx.object)
            compare.append({"id": x, "name": self.name(x), "amount": amt, "n_grants": len(gx), "is_this": x == d})
        # ---- where the work happens
        st = T["trial_sites"]
        st = st[st.nct.isin(edge_of)] if len(st) else st
        status_of = dict(zip(tf.nct, tf.status)) if len(tf) else {}
        cities = []
        if len(st):
            for (city, country), g in st[st.lat.notna()].groupby(["city", "country"]):
                ncts = sorted(set(g.nct))
                cities.append({"city": city, "country": country, "lat": g.lat.iloc[0], "lon": g.lon.iloc[0],
                               "n_studies": len(ncts), "recruiting": bool((g.site_status == "RECRUITING").any()),
                               "facilities": sorted(set(g.facility))[:3], "edge_ids": [edge_of[x] for x in ncts][:8]})
        cities.sort(key=lambda c: -c["n_studies"])
        countries = (st.groupby("country").nct.nunique().sort_values(ascending=False).to_dict() if len(st) else {})
        now = st[st.site_status == "RECRUITING"] if len(st) else st
        recruiting = [{"nct": n, "title": title(n), "places": sorted({f"{r.city}, {r.country}" for r in g.itertuples()})[:6],
                       "n_sites": len(g), "source_url": g.source_url.iloc[0], "edge_ids": [edge_of[n]]}
                      for n, g in now.groupby("nct") if status_of.get(n) == "RECRUITING"] if len(now) else []
        # ---- milestones on the way to a treatment, each one a fact in the graph or a registry record
        assets = self.G.assets[self.G.assets.disease_id == d]
        kind_ids = lambda k: assets[assets.kind == k].edge_id.tolist()
        recent = [g for g in grants if (g["fiscal_year"] or 0) >= 2024]
        late = [p for p in phases if p["phase"] in ("Phase 3", "Phase 4") and p["n"]]
        steps = [
            ("Causal gene known", [x for g in self.genes_of(d) for x in g["edge_ids"]], "Without a gene there is no mechanism to target."),
            ("Patient organisation exists", [x for o in self.orgs_of(d) for x in o["edge_ids"]][:4], "Someone to gather families, data and funding."),
            ("Patient registry", kind_ids("registry"), "A list of who has the disease and how to reach them."),
            ("Natural history study", kind_ids("natural history study"), "How the disease progresses untreated: what regulators ask for first."),
            ("Research funded recently", [x for g in recent for x in g["edge_ids"]][:6], "An NIH grant active in 2024 or later."),
            ("A treatment trial has started", [edge_of[x] for x in iv.nct][:8] if len(iv) else [], "Any interventional study registered."),
            ("A treatment trial is recruiting now", [edge_of[x] for x in iv[iv.status == "RECRUITING"].nct] if len(iv) else [], "Families can take part today."),
            ("A late-stage trial (phase 3) exists", [x for p in late for x in p["edge_ids"]][:8], "The last step before a treatment can be approved."),
        ]
        milestones = [{"step": s, "reached": bool(ids), "why_it_matters": why, "edge_ids": ids} for s, ids, why in steps]
        missing = [m["step"] for m in milestones if not m["reached"]]
        return clean({
            "disease": {"id": d, "name": name},
            "key_facts": self.key_facts(d),
            "milestones": {"steps": milestones, "reached": len(milestones) - len(missing), "of": len(milestones),
                           "next_missing": missing[0] if missing else None,
                           "note": "On record in the Atlas's sources. A missing step may exist outside them."},
            "trials": {"n_interventional": len(iv), "n_observational": len(tf) - len(iv), "phases": phases,
                       "furthest_phase": furthest,
                       "finished": {"completed": done, "ended": len(ended),
                                    "share_completed": round(done / len(ended), 2) if len(ended) else None,
                                    "note": "Share of ended treatment trials that ran to completion rather than being "
                                            "terminated or withdrawn. It says nothing about whether the treatment worked."},
                       "posted_results": int(iv.has_results.sum()) if len(iv) else 0,
                       "what_was_tested": kinds,
                       "why_stopped": [trial(r) for r in stopped.itertuples()],
                       "participants_enrolled": int(iv.enrollment.fillna(0).sum()) if len(iv) else 0},
            "funding": {"total_usd": total, "n_grants": len(grants), "source": "NIH RePORTER",
                        "note": "Sum of the most recent fiscal-year award of each NIH grant found. US public funding "
                                "only; it is not the cost of developing a treatment, for which no cited figure is used.",
                        "top": sorted([g for g in grants if g["amount"]], key=lambda g: -g["amount"])[:5],
                        "in_cluster": sorted(compare, key=lambda c: -c["amount"])},
            "where": {"n_sites": len(st), "n_countries": len(countries), "countries": countries, "cities": cities[:160],
                      "recruiting_now": recruiting},
        })

    def outside(self, q: str, limit: int = 3) -> list[dict]:
        """Rare diseases that match a search but are not loaded: what they are, and what adding them would take."""
        t = self._tables()["outside_index"]
        text = q.strip().lower()
        if not len(t) or len(text) < 3:
            return []
        if not hasattr(self, "_outside_names"):
            names = [(r.name.lower(), i) for i, r in enumerate(t.itertuples())]
            names += [(s.lower(), i) for i, r in enumerate(t.itertuples()) for s in r.synonyms.split("|") if s]
            self._outside_names = names
        found = process.extract(text, [n for n, _ in self._outside_names], scorer=fuzz.WRatio, limit=12, score_cutoff=86)
        seen, out = set(), []
        for _, score, k in found:
            i = self._outside_names[k][1]
            if i in seen:
                continue
            seen.add(i)
            r = t.iloc[i]
            out.append({"mondo_id": r.mondo_id, "name": r["name"], "genes": [g for g in r.genes.split("|") if g],
                        "orphanet_url": f"https://www.orpha.net/en/disease/detail/{r.orpha}",
                        "to_add": f"Add one row to data/manual/diseases.csv ({r.mondo_id}"
                                  + (f", gene {r.genes.split('|')[0]}" if r.genes else "") + ") and rebuild."})
        return out[:limit]

    # ------------------------------------------------------------------ numbers
    def stats(self) -> dict:
        e, n = self.edges, self.nodes
        tm = e[(e.evidence_type == "text_mined") & (e.source == "PubMed")]
        return clean({"nodes_by_type": n.node_type.value_counts().to_dict(),
                      "edges_by_evidence_type": e.evidence_type.value_counts().to_dict(),
                      "edges_by_predicate": e.predicate.value_counts().to_dict(),
                      "edges_by_source": e.source.value_counts().to_dict(),
                      "reviewer_verdicts": tm.reviewer_verdict.value_counts().to_dict(),
                      "connections": self.G.summary,
                      "confidence_rules": {"Orphadata causal gene": 0.95, "HPO annotation": "0.9 (0.7 if occasional)",
                                           "Reactome": 0.9, "trial match": "0.85 (0.5 if only the family is named)",
                                           "paper, stated": 0.7, "paper, suggested": 0.5,
                                           "paper, reviewer says supported": "+0.15, capped at 0.95",
                                           "similar_to": "the similarity score"}})
