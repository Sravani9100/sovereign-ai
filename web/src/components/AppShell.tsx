"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { Logo } from "@/components/Logo";
import { useSession } from "@/lib/session";

const MAIN = [
  { href: "/app/chat", label: "Chat" },
  { href: "/app/knowledge", label: "Knowledge" },
];

const ADMIN = [
  { href: "/app/admin/access", label: "Spaces & access" },
  { href: "/app/admin/members", label: "Members & teams" },
  { href: "/app/admin/models", label: "AI models" },
  { href: "/app/admin/audit", label: "Audit log" },
];

function NavLink({ href, label }: { href: string; label: string }) {
  const active = usePathname().startsWith(href);
  return (
    <Link
      href={href}
      className={`block rounded-lg px-3 py-1.5 text-sm transition ${
        active ? "bg-accent-soft font-medium text-accent" : "text-muted hover:bg-surface-2 hover:text-text"
      }`}
    >
      {label}
    </Link>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { me, org, isAdmin, switchOrg, logout } = useSession();

  return (
    <div className="min-h-screen lg:flex">
      <aside className="border-b border-border bg-surface lg:sticky lg:top-0 lg:flex lg:h-screen lg:w-60 lg:shrink-0 lg:flex-col lg:border-r lg:border-b-0">
        <div className="flex items-center justify-between gap-3 px-4 py-3 lg:block lg:px-4 lg:py-4">
          <Link href="/app/chat">
            <Logo />
          </Link>
          <select
            aria-label="Organization"
            value={org.organization_id}
            onChange={(e) => switchOrg(e.target.value)}
            disabled={me.organizations.length < 2}
            className="max-w-48 rounded-lg border border-border bg-surface px-2 py-1.5 text-sm lg:mt-4 lg:w-full lg:max-w-none"
          >
            {me.organizations.map((o) => (
              <option key={o.organization_id} value={o.organization_id}>
                {o.name}
              </option>
            ))}
          </select>
        </div>

        <nav className="flex gap-1 overflow-x-auto px-3 pb-3 lg:block lg:flex-1 lg:space-y-1 lg:overflow-visible lg:pb-0">
          {MAIN.map((item) => (
            <NavLink key={item.href} {...item} />
          ))}
          {isAdmin && (
            <>
              <div className="hidden px-3 pt-5 pb-1 text-xs font-semibold uppercase tracking-wide text-muted lg:block">
                Administration
              </div>
              {ADMIN.map((item) => (
                <NavLink key={item.href} {...item} />
              ))}
            </>
          )}
          <button
            onClick={logout}
            className="shrink-0 rounded-lg px-3 py-1.5 text-sm text-muted hover:bg-surface-2 lg:hidden"
          >
            Sign out
          </button>
        </nav>

        <div className="hidden border-t border-border px-4 py-3 text-sm lg:block">
          <div className="truncate font-medium">{me.display_name}</div>
          <div className="truncate text-xs text-muted">
            {me.email} · {org.role}
          </div>
          <button onClick={logout} className="mt-2 text-xs text-muted underline hover:text-text">
            Sign out
          </button>
        </div>
      </aside>

      <main className="min-w-0 flex-1">{children}</main>
    </div>
  );
}
