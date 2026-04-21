"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import "./globals.css";
import AuthProvider, { useAuth } from "./components/AuthProvider";
import AuthGuard from "./components/AuthGuard";

const NAV = [
  { href: "/", label: "New Campaign" },
  { href: "/campaigns", label: "Campaigns" },
  { href: "/inbox", label: "Inbox" },
  { href: "/activity", label: "Activity" },
  { href: "/settings", label: "Settings" },
];

function TopNav() {
  const pathname = usePathname();
  const { user, signOut } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 bg-surface/80 backdrop-blur-md border-b border-border">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
        {/* Logo */}
        <Link
          href="/"
          className="text-lg font-bold tracking-tight text-text-primary shrink-0"
        >
          Cold<span className="text-accent">Pilot</span>
        </Link>

        {/* Desktop nav — only on lg+ so it never crowds */}
        <nav className="hidden lg:flex items-center gap-0.5">
          {NAV.map((item) => {
            const active =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`px-3 py-2 rounded-lg text-sm transition-colors whitespace-nowrap ${
                  active
                    ? "bg-accent/10 text-accent font-medium"
                    : "text-text-secondary hover:text-text-primary hover:bg-surface-elevated"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* Desktop user */}
        {user && (
          <div className="hidden lg:flex items-center shrink-0">
            <button
              onClick={signOut}
              className="text-xs text-text-secondary hover:text-red transition-colors"
            >
              Sign out
            </button>
          </div>
        )}
        {!user && <div className="hidden lg:block w-16" />}

        {/* Hamburger — shows on everything below lg (1024px) */}
        <button
          className="lg:hidden p-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-surface-elevated transition-colors"
          onClick={() => setMenuOpen((o) => !o)}
          aria-label="Toggle navigation menu"
        >
          {menuOpen ? (
            <svg
              className="w-5 h-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          ) : (
            <svg
              className="w-5 h-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M4 6h16M4 12h16M4 18h16"
              />
            </svg>
          )}
        </button>
      </div>

      {/* Mobile/tablet dropdown */}
      {menuOpen && (
        <div className="lg:hidden border-t border-border bg-surface/95 backdrop-blur-md px-4 py-3 space-y-1">
          {NAV.map((item) => {
            const active =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setMenuOpen(false)}
                className={`flex items-center px-3 py-2.5 rounded-lg text-sm transition-colors ${
                  active
                    ? "bg-accent/10 text-accent font-medium"
                    : "text-text-secondary hover:text-text-primary hover:bg-surface-elevated"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
          {user && (
            <div className="pt-2 mt-1 border-t border-border">
              <button
                onClick={() => {
                  setMenuOpen(false);
                  signOut();
                }}
                className="w-full text-left px-3 py-2.5 text-sm text-red hover:text-red/80 transition-colors"
              >
                Sign out
              </button>
            </div>
          )}
        </div>
      )}
    </header>
  );
}

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="h-full antialiased">
      <head>
        <title>ColdPilot</title>
        <meta name="description" content="Autonomous cold outreach agent" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </head>
      <body className="min-h-screen bg-background text-text-primary">
        <AuthProvider>
          <AuthGuard>
            <TopNav />
            <main className="max-w-5xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
              {children}
            </main>
          </AuthGuard>
        </AuthProvider>
      </body>
    </html>
  );
}
