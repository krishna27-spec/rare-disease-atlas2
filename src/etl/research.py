"""Milestone 5: research layer = trials (ClinicalTrials.gov), grants (NIH RePORTER), papers (PubMed).

Run:  uv run python -m src.etl.research
Every API answer is cached in data/cache/, so re-runs download nothing twice.
Writes: data/cache/abstracts.jsonl, data/cache/papers.jsonl, and adds Trial / Investigator /
Grant / Asset nodes and their edges to data/graph/ (replacing any earlier version of this layer).
"""
import datetime
import hashlib
import json
import os
import re
import time
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv
from lxml import etree

from src.etl.terms import SPECIFIC, all_phrases, match_diseases, normalise
from src.graph.schema import make_edge, merge_layer

load_dotenv(".env")
CACHE = Path("data/cache")
TODAY = datetime.date.today().isoformat()
HEADERS = {"User-Agent": "rare-disease-atlas (hackathon project)"}
NCBI = {"api_key": os.getenv("NCBI_API_KEY"), "tool": "rare-disease-atlas", "email": os.getenv("NCBI_EMAIL")}
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"

PUBMED_RECENT, PUBMED_CITED = 30, 10        # per disease
GRANT_YEARS = list(range(2019, 2027))
TRIAL_CONF, GRANT_TITLE_CONF, GRANT_ABSTRACT_CONF, BROAD_CONF = 0.85, 0.8, 0.6, 0.5
PAUSE = {"ctgov": 0.3, "reporter": 1.0, "ncbi": 0.12}   # seconds between requests (rate limits)


# ---------- cached HTTP ----------
def cached(source: str, key: str, fetch):
    """Return the cached answer for (source, key), or call fetch() once and cache it."""
    path = CACHE / source / (hashlib.sha1(key.encode()).hexdigest() + ".json")
    if path.exists():
        return json.loads(path.read_text())
    for attempt in range(6):
        try:
            r = fetch()
        except (requests.ConnectionError, requests.Timeout):   # network blip: wait and retry
            time.sleep(5 * 2 ** attempt)
            continue
        if r.status_code == 429:
            time.sleep(2 ** attempt)
            continue
        r.raise_for_status()
        break
    else:
        raise RuntimeError(f"{source}: no answer after 6 tries (network down or rate limit)")
    data = r.json() if "json" in r.headers.get("content-type", "") else {"text": r.text}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    time.sleep(PAUSE.get(source.split("_")[0], 0.3))
    return data


# ---------- ClinicalTrials.gov ----------
CT_FIELDS = ("NCTId,BriefTitle,OfficialTitle,OverallStatus,StudyType,Phase,Condition,LeadSponsorName,"
             "OverallOfficialName,OverallOfficialAffiliation,OverallOfficialRole,StartDate")


def fetch_trials(phrase: str, max_pages: int = 3) -> list[dict]:
    studies, token = [], None
    for _ in range(max_pages):
        params = {"query.cond": f'"{phrase}"', "pageSize": 100, "fields": CT_FIELDS}
        if token:
            params["pageToken"] = token
        page = cached("ctgov", f"{phrase}|{token}", lambda: requests.get(
            "https://clinicaltrials.gov/api/v2/studies", params=params, headers=HEADERS, timeout=60))
        studies += page.get("studies", [])
        token = page.get("nextPageToken")
        if not token:
            break
    return studies


def parse_trial(s: dict) -> dict:
    p = s["protocolSection"]
    ident, design = p["identificationModule"], p.get("designModule", {})
    return {
        "nct": ident["nctId"], "title": ident.get("briefTitle", ""), "official_title": ident.get("officialTitle", ""),
        "status": p.get("statusModule", {}).get("overallStatus", ""),
        "start": p.get("statusModule", {}).get("startDate", ""),
        "type": design.get("studyType", ""), "phases": design.get("phases", []),
        "conditions": p.get("conditionsModule", {}).get("conditions", []),
        "sponsor": p.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {}).get("name", ""),
        "officials": p.get("contactsLocationsModule", {}).get("overallOfficials", []),
    }


GENERIC_NAME = re.compile(r"study director|medical director|clinical (trial|study)|sponsor|call center|"
                          r"contact|information|^director$|investigator$|^study chair$|\bmd\b$|use \w+ number")
