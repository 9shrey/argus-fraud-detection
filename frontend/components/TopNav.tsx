"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

const LINKS = [
  { href: "/", label: "Live Feed" },
  { href: "/metrics", label: "Model Metrics" },
];

export function TopNav() {
  const pathname = usePathname();
  const [theme, setTheme] = useState<"light" | "dark" | null>(null);

  useEffect(() => {
    // localStorage isn't available during SSR, so this can only run
    // post-mount — the one legitimate case for setState directly in an
    // effect (there's no external subscription to hang it off).
    const stored = window.localStorage.getItem("argus-theme");
    if (stored === "light" || stored === "dark") {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setTheme(stored);
      document.documentElement.dataset.theme = stored;
    }
  }, []);

  function toggle() {
    const next =
      theme === "dark"
        ? "light"
        : theme === "light"
          ? null
          : window.matchMedia("(prefers-color-scheme: dark)").matches
            ? "light"
            : "dark";
    setTheme(next);
    if (next) {
      document.documentElement.dataset.theme = next;
      window.localStorage.setItem("argus-theme", next);
    } else {
      delete document.documentElement.dataset.theme;
      window.localStorage.removeItem("argus-theme");
    }
  }

  return (
    <nav className="topnav">
      <div className="topnav-inner">
        <Link href="/" className="brand">
          <span className="brand-mark" />
          Argus
        </Link>
        <div className="nav-links">
          {LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={`nav-link${pathname === link.href ? " active" : ""}`}
            >
              {link.label}
            </Link>
          ))}
        </div>
        <button type="button" className="theme-toggle" onClick={toggle}>
          {theme === "dark" ? "Dark" : theme === "light" ? "Light" : "Auto"}
        </button>
      </div>
    </nav>
  );
}
