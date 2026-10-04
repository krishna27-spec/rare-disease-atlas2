import { useEffect, useRef, useState } from "react";

// The knowledge graph as a constellation: an orbital layout drawn on canvas.
// Centre = the chosen disease. Ring 1 = its gene(s). Ring 2 = shared mechanisms. Ring 3 = similar diseases with
// their genes. Outer arcs = symptoms that papers state, and patient groups. Line style = evidence type.

const COLOR = { centre: "#8b5cf6", disease: "#a78bfa", gene: "#8ec5ff", pathway: "#c9b8ff", symptom: "#f5b8d8", patient_org: "#86e3c3" };
const SIZE = { centre: 30, disease: 19, gene: 12, pathway: 11, symptom: 10, patient_org: 11 };
const KIND = { centre: "Disease", disease: "Similar disease", gene: "Gene", pathway: "Mechanism", symptom: "Symptom (from a paper)", patient_org: "Patient group" };
const EDGE = { curated: "95,211,154", text_mined: "103,198,214", inferred: "242,184,75" };   // verified, literature, Atlas-derived
const SAY = { similar_to: "is similar to", gene_associated_with_disease: "causes", participates_in_pathway: "works in", has_phenotype: "has symptom", serves_disease: "serves" };

const rad = (deg) => (deg * Math.PI) / 180;
const spread = (n, from, to) => Array.from({ length: n }, (_, i) => (n === 1 ? (from + to) / 2 : from + ((to - from) * i) / (n - 1)));

function layout(data) {
  const pos = {}, by = (t) => data.nodes.filter((n) => n.type === t);
  const E = data.edges, centre = data.centre;
  pos[centre] = { r: 0, a: 0 };
  const diseases = by("disease");
  spread(diseases.length, 198, 342).forEach((a, i) => (pos[diseases[i].id] = { r: 300, a }));
  const geneOf = (d) => E.filter((e) => e.predicate === "gene_associated_with_disease" && e.target === d).map((e) => e.source);
  const mine = [...new Set(geneOf(centre))];
  spread(mine.length, 250, 290).forEach((a, i) => (pos[mine[i]] = { r: 96, a: mine.length === 1 ? 270 : a }));
  for (const d of diseases) {
    const gs = [...new Set(geneOf(d.id))].filter((g) => !pos[g]);
    gs.forEach((g, i) => (pos[g] = { r: 232 - i * 34, a: pos[d.id].a + (pos[d.id].a < 270 ? -9 : 9) + i * 4 }));
  }
  const paths = by("pathway");
  paths.forEach((p) => {
    const gs = E.filter((e) => e.target === p.id && pos[e.source]).map((e) => pos[e.source].a);
    p._a = gs.length ? gs.reduce((s, a) => s + a, 0) / gs.length : 270;
  });
  paths.sort((x, y) => x._a - y._a);
  spread(paths.length, 208, 332).forEach((a, i) => (pos[paths[i].id] = { r: i % 2 ? 196 : 150, a }));
  const sym = by("symptom"), org = by("patient_org");
  spread(sym.length, 118, 172).forEach((a, i) => (pos[sym[i].id] = { r: 236, a }));
  spread(org.length, 8, 66).forEach((a, i) => (pos[org[i].id] = { r: 236, a }));
  data.nodes.filter((n) => !pos[n.id]).forEach((n, i) => (pos[n.id] = { r: 150, a: 60 + i * 24 }));
  return pos;
}

function glyph(ctx, type, s) {
  ctx.lineWidth = Math.max(1.2, s * 0.11); ctx.strokeStyle = "rgba(10,7,20,0.78)"; ctx.fillStyle = "rgba(10,7,20,0.78)";
  ctx.lineCap = "round"; ctx.beginPath();
  if (type === "gene") {          // double helix
    for (const k of [1, -1]) { ctx.moveTo(-s * 0.45, k * s * 0.3); ctx.bezierCurveTo(-s * 0.1, k * s * 0.3, s * 0.1, -k * s * 0.3, s * 0.45, -k * s * 0.3); }
    ctx.stroke();
  } else if (type === "pathway") { // branching path
    ctx.moveTo(-s * 0.4, s * 0.2); ctx.lineTo(0, -s * 0.25); ctx.lineTo(s * 0.4, s * 0.2); ctx.stroke();
    for (const [x, y] of [[-0.4, 0.2], [0, -0.25], [0.4, 0.2]]) { ctx.beginPath(); ctx.arc(x * s, y * s, s * 0.13, 0, 6.3); ctx.fill(); }
  } else if (type === "symptom") { // pulse
    ctx.moveTo(-s * 0.5, 0); ctx.lineTo(-s * 0.18, 0); ctx.lineTo(-s * 0.05, -s * 0.36); ctx.lineTo(s * 0.12, s * 0.32); ctx.lineTo(s * 0.24, 0); ctx.lineTo(s * 0.5, 0); ctx.stroke();
  } else if (type === "patient_org") { // people
    for (const [x, y] of [[-0.3, 0.12], [0.3, 0.12], [0, -0.22]]) { ctx.beginPath(); ctx.arc(x * s, y * s, s * 0.17, 0, 6.3); ctx.fill(); }
  } else {                         // disease: a cell with a nucleus
    ctx.arc(0, 0, s * 0.42, 0, 6.3); ctx.stroke(); ctx.beginPath(); ctx.arc(s * 0.1, -s * 0.06, s * 0.15, 0, 6.3); ctx.fill();
  }
}

