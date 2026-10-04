// Thin client for the Atlas API (see docs/BACKEND_API.md). The graph only changes on a rebuild, so answers are cached.
// Built in "pages" mode (npm run build:pages) the site has no server: the same paths are answered from the static
// files written by `python -m src.atlas.export_static`, and search runs here in the browser.
const cache = new Map();
const STATIC = typeof __STATIC__ !== "undefined" && __STATIC__;

const fetchJson = (url) => fetch(url).then((r) => { if (!r.ok) throw new Error(`${r.status} ${url}`); return r.json(); });

export function get(path) {
  if (!cache.has(path)) cache.set(path, (STATIC ? fromFiles(path) : fetchJson(path)).catch((e) => { cache.delete(path); throw e; }));
  return cache.get(path);
}

export const q = (s) => encodeURIComponent(s);
export const MPS3C = "MONDO:0009657"; // Maria's disease, the default journey

/* ------------------------------------------------------------------ static mode */
const file = (name) => get(`file:${name}`);
const safe = (id) => id.replace(/:/g, "_");

function fromFiles(path) {
  if (path.startsWith("file:")) return fetchJson(`api/${path.slice(5)}`);
  const [route, query = ""] = path.split("?");
  const args = Object.fromEntries(new URLSearchParams(query));
  const parts = route.split("/").filter(Boolean).map(decodeURIComponent);
  if (parts[0] === "search") return search(args.q || "");
  if (parts[0] === "mechanism") return mechanism(args.q || "");
  if (parts[0] === "edge") return file("edges.json").then((all) => { if (!all[parts[1]]) throw new Error("unknown edge"); return all[parts[1]]; });
  if (parts[0] === "connectors") return file(args.disease ? `disease/${safe(args.disease)}/connectors.json` : args.cross_cluster_only === "true" ? "connectors-cross.json" : "connectors.json");
  if (parts[0] === "disease") return file(parts[2] ? `disease/${safe(parts[1])}/${parts[2]}.json` : `disease/${safe(parts[1])}.json`);
  return file(`${parts[0]}.json`);   // diseases, stats, contradictions
}

// edit distance, stopping early once it exceeds `max`
function lev(a, b, max) {
  if (Math.abs(a.length - b.length) > max) return max + 1;
  let prev = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i++) {
    const cur = [i]; let best = i;
    for (let j = 1; j <= b.length; j++) { cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1)); best = Math.min(best, cur[j]); }
    if (best > max) return max + 1;
    prev = cur;
  }
  return prev[b.length];
}
// how well `text` answers the query: exact, contains it, or is within a typo or two of it
function score(query, text) {
  if (text === query) return 100;
  if (query.length >= 4 && text.includes(query)) return 90;
  const max = query.length >= 9 ? 2 : query.length >= 5 ? 1 : 0;
  if (!max) return 0;
  const whole = lev(query, text, max);
  if (whole <= max) return 96 - 3 * whole;               // the closer spelling ranks higher
  let best = max + 1;
  for (let i = 0; i + query.length - max <= text.length; i++) {            // a typo inside a longer name
    if (i && text[i - 1] !== " ") continue;
    for (const len of [query.length, query.length + 1, query.length - 1]) best = Math.min(best, lev(query, text.slice(i, i + len), max));
  }
  return best <= max ? 91 - 3 * best : 0;
}

async function hitsFor(text, limit = 8) {
  const { rows, leads } = await file("search-index.json");
  const best = {};
  for (const [t, kind, id, label] of rows) {
    const s = score(text, t);
    if (s && (!best[id] || s > best[id].score)) best[id] = { kind, id, label, matched: t, score: s };
  }
  return Object.values(best).sort((a, b) => b.score - a.score || (a.kind !== "disease") - (b.kind !== "disease")).slice(0, limit)
    .map((h) => (h.kind === "disease" ? h : { ...h, diseases: leads[h.id] || [] }));
}

async function search(raw) {
  const text = raw.trim().toLowerCase();
  const hits = text ? await hitsFor(text) : [];
  const out = { query: raw, hits };
  if (!hits.length) {
    const [{ searched }, outside] = await Promise.all([file("search-index.json"), file("outside.json")]);
    const found = [];
    for (const [mondo_id, name, synonyms, genes, orpha] of outside) {
      const names = [name, ...synonyms.split("|")].filter(Boolean).map((n) => n.toLowerCase());
      const s = Math.max(...names.map((n) => (n === text ? 100 : text.length >= 4 && n.includes(text) ? 90 - Math.min(n.length - text.length, 30) / 10 : 0)));
      if (s) found.push({ s, mondo_id, name, genes: genes ? genes.split("|") : [], orphanet_url: `https://www.orpha.net/en/disease/detail/${orpha}`,
        to_add: `Add one row to data/manual/diseases.csv (${mondo_id}${genes ? `, gene ${genes.split("|")[0]}` : ""}) and rebuild.` });
    }
    out.known_elsewhere = found.sort((a, b) => b.s - a.s).slice(0, 3);
    out.no_match = { message: `Nothing in the Atlas matches '${raw}'.`, searched };
  }
  return out;
}

async function mechanism(raw) {
  const text = raw.trim().toLowerCase();
  const hit = (await hitsFor(text, 12)).find((h) => h.kind === "pathway" || h.kind === "gene");
  if (!hit) {
    const { searched } = await file("search-index.json");
    return { query: raw, pathways: [], clusters: [], no_match: `No specific pathway or gene in the Atlas matches '${raw}'. ${searched.specific_pathways} pathways and ${searched.genes} genes were searched.` };
  }
  const res = await file(`mechanism/${safe(hit.id)}.json`);
  return { ...res, query: raw };
}
