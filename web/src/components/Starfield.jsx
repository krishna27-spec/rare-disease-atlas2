import { useEffect, useRef } from "react";

// "Five thousand scattered points of light": a slow, faint field behind every page.
export default function Starfield() {
  const ref = useRef(null);
  useEffect(() => {
    const c = ref.current, ctx = c.getContext("2d");
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let w, h, raf, stars = [];
    const size = () => {
      const d = Math.min(window.devicePixelRatio || 1, 2);
      w = window.innerWidth; h = window.innerHeight;
      c.width = w * d; c.height = h * d; ctx.setTransform(d, 0, 0, d, 0, 0);
      const n = Math.round((w * h) / 2600);
      let seed = 7;
      const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
      stars = Array.from({ length: n }, () => ({ x: rnd() * w, y: rnd() * h, r: rnd() * 1.1 + 0.2, a: rnd() * 0.5 + 0.08, p: rnd() * 6.28, s: rnd() * 0.5 + 0.2, v: rnd() < 0.12 }));
    };
    const draw = (t) => {
      ctx.clearRect(0, 0, w, h);
      for (const s of stars) {
        const tw = still ? 1 : 0.65 + 0.35 * Math.sin(t / 1400 * s.s + s.p);
        ctx.globalAlpha = s.a * tw;
        ctx.fillStyle = s.v ? "#a78bfa" : "#e9e4ff";
        ctx.beginPath(); ctx.arc(s.x, (s.y + (still ? 0 : t / 900 * s.s)) % h, s.r, 0, 6.2832); ctx.fill();
      }
      ctx.globalAlpha = 1;
      if (!still) raf = requestAnimationFrame(draw);
    };
    size(); raf = requestAnimationFrame(draw);
    window.addEventListener("resize", size);
    return () => { cancelAnimationFrame(raf); window.removeEventListener("resize", size); };
  }, []);
  return <canvas ref={ref} className="starfield" aria-hidden="true" />;
}
