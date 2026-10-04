"""The interactive evidence graph for the 'Who is like us' tab (pyvis / vis-network, one self-contained HTML page).

Centre = the chosen disease; around it its closest diseases, their genes, the specific (non-generic) shared
pathways, and symptoms that a paper stated. Edge colour = evidence type (blue curated, orange text-mined, grey
dashed inferred). Clicking an edge shows its source, date, confidence and, for text-mined edges, the exact quote:
all edge data is embedded in the page, so no server round trip is needed."""
import json
import textwrap

from pyvis.network import Network

from src.webapp.data import COLOURS, NEIGHBOUR_MIN

MAX_PHENO = 3        # text-mined symptoms drawn per disease (the rest are in the evidence boxes)
MAX_PATHWAYS = 4
NODE_STYLE = {   # kind -> (colour, shape, size)
    "centre": ("#2ca02c", "dot", 34), "disease": ("#9aa5b1", "dot", 24), "gene": ("#c9dcf0", "box", 16),
    "pathway": ("#f3e2b8", "box", 16), "symptom": ("#e3d4f0", "diamond", 16)}


def wrap(text: str, width: int = 16) -> str:
    return "\n".join(textwrap.wrap(text, width, break_long_words=False)) or text


def build_html(G, d: str) -> tuple[str, dict]:
    """Returns (html, counts) where counts says how many edges of each evidence type are drawn."""
    net = Network(height="560px", width="100%", bgcolor="#ffffff", font_color="#222222", cdn_resources="in_line")
    net.set_options(json.dumps({
        "physics": {"solver": "barnesHut", "barnesHut": {"gravitationalConstant": -5000, "springLength": 120,
                    "centralGravity": 0.6, "springConstant": 0.05, "avoidOverlap": 1, "damping": 0.5},
                    "stabilization": {"iterations": 400}},
        "nodes": {"font": {"size": 22, "face": "sans-serif"}, "borderWidth": 1, "scaling": {"label": {"enabled": False}}},
        "edges": {"width": 2.5, "smooth": {"type": "dynamic"}, "font": {"size": 12, "align": "middle"}},
        "interaction": {"hover": True, "tooltipDelay": 150, "navigationButtons": False}}))
    drawn_nodes: set[str] = set()
    edge_data: dict[str, dict] = {}
    counts = {"curated": 0, "text_mined": 0, "inferred": 0}

    def node(nid: str, label: str, kind: str, title: str = ""):
        if nid in drawn_nodes:
            return
        colour, shape, size = NODE_STYLE[kind]
        net.add_node(nid, label=wrap(label), title=title or label, color=colour, shape=shape, size=size,
                     font={"size": 26 if kind == "centre" else 20, "bold": kind == "centre"})
        drawn_nodes.add(nid)

    def edge(eid: str, a: str, b: str, label: str = "", curve: float = 0.0):
        e = G.edge(eid)
        if not e or eid in edge_data:
            return
        t = e["evidence_type"]
        edge_data[eid] = {k: (e[k] if e[k] == e[k] else "") for k in
                          ("evidence_type", "predicate", "source", "source_record", "source_url", "retrieved",
                           "confidence", "evidence_text", "method", "reviewer_verdict")}
        edge_data[eid].update(subject=G.label(e["subject"]), object=G.label(e["object"]))
        kw = {"smooth": {"type": "curvedCW", "roundness": curve}} if curve else {}
        net.add_edge(a, b, id=eid, color=COLOURS[t], dashes=(t == "inferred"), label=label,
                     title=f"{t.replace('_', '-')}: click for the source", **kw)
        counts[t] += 1

    node(d, G.label(d), "centre", f"{G.label(d)} ({d})")
    nb = G.neighbours_of(d)
    nb = nb[nb.score >= NEIGHBOUR_MIN].head(4)
    members = [(d, "centre")] + [(r.neighbour_id, "disease") for r in nb.itertuples()]
    for r in nb.itertuples():
        node(r.neighbour_id, r.neighbour, "disease", f"{r.neighbour} ({r.neighbour_id})")
        edge(r.similar_edge_id, d, r.neighbour_id, label=f"{r.score:.2f}")

    ed = G.edges
    for dis, _ in members:
        # genes: curated link and, if a paper also states it, the orange text-mined link (curved so both show)
        ge = ed[(ed.object == dis) & (ed.predicate == "gene_associated_with_disease")]
        for i, r in enumerate(ge.itertuples()):
            node(r.subject, r.subject, "gene", f"{r.subject}: {G.label(r.subject)}")
            edge(r.edge_id, dis, r.subject, curve=0.0 if r.evidence_type == "curated" else 0.35)
        # symptoms stated in papers (text-mined only; the curated HPO list has hundreds)
        pe = ed[(ed.subject == dis) & (ed.predicate == "has_phenotype") & (ed.evidence_type == "text_mined")]
        for r in pe.sort_values("confidence", ascending=False).drop_duplicates("object").head(MAX_PHENO).itertuples():
            node(r.object, G.label(r.object), "symptom", f"{G.label(r.object)} ({r.object})")
            edge(r.edge_id, dis, r.object)

    # specific shared pathways, drawn through the genes that carry them (edges are gene -> pathway, curated)
    seen_paths: set[str] = set()
    for r in nb.itertuples():
        for p in json.loads(r.shared_pathways):
            if p["id"] in seen_paths or len(seen_paths) >= MAX_PATHWAYS:
                continue
            seen_paths.add(p["id"])
            node(p["id"], p["name"], "pathway", f"{p['name']} ({p['id']})")
            for eid in p["edge_ids"]:
                e = G.edge(eid)
                if e and e["subject"] in drawn_nodes:
                    edge(eid, e["subject"], p["id"])

    html = net.generate_html()
    legend = ("<div style='font:14px sans-serif;margin:6px 0'>"
              f"<span style='color:{COLOURS['curated']}'>&#9632;</span> curated (database) &nbsp; "
              f"<span style='color:{COLOURS['text_mined']}'>&#9632;</span> text-mined (paper quote) &nbsp; "
              f"<span style='color:{COLOURS['inferred']}'>&#9632;</span> inferred (similarity, dashed) &nbsp; "
              "<i>Click a line to see its source.</i></div>"
              "<div id='ev' style='font:14px sans-serif;border:1px solid #ddd;border-radius:6px;padding:10px;"
              "margin-top:8px;min-height:90px'>Click an edge to see its evidence.</div>")
    script = f"""<script>
const EV = {json.dumps(edge_data)};
const fit = () => network.fit({{animation: false}});
network.once('stabilizationIterationsDone', fit);
network.on('stabilized', fit);
setTimeout(fit, 1500); setTimeout(fit, 4000);
const esc = s => String(s).replace(/[&<>]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;'}}[c]));
network.on('click', p => {{
  const box = document.getElementById('ev');
  if (p.edges.length && !p.nodes.length) {{
    const e = EV[p.edges[0]]; if (!e) return;
    box.innerHTML = '<b>' + esc(e.subject) + '</b> &rarr; ' + esc(e.predicate) + ' &rarr; <b>' + esc(e.object) + '</b>'
      + '<br>Evidence type: <b>' + esc(e.evidence_type.replace('_','-')) + '</b> &middot; confidence ' + Number(e.confidence).toFixed(2)
      + '<br>Source: ' + esc(e.source) + ' &middot; record ' + esc(e.source_record) + ' &middot; retrieved ' + esc(e.retrieved)
      + (e.evidence_text ? '<br><blockquote style="margin:6px 0;padding-left:10px;border-left:3px solid #ff7f0e">&ldquo;' + esc(e.evidence_text) + '&rdquo;</blockquote>' : '')
      + (e.method ? '<br>How computed: ' + esc(e.method) : '')
      + (e.source_url ? '<br><a href="' + esc(e.source_url) + '" target="_blank">Open source</a>' : '')
      + '<br><span style="color:#888">edge ' + esc(p.edges[0]) + ' &middot; reviewer: ' + esc(e.reviewer_verdict) + '</span>';
  }} else if (p.nodes.length) {{
    box.innerHTML = 'Node: <b>' + esc(p.nodes[0]) + '</b>. Click one of its lines to see the evidence.';
  }}
}});
</script>"""
    html = html.replace("</body>", legend + script + "</body>")
    return html, counts
