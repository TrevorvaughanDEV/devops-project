import { useEffect, useState } from "react";
import { useActiveSection } from "../useAmbient";
import { Wordmark } from "./Wordmark";

export type NavLink = { href: string; label: string };

/** Floating navigation. In-page links ("#id") are tracked as the page scrolls; below 760px the
 *  links move into a full-width menu. */
export function SiteHeader({ links }: { links: NavLink[] }) {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const active = useActiveSection(links.filter((l) => l.href.startsWith("#")).map((l) => l.href.slice(1)));

  useEffect(() => {
    const onScroll = () => setScrolled(scrollY > 12);
    onScroll();
    addEventListener("scroll", onScroll, { passive: true });
    return () => removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <header className={`masthead${scrolled ? " is-scrolled" : ""}${open ? " is-open" : ""}`}>
      <div className="masthead-inner">
        <Wordmark />
        <nav id="site-nav" aria-label="Sections">
          {links.map((l) => (
            <a
              key={l.href}
              href={l.href}
              aria-current={l.href === `#${active}` ? "location" : undefined}
              onClick={() => setOpen(false)}
            >
              {l.label}
            </a>
          ))}
        </nav>
        <button
          type="button"
          className="menu-toggle"
          aria-expanded={open}
          aria-controls="site-nav"
          aria-label={open ? "Close menu" : "Open menu"}
          onClick={() => setOpen((o) => !o)}
        >
          <span aria-hidden="true" />
          <span aria-hidden="true" />
        </button>
      </div>
      <div className="scroll-progress" aria-hidden="true" />
    </header>
  );
}
