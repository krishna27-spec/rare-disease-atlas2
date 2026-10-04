# Rare Disease Atlas

An evidence-backed knowledge graph for 22 neuronopathic lysosomal storage diseases (Sanfilippo/MPS III, the NCLs, Niemann-Pick C, GM1/GM2, MLD, Krabbe, alpha-mannosidosis, mucolipidosis IV, plus MPS I/II for contrast), with a JSON API that a UI builds on. Built for the Hack-Nation "AI Atlas for the World's Rare Diseases" challenge.

> **Research exploration tool. Not medical advice.** Always confirm with clinicians and researchers.

## What it answers: the "Maria" journey

Maria leads a patient group for **MPS IIIC (gene HGSNAT)**.

1. **Who shares our disease characteristics?** Search "Sanfilippo C"; the Atlas ranks the most similar diseases with *why* (shared heparan sulfate pathway, shared informative symptoms) and *what differs*.
2. **What useful work already exists?** Natural history studies, registries and trials, patient organisations, and the people who work across several of these diseases.
3. **What should we do together next?** 1 to 3 plain-language steps. Code finds candidate actions in the graph; gpt-oss may only reword them and must cite edge IDs, and code discards any sentence that cites nothing real.

When nothing is supported, the answer says so, lists what was searched and what evidence would change it.

## Architecture

```
sources   MONDO, HPO, Orphadata, HGNC, Reactome, Gene Ontology, ClinVar, PubMed, ClinicalTrials.gov,
          NIH RePORTER, patient organisations' own websites
   -> src/etl/      download once into data/raw, cache every API answer in data/cache
   -> src/graph/    nodes + edges, similarity + Louvain clusters, connection tables, review, checks
   -> data/graph/   nodes.parquet, edges.parquet, derived tables, STATS.md
   -> src/atlas/    query layer (queries.py) and JSON API (server.py); reads data/graph only
   -> web/          the website (React), served by the same process once built
                    (docs/BACKEND_GUIDE.md explains the API; docs/BACKEND_API.md lists the endpoints)
```

The four capabilities of the brief map to the API: **search engine** (`/search`), **clustering** (`/clusters`, `/disease/{id}/neighbours`, `/mechanism`), **pathway navigator** (`/disease/{id}/pathways`), **connector** (`/connectors`).

**Where OpenAI models are used** (open-weight gpt-oss through an OpenAI-compatible API; `src/llm.py` falls over between models and providers when one is rate-limited):

| Step | Model | What code checks afterwards |
|---|---|---|
| Extract facts from abstracts (`src/extract.py`) | gpt-oss-20b, gpt-oss-120b | The quoted sentence must be in the abstract word for word; names must resolve to IDs already in the graph |
| Review each text-mined edge (`src/graph/review.py`) | gpt-oss-120b | Verdict stored on the edge; only "supported" raises confidence |
| Plain-language next steps (`src/webapp/explain.py`) | gpt-oss-120b | Every line must cite edge IDs that were in its input |

The graph is built offline. The API never calls an LLM to build it, and the next-steps endpoint falls back to the cited candidate list if the LLM is unavailable.

## The website

`web/` is a React site (Vite, Framer Motion, a custom canvas graph) on top of the API. Build it once and the API process serves it:

```bash
cd web && npm install && npm run build && cd ..
uv run uvicorn src.atlas.server:app --port 8000     # site at http://localhost:8000, API docs at /docs
```

For front-end work, run the API as above and `npm run dev` in `web/` (requests are proxied to port 8000).

The site starts minimal and grows as the visitor asks for more:

