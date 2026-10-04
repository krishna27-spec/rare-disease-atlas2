"""Read patient organisations' own websites and keep only what the pages themselves say (no LLM).

Run:  uv run python -m src.etl.org_scrape        (writes data/manual/org_scrape.jsonl, read by src.etl.orgs)
Reads data/manual/org_sources.csv: candidate organisations (name, url). A candidate proves nothing by itself:
an organisation gets a "serves this disease" fact only if a fetched page of its own site contains a sentence that
names the disease. That sentence is stored as the quote, with the page URL and the date.

Fetching: through Bright Data Web Unlocker when BRIGHTDATA_API_KEY and BRIGHTDATA_ZONE are in .env (gets past
sites that block scripts), else a plain polite request. With BRIGHTDATA_SERP_ZONE set, a web search per disease
also proposes organisations that are not in the CSV yet (printed for a person to check and add; never auto-added).
Every page is cached in data/cache/org_pages/, so re-runs fetch nothing twice and spend no credits twice.
"""
import json
import os
import re
from pathlib import Path
from urllib.parse import quote_plus, urljoin, urlparse

import lxml.html
import pandas as pd
import requests

from src.etl.research import HEADERS, TODAY, cached
from src.etl.terms import BROAD, SPECIFIC, _has, match_diseases, normalise

SOURCES, OUT = Path("data/manual/org_sources.csv"), Path("data/manual/org_scrape.jsonl")
BRIGHT = "https://api.brightdata.com/request"
MIN_SENTENCES, MIN_PAGES = 4, 2   # how often a site must name a disease before we say it serves it
MAX_PAGES = 8            # per organisation: the home page plus the most relevant internal pages
LINK_WORDS = ("about", "mission", "who-we-are", "what-is", "what-we-do", "registry", "research", "natural-history",
              "disease", "condition", "learn", "families", "understanding", "science", "our-work")
ASSET = re.compile(r"\b(patient registry|contact registry|registry|registries|natural history stud\w+|biobank|"
                   r"biorepository|data sharing)\b", re.I)
PEOPLE_PAGE = re.compile(r"board|staff|team|advisor|leadership|people", re.I)   # bios mention registries in passing
SKIP_HOSTS = ("wikipedia.", "facebook.", "twitter.", "x.com", "linkedin.", "youtube.", "instagram.", "nih.gov",
              "clinicaltrials.gov", "rarediseases.org", "orpha.net", "globalgenes.org", "medlineplus.", "mayoclinic.",
              "clevelandclinic.", "healthline.", "webmd.", "sciencedirect.", "nature.com", "amazon.", "reddit.")


def host(url: str) -> str:
    return re.sub(r"^www\.", "", urlparse(url).netloc.lower())


