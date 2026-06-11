"use client";

import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { usePathname } from "next/navigation";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Menu, X } from "lucide-react";
import {
  SignedIn,
  SignedOut,
  SignInButton,
  SignUpButton,
  UserButton,
} from "@clerk/nextjs";

type Link = { href: string; label: string; accent?: boolean; external?: boolean };

const LINKS: Link[] = [
  { href: "/connect", label: "Add Agent", accent: true },
  { href: "/registry", label: "Registry" },
  { href: "/verify", label: "Verify" },
  { href: "/for-code", label: "For Code" },
  { href: "/docs", label: "Docs" },
];

// Auth UI engages only when Clerk is configured (publishable key inlined at
// build time). Without it nothing Clerk renders and the nav is unchanged —
// same gating as the middleware + the ClerkProvider in layout.
const clerkConfigured = !!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

export default function SiteNav() {
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false); // gate portal until client mount
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const drawerRef = useRef<HTMLDivElement | null>(null);
  const firstLinkRef = useRef<HTMLAnchorElement | null>(null);
  const drawerId = useId();
  const pathname = usePathname() || "/";
  const reducedMotion = useReducedMotion();

  useEffect(() => {
    setMounted(true);
  }, []);

  // Body scroll lock + Escape + focus trap. Restores everything on close.
  useEffect(() => {
    if (!open) return;

    const previouslyFocused = document.activeElement as HTMLElement | null;
    const scrollY = window.scrollY;

    document.body.style.position = "fixed";
    document.body.style.top = `-${scrollY}px`;
    document.body.style.left = "0";
    document.body.style.right = "0";
    document.body.style.width = "100%";

    // focus first link shortly after open so screen readers announce it
    const focusTimer = window.setTimeout(() => firstLinkRef.current?.focus(), 50);

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        setOpen(false);
        return;
      }
      if (e.key !== "Tab" || !drawerRef.current) return;
      const focusables = drawerRef.current.querySelectorAll<HTMLElement>(
        "a[href], button:not([disabled])",
      );
      if (focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey);

    return () => {
      document.removeEventListener("keydown", onKey);
      window.clearTimeout(focusTimer);
      document.body.style.position = "";
      document.body.style.top = "";
      document.body.style.left = "";
      document.body.style.right = "";
      document.body.style.width = "";
      window.scrollTo(0, scrollY);
      previouslyFocused?.focus?.();
    };
  }, [open]);

  // Close on route change (App Router pathname updates client-side)
  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  const isActive = (href: string) =>
    href !== "/" && (pathname === href || pathname.startsWith(href + "/"));

  return (
    <header className="sticky top-0 z-50 border-b border-garl-border bg-garl-bg/80 backdrop-blur-xl">
      <div
        className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4"
        style={{ paddingTop: "env(safe-area-inset-top, 0)" }}
      >
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
        <nav
          className="hidden items-center gap-6 md:flex"
          aria-label="Primary"
        >
          {LINKS.map((l) => {
            const active = isActive(l.href);
            return (
              <a
                key={l.href}
                href={l.href}
                aria-current={active ? "page" : undefined}
                className={`font-mono text-xs uppercase tracking-wider transition-colors hover:text-garl-accent ${
                  active
                    ? "text-garl-accent"
                    : l.accent
                      ? "text-garl-accent/70"
                      : "text-garl-muted"
                }`}
              >
                {l.label}
              </a>
            );
          })}
          <div className="h-4 w-px bg-garl-border" />
          <a
            href="https://github.com/Garl-Protocol/garl"
            target="_blank"
            rel="noopener noreferrer"
            className="font-mono text-xs uppercase tracking-wider text-garl-muted transition-colors hover:text-garl-accent"
          >
            GitHub
          </a>
          {clerkConfigured && (
            <>
              <div className="h-4 w-px bg-garl-border" />
              <SignedOut>
                <SignInButton mode="modal">
                  <button className="font-mono text-xs uppercase tracking-wider text-garl-muted transition-colors hover:text-garl-accent">
                    Sign in
                  </button>
                </SignInButton>
                <SignUpButton mode="modal">
                  <button className="rounded-md border border-garl-accent/40 bg-garl-accent/10 px-3 py-1.5 font-mono text-xs uppercase tracking-wider text-garl-accent transition-colors hover:bg-garl-accent/20">
                    Sign up
                  </button>
                </SignUpButton>
              </SignedOut>
              <SignedIn>
                <a
                  href="/account"
                  className="font-mono text-xs uppercase tracking-wider text-garl-muted transition-colors hover:text-garl-accent"
                >
                  My Account
                </a>
                <UserButton afterSignOutUrl="/" />
              </SignedIn>
            </>
          )}
        </nav>

        {/* Mobile hamburger — 44x44 tap target (Apple HIG / WCAG 2.5.5) */}
        <button
          ref={triggerRef}
          type="button"
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
          aria-controls={drawerId}
          onClick={() => setOpen((v) => !v)}
          className="inline-flex h-11 w-11 items-center justify-center rounded-md border border-garl-border bg-garl-surface text-garl-text transition-colors hover:border-garl-accent/40 active:scale-95 md:hidden"
        >
          {open ? (
            <X className="h-5 w-5" aria-hidden />
          ) : (
            <Menu className="h-5 w-5" aria-hidden />
          )}
        </button>
      </div>

      {/* Mobile drawer rendered via portal so the header's `backdrop-filter`
          containing block doesn't collapse the `position: fixed` overlay
          to the header's height (the actual root cause of the previous
          "click does nothing visible" bug). */}
      {mounted &&
        createPortal(
          <AnimatePresence>
            {open && (
              <motion.div
                key="garl-mobile-menu-root"
                className="fixed inset-0 z-[60] md:hidden"
                initial={reducedMotion ? false : { opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={reducedMotion ? { opacity: 1 } : { opacity: 0 }}
                transition={{ duration: 0.15 }}
                aria-modal="true"
                role="dialog"
                aria-label="Site navigation"
              >
                {/* Scrim */}
                <button
                  type="button"
                  aria-label="Close menu"
                  onClick={() => setOpen(false)}
                  className="absolute inset-0 h-full w-full bg-black/55 backdrop-blur-sm"
                />

                {/* Drawer panel */}
                <motion.div
                  ref={drawerRef}
                  id={drawerId}
                  initial={
                    reducedMotion ? { opacity: 0 } : { x: "100%", opacity: 1 }
                  }
                  animate={{ x: 0, opacity: 1 }}
                  exit={
                    reducedMotion ? { opacity: 0 } : { x: "100%", opacity: 1 }
                  }
                  transition={{ type: "tween", duration: 0.22, ease: "easeOut" }}
                  className="absolute right-0 top-0 flex h-full w-full max-w-[88vw] flex-col border-l border-garl-border bg-garl-bg shadow-2xl sm:max-w-sm"
                  style={{
                    paddingTop:
                      "calc(env(safe-area-inset-top, 0px) + 0.5rem)",
                    paddingBottom: "env(safe-area-inset-bottom, 0px)",
                  }}
                >
                  <div className="flex h-14 shrink-0 items-center justify-between border-b border-garl-border px-4">
                    <div className="flex items-center gap-2">
                      <div className="flex h-8 w-8 items-center justify-center rounded-md border border-garl-accent/30 bg-garl-accent/10">
                        <span className="font-mono text-sm font-bold text-garl-accent">
                          G
                        </span>
                      </div>
                      <span className="font-mono text-sm font-semibold tracking-wider text-garl-text">
                        GARL
                      </span>
                    </div>
                    <button
                      type="button"
                      aria-label="Close menu"
                      onClick={() => setOpen(false)}
                      className="inline-flex h-11 w-11 items-center justify-center rounded-md border border-garl-border bg-garl-surface text-garl-text transition-colors hover:border-garl-accent/40 active:scale-95"
                    >
                      <X className="h-5 w-5" aria-hidden />
                    </button>
                  </div>

                  <nav
                    className="flex-1 overflow-y-auto px-3 py-3"
                    aria-label="Primary mobile"
                  >
                    {LINKS.map((l, i) => {
                      const active = isActive(l.href);
                      return (
                        <a
                          key={l.href}
                          ref={i === 0 ? firstLinkRef : undefined}
                          href={l.href}
                          aria-current={active ? "page" : undefined}
                          onClick={() => setOpen(false)}
                          className={`mb-1 flex min-h-11 items-center gap-3 rounded-lg px-3 py-3 font-mono text-sm uppercase tracking-wider transition-colors active:bg-garl-surface/80 ${
                            active
                              ? "border border-garl-accent/40 bg-garl-accent/10 text-garl-accent"
                              : l.accent
                                ? "text-garl-accent hover:bg-garl-surface"
                                : "text-garl-text hover:bg-garl-surface"
                          }`}
                        >
                          <span className="flex-1">{l.label}</span>
                          {active && (
                            <span
                              className="h-1.5 w-1.5 rounded-full bg-garl-accent"
                              aria-hidden
                            />
                          )}
                        </a>
                      );
                    })}
                    <a
                      href="https://github.com/Garl-Protocol/garl"
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={() => setOpen(false)}
                      className="mt-3 flex min-h-11 items-center gap-2 rounded-lg border border-garl-accent/30 bg-garl-accent/10 px-3 py-3 font-mono text-xs uppercase tracking-wider text-garl-accent active:scale-[0.98]"
                    >
                      GitHub · Open source
                    </a>
                    {clerkConfigured && (
                      <div className="mt-3 border-t border-garl-border pt-3">
                        <SignedOut>
                          <SignInButton mode="modal">
                            <button className="mb-2 flex min-h-11 w-full items-center rounded-lg px-3 py-3 font-mono text-sm uppercase tracking-wider text-garl-text transition-colors hover:bg-garl-surface">
                              Sign in
                            </button>
                          </SignInButton>
                          <SignUpButton mode="modal">
                            <button className="flex min-h-11 w-full items-center rounded-lg border border-garl-accent/30 bg-garl-accent/10 px-3 py-3 font-mono text-sm uppercase tracking-wider text-garl-accent">
                              Sign up
                            </button>
                          </SignUpButton>
                        </SignedOut>
                        <SignedIn>
                          <a
                            href="/account"
                            onClick={() => setOpen(false)}
                            className="mb-2 flex min-h-11 items-center rounded-lg px-3 py-3 font-mono text-sm uppercase tracking-wider text-garl-text transition-colors hover:bg-garl-surface"
                          >
                            My Account
                          </a>
                          <div className="px-3 py-1">
                            <UserButton afterSignOutUrl="/" />
                          </div>
                        </SignedIn>
                      </div>
                    )}
                  </nav>

                  <div className="shrink-0 border-t border-garl-border px-4 py-3 font-mono text-[10px] text-garl-muted/70">
                    Apache 2.0 · Open source
                  </div>
                </motion.div>
              </motion.div>
            )}
          </AnimatePresence>,
          document.body,
        )}
    </header>
  );
}
