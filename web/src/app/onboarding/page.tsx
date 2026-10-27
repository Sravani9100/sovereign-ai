"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Logo } from "@/components/Logo";
import { Button, ErrorNotice, Field, inputClass } from "@/components/ui";
import { api, errorMessage, json, setActiveOrg } from "@/lib/api";
import type { OrgMembership } from "@/lib/types";

function slugify(name: string): string {
  return name
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60);
}

export default function OnboardingPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const org = await api<OrgMembership>("/organizations", {
        method: "POST",
        body: json({ name, slug: slugify(name) }),
      });
      setActiveOrg(org.organization_id);
      router.push("/app/knowledge");
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-4">
      <Logo className="text-lg" />
      <h1 className="mt-6 text-2xl font-semibold">Create your organization</h1>
      <p className="mt-2 text-sm text-muted">
        You&apos;ll be its owner. It starts with a Company Handbook space everyone can read, and an external model
        that is only allowed to see internal (not confidential) content.
      </p>
      <form onSubmit={create} className="mt-6 space-y-4 rounded-xl border border-border bg-surface p-5">
        <Field label="Organization name">
          <input className={inputClass} value={name} onChange={(e) => setName(e.target.value)} placeholder="Musterwerk GmbH" required minLength={2} />
        </Field>
        {error && <ErrorNotice message={error} />}
        <Button type="submit" disabled={busy || slugify(name).length < 2} className="w-full">
          {busy ? "Creating…" : "Create organization"}
        </Button>
      </form>
    </main>
  );
}
