# Graph statistics

Built from `data/graph/` on 2026-10-04.

## Nodes

| node type | count |
|---|---|
| Phenotype | 674 |
| Investigator | 618 |
| Trial | 342 |
| Grant | 233 |
| Pathway | 209 |
| Asset | 126 |
| Paper | 63 |
| Gene | 23 |
| Disease | 22 |
| PatientOrg | 20 |

## Edges by evidence type

| evidence type | count |
|---|---|
| curated | 3760 |
| text_mined | 191 |
| inferred | 39 |

## Edges by predicate

| predicate | count |
|---|---|
| has_phenotype | 1471 |
| investigator_of | 792 |
| studied_in_trial | 543 |
| participates_in_pathway | 390 |
| funded_by | 358 |
| has_asset | 232 |
| gene_associated_with_disease | 83 |
| serves_disease | 82 |
| similar_to | 39 |

## Text-mined facts

- 774 abstracts collected; 712 mention one of our diseases or genes (62 off-topic removed before reading).
- 120 abstracts read by the LLM; 103 gave at least one fact. Models: openai/gpt-oss-120b (90), openai/gpt-oss-20b (30).
- 420 facts kept after the quote check; 40 more were dropped because the quoted sentence was not in the abstract.
- 131 became graph edges. Dropped while resolving to stable IDs: 52 pathway predicate has no disease->pathway home, 111 out of scope (disease not one of ours / not this paper's), 104 unresolved (name not in graph), 22 quote does not name the gene/symptom.
- Second-model review of the text-mined edges (openai/gpt-oss-120b, openai/gpt-oss-20b): 67 supported, 33 not_reviewed, 22 unsupported, 9 partial.

## Connections

- 0 contradictions found among 131 text-mined facts (0 facts were denials; 0 of them deny something no other source asserts)
- 133 people link 2+ diseases through a trial, grant or paper (37 across clusters).
- 20 patient organisations serve 22 of 22 diseases (22 links hand-checked, 60 read from the organisations' own web pages with the sentence stored).
- Mechanism links: 214 gene-pathway edges from Reactome, 176 gene-process edges from Gene Ontology.
- 47 investigators work on trials for 2+ diseases (11 across clusters).
- 543 asset/trial rows linked to diseases.
