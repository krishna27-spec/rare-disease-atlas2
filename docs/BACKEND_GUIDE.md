# Understanding the backend: a guide for whoever builds the website

You do not need to know biology or read the Python to build the UI. This page explains what the backend is, how to think about its data, and which call feeds which part of the screen. The full endpoint list is in [`BACKEND_API.md`](BACKEND_API.md).

## 1. What the backend is, in one minute

The backend is a **knowledge graph stored in a few small files**, plus a **read-only JSON API** over it.

```
public sources ──► build scripts (src/etl, src/graph) ──► data/graph/*.parquet ──► API (src/atlas) ──► your UI
   (run once, offline)                                       (committed to git)      (read-only)
```

- The graph is **already built and committed**. You never run the build to work on the UI.
- The API only reads those files. It has no database, no login, no write endpoints, and it loads everything into memory at start-up (under a second).
- The only thing that calls an AI model at request time is `/disease/{id}/next-steps?explain=true`. Everything else is instant lookups.

## 2. Run it

```bash
uv sync                                              # once
uv run uvicorn src.atlas.server:app --port 8000
```

Open http://localhost:8000/docs. Every endpoint is listed there with a "Try it out" button, so you can see real responses before writing any code. CORS is open, so a dev server on another port can call it directly.

No keys are needed. Without a `.env`, `next-steps` simply returns the cited candidate list without the AI-written wording.

## 3. The mental model

### Nodes: the things

| Node type | What it is | ID looks like | How many |
|---|---|---|---|
| Disease | one of the 22 rare diseases | `MONDO:0009657` | 22 |
| Gene | the gene whose variants cause a disease | `HGSNAT` | 23 |
| Phenotype | a symptom or clinical sign | `HP:0001250` | 674 |
| Pathway | a biological mechanism (Reactome or Gene Ontology) | `R-HSA-2024096`, `GO:0007040` | 209 |
| Trial | a registered clinical study | `NCT05825131` | 342 |
| Asset | something reusable: natural history study, registry | `ASSET:NCT05825131` | 126 |
| Grant | an NIH-funded project | `R21NS135412` | 233 |
| Investigator | a researcher or clinician | `CTGOV-INV:…`, `NIHPI:…`, `AUTHOR:…` | 618 |
| Paper | a PubMed article a fact was read from | `PMID:20650889` | 63 |
| PatientOrg | a patient organisation | `ORG:curesanfilippofoundation.org` | 20 |

There are no "Variant" nodes: each gene carries a count of known disease-causing variants instead.

### Edges: the facts

An edge is one sentence: **subject → predicate → object**. For example `HGSNAT → gene_associated_with_disease → MPS IIIC`.

Every edge has an ID like `E7520cab1fc7b` and always carries its proof:

| Field | Meaning |
|---|---|
| `evidence_type` | how we know it (see below) |
| `confidence` | 0 to 1 |
| `source`, `source_record`, `source_url` | where it came from, with a link |
| `retrieved` | the date we fetched it |
| `evidence_text` | the exact quoted sentence, for facts read from text |
| `reviewer_verdict` | a second AI model's check of that quote: `supported`, `partial`, `unsupported`, `not_reviewed` |
| `contradicts` | IDs of edges that say the opposite |

### The three evidence types: the most important thing to show

| `evidence_type` | Plain meaning | Suggested colour |
|---|---|---|
| `curated` | copied from a trusted database (confirmed) | blue `#1f77b4` |
| `text_mined` | read from a paper or a web page; the exact sentence is stored | orange `#ff7f0e` |
| `inferred` | computed by us (disease similarity). A hypothesis, not an observation | grey `#8c8c8c`, dashed |

The judges score "evidence integrity", so the UI should make this distinction visible everywhere a connection is drawn or listed.

## 4. The one rule that makes the UI trustworthy

**Every item in every response has an `edge_ids` list.** Those are the facts that justify the item.

So the pattern for any "Why is this connected?" or "Show evidence" interaction is always the same:

```
user clicks a line, a card or a graph edge
   → take its edge_ids
   → GET /edge/{id} for each
   → show source, date, confidence, quote, reviewer verdict, and a link to source_url
```

You never have to work out the justification yourself.

## 5. Which call feeds which part of the screen

Following the flow in the UI spec: **Search → Understand → Connect → Verify → Act**.

