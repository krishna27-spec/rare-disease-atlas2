import { motion } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import { runIntro } from "./introAnimation.js";

// Two acts. First the animation plays as it is: the helix, one variant, the network growing out of it.
// Then it recedes and the name arrives. It never forces the visitor on: the final state idles until they enter.
const REVEAL_AT = 6200;   // ms: when the network has finished building
const ease = [0.22, 1, 0.36, 1];

export default function Intro({ enter }) {
  const ref = useRef(null);
  const still = typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const [named, setNamed] = useState(still);
  useEffect(() => runIntro(ref.current), []);
  useEffect(() => {
    const t = setTimeout(() => setNamed(true), REVEAL_AT);
    const key = (e) => (e.key === "Enter" || e.key === "Escape") && enter();
    window.addEventListener("keydown", key);
    return () => { clearTimeout(t); window.removeEventListener("keydown", key); };
  }, [enter]);
  const show = (delay) => ({ initial: false, animate: named ? { opacity: 1, y: 0 } : { opacity: 0, y: 10 }, transition: { delay: named ? delay : 0, duration: 1, ease } });
  return (
    <motion.div className="intro" exit={{ opacity: 0, scale: 1.06 }} transition={{ duration: 0.7, ease }}>
      <motion.canvas ref={ref} initial={false} animate={{ opacity: named ? 0.3 : 1 }} transition={{ duration: 2.2, ease: "easeInOut" }}
        aria-label="A DNA helix with one highlighted variant, whose signal grows into a knowledge graph" />
      <motion.div className="intro-veil" aria-hidden="true" initial={false} animate={{ opacity: named ? 1 : 0 }} transition={{ duration: 2.2, ease: "easeInOut" }} />
      <div className="brand intro-brand"><span className="brand-dot" />Rare Disease Atlas</div>
      <motion.button className="intro-skip" onClick={enter} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.8 }}>Skip intro</motion.button>
      <div className="intro-centre" style={{ pointerEvents: named ? "auto" : "none" }}>
        <motion.span className="eyebrow" {...show(0.5)}>AI Atlas for the world's rare diseases</motion.span>
        <motion.h1 className="wordmark" initial={false}
          animate={named ? { opacity: 1, scale: 1, filter: "blur(0px)" } : { opacity: 0, scale: 0.95, filter: "blur(16px)" }}
          transition={{ delay: named ? 0.7 : 0, duration: 1.9, ease }}>
          <span>Atlas AI</span>
        </motion.h1>
        <motion.p className="intro-tag" {...show(1.7)}>Connect the science. Find the path forward.</motion.p>
        <motion.div {...show(2.3)} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 18 }}>
          <p className="soft" style={{ maxWidth: 520 }}>From one gene to the pathways, symptoms, related diseases, studies and people around it, with the evidence behind every link.</p>
          <button className="btn" onClick={enter}>Enter the Atlas →</button>
        </motion.div>
      </div>
    </motion.div>
  );
}
