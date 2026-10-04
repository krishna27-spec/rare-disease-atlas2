"""Milestone 3: build the biology layer (diseases, genes, phenotypes, pathways) as curated edges.

Run:  uv run python -m src.etl.biology
Reads data/raw/ (run src.etl.download first), writes data/graph/nodes.parquet and edges.parquet.
"""
import datetime
import re
from pathlib import Path

import networkx as nx
import obonet
import pandas as pd
from lxml import etree

from src.etl.download import RAW, SOURCES, download_all
from src.graph.schema import EDGE_SCHEMA, NODE_SCHEMA, make_edge, write_table

# Orphadata association types we keep: the gene's germline mutation causes the disease.
CAUSAL_PREFIX = "Disease-causing germline mutation"
# HPO frequency terms that mean "only some patients have it" -> lower confidence
RARE_FREQ_TERMS = {"HP:0040283", "HP:0040284"}  # occasional, very rare
EXCLUDED_TERM = "HP:0040285"
# MONDO files CLN10 (gene CTSD, a different disease) under CLN1; keep it out of CLN1's family.
EXCLUDE_SUBTREES = {"MONDO:0009744": ["MONDO:0012414"]}
INDIRECT_CONFIDENCE = 0.85  # gene link found only through the disease's parent in Orphadata


def retrieved(filename: str) -> str:
    """Date the file was downloaded (from the file's own timestamp)."""
    return datetime.date.fromtimestamp((RAW / filename).stat().st_mtime).isoformat()


def hpo_confidence(freq: str) -> float | None:
    """0.9 normally, 0.7 for occasional/rare findings, None if the finding is 'excluded'."""
    if freq == EXCLUDED_TERM:
        return None
    if freq in RARE_FREQ_TERMS:
        return 0.7
    m = re.fullmatch(r"(\d+)/(\d+)", freq)
    if m and int(m.group(2)) and int(m.group(1)) / int(m.group(2)) < 0.3:
        return 0.7
    m = re.fullmatch(r"([\d.]+)%", freq)
    if m and float(m.group(1)) < 30:
        return 0.7
    return 0.9


