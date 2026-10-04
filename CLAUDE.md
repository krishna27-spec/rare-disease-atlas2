# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Rare Disease Atlas: a hackathon project (Hack-Nation challenge 05, brief in `docs/challenge-brief.pdf`) that builds an evidence-tracked knowledge graph for 22 neurological lysosomal storage diseases and uses it to suggest cited next steps to a patient-group leader ("Maria", whose child has Sanfilippo / MPS IIIC). The disease list is hand-picked in `data/manual/diseases.csv`.

## Commands

Everything runs as a module from the repo root (paths like `data/graph` are relative to the cwd):

```bash
uv sync
uv run python -m src.graph.build              # rebuild the whole graph from data/raw + data/cache (no LLM calls), then check it
uv run python -m src.etl.biology              # or any single step; each module in build.STEPS has its own __main__
uv run python -m src.extract --limit 20 --spread   # LLM extraction over abstracts (rate-limited, resumable; Groq free tier is 200K tokens/day per model)
uv run python -m src.graph.review             # second-model verdicts on text-mined edges (LLM, cached per edge; --cache-only skips the graph write)
uv run python -m src.graph.check              # evidence-rule checks; the closest thing to a test suite
uv run uvicorn src.atlas.server:app --port 8000    # JSON API for the UI; docs at /docs
bash scripts/publish_pages.sh                 # export static API files, build the server-less site, push to gh-pages
uv run python -m src.hello_llm                # check that the LLM settings in .env work
```

There are no unit tests or linter config. After changing a graph step, re-run that step and the ones after it in `build.STEPS`, then `src.graph.check`.

Environment (`.env`, see `.env.example`): `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` (Groq serving `openai/gpt-oss-20b`), optional `LLM_MODEL_QUALITY` (default `openai/gpt-oss-120b`), `OPENROUTER_API_KEY` (second provider), `NCBI_API_KEY`, `NCBI_EMAIL`, optional `BRIGHTDATA_API_KEY` + `BRIGHTDATA_ZONE` (Web Unlocker for `org_scrape`; plain requests are used without them) and `BRIGHTDATA_SERP_ZONE` (web search that proposes organisations to add).

The UI is built separately by someone else. Backend work stops at `src/atlas/` (the contract is `docs/BACKEND_API.md`); `src/webapp/` holds helpers the query layer reuses, so keep their behaviour stable.

## Architecture

Three layers, each only reading the output of the one before:

1. **`src/etl/`** downloads and parses sources into the graph.
2. **`src/graph/`** defines the schema and computes derived tables.
3. **`src/atlas/`** is the query layer (`queries.py`, class `Atlas`) and its FastAPI wrapper (`server.py`). It reads `data/graph/` only, never raw data or caches, and builds on `Graph` in `src/webapp/data.py`.

### Build order (`src/graph/build.py` `STEPS`)

Order matters, because `biology` creates `nodes.parquet`/`edges.parquet` and later steps add to them:

