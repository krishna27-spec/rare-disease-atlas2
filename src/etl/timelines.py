"""Real durations of the natural history studies registered for every disease in the Atlas.

Run:  uv run python -m src.etl.timelines
For each natural history study in the graph (Asset nodes), ask ClinicalTrials.gov for start date, completion date
and enrolment. Writes data/graph/nhs_timelines.csv, one row per (study, disease). Used by the 10x view as the cited
"how long does a study take" evidence (no invented figures)."""
import datetime

import pandas as pd
import requests

from src.etl.research import cached
from src.graph.schema import GRAPH_DIR

FIELDS = "NCTId,BriefTitle,StartDate,PrimaryCompletionDate,CompletionDate,EnrollmentCount,OverallStatus,LeadSponsorName"


def months(a: str, b: str) -> float | None:
    try:
        fa = lambda s: datetime.date.fromisoformat(s + "-01" if len(s) == 7 else s)
        return round((fa(b) - fa(a)).days / 30.44, 1)
    except ValueError:
        return None


def main() -> None:
    nodes = pd.read_parquet(GRAPH_DIR / "nodes.parquet").set_index("node_id")
    edges = pd.read_parquet(GRAPH_DIR / "edges.parquet")
    a = edges[edges.predicate == "has_asset"]
    rows, today = [], datetime.date.today().isoformat()
    for e in a.itertuples():
        if '"natural history study"' not in nodes.loc[e.object, "attrs"]:
            continue
        nct = e.object.replace("ASSET:", "")
        d = cached("ctgov_detail", nct, lambda: requests.get(
            f"https://clinicaltrials.gov/api/v2/studies/{nct}", params={"fields": FIELDS}, timeout=30))
        s = d["protocolSection"]
        st = s.get("statusModule", {})
        start = st.get("startDateStruct", {}).get("date", "")
        end = st.get("completionDateStruct", {}).get("date", "")
        rows.append({"nct": nct, "disease_id": e.subject, "disease": nodes.loc[e.subject, "name"], "title": s["identificationModule"]["briefTitle"],
                     "status": st.get("overallStatus", ""), "start": start, "completion": end,
                     "completion_type": st.get("completionDateStruct", {}).get("type", ""),
                     "months": months(start, end) if start and end else None,
                     "enrollment": s.get("designModule", {}).get("enrollmentInfo", {}).get("count"),
                     "sponsor": s.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {}).get("name", ""),
                     "edge_id": e.edge_id, "source_url": f"https://clinicaltrials.gov/study/{nct}", "retrieved": today})
    df = pd.DataFrame(rows).drop_duplicates(["nct", "disease_id"]).sort_values(["start", "nct"])
    df.to_csv(GRAPH_DIR / "nhs_timelines.csv", index=False)
    one = df.drop_duplicates("nct")
    done = one[(one.status == "COMPLETED") & one.months.notna()]
    print(f"{len(one)} natural history studies across {df.disease_id.nunique()} diseases; {len(done)} with status COMPLETED")
    if len(done):
        print(f"median duration of finished studies: {done.months.median():.0f} months")


if __name__ == "__main__":
    main()