- **Intro:** a DNA helix, one highlighted variant, and its signal growing into a network. It waits for the visitor to enter. (Animation from the Streamlit redesign of the original app, ported here.)
- **Home:** one search box and four doors, one for each person in the brief.
- **Disease page:** a header and seven tabs, one view at a time: **Overview** (one paragraph, five numbers, and a tile per tab with a one-line summary), **Biology**, **Connections** (the map), **Research** (reusable studies, cited next steps, researchers), **Communities**, **10× route** (computed for every disease from its own and its relatives' registered natural history studies) and **Evidence**.
- **The map:** a constellation drawn on canvas with the disease in the centre. It reveals itself in stages (mechanisms, then relatives) and adds patient groups and symptoms on "Expand connections". Line style shows the kind of evidence: verified source, research literature, Atlas-derived.
- **Mechanisms**, **Connectors** and **Evidence** pages for the therapy scout, the researcher, and anyone who wants to see how facts are checked.
- Any "Why?" chip, card or map line opens one evidence drawer: plain label and strength first, the technical record behind "Evidence details".

## Evidence model



Every edge carries `source`, `source_record`, `source_url`, `retrieved` date, `confidence` and one of three evidence types:

| type | meaning |
|---|---|
| `curated` | taken from a database file or API |
| `text_mined` | read from text, with the exact sentence stored: gpt-oss reading a PubMed abstract (plus a second model's verdict), or code matching disease names on a patient organisation's own web pages |
| `inferred` | computed by the Atlas (similarity); `method` says how |

**Confidence rules:** Orphadata "disease-causing germline mutation" 0.95 (0.85 via a parent disease); HPO annotation 0.9 (0.7 if occasional); Reactome 0.9; Gene Ontology 0.9 experimental, 0.8 curator-reviewed, 0.7 author statement (electronic annotations excluded); trials 0.85 (0.5 if only the disease family is named); patient organisation 0.9 hand-checked (0.5 if scope not verified), 0.85 when the disease is in its name, 0.7 when its site names the disease repeatedly; text-mined 0.7 "stated", 0.5 "suggested", +0.15 if the reviewer says supported (cap 0.95); inferred = the similarity score.

**Denials and contradictions:** a fact a paper denies becomes an edge with a `not_` predicate and is paired with any edge that asserts the same thing. None of the denials found so far resolved to one of our diseases, so the Atlas reports 0 contradictions and says why.

**Stable IDs:** MONDO, HGNC symbol, HP, Reactome, `PMID:`, `NCT`, NIH project numbers.

`uv run python -m src.graph.check` enforces these rules and fails the build if one is broken.

## Numbers

See [`data/graph/STATS.md`](data/graph/STATS.md), regenerated by the build: node and edge counts, the text-mining funnel (abstracts read, facts kept, facts dropped and why), reviewer verdicts, connectors.

## Rebuild the dataset

```bash
uv sync
cp .env.example .env                       # fill in LLM_* and NCBI_* values
uv run python -m src.graph.build           # first run downloads data; later runs use the caches
uv run uvicorn src.atlas.server:app --port 8000     # API docs at http://localhost:8000/docs
```

The LLM steps are separate because they are slow and rate-limited. Both are resumable:

```bash
uv run python -m src.etl.org_scrape                 # re-read patient organisation sites (cached; Bright Data if configured)
uv run python -m src.extract --spread --limit 60    # read more abstracts, taking turns between diseases
uv run python -m src.graph.review                   # second-model verdicts for edges not reviewed yet
uv run python -m src.graph.build                    # fold the results into the graph
```

## Limitations (honest)

- 22 diseases only. OMIM is not used. Variants are counts per gene (ClinVar), not individual variants.
- 120 of 712 on-topic abstracts have been read: the free Groq tier allows 200,000 tokens per model per day. Text-mined edges supplement the curated graph; they do not replace it.
- Reviewer verdicts were produced in more than one pass as the prompt improved, and the daily quota ran out before the last pass finished, so some verdicts are stricter than others. Re-run `src.graph.review` to finish.
- Patient organisations: 20, covering all 22 diseases. 5 were read by a person; the rest are linked because their own website names the disease repeatedly or in the organisation's name, with that sentence stored. "Names the disease" is weaker than "runs a programme for it", and registry mentions are sentences from their sites, not verified registries.
- Reactome has no specific pathway for CLN5, CLN6, CLN7 or CLN8. Gene Ontology processes fill that gap for navigation, but the similarity score still uses Reactome only, so the NCL cluster rests on symptoms.
- A paper that names only the disease family ("Batten disease") is linked to a subtype only when it was retrieved for exactly one subtype; those edges are marked and carry lower confidence.
- Paper authors are matched to known investigators by full name only, at lower confidence.
- Similarity uses HPO annotations, which are uneven across diseases.

## Scale-up path

Run the same extraction on a GPU (gpt-oss via vLLM) or a paid tier for all 712 abstracts; add more diseases to `data/manual/diseases.csv`; add more hand-checked patient organisations.
