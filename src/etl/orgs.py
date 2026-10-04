"""Patient organisations as graph nodes: PatientOrg -> serves_disease -> Disease.

Run:  uv run python -m src.etl.orgs      (after src.etl.biology)
Reads data/manual/patient_orgs.csv (one row per organisation whose website a person read: curated edges) and
data/manual/org_scrape.jsonl (what src.etl.org_scrape read on the organisations' own pages: text_mined edges that
store the sentence naming the disease; passing mentions are left out).
Writes PatientOrg nodes and serves_disease edges into data/graph/ (replacing the earlier version of this layer).

The source of every edge is the organisation's own URL and the date it was checked. A row whose note says the
scope was not verified gets a low confidence, so the app can show it as a lead rather than a fact.
"""
import json
import re
from pathlib import Path

import pandas as pd

from src.graph.schema import GRAPH_DIR, make_edge, merge_layer

CSV = "data/manual/patient_orgs.csv"
SCRAPE = Path("data/manual/org_scrape.jsonl")
VERIFIED_CONF, UNVERIFIED_CONF = 0.9, 0.5      # hand-checked rows
NAME_CONF, REPEAT_CONF, FAMILY_PENALTY = 0.85, 0.7, 0.1   # read from the website by code


def org_id(url: str) -> str:
    host = re.sub(r"^https?://(www\.)?", "", url.strip().lower()).split("/")[0]
    return "ORG:" + host


def main() -> None:
    orgs = pd.read_csv(CSV, dtype=str, keep_default_na=False)
    ours = set(pd.read_parquet(GRAPH_DIR / "nodes.parquet").query("node_type == 'Disease'").node_id)
    nodes: dict[str, dict] = {}
    edges = []
    # ---- hand-checked rows (curated)
    for r in orgs.itertuples():
        oid = org_id(r.url)
        verified = "not verified" not in r.note.lower()
        nodes[oid] = {"node_id": oid, "node_type": "PatientOrg", "name": r.name,
                      "attrs": {"url": r.url, "diseases_served": r.diseases_served,
                                "registry_or_study": r.registry_or_study, "date_checked": r.date_checked,
                                "scope_verified": verified, "note": r.note}}
        for d in r.mondo_ids.split("|"):
            if d not in ours:
                print(f"  skipped {r.name} -> {d}: not one of our diseases")
                continue
            edges.append(make_edge(oid, "serves_disease", d, "curated", VERIFIED_CONF if verified else UNVERIFIED_CONF,
                                   "Patient organisation website", f"{r.name}|{r.note}", r.url, r.date_checked))
    # ---- what the organisations' own pages say (src.etl.org_scrape): text_mined, with the sentence as the quote
    n_scraped = 0
    if SCRAPE.exists():
        for line in SCRAPE.read_text().splitlines():
            x = json.loads(line)
            strong = [v for v in x["serves"] if v["strength"] != "passing mention" and v["mondo_id"] in ours]
            if not strong:
                continue
            oid = org_id(x["url"])
            node = nodes.setdefault(oid, {"node_id": oid, "node_type": "PatientOrg", "name": x["name"],
                                          "attrs": {"url": x["url"], "date_checked": x["retrieved"],
                                                    "scope_verified": False, "registry_or_study": "",
                                                    "note": "Read automatically from its website; not hand-checked"}})
            node["attrs"].update(registry_mentions=x["registry_or_study"], pages_read=len(x["pages_read"]),
                                 fetched_via=x["fetched_via"])
            for v in strong:
                conf = (NAME_CONF if v["in_org_name"] else REPEAT_CONF) - (0 if v["match"] == "specific" else FAMILY_PENALTY)
                edges.append(make_edge(
                    oid, "serves_disease", v["mondo_id"], "text_mined", conf, "Patient organisation website",
                    f"{x['name']}|{v['strength']}" + ("" if v["match"] == "specific" else "|family-level wording"),
                    v["url"], x["retrieved"], evidence_text=v["quote"],
                    method="disease-name match on the organisation's own pages (code, no LLM)"))
                n_scraped += 1
    for n in nodes.values():
        n["attrs"] = json.dumps(n["attrs"], ensure_ascii=False)
    merge_layer(list(nodes.values()), edges, {"PatientOrg"}, {"serves_disease"})
    covered = {e["object"] for e in edges}
    print(f"{len(nodes)} patient organisations, {len(edges)} serves_disease edges "
          f"({len(edges) - n_scraped} hand-checked, {n_scraped} read from websites), "
          f"{len(covered)} of {len(ours)} diseases have an organisation")
    names = pd.read_parquet(GRAPH_DIR / "nodes.parquet").set_index("node_id")["name"]
    print("No organisation recorded for: " + (", ".join(sorted(names[d] for d in ours - covered)) or "none"))


if __name__ == "__main__":
    main()
