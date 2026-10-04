import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useEffect, useState } from "react";
import EvidenceDrawer from "./components/EvidenceDrawer.jsx";
import Search from "./components/Search.jsx";
import Starfield from "./components/Starfield.jsx";
import { Evidence } from "./hooks.js";
import Intro from "./components/Intro.jsx";
import About from "./views/About.jsx";
import Connectors from "./views/Connectors.jsx";
import Disease from "./views/Disease.jsx";
import Landing from "./views/Landing.jsx";
import Mechanism from "./views/Mechanism.jsx";

// The place is kept in the URL hash (#disease/MONDO:0009657/full) so pages can be linked and Back works.
const read = () => {
  const [view = "landing", id, mode] = decodeURIComponent(window.location.hash.slice(1)).split("/");
  return { view: view || "landing", id, mode: mode || "full" };
};

export default function App() {
  const [at, setAt] = useState(read);
  const [ev, setEv] = useState(null);
  // the intro plays once per visit, and only when arriving at the front door
  const [intro, setIntro] = useState(() => !window.location.hash && !sessionStorage.getItem("entered"));
  const enter = useCallback(() => { sessionStorage.setItem("entered", "1"); setIntro(false); }, []);
  useEffect(() => {
    const on = () => { setAt(read()); setEv(null); };
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  const go = useCallback((to) => { window.location.hash = [to.view, to.id, to.id && to.mode].filter(Boolean).join("/"); if (to.view !== "disease") window.scrollTo(0, 0); }, []);
  const openEvidence = useCallback((title, ids) => setEv({ title, ids: [...new Set(ids)] }), []);
  const close = useCallback(() => setEv(null), []);

  return (
    <Evidence.Provider value={openEvidence}>
      <Starfield />
      <div className="app">
        <header className="bar">
          <div className="wrap bar-in">
            <button className="brand" onClick={() => go({ view: "landing" })}><span className="brand-dot" />Rare Disease Atlas</button>
            {at.view !== "landing" && <div style={{ flex: 1, maxWidth: 420 }} className="barsearch"><Search placeholder="Search" onDisease={(id) => go({ view: "disease", id, mode: at.mode })} /></div>}
            <nav className="nav">
              <button className={at.view === "mechanism" ? "on" : ""} onClick={() => go({ view: "mechanism" })}>Mechanisms</button>
              <button className={at.view === "connectors" ? "on" : ""} onClick={() => go({ view: "connectors" })}>Connectors</button>
              <button className={at.view === "about" ? "on" : ""} onClick={() => go({ view: "about" })}>Evidence</button>
            </nav>
          </div>
        </header>
        <AnimatePresence mode="wait">
          <motion.main key={at.view + (at.id || "") + (at.view === "disease" ? at.mode : "")} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}>
            {at.view === "disease" && at.id ? <Disease id={at.id} mode={at.mode} go={go} />
              : at.view === "mechanism" ? <Mechanism go={go} />
              : at.view === "connectors" ? <Connectors go={go} />
              : at.view === "about" ? <About />
              : <Landing go={go} />}
          </motion.main>
        </AnimatePresence>
      </div>
      <EvidenceDrawer state={ev} close={close} />
      <AnimatePresence>{intro && <Intro enter={enter} />}</AnimatePresence>
    </Evidence.Provider>
  );
}
