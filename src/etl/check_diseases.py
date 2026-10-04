"""Check every ID in data/manual/diseases.csv exists in MONDO; show the official name next to ours."""
import csv

import obonet

graph = obonet.read_obo("data/raw/mondo.obo")
rows = list(csv.DictReader(open("data/manual/diseases.csv")))
bad = 0
print(f"{'MONDO ID':<14}{'Our name':<32}{'Official MONDO name':<46}{'Genes':<11}Group")
for r in rows:
    node = graph.nodes.get(r["mondo_id"])
    if node is None or node.get("is_obsolete"):
        official, bad = "!! NOT FOUND / OBSOLETE", bad + 1
    else:
        official = node["name"]
    print(f"{r['mondo_id']:<14}{r['name']:<32}{official:<46}{r['genes']:<11}{r['group']}")
print(f"\n{len(rows)} diseases, {bad} problems")
