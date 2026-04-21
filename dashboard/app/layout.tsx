"use client";

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

  return (
    <header className="sticky top-0 z-50 bg-surface/80 backdrop-blur-md border-b border-border">
      <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
        {/* Logo */}
        <Link href="/" className="text-lg font-bold tracking-tight text-text-primary shrink-0">
          Cold<span className="text-accent">Pilot</span>
        </Link>

        {/* Nav links */}
        <nav className="flex items-center gap-1">
          {NAV.map((item) => {
            const active =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`px-4 py-2 rounded-lg text-sm transition-colors ${
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

        {/* User */}
        {user && (
          <div className="flex items-center gap-3 shrink-0">
            <span className="text-xs text-text-muted hidden sm:inline truncate max-w-[160px]">
              {user.email}
            </span>
            <button
              onClick={signOut}
              className="text-xs text-text-secondary hover:text-red transition-colors"
            >
              Sign out
            </button>
          </div>
        )}
        {!user && <div className="w-16" />}
      </div>
    </header>
  );
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="h-full antialiased">
      <head>
        <title>ColdPilot</title>
        <meta name="description" content="Autonomous cold outreach agent" />
      </head>
      <body className="min-h-screen bg-background text-text-primary">
        <AuthProvider>
          <AuthGuard>
            <TopNav />
            <main className="max-w-5xl mx-auto px-6 py-8">{children}</main>
          </AuthGuard>
        </AuthProvider>
      </body>
    </html>
  );
}
