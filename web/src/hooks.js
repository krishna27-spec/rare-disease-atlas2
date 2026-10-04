import { createContext, useContext, useEffect, useState } from "react";
import { get } from "./api.js";

// Load one API path. Returns [data, error]; data is undefined while loading.
export function useApi(path) {
  const [state, set] = useState([undefined, null]);
  useEffect(() => {
    if (!path) return;
    let live = true;
    set([undefined, null]);
    get(path).then((d) => live && set([d, null])).catch((e) => live && set([undefined, e]));
    return () => { live = false; };
  }, [path]);
  return state;
}

// One evidence drawer for the whole site: anything can call open(title, edgeIds).
export const Evidence = createContext(() => {});
export const useEvidence = () => useContext(Evidence);
