"""The landscape around each disease: how common it is and where, how its trials went, and where they run.

Run:  uv run python -m src.etl.landscape      (after src.etl.research)
Everything here is copied from a registry, with its source kept on each row. Nothing is estimated.

Writes to data/graph/:
  disease_facts.parquet  prevalence by country, age of onset, inheritance   (Orphadata product 9, with its PMIDs)
  trial_facts.parquet    phase, status, enrolment, dates, why a trial stopped, what was tested (ClinicalTrials.gov)
  trial_sites.parquet    every study site with city, country, coordinates and recruiting status (ClinicalTrials.gov)
  outside_index.parquet  rare diseases that are NOT in the Atlas yet (MONDO name, synonyms, Orphadata gene), so a
                         search for one can say what it is and what adding it would take
These are attributes of diseases and trials, not new edges, so they carry `source`/`source_url` instead of edge IDs.
"""
import re

import obonet
import pandas as pd
import requests
from lxml import etree

from src.etl.download import RAW, SOURCES
from src.etl.research import HEADERS, TODAY, cached
from src.graph.schema import GRAPH_DIR

FIELDS = ("NCTId,OverallStatus,Phase,StudyType,EnrollmentCount,StartDate,CompletionDate,WhyStopped,HasResults,"
          "InterventionType,InterventionName,LocationFacility,LocationCity,LocationCountry,LocationGeoPoint,"
          "LocationStatus")
ORPHA_PAGE = "https://www.orpha.net/en/disease/detail/"


def orpha_of(xrefs) -> str | None:
    for x in xrefs if xrefs is not None else []:
        if x.startswith("Orphanet:"):
            return x.split(":")[1]
    return None


def disease_facts(diseases: pd.DataFrame) -> pd.DataFrame:
    code = {orpha_of(r.xrefs): r.node_id for r in diseases.itertuples() if orpha_of(r.xrefs)}
    rows = []
    for d in etree.parse(RAW / "en_product9_prev.xml").iterfind(".//Disorder"):
        oc = d.findtext("OrphaCode")
        if oc not in code:
            continue
        for p in d.iterfind(".//Prevalence"):
            get = lambda tag: p.findtext(f"{tag}/Name") or ""
            val = p.findtext("ValMoy")
            rows.append({"disease_id": code[oc], "kind": "prevalence", "value": get("PrevalenceClass"),
                         "per_100k": float(val) if val and float(val) > 0 else None,
                         "measure": get("PrevalenceType"), "where": get("PrevalenceGeographic"),
                         "validated": get("PrevalenceValidationStatus") == "Validated",
                         "reference": (p.findtext("Source") or "").replace("[PMID]", ""),
                         "source": "Orphadata product 9 (epidemiology)", "source_url": ORPHA_PAGE + oc,
                         "retrieved": TODAY})
    for d in etree.parse(RAW / "en_product9_ages.xml").iterfind(".//Disorder"):
        oc = d.findtext("OrphaCode")
        if oc not in code:
            continue
        for kind, tag in (("onset", "AverageAgeOfOnset"), ("inheritance", "TypeOfInheritance")):
            for x in d.iterfind(f".//{tag}/Name"):
                rows.append({"disease_id": code[oc], "kind": kind, "value": x.text, "per_100k": None, "measure": "",
                             "where": "", "validated": True, "reference": "",
                             "source": "Orphadata product 9 (natural history)", "source_url": ORPHA_PAGE + oc,
                             "retrieved": TODAY})
    df = pd.DataFrame(rows)
    df.to_parquet(GRAPH_DIR / "disease_facts.parquet", index=False)
    return df


