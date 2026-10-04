"""HTTP wrapper around src/atlas/queries.py, so a UI in any language can use the Atlas.

Run:  uv run uvicorn src.atlas.server:app --port 8000        (interactive docs at http://localhost:8000/docs)
If web/dist exists (cd web && npm run build) the website is served at / by the same process.
Every endpoint is a GET that returns JSON. Disease IDs are MONDO IDs, e.g. /disease/MONDO:0009657 (MPS IIIC).
The graph is loaded once at start-up; restart the server after a rebuild.
"""
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.atlas.queries import Atlas

app = FastAPI(title="Rare Disease Atlas API",
              description="Evidence-backed knowledge graph for rare diseases. Every item carries `edge_ids`; "
                          "GET /edge/{id} returns the source, date, confidence and quote behind it. "
                          "Research exploration tool, not medical advice.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])


@lru_cache(maxsize=1)
def atlas() -> Atlas:
    return Atlas()


def call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e).strip("'\""))


# ---- search engine
@app.get("/search", tags=["1. Search"])
def search(q: str, limit: int = 8):
    """Disease, synonym, gene, symptom, pathway or patient group. Typos tolerated. Empty `hits` comes with `no_match`."""
    return atlas().search(q, limit)


@app.get("/diseases", tags=["1. Search"])
def diseases():
    return atlas().diseases()


@app.get("/disease/{disease_id}", tags=["1. Search"])
def disease(disease_id: str):
    """Summary card: genes, cluster, patient groups, counts, facts read from papers."""
    return call(atlas().disease, disease_id)


# ---- clustering
@app.get("/clusters", tags=["2. Clustering"])
def clusters():
    return atlas().clusters()


@app.get("/cluster/{cluster_id}", tags=["2. Clustering"])
def cluster(cluster_id: int):
    """Members, why they belong together (shared pathways and symptoms), reusable assets, groups, connectors."""
    return call(atlas().cluster, cluster_id)


@app.get("/disease/{disease_id}/neighbours", tags=["2. Clustering"])
def neighbours(disease_id: str):
    """Who is like us: most similar diseases, what is shared, what differs."""
    return call(atlas().neighbours, disease_id)


@app.get("/mechanism", tags=["2. Clustering"])
def mechanism(q: str):
    """Rank clusters for a mechanism: `q` is a pathway name, a Reactome ID (R-HSA-...) or a gene symbol."""
    return atlas().clusters_for_mechanism(q)


# ---- pathway navigator
@app.get("/disease/{disease_id}/pathways", tags=["3. Pathway navigator"])
def pathway_paths(disease_id: str, max_paths: int = 12):
    """Cited paths: disease -> gene -> pathway -> gene -> other disease -> its groups and reusable assets."""
    return call(atlas().pathway_paths, disease_id, max_paths)


# ---- connector
@app.get("/connectors", tags=["4. Connector"])
def connectors(disease: str | None = None, pathway: str | None = None, cluster: int | None = None,
               cross_cluster_only: bool = False, limit: int = 50):
    """People and organisations linking 2+ diseases, scoped to a disease, a pathway, a cluster, or everything."""
    return call(atlas().connectors, disease=disease, pathway=pathway, cluster=cluster,
                cross_cluster_only=cross_cluster_only, limit=limit)


# ---- what exists, what next
@app.get("/disease/{disease_id}/assets", tags=["Action"])
def assets(disease_id: str, include_cluster: bool = True):
    """Registries, natural history studies and trials for the disease and reusable ones in its cluster."""
    return call(atlas().assets, disease_id, include_cluster)


@app.get("/disease/{disease_id}/next-steps", tags=["Action"])
def next_steps(disease_id: str, explain: bool = True):
    """Cited candidate actions; with explain=true also 1-3 plain-language steps from gpt-oss (falls back safely)."""
    return call(atlas().next_steps, disease_id, explain)


@app.get("/disease/{disease_id}/biology", tags=["Action"])
def biology(disease_id: str):
    """Gene (and how it is affected), mechanisms and symptoms, the most informative first."""
    return call(atlas().biology, disease_id)


@app.get("/disease/{disease_id}/ten-x", tags=["Action"])
def ten_x(disease_id: str):
    """The 10x case: a natural history study for this disease, from scratch versus reusing what relatives built."""
    return call(atlas().ten_x, disease_id)


# ---- evidence
@app.get("/edge/{edge_id}", tags=["Evidence"])
def edge(edge_id: str):
    return call(atlas().edge, edge_id)


@app.get("/disease/{disease_id}/graph", tags=["Evidence"])
def subgraph(disease_id: str):
    """Nodes and edges to draw around a disease."""
    return call(atlas().subgraph, disease_id)


@app.get("/contradictions", tags=["Evidence"])
def contradictions():
    return atlas().contradictions()


@app.get("/stats", tags=["Evidence"])
def stats():
    return atlas().stats()


# ---- the website: served from the same process when it has been built (cd web && npm run build)
SITE = Path(__file__).resolve().parents[2] / "web" / "dist"
if SITE.exists():
    app.mount("/", StaticFiles(directory=SITE, html=True), name="site")
