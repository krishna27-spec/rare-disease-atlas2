// Thin client for the Atlas API (see docs/BACKEND_API.md). The graph only changes on a rebuild, so answers are cached.
const cache = new Map();

export function get(path) {
  if (!cache.has(path)) {
    cache.set(
      path,
      fetch(path).then((r) => {
        if (!r.ok) throw new Error(`${r.status} ${path}`);
        return r.json();
      }).catch((e) => { cache.delete(path); throw e; })
    );
  }
  return cache.get(path);
}

export const q = (s) => encodeURIComponent(s);
export const MPS3C = "MONDO:0009657"; // Maria's disease, the default journey