`etl.download` → `etl.biology` (Disease/Gene/Phenotype/Pathway from MONDO, Orphadata, HPO, HGNC, Reactome, ClinVar) → `etl.research` (Trial/Grant/Investigator/Asset from ClinicalTrials.gov, NIH RePORTER, PubMed; also writes `data/cache/abstracts.jsonl`) → `etl.go` (Gene Ontology processes per gene, via QuickGO) → `etl.org_scrape` (reads patient organisations' own pages, cached) → `etl.orgs` (PatientOrg from the hand-checked `data/manual/patient_orgs.csv` plus `data/manual/org_scrape.jsonl`) → `etl.landscape` (prevalence/onset/inheritance from Orphadata product 9, trial outcomes and sites from ClinicalTrials.gov, and an index of rare diseases not loaded) → `etl.timelines` → `graph.similarity` (inferred `similar_to` edges, Louvain clusters) → `etl.filter_abstracts` → `extract --limit 0` → `graph.text_mined` (text-mined edges, Paper nodes, paper authors) → `graph.review --limit 0` → `graph.connections` (tables for the query layer, `contradicts` links) → `graph.stats` (`data/graph/STATS.md`) → `graph.check`.

`src.extract` and `src.graph.review` are called with `--limit 0`: no LLM calls, they only apply what is already cached in `data/cache/extractions.jsonl` and `reviews.jsonl`. Real extraction and review are separate manual runs. `review` must run after `text_mined` (which resets confidences and verdicts) and before `connections`.

### Re-runnable layers

Each step replaces only its own rows so it can be re-run alone: `research` and `orgs` use `schema.merge_layer(node_types, predicates)`, `similarity` drops old `similar_to` edges, `go` drops `GO:` nodes and its own source's edges, `text_mined` drops every edge whose `source` is `PubMed`, `Paper` nodes, `AUTHOR:` investigators and PubMed `investigator_of` edges. `research` owns the `Investigator` node type, so re-running it alone removes paper authors until `text_mined` runs again. A new step that writes to the graph must do the same or it will duplicate rows. `biology` rewrites both files from scratch, so re-running it alone wipes the later layers.

### Caching

- `data/raw/`: bulk files, downloaded once (`download_dates.json` records when). An edge's `retrieved` date for these comes from the file mtime.
- `data/cache/<source>/<sha1>.json`: every API response, via `research.cached()`. Re-runs make no network calls; delete a file to refetch.
- `data/cache/extractions.jsonl`: one line per abstract already read by the LLM. `src.extract` skips those PMIDs; failed abstracts are not written, so they retry next run.

### Edge schema and evidence rules (`src/graph/schema.py`)

Always build edges with `make_edge()`; it asserts the project's provenance rules:

- `evidence_type` is `curated`, `text_mined` or `inferred`; every edge needs `source`, `source_record`, `retrieved` and a 0–1 `confidence`.
- `inferred` edges must carry `method`; `text_mined` edges must carry `evidence_text`.
- `edge_id` is `"E"` + 12 hex chars of a SHA-1 over subject/predicate/object/source/record, so IDs are stable across rebuilds. The app and the LLM prompt cite these IDs (regex `E[0-9a-f]{12}`).

Node IDs are stable external identifiers: MONDO for diseases, HGNC symbol for genes, HP for phenotypes, `R-HSA-` for pathways, `PMID:` for papers, `ASSET:` for assets, `ORG:<host>` for patient organisations.

Edge direction: `Gene → gene_associated_with_disease → Disease` (curated and text-mined alike), `Disease → has_phenotype → Phenotype`, `Gene → participates_in_pathway → Pathway`, `PatientOrg → serves_disease → Disease`, `Investigator → investigator_of → Trial | Grant | Paper`. Similarity and the "what differs" tables use curated gene edges only, since a paper can be wrong.

### Text-mining pipeline: the LLM proposes, code verifies

- `src/llm.py`: one OpenAI-compatible client. `tier="bulk"` tries gpt-oss-20b then 120b, `tier="quality"` the reverse, on each configured provider in turn; a provider that returns 429 or an error is rested and the next is used. `last_model()` reports which model answered, and results record it.
- `src/extract.py`: the LLM returns `Fact`s (Pydantic) with certainty `stated`, `suggested` or `denied`; a fact is kept only if its `evidence_text` appears verbatim in the title+abstract (whitespace and case ignored).
- `src/graph/text_mined.py`: a fact becomes an edge only if the disease resolves to exactly one MONDO ID that is one of that paper's own diseases, the object resolves to a gene/phenotype already in the graph, and the quote itself names that object. `participates_in_pathway` facts are always dropped (pathway edges are gene→pathway, not disease→pathway). Denied facts become edges with a `not_` predicate prefix so nothing that counts genes or phenotypes picks them up; `connections.contradictions()` pairs them with the edges they deny. Drop counts go to `text_mined_drops.json` and `STATS.md`.
- `src/graph/review.py`: gpt-oss-120b sees only the claim and the quote and returns `supported | partial | unsupported`; supported edges get +0.15 confidence (cap 0.95).
- `src/webapp/explain.py` is the only LLM call in the app: it rewrites code-built candidate actions (`Graph.candidates()` in `webapp/data.py`) into plain-language steps, and `validate_steps()` discards any line that cites no edge ID or an edge ID that was not in the input. If the LLM fails, the caller shows the raw candidates.

Keep this shape when changing things: no unverified LLM output reaches the graph or the UI, and nothing is shown without edge IDs behind it. The same goes for numbers: `ten_x.py` and `connections.contradictions()` state "not found" or write an empty table instead of inventing a figure.

### Two kinds of `text_mined` edge

`evidence_type == "text_mined"` covers paper facts (`source == "PubMed"`, extracted by gpt-oss, reviewed) and patient-organisation links (`source == "Patient organisation website"`, a disease-name match by code on the organisation's own pages, no LLM, no reviewer). Code that means "paper facts" must also filter on `source == "PubMed"`. `org_scrape` only turns a mention into `serves_disease` when the disease is in the organisation's name or home page title, or is named at least `MIN_SENTENCES` times on `MIN_PAGES` pages; anything less is a passing mention and is left out. Candidate organisations live in `data/manual/org_sources.csv`; a candidate proves nothing until its own page supplies the quote.

### Mechanism sources

`participates_in_pathway` edges come from Reactome (`R-HSA-` IDs) and Gene Ontology biological processes (`GO:` IDs, curated annotations only, IEA excluded). Both are `Pathway` nodes. The similarity score uses Reactome only: with GO included the NCL cluster fell apart, because GO terms are assigned gene by gene at uneven granularity. GO edges serve the pathway navigator, shared-pathway lists and search.

### Name matching

- `src/etl/terms.py`: per-disease `SPECIFIC` terms (one disease) and broad family terms, matched on whole words after `normalise()`. Broad terms count only when no specific disease is named. This decides which disease a trial, grant or abstract belongs to.
- `src/etl/genes.py`: HGNC aliases → symbol, limited to genes in the graph; ambiguous names are dropped.
- `CLN1`–`CLN8` are also yeast cyclin genes, so `filter_abstracts.py` accepts a bare `CLNn` only with lysosomal/Batten context.
- `src/graph/reactome.py`: Reactome roots and their direct children are "generic" and excluded from similarity, shared-pathway lists and the graph view (the edges stay in `edges.parquet`).

### Similarity (`src/graph/similarity.py`)

IC-weighted Jaccard over HPO terms propagated up the ontology (weight 0.6) and non-generic Reactome pathways of the disease's genes (0.4); phenotype alone if either disease has no pathways. Pairs scoring ≥ 0.15 get a `similar_to` edge; the webapp uses the same threshold (`NEIGHBOUR_MIN` in `webapp/data.py`), so change both together. Louvain uses a fixed seed for reproducible clusters.

### Shared constants

Evidence-type colours (`COLOURS` in `webapp/data.py`: blue curated, orange text-mined, grey inferred) are reused by every view. `ten_x.py` hardcodes MPS IIIC (`MONDO:0009657`) as the demo disease.

### Attribute tables (not edges)

`etl.landscape` writes `disease_facts`, `trial_facts`, `trial_sites` and `outside_index` parquet files. They describe diseases and trials rather than relate two nodes, so rows carry `source` / `source_url` instead of edge IDs. `Atlas.landscape()` joins them back to the graph through each trial's `studied_in_trial` edge, which is what its `edge_ids` point at. Keep every figure there a count of registry records: no estimated costs or success probabilities.

### Query layer (`src/atlas/queries.py`)

`Atlas` exposes the brief's four capabilities as methods returning JSON-ready dicts: `search` (search engine), `clusters` / `cluster` / `neighbours` / `clusters_for_mechanism` (clustering), `pathway_paths` (pathway navigator), `connectors` (connector), plus `disease`, `assets`, `next_steps`, `edge`, `subgraph`, `contradictions`, `stats`. Every returned item carries `edge_ids`; `graph.check` asserts they all exist. When nothing is supported the result carries `no_match` / `no_route` / `no_connector` with what was searched. Pass results through `clean()` so numpy values and NaN are JSON-safe. New precomputed inputs belong in `connections.py` (as `pathways.parquet` and `connectors.parquet` are), because the deployed query layer has no `data/raw`.

### Two ways the site is served

`npm run build` makes `web/dist`, which FastAPI serves and which calls the live API. `npm run build:pages` makes `web/dist-pages` for GitHub Pages: `src/atlas/export_static.py` writes every API answer to `web/static-api/`, and `web/src/api.js` (when `__STATIC__` is set) maps each API path to one of those files and runs search and the mechanism lookup in the browser. A new endpoint therefore needs three things: the query method, the route in `server.py`, and a line in `export_static.py` plus its path mapping in `api.js`. IDs lose their colon in file names (`MONDO_0009657`).
