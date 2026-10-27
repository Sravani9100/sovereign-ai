"use client";

import { useCallback, useEffect, useState } from "react";

import { AdminOnly } from "@/components/AdminOnly";
import { Badge, Button, Card, ErrorNotice, PageHeader } from "@/components/ui";
import { api, errorMessage, json } from "@/lib/api";
import type { Classification, ModelProfile } from "@/lib/types";

export default function ModelsPage() {
  return (
    <AdminOnly>
      <Models />
    </AdminOnly>
  );
}

const PROVIDERS: Record<ModelProfile["provider"], string> = {
  anthropic: "Anthropic API (external)",
  ollama: "Ollama (your infrastructure)",
  fake: "Test model",
};

function Models() {
  const [profiles, setProfiles] = useState<ModelProfile[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api<ModelProfile[]>("/model-profiles").then(setProfiles).catch((e) => setError(errorMessage(e)));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function update(id: string, body: Partial<ModelProfile>) {
    setError(null);
    try {
      await api(`/model-profiles/${id}`, { method: "PATCH", body: json(body) });
      load();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
      <PageHeader
        title="AI models"
        description="Approved models people can choose in chat. Each one has a data ceiling: the most sensitive space whose content may be sent to it. Retrieval enforces it, so a confidential passage is never part of a request to a model capped at internal."
      />
      {error && (
        <div className="mb-4">
          <ErrorNotice message={error} />
        </div>
      )}
      <div className="space-y-4">
        {profiles.map((p) => (
          <Card
            key={p.id}
            title={
              <span className="flex flex-wrap items-center gap-2">
                {p.name}
                {p.is_default && <Badge tone="accent">Default</Badge>}
                {!p.enabled && <Badge>Disabled</Badge>}
              </span>
            }
            action={
              <div className="flex gap-2">
                {p.enabled && !p.is_default && (
                  <Button size="sm" variant="secondary" onClick={() => update(p.id, { is_default: true })}>
                    Make default
                  </Button>
                )}
                <Button size="sm" variant="secondary" onClick={() => update(p.id, { enabled: !p.enabled })}>
                  {p.enabled ? "Disable" : "Enable"}
                </Button>
              </div>
            }
          >
            <dl className="grid gap-4 text-sm sm:grid-cols-3">
              <div>
                <dt className="text-xs uppercase tracking-wide text-muted">Provider</dt>
                <dd className="mt-1">{PROVIDERS[p.provider]}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-muted">Model</dt>
                <dd className="mt-1 font-mono text-xs">{p.model}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-muted">May receive</dt>
                <dd className="mt-1">
                  <select
                    aria-label={`Data ceiling for ${p.name}`}
                    value={p.max_classification}
                    onChange={(e) => update(p.id, { max_classification: e.target.value as Classification })}
                    className="rounded-lg border border-border bg-surface px-2 py-1 text-sm"
                  >
                    <option value="internal">Internal content only</option>
                    <option value="confidential">Internal and confidential</option>
                  </select>
                </dd>
              </div>
            </dl>
            {p.external && p.max_classification === "confidential" && (
              <p className="mt-4 rounded-lg bg-warn-soft px-3 py-2 text-sm text-warn">
                Confidential content will be sent to an external provider. Make sure your data processing agreement
                covers it. This change is recorded in the audit log.
              </p>
            )}
            {p.provider === "ollama" && !p.enabled && (
              <p className="mt-4 text-sm text-muted">
                Enable once Ollama is running and serving <code className="font-mono">{p.model}</code>.
              </p>
            )}
          </Card>
        ))}
      </div>
    </div>
  );
}
