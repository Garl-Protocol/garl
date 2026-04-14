"use client";

import { useEffect, useState } from "react";
import { Menu, X } from "lucide-react";

const LINKS: { href: string; label: string; accent?: boolean; external?: boolean }[] = [
  { href: "/for-code", label: "For Code", accent: true },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/leaderboard", label: "Leaderboard" },
  { href: "/compare", label: "Compare" },
  { href: "/compliance", label: "Compliance" },
  { href: "/docs", label: "Docs" },
  { href: "/simulator", label: "Simulator" },
  { href: "/playground", label: "Try It" },
  { href: "/verify", label: "Verify" },
  { href: "mailto:contact@garl.ai", label: "Contact", external: true },
];

export default function SiteNav() {
  const [open, setOpen] = useState(false);

  // Close on route change / escape
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open]);

  return (
    <header className="sticky top-0 z-50 border-b border-garl-border bg-garl-bg/80 backdrop-blur-xl">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4">
        <a
          href="/"
          className="flex items-center gap-2"
          onClick={() => setOpen(false)}
        >
          <div className="flex h-8 w-8 items-center justify-center rounded-md border border-garl-accent/30 bg-garl-accent/10">
            <span className="font-mono text-sm font-bold text-garl-accent">G</span>
          </div>
          <span className="font-mono text-sm font-semibold tracking-wider text-garl-text">
            GARL
            <span className="ml-1 text-garl-muted">PROTOCOL</span>
          </span>
        </a>

        {/* Desktop nav (md and up) */}
        <nav className="hidden items-center gap-6 md:flex">
          {LINKS.map((l) => (
            <a
              key={l.href}
              href={l.href}
              className={`font-mono text-xs uppercase tracking-wider transition-colors hover:text-garl-accent ${
                l.accent ? "text-garl-accent/70" : "text-garl-muted"
              }`}
            >
              {l.label}
            </a>
          ))}
          <div className="h-4 w-px bg-garl-border" />
          <a
            href="/dashboard"
            className="flex items-center gap-1.5 transition-opacity hover:opacity-80"
          >
            <div className="h-2 w-2 rounded-full bg-garl-accent animate-pulse" />
            <span className="font-mono text-[10px] uppercase tracking-wider text-garl-accent">
              Live
            </span>
          </a>
        </nav>

        {/* Mobile hamburger */}
        <button
          type="button"
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
          className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-garl-border bg-garl-surface text-garl-text transition-colors hover:border-garl-accent/40 md:hidden"
        >
          {open ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
        </button>
      </div>

      {/* Mobile drawer */}
      {open && (
        <div
          id="mobile-menu"
          className="fixed inset-x-0 top-14 z-40 border-b border-garl-border bg-garl-bg/98 backdrop-blur-xl md:hidden"
          onClick={() => setOpen(false)}
        >
          <nav className="mx-auto flex max-w-7xl flex-col gap-1 px-4 py-4">
            {LINKS.map((l) => (
              <a
                key={l.href}
                href={l.href}
                className={`rounded-lg px-3 py-3 font-mono text-sm uppercase tracking-wider transition-colors hover:bg-garl-surface hover:text-garl-accent ${
                  l.accent ? "text-garl-accent" : "text-garl-text"
                }`}
              >
                {l.label}
              </a>
            ))}
            <a
              href="/dashboard"
              className="mt-2 flex items-center gap-2 rounded-lg border border-garl-accent/30 bg-garl-accent/10 px-3 py-3 font-mono text-xs uppercase tracking-wider text-garl-accent"
            >
              <div className="h-2 w-2 rounded-full bg-garl-accent animate-pulse" />
              Live · Dashboard
            </a>
          </nav>
        </div>
      )}
    </header>
  );
}
