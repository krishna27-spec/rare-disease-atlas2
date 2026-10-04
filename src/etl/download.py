"""Download the biology data files once and cache them in data/raw/."""
import datetime
import json
import sys
from pathlib import Path

import requests

RAW = Path("data/raw")

# name on disk -> URL
SOURCES = {
    "mondo.obo": "https://purl.obolibrary.org/obo/mondo.obo",
    "phenotype.hpoa": "https://github.com/obophenotype/human-phenotype-ontology/releases/latest/download/phenotype.hpoa",
    "hp.obo": "https://purl.obolibrary.org/obo/hp.obo",
    "en_product6.xml": "https://www.orphadata.com/data/xml/en_product6.xml",
    "hgnc_complete_set.txt": "https://storage.googleapis.com/public-download-files/hgnc/tsv/tsv/hgnc_complete_set.txt",
    "NCBI2Reactome_All_Levels.txt": "https://reactome.org/download/current/NCBI2Reactome_All_Levels.txt",
    "ReactomePathways.txt": "https://reactome.org/download/current/ReactomePathways.txt",
    "ReactomePathwaysRelation.txt": "https://reactome.org/download/current/ReactomePathwaysRelation.txt",
    "gene_specific_summary.txt": "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/gene_specific_summary.txt",
}


def download_all() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    meta_path = RAW / "download_dates.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    for name, url in SOURCES.items():
        path = RAW / name
        if path.exists() and path.stat().st_size > 0:
            print(f"cached   {name}")
            continue
        try:
            r = requests.get(url, timeout=120, headers={"User-Agent": "rare-disease-atlas"})
            r.raise_for_status()
        except requests.RequestException as e:
            print(f"FAILED   {name}: {e}  ({url})", file=sys.stderr)
            continue
        path.write_bytes(r.content)
        meta[name] = {"url": url, "retrieved": datetime.date.today().isoformat()}
        print(f"download {name} ({len(r.content) / 1e6:.1f} MB)")
    meta_path.write_text(json.dumps(meta, indent=2))


if __name__ == "__main__":
    download_all()
