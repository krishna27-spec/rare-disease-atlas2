// The landing animation: a rotating DNA helix, one highlighted variant, and the signal growing outward into a
// knowledge graph. Pure canvas, no assets. About 6.5 s to the final state, then it idles until the user enters.
// Written for the Streamlit app (src/webapp/intro.py) and ported here unchanged apart from sizing and clean-up.
// The labels are entity types, not data: the intro makes no claim about any disease.
export function runIntro(cv) {

const C = { bg: '#08070D', purple: '#8B5CF6', deep: '#6D3BFF', lav: '#A78BFA', text: '#F5F3FA', text2: '#B8B3C7' };
const ctx = cv.getContext('2d');
let W = 0, H = 0, DPR = 1;
function resize() { DPR = Math.min(window.devicePixelRatio || 1, 2); W = cv.clientWidth; H = cv.clientHeight;
  cv.width = W * DPR; cv.height = H * DPR; ctx.setTransform(DPR, 0, 0, DPR, 0, 0); layout(); }
const ease = x => x <= 0 ? 0 : x >= 1 ? 1 : 1 - Math.pow(1 - x, 3);
const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
const prog = (t, a, b) => clamp((t - a) / (b - a), 0, 1);
const rgba = (hex, a) => { const n = parseInt(hex.slice(1), 16); return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${a})`; };

// dust
const dust = Array.from({ length: 110 }, () => ({ x: Math.random(), y: Math.random(), r: Math.random() * 1.4 + .3,
  v: Math.random() * .006 + .002, a: Math.random() * .35 + .08 }));

// graph: 8 entity types around the variant, each with 2-3 children, plus a few cross links
const TYPES = ['Gene', 'Pathway', 'Mechanism', 'Symptoms', 'Related diseases', 'Studies', 'Patient groups', 'Researchers'];
let G = { origin: { x: 0, y: 0 }, t1: [], t2: [], cross: [] };
function layout() {
  const ox = W * .5, oy = H * .34;
  const rx = Math.min(W * .34, 520), ry = Math.min(H * .2, 210);
  G.origin = { x: ox, y: oy };
  G.t1 = TYPES.map((name, i) => { const a = -Math.PI / 2 + (i + .5) * 2 * Math.PI / TYPES.length;
    return { name, a, x: ox + Math.cos(a) * rx, y: oy + Math.sin(a) * ry, delay: 2.75 + i * .17, bend: (i % 2 ? 1 : -1) * .18 }; });
  G.t2 = []; let seed = 7; const rnd = () => (seed = (seed * 9301 + 49297) % 233280) / 233280;
  G.t1.forEach((p, i) => { const n = 2 + (i % 2); for (let k = 0; k < n; k++) {
    const a = p.a + (k - (n - 1) / 2) * .32 + (rnd() - .5) * .1, f = 1.45 + rnd() * .3;
    G.t2.push({ parent: i, x: ox + Math.cos(a) * rx * f, y: oy + Math.sin(a) * ry * f, delay: p.delay + .45 + k * .12, r: 2.2 + rnd() * 1.6 }); } });
  G.cross = [];
  for (let i = 0; i < G.t2.length; i++) { const j = (i + 3) % G.t2.length; if (G.t2[i].parent !== G.t2[j].parent && i % 2 === 0)
    G.cross.push({ a: i, b: j, delay: 5.1 + (i % 5) * .1 }); }
  for (let i = 0; i < G.t1.length; i++) G.cross.push({ t1: true, a: i, b: (i + 1) % G.t1.length, delay: 5.0 + i * .06 });
}

// helix (drawn in a rotated frame through the origin)
function helix(t, alpha) {
  const tilt = -.2, len = Math.max(H, W) * 1.25, R = Math.min(70, W * .09), k = .0115, spin = t * .9;
  ctx.save(); ctx.translate(G.origin.x, G.origin.y); ctx.rotate(tilt);
  const step = 15, back = [];
  for (let y = -len / 2; y <= len / 2; y += step) {
    const ph = y * k + spin, sa = Math.sin(ph), ca = Math.cos(ph);
    const fade = 1 - Math.pow(Math.abs(y) / (len / 2), 2);
    const rung = { y, xa: R * sa, xb: -R * sa, za: ca, zb: -ca, fade, variant: Math.abs(y) < step / 2 };
    back.push(rung);
  }
  // rungs
  for (const r of back) { const a = alpha * r.fade * .45 * (.55 + .45 * Math.abs(r.za));
    ctx.strokeStyle = r.variant && t > 1.4 ? rgba(C.text, alpha * clamp((t - 1.4) * 1.5, 0, 1)) : rgba(C.lav, a);
    ctx.lineWidth = r.variant && t > 1.4 ? 3 : 2.2;
    ctx.beginPath(); ctx.moveTo(r.xa, r.y); ctx.lineTo(r.xb, r.y); ctx.stroke(); }
  // strands: points with depth shading
  for (const s of [0, 1]) { for (let y = -len / 2; y <= len / 2; y += 3) {
    const ph = y * k + spin + s * Math.PI, x = R * Math.sin(ph), z = Math.cos(ph);
    const fade = 1 - Math.pow(Math.abs(y) / (len / 2), 2), a = alpha * fade * (.25 + .6 * (z + 1) / 2);
    ctx.fillStyle = rgba(z > 0 ? C.lav : C.deep, a); ctx.beginPath(); ctx.arc(x, y, 2.6 + 1.6 * (z + 1) / 2, 0, 7); ctx.fill(); } }
  ctx.restore();
}

function curve(a, b, bend, p) {   // partial quadratic curve from a to b
  const mx = (a.x + b.x) / 2 - (b.y - a.y) * bend, my = (a.y + b.y) / 2 + (b.x - a.x) * bend;
  ctx.beginPath(); ctx.moveTo(a.x, a.y);
  const N = 24, n = Math.max(1, Math.round(N * p));
  for (let i = 1; i <= n; i++) { const u = i / N, v = 1 - u;
    ctx.lineTo(v * v * a.x + 2 * v * u * mx + u * u * b.x, v * v * a.y + 2 * v * u * my + u * u * b.y); }
  ctx.stroke();
  return (u) => { const v = 1 - u; return { x: v * v * a.x + 2 * v * u * mx + u * u * b.x, y: v * v * a.y + 2 * v * u * my + u * u * b.y }; };
}

let pulses = [], lastPulse = 0;
function frame(t) {
  ctx.fillStyle = C.bg; ctx.fillRect(0, 0, W, H);
  const glow = ctx.createRadialGradient(G.origin.x, G.origin.y, 0, G.origin.x, G.origin.y, Math.max(W, H) * .6);
  glow.addColorStop(0, rgba(C.deep, .12 + .06 * prog(t, 2.5, 5))); glow.addColorStop(1, rgba(C.bg, 0));
  ctx.fillStyle = glow; ctx.fillRect(0, 0, W, H);
  for (const d of dust) { const y = ((d.y - t * d.v) % 1 + 1) % 1;
    ctx.fillStyle = rgba(C.lav, d.a * prog(t, 0, 1.2)); ctx.beginPath(); ctx.arc(d.x * W, y * H, d.r, 0, 7); ctx.fill(); }

  // helix fades in, then recedes as the graph takes over
  helix(t, ease(prog(t, 0, 1.3)) * (1 - .62 * ease(prog(t, 4.6, 6.4))));

  // the variant: a ring that opens around one base pair
  const o = G.origin, rv = ease(prog(t, 1.5, 2.4));
  if (rv > 0) { const pulse = t > 2.4 ? Math.sin((t - 2.4) * 2.4) * .08 : 0;
    ctx.save(); ctx.shadowColor = C.purple; ctx.shadowBlur = 22;
    ctx.strokeStyle = rgba(C.lav, .9 * rv); ctx.lineWidth = 2;
    ctx.beginPath(); ctx.arc(o.x, o.y, 30 * rv * (1 + pulse), 0, 7); ctx.stroke(); ctx.restore();
    ctx.fillStyle = rgba(C.text2, .85 * prog(t, 2.0, 2.6)); ctx.font = '500 12px Inter, system-ui, sans-serif';
    ctx.textAlign = 'left'; ctx.fillText('one variant', o.x + 42, o.y - 34);
  }
  // shockwave as the signal leaves the variant
  const sw = prog(t, 2.5, 3.6);
  if (sw > 0 && sw < 1) { ctx.strokeStyle = rgba(C.lav, .35 * (1 - sw)); ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.arc(o.x, o.y, 30 + sw * Math.min(W, H) * .32, 0, 7); ctx.stroke(); }

  // cross links (fainter), then branches, then nodes
  ctx.lineWidth = 1;
  for (const c of G.cross) { const p = ease(prog(t, c.delay, c.delay + .8)); if (!p) continue;
    const a = c.t1 ? G.t1[c.a] : G.t2[c.a], b = c.t1 ? G.t1[c.b] : G.t2[c.b];
    ctx.strokeStyle = rgba(C.lav, (c.t1 ? .16 : .12) * p); ctx.setLineDash(c.t1 ? [] : [3, 5]); curve(a, b, .12, p); }
  ctx.setLineDash([]);
  const paths = [];
  for (const n of G.t1) { const p = ease(prog(t, n.delay, n.delay + .7)); if (!p) continue;
    ctx.strokeStyle = rgba(C.lav, .55 * p); ctx.lineWidth = 1.4; paths.push(curve(o, n, n.bend, p)); }
  for (const n of G.t2) { const par = G.t1[n.parent], p = ease(prog(t, n.delay, n.delay + .6)); if (!p) continue;
    ctx.strokeStyle = rgba(C.lav, .3 * p); ctx.lineWidth = 1; paths.push(curve(par, n, .1, p)); }

  // pulses travel along branches once the graph exists
  if (t > 6.3 && t - lastPulse > .55 && paths.length) { lastPulse = t; pulses.push({ f: paths[Math.floor(Math.random() * paths.length)], t0: t }); }
  pulses = pulses.filter(p => t - p.t0 < 1.4);
  for (const p of pulses) { const u = (t - p.t0) / 1.4, pt = p.f(u);
    ctx.save(); ctx.shadowColor = C.purple; ctx.shadowBlur = 10; ctx.fillStyle = rgba(C.text, .8 * Math.sin(u * Math.PI));
    ctx.beginPath(); ctx.arc(pt.x, pt.y, 2.2, 0, 7); ctx.fill(); ctx.restore(); }

  for (const n of G.t2) { const p = ease(prog(t, n.delay + .4, n.delay + .8)); if (!p) continue;
    ctx.fillStyle = rgba(C.lav, .6 * p); ctx.beginPath(); ctx.arc(n.x, n.y, n.r * p, 0, 7); ctx.fill(); }
  ctx.textAlign = 'center';
  G.t1.forEach((n, i) => { const p = ease(prog(t, n.delay + .5, n.delay + 1)); if (!p) return;
    const br = 1 + Math.sin(t * 1.3 + i) * .05 * prog(t, 6, 7);
    ctx.save(); ctx.shadowColor = C.purple; ctx.shadowBlur = 14 * p;
    ctx.fillStyle = '#171321'; ctx.strokeStyle = rgba(C.lav, .9 * p); ctx.lineWidth = 1.6;
    ctx.beginPath(); ctx.arc(n.x, n.y, 9 * p * br, 0, 7); ctx.fill(); ctx.stroke(); ctx.restore();
    ctx.fillStyle = rgba(C.lav, p); ctx.beginPath(); ctx.arc(n.x, n.y, 3 * p, 0, 7); ctx.fill();
    ctx.fillStyle = rgba(C.text2, p); ctx.font = '500 13px Inter, system-ui, sans-serif';
    ctx.fillText(n.name, n.x, n.y + (n.y > o.y + 5 ? 28 : -18)); });
}

resize(); window.addEventListener('resize', resize);
  const still = matchMedia('(prefers-reduced-motion: reduce)').matches;
  let raf = 0;
  if (still) frame(7.5);
  else { const t0 = performance.now(); let last = 0;
    const loop = now => { const t = (now - t0) / 1000;
      // after the build-up, ~30 fps is plenty for the slow idle loop
      if (t < 7 || now - last > 33) { frame(t); last = now; }
      raf = requestAnimationFrame(loop); };
    raf = requestAnimationFrame(loop); }
  return () => { cancelAnimationFrame(raf); window.removeEventListener('resize', resize); };
}
