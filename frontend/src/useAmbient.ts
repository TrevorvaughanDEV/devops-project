import { useEffect, useState } from "react";

const SPOT = ".rank, .campaign, .insight-list li, .project, .try, .heat, .daybars, .report-botnets li";
const reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

/** Pointer-driven CSS variables, set without re-rendering anything:
 *  --px / --py (-1..1) on <html> for the hero's parallax, and --mx / --my (px) on the
 *  hovered card (see SPOT) so its edge light can follow the cursor. */
export function useAmbient() {
  useEffect(() => {
    if (!matchMedia("(hover: hover) and (pointer: fine)").matches) return;
    const root = document.documentElement;
    let frame = 0;
    let event: PointerEvent | null = null;

    const apply = () => {
      frame = 0;
      if (!event) return;
      const e = event;
      if (!reduced()) {
        root.style.setProperty("--px", ((e.clientX / innerWidth) * 2 - 1).toFixed(3));
        root.style.setProperty("--py", ((e.clientY / innerHeight) * 2 - 1).toFixed(3));
      }
      const spot = (e.target as Element | null)?.closest<HTMLElement>(SPOT);
      if (spot) {
        const r = spot.getBoundingClientRect();
        spot.style.setProperty("--mx", `${e.clientX - r.left}px`);
        spot.style.setProperty("--my", `${e.clientY - r.top}px`);
      }
    };
    const onMove = (e: PointerEvent) => {
      event = e;
      if (!frame) frame = requestAnimationFrame(apply);
    };
    addEventListener("pointermove", onMove, { passive: true });
    return () => {
      removeEventListener("pointermove", onMove);
      if (frame) cancelAnimationFrame(frame);
    };
  }, []);
}

/** The id of the section currently crossing the middle of the viewport. */
export function useActiveSection(ids: string[]) {
  const [active, setActive] = useState<string | null>(null);
  const key = ids.join(",");
  useEffect(() => {
    const els = key.split(",").map((id) => document.getElementById(id)).filter((e): e is HTMLElement => !!e);
    if (els.length === 0) return;
    const seen = new Set<string>();
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) (e.isIntersecting ? seen.add(e.target.id) : seen.delete(e.target.id));
        const first = els.find((el) => seen.has(el.id));
        setActive(first ? first.id : null);
      },
      { rootMargin: "-35% 0px -60% 0px" },
    );
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, [key]);
  return active;
}
