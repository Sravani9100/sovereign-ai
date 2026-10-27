"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { LoginForm } from "@/components/LoginForm";
import { Logo } from "@/components/Logo";
import { ErrorNotice } from "@/components/ui";
import { api, errorMessage, json, setActiveOrg } from "@/lib/api";
import type { Me } from "@/lib/types";

const DEMO_PASSWORD = "demo-password-2026";

// Seeded by demo-data/seed.py. Each one shows a different slice of the permission model.
const DEMO_USERS = [
  { email: "anna.schmidt@musterwerk.example", name: "Anna Schmidt", role: "Owner, Musterwerk", note: "Manages members, access, models, and the audit log" },
  { email: "ben.weber@musterwerk.example", name: "Ben Weber", role: "Engineer", note: "Reads manuals; can't see HR or Finance" },
  { email: "clara.fischer@musterwerk.example", name: "Clara Fischer", role: "HR editor", note: "Reads confidential salary bands; uploads policies" },
  { email: "david.koch@musterwerk.example", name: "David Koch", role: "Finance", note: "Reads procurement and supplier contracts" },
  { email: "felix.wagner@consulting.example", name: "Felix Wagner", role: "Consultant", note: "Member of both companies; sees one at a time" },
  { email: "eva.braun@rheintech.example", name: "Eva Braun", role: "Owner, RheinTech", note: "A separate tenant with overlapping documents" },
];

export default function LoginPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function enter(me: Me) {
    setActiveOrg(me.organizations[0]?.organization_id ?? null);
    router.push(me.organizations.length ? "/app/chat" : "/onboarding");
  }

  // Demo addresses (.example) can't receive email, so demo buttons use the shared password.
  async function signInAsDemo(email: string) {
    setBusy(true);
    setError(null);
    try {
      enter(await api<Me>("/auth/login", { method: "POST", body: json({ email, password: DEMO_PASSWORD }) }));
    } catch (e) {
      setError(errorMessage(e));
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto grid min-h-screen max-w-5xl items-center gap-10 px-4 py-10 sm:px-6 lg:grid-cols-2">
      <div>
        <Logo className="text-lg" />
        <h1 className="mt-6 text-3xl font-semibold leading-tight">
          Ask your company&apos;s documents.
          <br />
          The AI only sees what you&apos;re allowed to read.
        </h1>
        <p className="mt-4 text-muted">
          Permissions are enforced before retrieval, so confidential content never reaches the model for people
          without access. Confidential spaces never leave for external AI providers. Every answer cites its
          sources.
        </p>
        <div className="mt-8">
          <LoginForm onSignedIn={enter} />
        </div>
      </div>

      <div>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">Try a demo account</h2>
        <p className="mt-1 text-sm text-muted">
          Two fictional companies with synthetic documents. Sign in as different people and ask the same question.
        </p>
        <ul className="mt-4 space-y-2">
          {DEMO_USERS.map((user) => (
            <li key={user.email}>
              <button
                type="button"
                disabled={busy}
                onClick={() => signInAsDemo(user.email)}
                className="w-full rounded-xl border border-border bg-surface px-4 py-3 text-left transition hover:border-accent disabled:opacity-50"
              >
                <div className="flex items-baseline justify-between gap-3">
                  <span className="font-medium">{user.name}</span>
                  <span className="text-xs text-muted">{user.role}</span>
                </div>
                <div className="mt-0.5 text-sm text-muted">{user.note}</div>
              </button>
            </li>
          ))}
        </ul>
        {error && (
          <div className="mt-3">
            <ErrorNotice message={error} />
          </div>
        )}
      </div>
    </main>
  );
}