def main() -> None:
    download_all()  # no-op for files already cached
    diseases = pd.read_csv("data/manual/diseases.csv")

    # ---- MONDO: names, synonyms, and OMIM/Orphanet IDs (including those of subtypes) ----
    print("Reading MONDO ...")
    mondo = obonet.read_obo(RAW / "mondo.obo")
    nodes, edges = [], []
    omim_orpha: dict[str, set[str]] = {}   # our MONDO id -> {"OMIM:..", "ORPHA:.."}
    for _, d in diseases.iterrows():
        mid = d["mondo_id"]
        family = {mid} | nx.ancestors(mondo, mid)   # the disease plus all its subtypes
        for bad in EXCLUDE_SUBTREES.get(mid, []):
            family -= {bad} | nx.ancestors(mondo, bad)
        ids = set()
        for f in family:
            for x in mondo.nodes[f].get("xref", []):
                if x.startswith("OMIM:"):
                    ids.add(x)
                elif x.startswith("Orphanet:"):
                    ids.add("ORPHA:" + x.split(":")[1])
        omim_orpha[mid] = ids
        m = mondo.nodes[mid]
        syns = sorted({s for line in m.get("synonym", []) for s in re.findall(r'^"(.+?)"', line)})
        own_xrefs = sorted(x for x in m.get("xref", []) if x.startswith(("OMIM:", "Orphanet:")))
        nodes.append({"node_id": mid, "node_type": "Disease", "name": d["name"],
                      "synonyms": [m["name"]] + syns, "xrefs": own_xrefs, "group": d["group"]})
    orpha_to_disease: dict[str, list[str]] = {}
    for mid, ids in omim_orpha.items():
        for i in ids:
            orpha_to_disease.setdefault(i, []).append(mid)
    # Diseases with no Orphanet ID of their own (e.g. NPC1/NPC2): use the parent's Orphanet ID,
    # but only for genes we named in diseases.csv.
    parent_orpha: dict[str, list[str]] = {}   # ORPHA id -> diseases that inherit it
    for mid, ids in omim_orpha.items():
        if not any(i.startswith("ORPHA:") for i in ids):
            for parent in mondo.successors(mid):
                if parent not in mondo.nodes:
                    continue
                for rel in {parent} | nx.ancestors(mondo, parent):   # parent + its subtypes
                    for x in mondo.nodes[rel].get("xref", []):
                        if x.startswith("Orphanet:"):
                            parent_orpha.setdefault("ORPHA:" + x.split(":")[1], []).append(mid)

    # ---- HGNC: official gene symbols, HGNC IDs, Entrez IDs ----
    hgnc = pd.read_csv(RAW / "hgnc_complete_set.txt", sep="\t", dtype=str,
                       usecols=["hgnc_id", "symbol", "name", "entrez_id"]).set_index("symbol")

    # ---- Orphadata: disease -> gene (curated) ----
    print("Reading Orphadata ...")
    ret = retrieved("en_product6.xml")
    gene_symbols: set[str] = set()
    found: dict[str, set[str]] = {m: set() for m in diseases["mondo_id"]}
    for disorder in etree.parse(RAW / "en_product6.xml").iterfind(".//Disorder"):
        code = "ORPHA:" + disorder.findtext("OrphaCode")
        direct = [(m, False) for m in orpha_to_disease.get(code, [])]
        inherited = [(m, True) for m in parent_orpha.get(code, [])]
        for mid, indirect in direct + inherited:
            ours = set(diseases.loc[diseases["mondo_id"] == mid, "genes"].iloc[0].split(";"))
            for a in disorder.iterfind(".//DisorderGeneAssociation"):
                kind = a.findtext("DisorderGeneAssociationType/Name") or ""
                sym = a.findtext("Gene/Symbol")
                if not kind.startswith(CAUSAL_PREFIX) or sym is None:
                    continue
                if sym in found[mid] or (indirect and sym not in ours):
                    continue
                found[mid].add(sym)
                gene_symbols.add(sym)
                note = f"{code}|{sym}|{kind}" + ("|via parent disease" if indirect else "")
                edges.append(make_edge(
                    sym, "gene_associated_with_disease", mid, "curated",
                    INDIRECT_CONFIDENCE if indirect else 0.95,
                    "Orphadata product 6", note, SOURCES["en_product6.xml"], ret))
    # Check the genes we typed into diseases.csv against what Orphadata says
    print("\nGene check (diseases.csv vs Orphadata):")
    for _, d in diseases.iterrows():
        ours, theirs = set(d["genes"].split(";")), found[d["mondo_id"]]
        flag = "ok" if ours <= theirs else "MISSING in Orphadata: " + ",".join(sorted(ours - theirs))
        extra = theirs - ours
        print(f"  {d['name']:<32} {flag}" + (f"   (Orphadata also lists: {','.join(sorted(extra))})" if extra else ""))

    # ---- Gene nodes (+ ClinVar counts) ----
    clin = pd.read_csv(RAW / "gene_specific_summary.txt", sep="\t", skiprows=1, dtype=str)
    clin.columns = [c.lstrip("#") for c in clin.columns]
    clin = clin.set_index("Symbol")
    clin_ret = retrieved("gene_specific_summary.txt")
    entrez_to_gene: dict[str, str] = {}
    for sym in sorted(gene_symbols):
        h = hgnc.loc[sym] if sym in hgnc.index else None
        if h is None:
            print(f"  warning: {sym} is not an approved HGNC symbol")
        n_path = None
        if sym in clin.index:
            v = clin.loc[sym, "Alleles_reported_Pathogenic_Likely_pathogenic"]
            n_path = int(v) if str(v).isdigit() else 0
        nodes.append({"node_id": sym, "node_type": "Gene", "name": h["name"] if h is not None else sym,
                      "hgnc_id": h["hgnc_id"] if h is not None else None,
                      "entrez_id": h["entrez_id"] if h is not None else None,
                      "clinvar_pathogenic_alleles": n_path})
        if h is not None and isinstance(h["entrez_id"], str):
            entrez_to_gene[h["entrez_id"]] = sym

    # ---- HPO: disease -> phenotype (curated) ----
    print("\nReading HPO annotations ...")
    hpo_ret = retrieved("phenotype.hpoa")
    hp = obonet.read_obo(RAW / "hp.obo")
    best: dict[tuple[str, str], tuple[float, str]] = {}   # (disease, hp) -> (confidence, row key)
    hpoa = pd.read_csv(RAW / "phenotype.hpoa", sep="\t", comment="#", dtype=str, keep_default_na=False)
    hpoa = hpoa[(hpoa["aspect"] == "P") & (hpoa["qualifier"] != "NOT")]
    for row in hpoa[hpoa["database_id"].isin(orpha_to_disease)].itertuples():
        conf = hpo_confidence(row.frequency)
        if conf is None or row.hpo_id not in hp.nodes:
            continue
        for mid in orpha_to_disease[row.database_id]:
            key = (mid, row.hpo_id)
            if key not in best or conf > best[key][0]:
                best[key] = (conf, f"{row.database_id}|{row.hpo_id}|freq={row.frequency or 'n/a'}")
    hp_used = set()
    for (mid, hp_id), (conf, record) in sorted(best.items()):
        hp_used.add(hp_id)
        edges.append(make_edge(mid, "has_phenotype", hp_id, "curated", conf, "HPO annotations",
                               record, SOURCES["phenotype.hpoa"], hpo_ret))
    for hp_id in sorted(hp_used):
        nodes.append({"node_id": hp_id, "node_type": "Phenotype", "name": hp.nodes[hp_id]["name"]})

    # ---- Reactome: gene -> pathway (curated) ----
    print("Reading Reactome ...")
    re_ret = retrieved("NCBI2Reactome_All_Levels.txt")
    names = pd.read_csv(RAW / "ReactomePathways.txt", sep="\t", header=None, dtype=str,
                        names=["pid", "name", "species"]).set_index("pid")["name"]
    react = pd.read_csv(RAW / "NCBI2Reactome_All_Levels.txt", sep="\t", header=None, dtype=str,
                        names=["entrez", "pid", "url", "name", "evidence", "species"])
    react = react[(react["species"] == "Homo sapiens") & react["entrez"].isin(entrez_to_gene)]
    for row in react.drop_duplicates(["entrez", "pid"]).itertuples():
        gene = entrez_to_gene[row.entrez]
        edges.append(make_edge(gene, "participates_in_pathway", row.pid, "curated", 0.9, "Reactome",
                               f"NCBI2Reactome_All_Levels|{row.entrez}|{row.pid}",
                               SOURCES["NCBI2Reactome_All_Levels.txt"], re_ret))
    for pid in sorted(react["pid"].unique()):
        nodes.append({"node_id": pid, "node_type": "Pathway", "name": names.get(pid, pid)})

    # ---- Write ----
    ndf = write_table(nodes, NODE_SCHEMA, "nodes")
    edf = write_table(edges, EDGE_SCHEMA, "edges")
    print(f"\nWrote data/graph/nodes.parquet ({len(ndf)} nodes) and edges.parquet ({len(edf)} edges)")
    print("\nNodes by type:\n" + ndf["node_type"].value_counts().to_string())
    print("\nEdges by type:\n" + edf["predicate"].value_counts().to_string())
    print_summary(ndf, edf, diseases)


def print_summary(ndf: pd.DataFrame, edf: pd.DataFrame, diseases: pd.DataFrame) -> None:
    print("\nPer disease:")
    print(f"  {'Disease':<32}{'genes':>6}{'phenotypes':>12}{'pathways':>10}{'ClinVar P/LP alleles':>22}")
    genes = ndf[ndf["node_type"] == "Gene"].set_index("node_id")["clinvar_pathogenic_alleles"]
    for _, d in diseases.iterrows():
        mid = d["mondo_id"]
        g = edf[(edf["object"] == mid) & (edf["predicate"] == "gene_associated_with_disease")]["subject"]
        ph = (edf[(edf["subject"] == mid) & (edf["predicate"] == "has_phenotype")]).shape[0]
        pw = edf[(edf["subject"].isin(g)) & (edf["predicate"] == "participates_in_pathway")]["object"].nunique()
        cv = ",".join(f"{x}:{int(genes[x]) if pd.notna(genes.get(x)) else 'n/a'}" for x in g)
        print(f"  {d['name']:<32}{len(g):>6}{ph:>12}{pw:>10}   {cv}")


if __name__ == "__main__":
    main()
