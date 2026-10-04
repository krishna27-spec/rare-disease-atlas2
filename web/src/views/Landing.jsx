import { motion } from "framer-motion";
import Search from "../components/Search.jsx";
import { MPS3C } from "../api.js";

const up = (i) => ({ initial: { opacity: 0, y: 22 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.9, delay: 0.12 * i, ease: [0.22, 1, 0.36, 1] } });

export default function Landing({ go }) {
  return (
    <div className="wrap hero">
      <motion.span className="eyebrow" {...up(0)}>AI Atlas for the world's rare diseases</motion.span>
      <motion.h1 {...up(1)}>What would you like<br /><span className="grad">to explore?</span></motion.h1>
      <motion.p className="lead" {...up(2)}>
        Start from one rare disease. See which others share its biology, what research already exists, and who could help. It starts simple and goes as deep as you ask.
      </motion.p>
      <motion.div {...up(3)} style={{ width: "100%", display: "flex", justifyContent: "center", position: "relative", zIndex: 5 }}>
        <Search autoFocus onDisease={(id) => go({ view: "disease", id, mode: "overview" })} />
      </motion.div>
      <motion.p className="small muted" {...up(4)}>
        Try <a onClick={() => go({ view: "disease", id: MPS3C, mode: "overview" })} style={{ cursor: "pointer" }}>Sanfilippo C</a>, a gene like HEXB, or a symptom like seizure
      </motion.p>
    </div>
  );
}
