import { motion } from "framer-motion";
import { useEffect, useRef } from "react";
import { runIntro } from "./introAnimation.js";

// Shown once per visit. It never forces the visitor on: the final state idles until they choose to enter.
export default function Intro({ enter }) {
  const ref = useRef(null);
  useEffect(() => runIntro(ref.current), []);
  useEffect(() => {
    const key = (e) => (e.key === "Enter" || e.key === "Escape") && enter();
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [enter]);
  return (
    <motion.div className="intro" exit={{ opacity: 0, scale: 1.06 }} transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}>
      <canvas ref={ref} aria-label="A DNA helix with one highlighted variant, whose signal grows into a knowledge graph" />
      <div className="intro-veil" aria-hidden="true" />
      <div className="brand intro-brand"><span className="brand-dot" />Rare Disease Atlas</div>
      <motion.button className="intro-skip" onClick={enter} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.8 }}>Skip intro</motion.button>
      <div className="intro-centre">
        <motion.span className="eyebrow" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.5, duration: 0.9 }}>AI Atlas for the world's rare diseases</motion.span>
        <motion.h1 className="wordmark" initial={{ opacity: 0, scale: 0.94, filter: "blur(14px)" }} animate={{ opacity: 1, scale: 1, filter: "blur(0px)" }} transition={{ delay: 0.7, duration: 1.6, ease: [0.22, 1, 0.36, 1] }}>
          <span>Atlas AI</span>
        </motion.h1>
        <motion.p className="intro-tag" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 1.6, duration: 0.9 }}>Connect the science. Find the path forward.</motion.p>
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 2.6, duration: 0.9 }} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 18 }}>
          <p className="soft" style={{ maxWidth: 520 }}>From one gene to the pathways, symptoms, related diseases, studies and people around it, with the evidence behind every link.</p>
          <button className="btn" onClick={enter}>Enter the Atlas →</button>
        </motion.div>
      </div>
    </motion.div>
  );
}
