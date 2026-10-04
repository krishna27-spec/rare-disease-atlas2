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
      <div className="brand intro-brand"><span className="brand-dot" />Rare Disease Atlas</div>
      <motion.button className="intro-skip" onClick={enter} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.8 }}>Skip intro</motion.button>
      <motion.div className="intro-cta" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 5.2, duration: 0.9 }}>
        <span className="eyebrow">AI Atlas for the world's rare diseases</span>
        <h1>Connect the science.<br /><span className="grad">Find the path forward.</span></h1>
        <p className="soft" style={{ maxWidth: 560 }}>From one gene to the pathways, symptoms, related diseases, studies and people around it, with the evidence behind every link.</p>
        <button className="btn" onClick={enter} style={{ marginTop: 10 }}>Enter the Atlas →</button>
      </motion.div>
    </motion.div>
  );
}