TITLE_WORDS = {"dr", "md", "phd", "prof", "professor", "mph", "msc", "mbbs", "do", "frcp", "m", "d"}


def real_person(name: str) -> bool:
    """CT.gov 'officials' are often just a role ('Study Director'). Keep only real-looking names."""
    n = normalise(name)
    words = [w for w in n.split() if w not in TITLE_WORDS]
    return len(words) >= 2 and not GENERIC_NAME.search(n)


def investigator_id(name: str, affiliation: str) -> str:
    key = " ".join(w for w in normalise(name).split() if w not in TITLE_WORDS) + "|" + normalise(affiliation)
    return "CTGOV-INV:" + hashlib.sha1(key.encode()).hexdigest()[:10]


def asset_type(trial: dict) -> str:
    t = normalise(trial["title"] + " " + trial["official_title"])
    return ("natural history study" if "natural history" in t
            else "registry" if "registry" in t or "registries" in t else "observational study")


# ---------- NIH RePORTER ----------
RP_FIELDS = ["ProjectNum", "CoreProjectNum", "ProjectTitle", "PrincipalInvestigators", "Organization",
             "AwardAmount", "FiscalYear", "AbstractText"]


def fetch_grants(phrase: str, max_rows: int = 300) -> list[dict]:
    rows, offset = [], 0
    while offset < max_rows:
        body = {"criteria": {"advanced_text_search": {"operator": "and", "search_field": "projecttitle,abstracttext",
                                                      "search_text": f'"{phrase}"'}, "fiscal_years": GRANT_YEARS},
                "include_fields": RP_FIELDS, "offset": offset, "limit": 100}
        page = cached("reporter", f"{phrase}|{offset}", lambda: requests.post(
            "https://api.reporter.nih.gov/v2/projects/search", json=body, headers=HEADERS, timeout=60))
        rows += page.get("results", [])
        offset += 100
        if offset >= page.get("meta", {}).get("total", 0):
            break
    return rows


# ---------- PubMed ----------
def pubmed_query(mondo_id: str) -> str:
    return "(" + " OR ".join(f'"{p}"[tiab]' for p in SPECIFIC[mondo_id]) + ") AND hasabstract"


def esearch(term: str, sort: str, retmax: int) -> list[str]:
    params = {"db": "pubmed", "term": term, "sort": sort, "retmax": retmax, "retmode": "json", **NCBI}
    data = cached("ncbi_esearch", f"{term}|{sort}|{retmax}", lambda: requests.get(
        EUTILS + "esearch.fcgi", params=params, headers=HEADERS, timeout=60))
    return data["esearchresult"]["idlist"]


def citation_counts(pmids: list[str]) -> dict[str, int]:
    """iCite (NIH) gives citation counts; PubMed itself can't sort by citations."""
    out = {}
    for i in range(0, len(pmids), 100):
        chunk = pmids[i:i + 100]
        data = cached("ncbi_icite", ",".join(chunk), lambda: requests.get(
            "https://icite.od.nih.gov/api/pubs", params={"pmids": ",".join(chunk)}, headers=HEADERS, timeout=60))
        out.update({str(p["pmid"]): p.get("citation_count") or 0 for p in data["data"]})
    return out


def parse_article(a: etree._Element) -> dict:
    def text(el):
        return "".join(el.itertext()).strip() if el is not None else ""
    abstract = " ".join((f"{t.get('Label')}: " if t.get("Label") else "") + text(t)
                        for t in a.iterfind(".//Abstract/AbstractText"))
    year = (a.findtext(".//Article/Journal/JournalIssue/PubDate/Year")
            or (a.findtext(".//Article/Journal/JournalIssue/PubDate/MedlineDate") or "")[:4]
            or a.findtext(".//Article/ArticleDate/Year") or "")
    authors = []
    for au in a.iterfind(".//AuthorList/Author"):
        name = " ".join(x for x in [au.findtext("ForeName"), au.findtext("LastName")] if x) or au.findtext("CollectiveName") or ""
        if name:
            authors.append({"name": name, "affiliation": au.findtext("AffiliationInfo/Affiliation") or ""})
    return {"pmid": a.findtext(".//MedlineCitation/PMID"), "title": text(a.find(".//ArticleTitle")),
            "abstract": abstract, "year": year, "journal": a.findtext(".//Journal/Title") or "", "authors": authors}