| UI moment | Call | What you get |
|---|---|---|
| **Search** box (disease, gene, symptom, pathway, patient group; typos OK) | `GET /search?q=` | `hits[]` with `kind`, `id`, `label`, and what it `matched`. Gene, symptom, pathway and organisation hits include the `diseases[]` they lead to |
| Disease picker / landing list | `GET /diseases` | all 22 with cluster and genes |
| **Understand**: the disease panel | `GET /disease/{id}` | synonyms, genes, cluster, patient groups, counts, facts read from papers |
| The **knowledge graph** in the centre | `GET /disease/{id}/graph` | `nodes[]` (`id`, `label`, `type`) and `edges[]` (`id`, `source`, `target`, `predicate`, `evidence_type`, `confidence`). Feed straight into any graph library |
| **Connect**: "who is like us" | `GET /disease/{id}/neighbours` | ranked similar diseases with what is shared and **what differs** |
| **Connect**: the mechanism path | `GET /disease/{id}/pathways` | step-by-step paths: disease → gene → pathway → gene → other disease, and what exists there |
| **Connect**: people and groups | `GET /connectors?disease={id}` | researchers and organisations that link this disease to others |
| Cluster view / map of all diseases | `GET /clusters`, `GET /cluster/{n}` | members, why they belong together, assets, groups |
| Scout view: "which diseases share this mechanism?" | `GET /mechanism?q=` | ranked clusters for a pathway or gene |
| **Verify**: evidence drawer | `GET /edge/{id}` | full proof for one fact |
| **Verify**: contradictions | `GET /contradictions` | pairs of facts that disagree (currently none; the response explains why) |
| **Act**: existing work to reuse | `GET /disease/{id}/assets` | registries, natural history studies, trials |
| **Act**: next steps | `GET /disease/{id}/next-steps` | `candidates[]` (always present) and `steps[]` (AI wording, may be empty) |
| "About the data" page | `GET /stats` | counts and the confidence rules |

`type` values in `/graph` nodes are: `centre`, `disease`, `gene`, `pathway`, `symptom`, `patient_org`. Map your icons to these.

## 6. Things that will otherwise surprise you

**"Nothing found" is a real answer, not an error.** When there is no supported result, the response is still `200` and contains one of `no_match`, `no_route` or `no_connector`. Each explains what was searched and what would change the answer. Design a proper state for these: showing honest gaps is one of the judging criteria. Try `/search?q=cystic fibrosis`.

**`supported: false` on a neighbour** means the similarity is too weak to recommend. Show it greyed out or under "weak links", not as a recommendation.

**`next-steps` has two lists.** `candidates[]` is built by code and is always there. `steps[]` is the same content reworded by an AI model in plain language, each line ending with edge IDs in square brackets like `[E7520cab1fc7b]`. If the model is unavailable, `steps` is empty and `llm_note` says why: fall back to `candidates`. Always show `disclaimer` and `expert_must_check[]` near this section. This call can take a few seconds with `explain=true`; use `explain=false` for an instant answer.

**Patient organisations come in two strengths.** `hand_checked: true` means a person read the site. Otherwise the link exists because the organisation's own website names the disease, and `quote` is that sentence. `registry_mentions[]` are sentences from their site about registries or studies: present them as leads to follow up.

**Reviewer verdicts on paper facts.** A `text_mined` edge from a paper has `reviewer_verdict`. Suggested treatment: `supported` normal, `partial` with a caution mark, `unsupported` hidden by default or clearly flagged, `not_reviewed` neutral.

**IDs contain colons.** `MONDO:0009657` works as-is in a URL path. Use the ID, never the name, as the key.

**The data only changes when the graph is rebuilt.** Responses are safe to cache on the client for the whole session. After a rebuild, restart the API.

## 7. A good demo path

Maria's child has MPS IIIC. These calls, in order, tell the whole story:

1. `/search?q=sanfilipo c` (typo on purpose) → `MONDO:0009657`
2. `/disease/MONDO:0009657` → gene HGSNAT, 4 patient organisations
3. `/disease/MONDO:0009657/graph` → the picture
4. `/disease/MONDO:0009657/neighbours` → MPS IIIA and IIIB share the heparan sulfate pathway; here is what differs
5. `/disease/MONDO:0009657/pathways` → the cited path, hop by hop
6. `/disease/MONDO:0009657/assets` → natural history studies that already exist
7. `/connectors?disease=MONDO:0009657` → people working across these diseases
8. `/disease/MONDO:0009657/next-steps` → what she can do this week
9. Click anything → `/edge/{id}` → the proof

Honest-gap examples: `/search?q=cystic fibrosis` (outside the Atlas) and `/cluster/6` (a cluster of one: no similar disease found).

## 8. What you should not need to touch

| Folder | What it is | UI work needs it? |
|---|---|---|
| `src/atlas/` | the API and its query functions | read `server.py` if you want to see an endpoint's code |
| `src/etl/`, `src/graph/` | scripts that build the graph | no |
| `src/webapp/` | helpers the API reuses | no |
| `data/graph/` | the built graph | no, use the API |
| `data/manual/` | hand-maintained inputs | no |

If a screen needs data in a shape the API does not return, ask for a new field or endpoint rather than reading the parquet files: the API is what guarantees that every item still carries its `edge_ids`.

If you build in Python (for example Streamlit), you can skip HTTP and call the same functions directly; they return the same dictionaries:

```python
from src.atlas.queries import Atlas
A = Atlas()
A.search("sanfilipo c")
A.neighbours("MONDO:0009657")
```
