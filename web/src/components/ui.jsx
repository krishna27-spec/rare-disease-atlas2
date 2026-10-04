import { motion } from "framer-motion";
import { useState } from "react";
import { useEvidence } from "../hooks.js";

const rise = { hidden: { opacity: 0, y: 18 }, show: { opacity: 1, y: 0, transition: { duration: 0.7, ease: [0.22, 1, 0.36, 1] } } };

export function Reveal({ children, delay = 0, ...rest }) {
  return (
    <motion.div variants={rise} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-80px" }} transition={{ delay }} {...rest}>
      {children}
    </motion.div>
  );
}

// A chapter: one eyebrow, one headline sentence, then content.
export function Chapter({ id, eyebrow, title, lead, children }) {
  return (
    <section id={id} className="chapter">
      <Reveal className="chapter-head">
        <span className="eyebrow">{eyebrow}</span>
        <h2>{title}</h2>
        {lead && <p className="lead">{lead}</p>}
      </Reveal>
      {children}
    </section>
  );
}

// The "Why?" chip: opens the evidence drawer for the edges behind a claim.
export function Why({ ids, title, label = "Why?" }) {
  const open = useEvidence();
  if (!ids || !ids.length) return null;
  return <button className="chip why" onClick={(e) => { e.stopPropagation(); open(title, ids); }}>{label}</button>;
}

export function Card({ meta, title, children, foot }) {
  return (
    <Reveal className="card">
      {meta && <span className="meta">{meta}</span>}
      {title && <h3>{title}</h3>}
      {children}
      {foot && <div className="foot">{foot}</div>}
    </Reveal>
  );
}

// Level 2 of "simple to depth": show a few, offer the rest.
export function Limit({ items, n = 3, render, className = "cards", noun = "more" }) {
  const [all, setAll] = useState(false);
  const shown = all ? items : items.slice(0, n);
  return (
    <>
      <div className={className}>{shown.map(render)}</div>
      {items.length > n && (
        <button className="more" onClick={() => setAll(!all)}>{all ? "Show fewer" : `Show all ${items.length} ${noun}`}</button>
      )}
    </>
  );
}

export function Gap({ title, children }) {
  return (
    <Reveal className="gap">
      <h3>{title}</h3>
      {children}
    </Reveal>
  );
}

export const Skeletons = ({ n = 3 }) => <div className="cards">{Array.from({ length: n }, (_, i) => <div key={i} className="skeleton" />)}</div>;

export const pretty = (s) => (s || "").replace(/_/g, " ").toLowerCase();