def fetch_articles(pmids: list[str]) -> dict[str, dict]:
    """Title, abstract, authors for each PMID. Each article is cached on its own."""
    art_dir = CACHE / "pubmed_articles"
    art_dir.mkdir(parents=True, exist_ok=True)
    missing = [p for p in pmids if not (art_dir / f"{p}.json").exists()]
    for i in range(0, len(missing), 100):
        chunk = missing[i:i + 100]
        r = requests.post(EUTILS + "efetch.fcgi", data={"db": "pubmed", "id": ",".join(chunk), "retmode": "xml", **NCBI},
                          headers=HEADERS, timeout=120)
        r.raise_for_status()
        for a in etree.fromstring(r.content).iterfind(".//PubmedArticle"):
            art = parse_article(a)
            (art_dir / f"{art['pmid']}.json").write_text(json.dumps(art))
        time.sleep(PAUSE["ncbi"])
    return {p: json.loads((art_dir / f"{p}.json").read_text()) for p in pmids if (art_dir / f"{p}.json").exists()}


# ---------- build ----------
def main() -> None:
    diseases = pd.read_csv("data/manual/diseases.csv")
    ids = diseases["mondo_id"].tolist()
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    def node(nid, ntype, name, **attrs):
        nodes.setdefault(nid, {"node_id": nid, "node_type": ntype, "name": name, "attrs": json.dumps(attrs)})

    # --- trials
    print("ClinicalTrials.gov ...")
    trials: dict[str, dict] = {}
    for phrase in all_phrases():
        for s in fetch_trials(phrase):
            t = parse_trial(s)
            trials[t["nct"]] = t
    n_trial_edges = 0
    for t in trials.values():
        matches = match_diseases(" ".join(t["conditions"] + [t["title"], t["official_title"]]))
        if not matches:
            continue
        url = f"https://clinicaltrials.gov/study/{t['nct']}"
        node(t["nct"], "Trial", t["title"], status=t["status"], phases=t["phases"], study_type=t["type"],
             sponsor=t["sponsor"], start=t["start"], conditions=t["conditions"])
        for d, kind in matches:
            conf = TRIAL_CONF if kind == "specific" else BROAD_CONF
            rec = t["nct"] + ("" if kind == "specific" else "|broad family match")
            edges.append(make_edge(d, "studied_in_trial", t["nct"], "curated", conf, "ClinicalTrials.gov", rec, url, TODAY))
            n_trial_edges += 1
            if t["type"] == "OBSERVATIONAL":
                aid = "ASSET:" + t["nct"]
                node(aid, "Asset", t["title"], asset_type=asset_type(t), status=t["status"], sponsor=t["sponsor"])
                edges.append(make_edge(d, "has_asset", aid, "curated", conf, "ClinicalTrials.gov", rec, url, TODAY))
        for o in t["officials"]:
            if real_person(o.get("name", "")):
                iid = investigator_id(o["name"], o.get("affiliation", ""))
                node(iid, "Investigator", o["name"], affiliation=o.get("affiliation", ""), source="ClinicalTrials.gov")
                edges.append(make_edge(iid, "investigator_of", t["nct"], "curated", 0.9, "ClinicalTrials.gov",
                                       f"{t['nct']}|{o.get('role', '')}", url, TODAY))
    print(f"  {len(trials)} studies fetched, {sum(1 for n in nodes.values() if n['node_type'] == 'Trial')} relevant")

    # --- grants
    print("NIH RePORTER ...")
    grants: dict[str, dict] = {}
    for phrase in all_phrases():
        for g in fetch_grants(phrase):
            core = g.get("core_project_num") or g["project_num"]
            if core not in grants or g["fiscal_year"] > grants[core]["fiscal_year"]:
                grants[core] = g
    for core, g in grants.items():
        title_matches = match_diseases(g.get("project_title") or "")
        abs_matches = [m for m in match_diseases(g.get("abstract_text") or "") if m[1] == "specific"]
        if title_matches:
            matches, specific_conf = title_matches, GRANT_TITLE_CONF
        elif abs_matches:   # abstract-only matches count only if a specific disease is named
            matches, specific_conf = abs_matches, GRANT_ABSTRACT_CONF
        else:
            continue
        url = f"https://reporter.nih.gov/project-details/{core}"
        org = (g.get("organization") or {}).get("org_name", "")
        node(core, "Grant", g.get("project_title") or core, fiscal_year=g["fiscal_year"],
             award_amount=g.get("award_amount"), organization=org, project_num=g["project_num"])
        for d, kind in matches:
            conf = specific_conf if kind == "specific" else BROAD_CONF
            rec = core + ("" if kind == "specific" else "|broad family match")
            edges.append(make_edge(d, "funded_by", core, "curated", conf, "NIH RePORTER", rec, url, TODAY))
        for pi in g.get("principal_investigators") or []:
            if pi.get("profile_id") and pi.get("full_name"):
                iid = f"NIHPI:{pi['profile_id']}"
                node(iid, "Investigator", pi["full_name"].title(), affiliation=org, source="NIH RePORTER")
                edges.append(make_edge(iid, "investigator_of", core, "curated", 0.95, "NIH RePORTER",
                                       f"{core}|PI profile {pi['profile_id']}", url, TODAY))
    print(f"  {len(grants)} grants fetched, {sum(1 for n in nodes.values() if n['node_type'] == 'Grant')} relevant")

    # --- papers
    print("PubMed ...")
    selected: dict[str, dict[str, set[str]]] = {}   # pmid -> {"diseases": set, "why": set}
    for d in ids:
        q = pubmed_query(d)
        recent = esearch(q, "pub_date", PUBMED_RECENT)
        pool = esearch(q, "relevance", 100)
        cites = citation_counts(pool)
        cited = sorted(pool, key=lambda p: -cites.get(p, 0))[:PUBMED_CITED]
        for p, why in [(p, "recent") for p in recent] + [(p, "cited") for p in cited]:
            s = selected.setdefault(p, {"diseases": set(), "why": set()})
            s["diseases"].add(d)
            s["why"].add(why)
    articles = fetch_articles(sorted(selected))
    CACHE.mkdir(parents=True, exist_ok=True)
    with open(CACHE / "abstracts.jsonl", "w") as fa, open(CACHE / "papers.jsonl", "w") as fp:
        for p, art in articles.items():
            dis = sorted(selected[p]["diseases"])
            fp.write(json.dumps({**art, "disease_ids": dis, "selected_as": sorted(selected[p]["why"]),
                                 "retrieved": TODAY}) + "\n")
            if art["abstract"]:
                fa.write(json.dumps({"pmid": p, "title": art["title"], "abstract": art["abstract"],
                                     "disease_ids": dis}) + "\n")
    n_abs = sum(1 for a in articles.values() if a["abstract"])
    print(f"  {len(articles)} papers, {n_abs} with abstracts -> data/cache/abstracts.jsonl")

    # --- save to the graph
    merge_layer(list(nodes.values()), edges, {"Trial", "Investigator", "Grant", "Asset"},
                {"studied_in_trial", "investigator_of", "funded_by", "has_asset"})
    summarise(diseases, edges, nodes, selected)


def summarise(diseases, edges, nodes, selected) -> None:
    e = pd.DataFrame(edges)
    print(f"\nAdded {len(nodes)} nodes and {len(edges)} edges. Per disease:")
    print(f"  {'Disease':<32}{'trials':>7}{'(broad)':>8}{'assets':>7}{'grants':>7}{'papers':>7}")
    for _, d in diseases.iterrows():
        m = d["mondo_id"]
        t = e[(e.subject == m) & (e.predicate == "studied_in_trial")]
        n_broad = int(t["source_record"].str.contains("broad").sum())
        print(f"  {d['name']:<32}{len(t):>7}{n_broad:>8}"
              f"{(e.subject == m).where(e.predicate == 'has_asset').sum():>7}"
              f"{(e.subject == m).where(e.predicate == 'funded_by').sum():>7}"
              f"{sum(1 for s in selected.values() if m in s['diseases']):>7}")


if __name__ == "__main__":
    main()
