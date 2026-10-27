"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Logo } from "@/components/Logo";
import { Button, ErrorNotice, Field, inputClass } from "@/components/ui";
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
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function signIn(address: string, secret: string) {
    setBusy(true);
    setError(null);
    try {
      const me = await api<Me>("/auth/login", { method: "POST", body: json({ email: address, password: secret }) });
      setActiveOrg(me.organizations[0]?.organization_id ?? null);
      router.push(me.organizations.length ? "/app/chat" : "/onboarding");
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
        <form
          className="mt-8 space-y-4 rounded-xl border border-border bg-surface p-5"
          onSubmit={(e) => {
            e.preventDefault();
            signIn(email, password);
          }}
        >
          <Field label="Email">
            <input className={inputClass} type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </Field>
          <Field label="Password">
            <input className={inputClass} type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </Field>
          {error && <ErrorNotice message={error} />}
          <Button type="submit" disabled={busy} className="w-full">
            {busy ? "Signing in…" : "Sign in"}
          </Button>
        </form>
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
                onClick={() => signIn(user.email, DEMO_PASSWORD)}
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
      </div>
    </main>
  );
}
