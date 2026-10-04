# The dataset

Everything the website shows comes from the files in `graph/`. They are built by `uv run python -m src.graph.build` from the sources below.

## `graph/` (processed output)

| File | One row is | Main columns |
|---|---|---|
| `nodes.parquet` | a thing: disease, gene, symptom, mechanism, trial, asset, grant, researcher, paper, patient organisation | `node_id` (stable ID), `node_type`, `name`, `synonyms`, `xrefs`, `attrs` (JSON with extra facts) |
| `edges.parquet` | one fact linking two nodes | `edge_id`, `subject`, `predicate`, `object`, `evidence_type` (curated / text_mined / inferred), `confidence`, `source`, `source_record`, `source_url`, `retrieved`, `evidence_text` (the quoted sentence), `method`, `contradicts`, `reviewer_verdict` |
| `neighbours.parquet` | a disease and one of its most similar diseases | scores, shared mechanisms and symptoms, what differs, the edge IDs behind each |
| `similarity_pairs.csv`, `clusters.csv` | every disease pair with its scores; each disease's cluster | |
| `pathways.parquet` | a mechanism with its genes and diseases | |
| `connectors.parquet`, `shared_people.parquet` | a person linked to two or more diseases | diseases, routes (trial, grant, paper), edge IDs |
| `cluster_assets.parquet` | a study, registry or trial for a disease | kind, status, sponsor, edge ID |
| `nhs_timelines.csv` | a natural history study | start, completion, months, enrolment |
| `disease_facts.parquet` | a prevalence figure, age of onset or inheritance pattern | value, where, measure, reference |
| `trial_facts.parquet`, `trial_sites.parquet` | a trial's outcome; one study site | phase, status, why it stopped; city, country, coordinates |
| `outside_index.parquet` | a rare disease that is not loaded yet | MONDO ID, name, genes |
| `STATS.md` | the counts, including how many extracted facts were dropped and why | |

## `manual/` (hand-maintained input)

`diseases.csv` is the list of 22 diseases with their MONDO IDs and genes. `patient_orgs.csv` holds the organisations a person checked. `org_sources.csv` lists organisation websites to read; `org_scrape.jsonl` is what was found on them.

## `cache/` (LLM results kept for reproducibility)

`abstracts.jsonl` and `abstracts_filtered.jsonl` are the PubMed abstracts collected and the on-topic subset. `extractions.jsonl` is what gpt-oss extracted from the 120 it read. `edges_text_mined.jsonl` is the same, flattened to one fact per line. `reviews.jsonl` holds the second model's verdict per fact. `papers.jsonl` has authors and journals.

## Sources

MONDO, HPO, Orphadata (CC BY 4.0), HGNC, Reactome, Gene Ontology, ClinVar, PubMed, ClinicalTrials.gov, NIH RePORTER, and the websites of 21 patient organisations. The large raw downloads (about 230 MB) are not in the repository; the build fetches them into `data/raw/`.
