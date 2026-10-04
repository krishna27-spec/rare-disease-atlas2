import { motion } from "framer-motion";
import Search from "../components/Search.jsx";
import { MPS3C } from "../api.js";

const DOORS = [
  { who: "Patient group leader", say: "I lead a patient group", get: "Who is like us, what already exists, what to do next.", to: { view: "disease", id: MPS3C, mode: "full" } },
  { who: "Family or caregiver", say: "We just got a diagnosis", get: "Your community first, in plain language.", to: { view: "disease", id: MPS3C, mode: "simple" } },
  { who: "Biotech or pharma scout", say: "I'm scouting a therapy", get: "Every disease cluster a mechanism could reach.", to: { view: "mechanism" } },
  { who: "Researcher or clinician", say: "I study one gene", get: "Who else works on your mechanism, across diseases.", to: { view: "connectors" } },
];
const up = (i) => ({ initial: { opacity: 0, y: 22 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.9, delay: 0.12 * i, ease: [0.22, 1, 0.36, 1] } });

export default function Landing({ go }) {
  return (
    <div className="wrap hero">
      <motion.span className="eyebrow" {...up(0)}>AI Atlas for the world's rare diseases</motion.span>
      <motion.h1 {...up(1)}>Scattered points of light.<br /><span className="grad">One map to connect them.</span></motion.h1>
      <motion.p className="lead" {...up(2)}>
        Start from one rare disease. See which others share its biology, what research already exists, and who could help. Every connection shows its source.
      </motion.p>
      <motion.div {...up(3)} style={{ width: "100%", display: "flex", justifyContent: "center", position: "relative", zIndex: 5 }}>
        <Search autoFocus onDisease={(id) => go({ view: "disease", id, mode: "full" })} />
      </motion.div>
      <motion.p className="small muted" {...up(4)}>
        Try <a onClick={() => go({ view: "disease", id: MPS3C, mode: "full" })} style={{ cursor: "pointer" }}>Sanfilippo C</a>, a gene like HEXB, or a symptom like seizure
      </motion.p>
      <motion.div className="doors" {...up(5)}>
        {DOORS.map((d) => (
          <button key={d.say} className="door" onClick={() => go(d.to)}>
            <span className="who">{d.who}</span>
            <span className="say">{d.say}</span>
            <span className="get">{d.get}</span>
          </button>
        ))}
      </motion.div>
    </div>
  );
}
