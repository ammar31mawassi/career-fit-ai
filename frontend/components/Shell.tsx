"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type CSSProperties, type ReactNode } from "react";
import { BriefcaseBusiness, LogOut, ShieldCheck, UserRound, Waypoints } from "lucide-react";

const nav = [
  { href: "/", label: "Opportunities", icon: BriefcaseBusiness },
  { href: "/profile", label: "My profile", icon: UserRound }
];

export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const activeIndex = Math.max(0, nav.findIndex((item) => item.href === pathname));
  const [indicatorIndex, setIndicatorIndex] = useState(activeIndex);

  useEffect(() => setIndicatorIndex(activeIndex), [activeIndex]);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header-inner">
          <Link className="brand" href="/" prefetch={false} aria-label="CareerFit home">
            <span className="brand-mark"><Waypoints size={18} aria-hidden /></span>
            <span className="brand-copy"><strong>CareerFit</strong><small>Evidence-led matching</small></span>
          </Link>

          <nav
            aria-label="Primary"
            className="nav-hub"
            onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) setIndicatorIndex(activeIndex); }}
            onMouseLeave={() => setIndicatorIndex(activeIndex)}
            style={{ "--hub-index": indicatorIndex } as CSSProperties}
          >
            <span className="nav-hub-indicator" aria-hidden />
            {nav.map((item, index) => {
              const Icon = item.icon;
              const active = pathname === item.href;
              return (
                <Link
                  aria-current={active ? "page" : undefined}
                  className={active ? "active" : ""}
                  href={item.href}
                  prefetch={false}
                  key={item.href}
                  onFocus={() => setIndicatorIndex(index)}
                  onMouseEnter={() => setIndicatorIndex(index)}
                >
                  <Icon size={16} aria-hidden />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </nav>

          <div className="header-actions">
            <span className="trust-badge"><ShieldCheck size={14} /> Private evidence</span>
            <form action="/auth/logout" className="logout-form" method="post">
              <button aria-label="Sign out" title="Sign out" type="submit"><LogOut size={16} aria-hidden /></button>
            </form>
          </div>
        </div>
      </header>
      <main className="workspace">{children}</main>
    </div>
  );
}
