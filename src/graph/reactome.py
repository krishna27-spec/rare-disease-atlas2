"""Which Reactome pathways are too generic to be informative?

A pathway is generic if it is a root of the Reactome tree ("Metabolism", "Disease", "Immune System",
"Signal Transduction", ...) or a direct child of a root ("Innate Immune System", "Metabolism of lipids",
"Diseases of metabolism", ...). They fit almost every disease, so they are left out of the similarity score,
the shared-pathway lists and the graph view. The edges themselves stay in edges.parquet (they are true).
Change MAX_GENERIC_DEPTH to loosen or tighten the rule."""
import pandas as pd

from src.etl.download import RAW

MAX_GENERIC_DEPTH = 1   # 0 = roots only, 1 = roots and their direct children


def generic_pathways() -> set[str]:
    rel = pd.read_csv(RAW / "ReactomePathwaysRelation.txt", sep="\t", header=None, names=["parent", "child"], dtype=str)
    rel = rel[rel.parent.str.startswith("R-HSA-") & rel.child.str.startswith("R-HSA-")]
    roots = set(rel.parent) - set(rel.child)
    level, generic = roots, set(roots)
    for _ in range(MAX_GENERIC_DEPTH):
        level = set(rel[rel.parent.isin(level)].child)
        generic |= level
    return generic
