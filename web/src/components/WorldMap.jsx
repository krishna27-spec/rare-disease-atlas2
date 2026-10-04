import { geoContains, geoNaturalEarth1, geoPath } from "d3-geo";
import { useEffect, useMemo, useRef, useState } from "react";
import { feature } from "topojson-client";
import world from "world-atlas/countries-110m.json";

// The world as a field of points, in the same visual language as the constellation.
// "sites": a glow per city, larger where more studies run, green where one is recruiting.
// "prevalence": countries with a reported figure light up, brighter where the disease is more common.
const COUNTRIES = feature(world, world.objects.countries).features;
const ALIAS = { "United States": "United States of America", "Czech Republic": "Czechia", "Korea, Republic of": "South Korea", "Taiwan, Province of China": "Taiwan", "Turkey (Türkiye)": "Turkey" };
const STEP = 7;

export default function WorldMap({ cities, prevalence, mode }) {
  const ref = useRef(null);
  const [tip, setTip] = useState(null);
  const byCountry = useMemo(() => {
    const best = {};      // one figure per country: validated first, then the highest reported
    for (const p of prevalence) {
      const name = ALIAS[p.where] || p.where;
      if (p.per_100k && (!best[name] || p.per_100k > best[name].per_100k)) best[name] = p;
    }
    return best;
  }, [prevalence]);

  useEffect(() => {
    const c = ref.current, ctx = c.getContext("2d");
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let w, h, raf, dots = [], pts = [], proj;
    const build = () => {
      const d = Math.min(window.devicePixelRatio || 1, 2), b = c.getBoundingClientRect();
      w = b.width; h = b.height; c.width = w * d; c.height = h * d; ctx.setTransform(d, 0, 0, d, 0, 0);
      proj = geoNaturalEarth1().fitExtent([[10, 10], [w - 10, h - 10]], { type: "Sphere" });
      // rasterise the land once, then keep only the grid points that fall on it
      const off = document.createElement("canvas"); off.width = w; off.height = h;
      const o = off.getContext("2d"), path = geoPath(proj, o);
      o.fillStyle = "#fff"; o.beginPath(); path({ type: "FeatureCollection", features: COUNTRIES }); o.fill();
      const px = o.getImageData(0, 0, w, h).data;
      const lit = COUNTRIES.filter((f) => byCountry[f.properties.name]);
      const max = Math.max(...Object.values(byCountry).map((p) => p.per_100k), 0.0001);
      dots = [];
      for (let y = STEP / 2; y < h; y += STEP) for (let x = STEP / 2; x < w; x += STEP) {
        if (px[(Math.floor(y) * Math.floor(w) + Math.floor(x)) * 4 + 3] < 128) continue;
        let heat = 0, name = "";
        if (lit.length) { const ll = proj.invert([x, y]); const f = ll && lit.find((g) => geoContains(g, ll)); if (f) { name = f.properties.name; heat = 0.25 + 0.75 * Math.sqrt(byCountry[name].per_100k / max); } }
        dots.push({ x, y, heat, name });
      }
      pts = cities.map((s) => { const p = proj([s.lon, s.lat]); return p && { ...s, x: p[0], y: p[1], r: 3 + 2.6 * Math.sqrt(s.n_studies) }; }).filter(Boolean);
    };
    const draw = (t) => {
      ctx.clearRect(0, 0, w, h);
      for (const d of dots) {
        const on = mode === "prevalence" && d.heat;
        ctx.fillStyle = on ? `rgba(103,198,214,${0.25 + d.heat * 0.75})` : "rgba(167,139,250,0.2)";
        ctx.beginPath(); ctx.arc(d.x, d.y, on ? 1.9 : 1.3, 0, 6.2832); ctx.fill();
      }
      if (mode === "sites") for (const p of pts) {
        const col = p.recruiting ? "95,211,154" : "167,139,250";
        const pulse = p.recruiting && !still ? 1 + 0.25 * Math.sin(t / 520 + p.x) : 1;
        const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r * 3.2 * pulse);
        g.addColorStop(0, `rgba(${col},0.55)`); g.addColorStop(1, `rgba(${col},0)`);
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(p.x, p.y, p.r * 3.2 * pulse, 0, 6.2832); ctx.fill();
        ctx.fillStyle = p.recruiting ? "#b9f5d8" : "#e9e2ff"; ctx.beginPath(); ctx.arc(p.x, p.y, Math.max(1.6, p.r * 0.42), 0, 6.2832); ctx.fill();
      }
      raf = requestAnimationFrame(draw);
    };
    const move = (ev) => {
      const b = c.getBoundingClientRect(), x = ev.clientX - b.left, y = ev.clientY - b.top;
      if (mode === "sites") {
        const hit = pts.filter((p) => Math.hypot(p.x - x, p.y - y) < p.r * 1.6 + 5).sort((a, z) => Math.hypot(a.x - x, a.y - y) - Math.hypot(z.x - x, z.y - y))[0];
        return setTip(hit ? { x: hit.x, y: hit.y - hit.r, head: `${hit.city}, ${hit.country}`, text: `${hit.n_studies} ${hit.n_studies === 1 ? "study" : "studies"}${hit.recruiting ? " · recruiting now" : ""}` } : null);
      }
      const d = dots.find((q) => q.heat && Math.abs(q.x - x) < STEP && Math.abs(q.y - y) < STEP);
      const key = d && Object.keys(byCountry).find((k) => k === d.name);
      setTip(key ? { x, y: y - 8, head: byCountry[key].where, text: `${byCountry[key].value} · ${byCountry[key].measure.toLowerCase()}` } : null);
    };
    build(); raf = requestAnimationFrame(draw);
    const ro = new ResizeObserver(build); ro.observe(c);
    c.addEventListener("mousemove", move); c.addEventListener("mouseleave", () => setTip(null));
    return () => { cancelAnimationFrame(raf); ro.disconnect(); c.removeEventListener("mousemove", move); };
  }, [cities, byCountry, mode]);

  return (
    <div className="worldmap">
      <canvas ref={ref} role="img" aria-label={mode === "sites" ? "World map of study sites" : "World map of reported prevalence"} />
      {tip && <div className="tip" style={{ left: tip.x, top: tip.y }}><b>{tip.head}</b><br /><span>{tip.text}</span></div>}
    </div>
  );
}