// `show` is the set of layers the reader has asked for so far: "mechanism", "related", "groups", "symptoms".
// The map starts as the disease and its gene and grows as the reader goes deeper (or presses "Expand connections").
export default function ConstellationGraph({ data, onNode, onEdge, show, onExpand }) {
  const vis = useRef(show);
  vis.current = show;
  const ref = useRef(null);
  const [tip, setTip] = useState(null);
  const cb = useRef({ onNode, onEdge });
  cb.current = { onNode, onEdge };

  useEffect(() => {
    if (!data) return;
    const c = ref.current, ctx = c.getContext("2d");
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const P = layout(data), byId = Object.fromEntries(data.nodes.map((n) => [n.id, n]));
    const edges = data.edges.filter((e) => P[e.source] && P[e.target]);
    let w = 0, h = 0, k = 1, raf, hover = null, zoom = 1, zt = 1, ox = 0, oy = 0, drag = null;
    const XY = {}, born = {};
    const own = new Set(data.edges.filter((e) => e.predicate === "gene_associated_with_disease" && e.target === data.centre).map((e) => e.source));
    const layer = (n) => (n.type === "centre" || own.has(n.id) ? "core" : n.type === "pathway" ? "mechanism" : n.type === "patient_org" ? "groups" : n.type === "symptom" ? "symptoms" : "related");
    const visible = (n) => layer(n) === "core" || !vis.current || vis.current.has(layer(n));

    const size = () => {
      const d = Math.min(window.devicePixelRatio || 1, 2), b = c.getBoundingClientRect();
      w = b.width; h = b.height; c.width = w * d; c.height = h * d; ctx.setTransform(d, 0, 0, d, 0, 0);
      k = Math.max(0.62, Math.min(w / 980, h / 700));
    };
    const place = (t) => {
      const cx = w / 2 + ox, cy = h * (h < 400 ? 0.62 : 0.54) + oy;
      data.nodes.forEach((n, i) => {
        const p = P[n.id];
        if (!visible(n)) delete born[n.id];
        else if (born[n.id] === undefined) born[n.id] = t + (n.type === "centre" ? 0 : 120 + p.r * 1.6 + (i % 7) * 60);   // each layer grows outward
        const u = born[n.id] === undefined ? 0 : still ? 1 : Math.min(1, Math.max(0, (t - born[n.id]) / 900)), e = 1 - Math.pow(1 - u, 4);
        const drift = still ? 0 : Math.sin(t / 2600 + i * 1.7) * 2.2;
        const r = p.r * k * zoom * e;
        XY[n.id] = { x: cx + Math.cos(rad(p.a)) * r + drift * 0.6, y: cy + Math.sin(rad(p.a)) * r + drift, o: e, a: p.a, r: p.r };
      });
      return { cx, cy };
    };
    const ctrl = (a, b, cx, cy) => {   // bend each line gently toward the centre so lines read as orbits, not spokes
      const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
      return { x: mx + (cx - mx) * 0.22, y: my + (cy - my) * 0.22 };
    };
    const at = (a, q, b, u) => ({ x: (1 - u) ** 2 * a.x + 2 * (1 - u) * u * q.x + u * u * b.x, y: (1 - u) ** 2 * a.y + 2 * (1 - u) * u * q.y + u * u * b.y });
    const related = (id) => new Set(edges.filter((e) => e.source === id || e.target === id).flatMap((e) => [e.source, e.target]));

    const draw = (t) => {
      zoom += (zt - zoom) * 0.14;
      const { cx, cy } = place(t);
      ctx.clearRect(0, 0, w, h);
      // orbits
      for (const r of [96, 173, 300]) {
        ctx.beginPath(); ctx.arc(cx, cy, r * k * zoom, 0, 6.2832);
        ctx.strokeStyle = "rgba(167,139,250,0.07)"; ctx.lineWidth = 1; ctx.setLineDash([2, 7]); ctx.stroke();
      }
      ctx.setLineDash([]);
      const focusNode = hover && hover.node, focusEdge = hover && hover.edge;
      const near = focusNode ? related(focusNode) : null;
      // edges
      for (const e of edges) {
        const a = XY[e.source], b = XY[e.target], q = ctrl(a, b, cx, cy);
        if (a.o < 0.02 || b.o < 0.02) continue;
        const lit = focusEdge === e.id || (focusNode && (e.source === focusNode || e.target === focusNode));
        const dim = (focusNode || focusEdge) && !lit;
        const quiet = e.predicate === "serves_disease" && e.target !== data.centre;   // groups of other diseases stay in the background
        const alpha = Math.min(a.o, b.o) * (dim ? 0.06 : lit ? 0.95 : quiet ? 0.07 : 0.2 + e.confidence * 0.32);
        const g = ctx.createLinearGradient(a.x, a.y, b.x, b.y), rgb = EDGE[e.evidence_type];
        g.addColorStop(0, `rgba(${rgb},${alpha})`); g.addColorStop(0.5, `rgba(${rgb},${alpha * 0.55})`); g.addColorStop(1, `rgba(${rgb},${alpha})`);
        ctx.strokeStyle = g; ctx.lineWidth = (0.7 + e.confidence * 1.5) * (lit ? 1.5 : 1);
        ctx.setLineDash(e.evidence_type === "inferred" ? [7, 6] : e.evidence_type === "text_mined" ? [1.5, 5] : []);
        ctx.lineCap = "round";
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.quadraticCurveTo(q.x, q.y, b.x, b.y); ctx.stroke();
        ctx.setLineDash([]);
        if (lit && !still) {            // a point of light travels the connection that is being read
          const u = ((t / 1700) % 1), p = at(a, q, b, u);
          const glow = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, 9);
          glow.addColorStop(0, `rgba(${rgb},0.95)`); glow.addColorStop(1, `rgba(${rgb},0)`);
          ctx.fillStyle = glow; ctx.beginPath(); ctx.arc(p.x, p.y, 9, 0, 6.2832); ctx.fill();
        }
      }
      // nodes
      for (const n of data.nodes) {
        const p = XY[n.id], col = COLOR[n.type] || "#a78bfa", is = focusNode === n.id;
        if (p.o < 0.02) continue;
        const dim = (near && !near.has(n.id) && !is) || (focusEdge && !edges.some((e) => e.id === focusEdge && (e.source === n.id || e.target === n.id)));
        const s = SIZE[n.type] * Math.max(0.72, k) * Math.sqrt(zoom) * (is ? 1.14 : 1);
        ctx.globalAlpha = p.o * (dim ? 0.2 : 1);
        const halo = ctx.createRadialGradient(p.x, p.y, s * 0.4, p.x, p.y, s * (n.type === "centre" ? 3.4 : 2.6));
        halo.addColorStop(0, col + (is || n.type === "centre" ? "66" : "30")); halo.addColorStop(1, col + "00");
        ctx.fillStyle = halo; ctx.beginPath(); ctx.arc(p.x, p.y, s * 3.4, 0, 6.2832); ctx.fill();
        const body = ctx.createRadialGradient(p.x - s * 0.35, p.y - s * 0.4, s * 0.1, p.x, p.y, s);
        body.addColorStop(0, "#ffffff"); body.addColorStop(0.28, col); body.addColorStop(1, col + "b0");
        ctx.fillStyle = body; ctx.beginPath(); ctx.arc(p.x, p.y, s, 0, 6.2832); ctx.fill();
        ctx.save(); ctx.translate(p.x, p.y); glyph(ctx, n.type, s); ctx.restore();
        // label, pushed outward from the centre so it never sits on a line
        const big = n.type === "centre" || n.type === "disease";
        if (big || is || own.has(n.id) || (near && near.has(n.id)) || k * zoom > 0.9) {
          ctx.font = `${big ? 600 : 500} ${n.type === "centre" ? 16 : big ? 14 : 12}px "Inter Variable", Inter, sans-serif`;
          ctx.fillStyle = big || is ? "#f5f3fa" : "rgba(184,179,199,0.92)";
          const full = n.type === "gene" ? n.id : n.label, max = n.type === "pathway" ? 24 : 30;
          const label = full.length > max && !is ? full.slice(0, max - 2) + "…" : full;
          if (n.type === "centre") { ctx.textAlign = "center"; ctx.textBaseline = "top"; ctx.fillText(label, p.x, p.y + s + 12); }
          else {
            const dx = Math.cos(rad(p.a)), dy = Math.sin(rad(p.a));
            ctx.textAlign = Math.abs(dx) < 0.25 ? "center" : dx > 0 ? "left" : "right";
            ctx.textBaseline = dy < -0.5 ? "bottom" : dy > 0.5 ? "top" : "middle";
            ctx.fillText(label, p.x + dx * (s + 9), p.y + dy * (s + 9));
          }
        }
        ctx.globalAlpha = 1;
      }
      raf = requestAnimationFrame(draw);
    };

    const pick = (ev) => {
      const b = c.getBoundingClientRect(), x = ev.clientX - b.left, y = ev.clientY - b.top;
      for (const n of [...data.nodes].reverse()) {
        const p = XY[n.id]; if (p && p.o > 0.5 && Math.hypot(p.x - x, p.y - y) < SIZE[n.type] * Math.max(0.72, k) + 7) return { node: n.id, x: p.x, y: p.y };
      }
      const cx = w / 2 + ox, cy = h * (h < 400 ? 0.62 : 0.54) + oy;
      let best = null;
      for (const e of edges) {
        const a = XY[e.source], bb = XY[e.target], q = ctrl(a, bb, cx, cy);
        if (a.o < 0.5 || bb.o < 0.5) continue;
        for (let u = 0.12; u < 0.9; u += 0.06) {
          const p = at(a, q, bb, u), d = Math.hypot(p.x - x, p.y - y);
          if (d < 9 && (!best || d < best.d)) best = { edge: e.id, x: p.x, y: p.y, d };
        }
      }
      return best;
    };
    const move = (ev) => {
      if (drag) { ox = drag.ox + ev.clientX - drag.x; oy = drag.oy + ev.clientY - drag.y; drag.moved = true; return; }
      hover = pick(ev);
      c.style.cursor = hover ? "pointer" : "grab";
      if (!hover) return setTip(null);
      if (hover.node) { const n = byId[hover.node]; setTip({ x: hover.x, y: hover.y - SIZE[n.type], kind: KIND[n.type], text: n.type === "gene" ? `${n.id} · ${n.label}` : n.label }); }
      else { const e = edges.find((z) => z.id === hover.edge); const nm = (id) => (byId[id].type === "gene" ? id : byId[id].label); setTip({ x: hover.x, y: hover.y, kind: "Why is this connected?", text: `${nm(e.source)} ${SAY[e.predicate] || e.predicate} ${nm(e.target)}` }); }
    };
    const down = (ev) => { drag = { x: ev.clientX, y: ev.clientY, ox, oy, moved: false }; };
    const up = (ev) => {
      const was = drag; drag = null;
      if (!was || was.moved) return;
      const hit = pick(ev); if (!hit) return;
      if (hit.node) cb.current.onNode && cb.current.onNode(byId[hit.node], edges.filter((e) => e.source === hit.node || e.target === hit.node).map((e) => e.id));
      else cb.current.onEdge && cb.current.onEdge(edges.find((e) => e.id === hit.edge));
    };
    const wheel = (ev) => { if (!ev.ctrlKey && !ev.metaKey) return; ev.preventDefault(); zt = Math.min(2.2, Math.max(0.7, zt * (ev.deltaY < 0 ? 1.1 : 0.9))); };
    const leave = () => { hover = null; drag = null; setTip(null); };

    size(); raf = requestAnimationFrame(draw);
    const ro = new ResizeObserver(size); ro.observe(c);
    c.addEventListener("mousemove", move); c.addEventListener("mousedown", down); window.addEventListener("mouseup", up);
    c.addEventListener("wheel", wheel, { passive: false }); c.addEventListener("mouseleave", leave);
    return () => {
      cancelAnimationFrame(raf); ro.disconnect();
      c.removeEventListener("mousemove", move); c.removeEventListener("mousedown", down); window.removeEventListener("mouseup", up);
      c.removeEventListener("wheel", wheel); c.removeEventListener("mouseleave", leave);
    };
  }, [data]);

  return (
    <div className={"graphshell" + (show && show.size === 0 ? " compact" : "")}>
      <canvas ref={ref} role="img" aria-label="Knowledge graph around the selected disease" />
      {tip && <div className="tip" style={{ left: tip.x, top: tip.y }}><span>{tip.kind}</span><br /><b>{tip.text}</b></div>}
      <div className="legend">
        <span><i />Verified source</span>
        <span><i className="mined" />Research literature</span>
        <span><i className="inferred" />Atlas-derived</span>
      </div>
      {onExpand
        ? <button className="expand" onClick={onExpand}>Expand connections</button>
        : <div className="hint">Click any point or line to see why it is there</div>}
    </div>
  );
}
