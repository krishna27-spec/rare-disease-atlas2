# Rare Disease Atlas: backend API for the UI

The backend is a set of read-only JSON endpoints over the graph files in `data/graph/`. The UI never needs to read parquet files or call an LLM itself.

## Start it

```bash
uv sync
uv run uvicorn src.atlas.server:app --port 8000
```

- Interactive docs with every endpoint and a "Try it out" button: http://localhost:8000/docs
- CORS is open, so a browser app on another port can call it.
- `.env` is only needed for `/next-steps?explain=true` (the one LLM call). Everything else works without keys.
- From Python (for example a Streamlit app) skip HTTP and call the same functions directly:
  ```python
  from src.atlas.queries import Atlas
  A = Atlas()                      # loads the graph once
  A.search("sanfilipo c")
  ```

## Three rules the UI should follow

1. **Disease IDs are MONDO IDs.** Maria's disease, MPS IIIC, is `MONDO:0009657`. Get an ID from `/search` or `/diseases`.
2. **Everything carries `edge_ids`.** Each ID (like `E7520cab1fc7b`) is one fact in the graph. Call `/edge/{id}` to show its source, date, confidence, quote and reviewer verdict. Show this wherever a claim is shown.
3. **Colour by `evidence_type`.** `curated` (from a database) blue `#1f77b4`, `text_mined` (an LLM read a paper, quote verified) orange `#ff7f0e`, `inferred` (computed similarity) grey `#8c8c8c`, dashed.

When nothing is supported, the response has a `no_match`, `no_route` or `no_connector` field that says what was searched and what would change the answer. Show it; do not hide it.

## Endpoints

| Capability | Endpoint | Returns |
|---|---|---|
| Search | `GET /search?q=` | `hits[]`: `kind` (disease, gene, symptom, pathway, patient_org), `id`, `label`, `matched`, `score`. Non-disease hits include `diseases[]`. Typos are tolerated. |
| | `GET /diseases` | All diseases with cluster and genes (for a picker). |
| | `GET /disease/{id}` | Summary card: synonyms, genes, cluster members, patient groups, counts, `facts_from_papers[]`. |
| Clustering | `GET /clusters` | Every cluster: members, top shared pathways and symptoms, asset counts. |
| | `GET /cluster/{n}` | One cluster in full: why the members belong together, reusable assets, patient groups, connectors. |
| | `GET /disease/{id}/neighbours` | "Who is like us": ranked similar diseases with `shared_pathways`, `shared_phenotypes`, `only_here`, `only_there`, and `supported` (false = too weak to recommend). |
| | `GET /mechanism?q=` | For a pathway name, Reactome ID or gene: ranked clusters with patient groups, infrastructure, unmet need and contacts. |
| Pathway navigator | `GET /disease/{id}/pathways` | `paths[]`: disease → gene → pathway → gene → other disease, each hop with its `edge_id`, plus `what_is_there` (groups, reusable assets) and `check_before_acting`. |
| Connector | `GET /connectors` | People and organisations that link 2+ diseases. Scope with `disease=`, `pathway=` or `cluster=`; `cross_cluster_only=true` for links between clusters. Each person has `via` (trial, grant, paper) and `links[]`. |
| What exists | `GET /disease/{id}/assets` | `own[]` (registries, natural history studies, trials) and `cluster_reusable[]`. |
| What next | `GET /disease/{id}/next-steps?explain=true` | `candidates[]` (cited actions built by code), `steps[]` (1 to 3 plain-language steps from gpt-oss, each ending with edge IDs in brackets), `expert_must_check[]`, `searched[]`, `disclaimer`. If the LLM is unavailable `steps` is empty and `llm_note` says why; show `candidates` instead. |
| Evidence | `GET /edge/{id}` | One fact with its full provenance and `contradicted_by[]`. |
| | `GET /disease/{id}/graph` | `nodes[]` (`id`, `label`, `type`) and `edges[]` (`id`, `source`, `target`, `predicate`, `evidence_type`, `confidence`) ready for any graph library. |
| | `GET /contradictions` | Pairs of edges where a paper denies what another source asserts. |
| | `GET /stats` | Counts by node type, evidence type, predicate, source and reviewer verdict, and the confidence rules. |

Unknown IDs return `404` with a `detail` message.

## The Maria journey, as calls

```
GET /search?q=sanfilippo c                        → MONDO:0009657
GET /disease/MONDO:0009657                        → gene HGSNAT, cluster 2, patient groups
GET /disease/MONDO:0009657/neighbours             → MPS IIIA / IIIB: shared pathways and symptoms, what differs
GET /disease/MONDO:0009657/pathways               → the cited path through heparan sulfate metabolism
GET /disease/MONDO:0009657/assets                 → natural history studies already registered
GET /connectors?disease=MONDO:0009657             → people who work across these diseases
GET /disease/MONDO:0009657/next-steps             → cited steps she can take this week
GET /edge/<any id shown>                          → the proof behind a line
```

Honest gaps to demo: `/search?q=cystic fibrosis` (outside the Atlas) and `/disease/MONDO:0009745/pathways` (CLN5: no shared pathway on record, with symptom-based alternatives).

## Example: one edge

```json
{
  "edge_id": "Ef17709291190",
  "subject": "MONDO:0009657", "subject_name": "MPS IIIC (Sanfilippo C)",
  "predicate": "has_asset",
  "object": "ASSET:NCT07712003", "object_name": "Natural History to Assess Disease in Patients With MPS IIIC",
  "evidence_type": "curated", "kind": "from a database or registry",
  "confidence": 0.85,
  "source": "ClinicalTrials.gov", "source_record": "NCT07712003",
  "source_url": "https://clinicaltrials.gov/study/NCT07712003",
  "retrieved": "2026-10-04",
  "evidence_text": "", "method": "",
  "reviewer_verdict": "not_reviewed", "contradicts": [], "contradicted_by": []
}
```

Patient organisations appear as `patient_orgs[]` in several responses. Each has `name`, `url`, `hand_checked` (a person read the site) and `quote` (the sentence on its own website that names the disease), plus `registry_mentions[]`: up to three sentences from its site about a registry, natural history study or biobank, each with the page `url`. Show these as leads to follow up, not as confirmed facts.

Pathways come from two sources: Reactome (`R-HSA-...`) and Gene Ontology processes (`GO:...`); `pathway.source` says which.

For a `text_mined` edge, `evidence_text` is the exact sentence from the abstract, `method` names the gpt-oss model that extracted it, and `reviewer_verdict` is the second model's check (`supported`, `partial`, `unsupported`).