def fetch(url: str) -> str:
    """HTML of one page ('' if it cannot be fetched). Cached, so each URL costs at most one request, ever."""
    key, zone = os.getenv("BRIGHTDATA_API_KEY"), os.getenv("BRIGHTDATA_ZONE")

    def get():
        if key and zone:
            return requests.post(BRIGHT, json={"zone": zone, "url": url, "format": "raw"}, timeout=90,
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        return requests.get(url, timeout=30, headers={**HEADERS, "Accept": "text/html"})
    try:
        return cached("org_pages", url, get).get("text", "")
    except Exception as e:   # a dead or blocking site must not stop the run
        print(f"    could not fetch {url}: {type(e).__name__} {str(e)[:80]}")
        return ""


def page_text(html: str) -> tuple[str, list[str], list[tuple[str, str]]]:
    """(title, sentences, links) of a page. Scripts, styles and navigation chrome are removed first."""
    if not html.strip():
        return "", [], []
    try:
        doc = lxml.html.fromstring(html)
    except Exception:
        return "", [], []
    links = [(a.get("href") or "", a.text_content().strip()) for a in doc.iter("a")]
    title = (doc.findtext(".//title") or "").strip()
    for el in doc.xpath("//script|//style|//noscript|//svg|//form"):
        el.drop_tree()
    for br in doc.iter("br", "p", "div", "li", "h1", "h2", "h3", "h4", "td"):
        br.tail = (br.tail or "") + "\n"
    text = doc.text_content()
    meta = doc.xpath("//meta[@name='description']/@content")
    parts = re.split(r"(?<=[.!?])\s+|\n+", (meta[0] + "\n" if meta else "") + text)
    sentences = [re.sub(r"\s+", " ", p).strip() for p in parts]
    return title, [s for s in sentences if 25 <= len(s) <= 400], links


def pages_of(url: str) -> list[tuple[str, str, list[str]]]:
    """(page url, title, sentences) for the home page and the most relevant pages it links to on the same site."""
    home = fetch(url)
    title, sentences, links = page_text(home)
    out = [(url, title, sentences)] if sentences else []
    seen, picked = {url.rstrip("/")}, []
    for href, label in links:
        full = urljoin(url, href).split("#")[0]
        probe = (urlparse(full).path + " " + label).lower().replace(" ", "-")
        if host(full) != host(url) or full.rstrip("/") in seen or not any(w in probe for w in LINK_WORDS):
            continue
        if re.search(r"\.(pdf|jpg|png|zip|docx?)$", full, re.I):
            continue
        seen.add(full.rstrip("/"))
        picked.append((sum(w in probe for w in LINK_WORDS), full))
    for _, full in sorted(picked, key=lambda x: -x[0])[:MAX_PAGES - 1]:
        t, s, _ = page_text(fetch(full))
        if s:
            out.append((full, t, s))
    return out


def read_org(name: str, url: str) -> dict:
    """What the organisation's own pages say: which of our diseases they name, and any registry or study."""
    pages = pages_of(url)
    serves: dict[str, dict] = {}       # mondo id -> best sentence, and how often the site names the disease
    assets: list[dict] = []
    for i, (page_url, title, sentences) in enumerate(pages):
        for s in dict.fromkeys(sentences):          # the same menu text repeats on every page: count it once per page
            for d, kind in match_diseases(s):
                v = serves.setdefault(d, {"mondo_id": d, "match": kind, "quote": s, "url": page_url,
                                          "n_sentences": 0, "pages": set(), "_rank": (False, 0)})
                v["n_sentences"] += 1
                v["pages"].add(page_url)
                # a sentence naming the specific disease beats a family-level one; then prefer the shorter quote
                rank = (kind == "specific", -len(s))
                if rank > v["_rank"]:
                    v.update(match=kind, quote=s, url=page_url, _rank=rank)
            m = ASSET.search(s)
            if m and not PEOPLE_PAGE.search(page_url) and s not in [a["quote"] for a in assets]:
                assets.append({"quote": s, "url": page_url, "kind": m.group(1).lower()})
    # keep the three most telling mentions: a natural history study or a patient registry beats a vague one
    order = ["natural history", "patient registry", "contact registry", "registry", "registries", "biobank",
             "biorepository", "data sharing"]
    assets = sorted(assets, key=lambda a: (next(i for i, w in enumerate(order) if a["kind"].startswith(w)),
                                           len(a["quote"]) < 60, len(a["quote"])))[:3]   # headings last
    in_name = {d for d, _ in match_diseases(name + " " + (pages[0][1] if pages else ""))}
    for d, v in serves.items():
        v.pop("_rank")
        v["n_pages"] = len(v.pop("pages"))
        v["in_org_name"] = d in in_name
        # "serves" needs more than a passing mention: the disease is in the organisation's name or page title,
        # or its site names it repeatedly on several pages. Anything less is kept only as "mentions".
        v["strength"] = ("named in the organisation's name or home page title" if v["in_org_name"] else
                         f"named {v['n_sentences']} times on {v['n_pages']} of its pages"
                         if v["n_sentences"] >= MIN_SENTENCES and v["n_pages"] >= MIN_PAGES else "passing mention")
    return {"name": name, "url": url, "org_host": host(url), "pages_read": [p[0] for p in pages],
            "page_title": pages[0][1] if pages else "", "serves": sorted(serves.values(), key=lambda x: x["mondo_id"]),
            "registry_or_study": assets, "retrieved": TODAY,
            "fetched_via": "Bright Data Web Unlocker" if os.getenv("BRIGHTDATA_API_KEY") and os.getenv("BRIGHTDATA_ZONE")
            else "direct request"}


def discover(known_hosts: set[str], names: dict[str, str]) -> None:
    """With a Bright Data SERP zone: search the web per disease and print organisation sites not in the CSV yet."""
    key, zone = os.getenv("BRIGHTDATA_API_KEY"), os.getenv("BRIGHTDATA_SERP_ZONE")
    if not (key and zone):
        return
    print("\nWeb search for organisations not in org_sources.csv (check each, then add a row and re-run):")
    for d, terms in SPECIFIC.items():
        q = f'"{terms[0]}" patient organization foundation registry'
        url = f"https://www.google.com/search?q={quote_plus(q)}&brd_json=1&num=20"
        try:
            data = cached("org_serp", url, lambda: requests.post(
                BRIGHT, json={"zone": zone, "url": url, "format": "raw"}, timeout=90,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}))
        except Exception as e:
            print(f"  {names.get(d, d)}: search failed ({type(e).__name__})")
            continue
        found = []
        for r in data.get("organic", []):
            h = host(r.get("link", ""))
            if h and h not in known_hosts and not any(x in h for x in SKIP_HOSTS) and h not in [f[0] for f in found]:
                found.append((h, r.get("title", "")[:70]))
        print(f"  {names.get(d, d)}: " + ("; ".join(f"{h} ({t})" for h, t in found[:5]) or "nothing new"))


def main() -> None:
    src = pd.read_csv(SOURCES, dtype=str, keep_default_na=False)
    names = dict(pd.read_csv("data/manual/diseases.csv")[["mondo_id", "name"]].values)
    rows = []
    for r in src.itertuples():
        print(f"  {r.name} ...")
        res = read_org(r.name, r.url)
        rows.append(res)
        got = ", ".join(f"{names.get(s['mondo_id'], s['mondo_id'])}{'' if s['match'] == 'specific' else ' (family)'}"
                        f" x{s['n_sentences']}" for s in res["serves"] if s["strength"] != "passing mention") \
            or "no disease of ours named more than in passing"
        got += " | passing: " + (", ".join(names.get(s["mondo_id"], s["mondo_id"]) for s in res["serves"]
                                           if s["strength"] == "passing mention") or "none")
        print(f"    {len(res['pages_read'])} pages read; {got}; {len(res['registry_or_study'])} registry/study mentions")
    OUT.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows))
    covered = {s["mondo_id"] for x in rows for s in x["serves"] if s["strength"] != "passing mention"}
    print(f"\n{len(rows)} organisations checked, {sum(1 for x in rows if x['serves'])} name at least one of our "
          f"diseases; {len(covered)} of {len(names)} diseases are named by some organisation -> {OUT}")
    print("Not named by any organisation: " + (", ".join(names[d] for d in names if d not in covered) or "none"))
    discover({host(u) for u in src.url}, names)


if __name__ == "__main__":
    main()