def trials(ncts: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    facts, sites = [], []
    for i in range(0, len(ncts), 50):
        chunk = ncts[i:i + 50]
        data = cached("ctgov_landscape", ",".join(chunk), lambda: requests.get(
            "https://clinicaltrials.gov/api/v2/studies", headers=HEADERS, timeout=90,
            params={"filter.ids": ",".join(chunk), "pageSize": 100, "fields": FIELDS}))
        for s in data.get("studies", []):
            p = s["protocolSection"]
            nct, st, des = p["identificationModule"]["nctId"], p.get("statusModule", {}), p.get("designModule", {})
            iv = p.get("armsInterventionsModule", {}).get("interventions", [])
            url = f"https://clinicaltrials.gov/study/{nct}"
            facts.append({"nct": nct, "status": st.get("overallStatus", ""), "study_type": des.get("studyType", ""),
                          "phases": "|".join(des.get("phases", [])),
                          "enrollment": des.get("enrollmentInfo", {}).get("count"),
                          "start": st.get("startDateStruct", {}).get("date", ""),
                          "completion": st.get("completionDateStruct", {}).get("date", ""),
                          "why_stopped": st.get("whyStopped", ""), "has_results": bool(s.get("hasResults")),
                          "intervention_types": "|".join(sorted({x.get("type", "") for x in iv if x.get("type")})),
                          "interventions": "|".join(dict.fromkeys(x.get("name", "") for x in iv if x.get("name"))),
                          "source": "ClinicalTrials.gov", "source_url": url, "retrieved": TODAY})
            for loc in p.get("contactsLocationsModule", {}).get("locations", []):
                g = loc.get("geoPoint") or {}
                sites.append({"nct": nct, "facility": loc.get("facility", ""), "city": loc.get("city", ""),
                              "country": loc.get("country", ""), "lat": g.get("lat"), "lon": g.get("lon"),
                              "site_status": loc.get("status", ""), "source_url": url, "retrieved": TODAY})
    f, s = pd.DataFrame(facts), pd.DataFrame(sites)
    f.to_parquet(GRAPH_DIR / "trial_facts.parquet", index=False)
    s.to_parquet(GRAPH_DIR / "trial_sites.parquet", index=False)
    return f, s


def outside_index(ours: set[str]) -> pd.DataFrame:
    """Rare diseases MONDO knows (with an Orphanet ID) that the Atlas has not loaded, with their causal genes."""
    mondo = obonet.read_obo(RAW / "mondo.obo")
    genes: dict[str, list[str]] = {}
    for d in etree.parse(RAW / "en_product6.xml").iterfind(".//Disorder"):
        syms = [a.findtext("Gene/Symbol") for a in d.iterfind(".//DisorderGeneAssociation")
                if (a.findtext("DisorderGeneAssociationType/Name") or "").startswith("Disease-causing germline")]
        genes[d.findtext("OrphaCode")] = sorted({s for s in syms if s})
    rows = []
    for mid, n in mondo.nodes(data=True):
        if not mid.startswith("MONDO:") or mid in ours or n.get("is_obsolete") or "name" not in n:
            continue
        oc = orpha_of(n.get("xref", []))
        if not oc:
            continue
        syn = [m.group(1) for s in n.get("synonym", []) if "EXACT" in s and (m := re.match(r'"(.+?)"', s))][:4]
        rows.append({"mondo_id": mid, "name": n["name"], "synonyms": "|".join(syn), "orpha": oc,
                     "genes": "|".join(genes.get(oc, []))})
    df = pd.DataFrame(rows)
    df.to_parquet(GRAPH_DIR / "outside_index.parquet", index=False)
    return df


def main() -> None:
    nodes = pd.read_parquet(GRAPH_DIR / "nodes.parquet")
    diseases = nodes[nodes.node_type == "Disease"]
    facts = disease_facts(diseases)
    by = facts.groupby("kind").disease_id.nunique().to_dict()
    print(f"disease facts: {len(facts)} rows; prevalence for {by.get('prevalence', 0)} of {len(diseases)} diseases, "
          f"onset for {by.get('onset', 0)}, inheritance for {by.get('inheritance', 0)}")
    f, s = trials(sorted(nodes[nodes.node_type == "Trial"].node_id))
    print(f"trial facts: {len(f)} studies, {int((f.why_stopped != '').sum())} say why they stopped, "
          f"{int(f.has_results.sum())} posted results; {len(s)} sites in {s.country.nunique()} countries")
    out = outside_index(set(diseases.node_id))
    print(f"outside index: {len(out)} rare diseases not in the Atlas yet ({int((out.genes != '').sum())} with a known gene)")
    print(f"sources: {SOURCES['en_product9_prev.xml']}")


if __name__ == "__main__":
    main()
