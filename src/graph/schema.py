"""The edge and node tables every milestone writes to (see CLAUDE.md, "Edge schema")."""
import hashlib
from pathlib import Path

import pandas as pd
import pyarrow as pa

GRAPH_DIR = Path("data/graph")

EDGE_SCHEMA = pa.schema([
    ("edge_id", pa.string()),
    ("subject", pa.string()),
    ("predicate", pa.string()),
    ("object", pa.string()),
    ("evidence_type", pa.string()),      # curated | text_mined | inferred
    ("confidence", pa.float64()),        # 0-1
    ("source", pa.string()),
    ("source_record", pa.string()),
    ("source_url", pa.string()),
    ("retrieved", pa.string()),          # ISO date
    ("evidence_text", pa.string()),      # exact quote for text_mined, else ""
    ("method", pa.string()),             # for inferred edges
    ("contradicts", pa.list_(pa.string())),
    ("reviewer_verdict", pa.string()),   # supported | unsupported | partial | not_reviewed
])

NODE_SCHEMA = pa.schema([
    ("node_id", pa.string()),
    ("node_type", pa.string()),          # Disease | Gene | Phenotype | Pathway | ...
    ("name", pa.string()),
    ("synonyms", pa.list_(pa.string())),
    ("xrefs", pa.list_(pa.string())),
    ("group", pa.string()),              # diseases only
    ("hgnc_id", pa.string()),            # genes only
    ("entrez_id", pa.string()),          # genes only
    ("clinvar_pathogenic_alleles", pa.int64()),  # genes only (variant counts, not variants)
    ("attrs", pa.string()),              # JSON text with extra facts (trial status, grant amount, ...)
])


def make_edge(subject, predicate, obj, evidence_type, confidence, source,
              source_record, source_url, retrieved, evidence_text="", method=""):
    """Build one edge. Refuses to build one without its source, date, confidence or type."""
    assert evidence_type in ("curated", "text_mined", "inferred"), evidence_type
    assert 0 <= confidence <= 1, confidence
    assert source and source_record and retrieved, "every edge needs source, record and date"
    if evidence_type == "inferred":
        assert method, "inferred edges must say how they were computed"
    if evidence_type == "text_mined":
        assert evidence_text, "text_mined edges must store the exact sentence"
    key = "|".join([subject, predicate, obj, source, source_record])
    return {
        "edge_id": "E" + hashlib.sha1(key.encode()).hexdigest()[:12],
        "subject": subject, "predicate": predicate, "object": obj,
        "evidence_type": evidence_type, "confidence": float(confidence),
        "source": source, "source_record": source_record, "source_url": source_url,
        "retrieved": retrieved, "evidence_text": evidence_text, "method": method,
        "contradicts": [], "reviewer_verdict": "not_reviewed",
    }


def write_table(rows: list[dict], schema: pa.Schema, name: str) -> pd.DataFrame:
    GRAPH_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows, columns=schema.names)
    import pyarrow.parquet as pq
    pq.write_table(pa.Table.from_pandas(df, schema=schema, preserve_index=False),
                   GRAPH_DIR / f"{name}.parquet")
    return df


def merge_layer(nodes: list[dict], edges: list[dict], node_types: set[str], predicates: set[str]) -> None:
    """Replace one layer inside the saved graph: drop the old nodes/edges of this layer, add the new.

    Lets a milestone be re-run without duplicating its rows or touching other layers."""
    import pyarrow.parquet as pq
    old_nodes = pq.read_table(GRAPH_DIR / "nodes.parquet").to_pylist()
    old_edges = pq.read_table(GRAPH_DIR / "edges.parquet").to_pylist()
    keep_nodes = [n for n in old_nodes if n["node_type"] not in node_types]
    keep_edges = [e for e in old_edges if e["predicate"] not in predicates]
    write_table(keep_nodes + nodes, NODE_SCHEMA, "nodes")
    write_table(keep_edges + edges, EDGE_SCHEMA, "edges")
