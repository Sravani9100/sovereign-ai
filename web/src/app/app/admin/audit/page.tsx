"use client";

import { useCallback, useEffect, useState } from "react";

import { AdminOnly } from "@/components/AdminOnly";
import { Badge, Button, Card, Empty, ErrorNotice, PageHeader, Table, Td, Th } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { bytes, dateTime, fileType } from "@/lib/format";
import type { AuditEvent } from "@/lib/types";

const PAGE = 50;

const FILTERS = [
  ["", "All events"],
  ["chat.answered", "Answers"],
  ["access.denied", "Access denied"],
  ["document.uploaded", "Uploads"],
  ["document.deleted", "Deletions"],
  ["grant.set", "Grants"],
  ["member.revoked", "Revocations"],
  ["model_profile.updated", "Model changes"],
] as const;

export default function AuditPage() {
  return (
    <AdminOnly>
      <Audit />
    </AdminOnly>
  );
}

function Audit() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [filter, setFilter] = useState("");
  const [more, setMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (before?: string) => {
      const params = new URLSearchParams({ limit: String(PAGE) });
      if (filter) params.set("event_type", filter);
      if (before) params.set("before", before);
      try {
        const page = await api<AuditEvent[]>(`/audit-events?${params}`);
        setEvents((current) => (before ? [...current, ...page] : page));
        setMore(page.length === PAGE);
      } catch (e) {
        setError(errorMessage(e));
      }
    },
    [filter],
  );

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
      <PageHeader
        title="Audit log"
        description="Append-only: the application's database role can't update or delete these rows. Events record who did what and which documents were used, never the text of questions or answers."
      />
      <div className="mb-4 flex flex-wrap gap-2">
        {FILTERS.map(([value, label]) => (
          <button
            key={value}
            onClick={() => setFilter(value)}
            className={`rounded-full border px-3 py-1 text-sm ${
              filter === value ? "border-accent bg-accent-soft text-accent" : "border-border bg-surface hover:border-accent"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      {error && <ErrorNotice message={error} />}
      <Card padded={false}>
        {events.length === 0 ? (
          <div className="p-5">
            <Empty title="No events" />
          </div>
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>When</Th>
                <Th>Event</Th>
                <Th>Who</Th>
                <Th>Details</Th>
              </tr>
            </thead>
            <tbody>
              {events.map((e) => (
                <tr key={e.id}>
                  <Td className="whitespace-nowrap text-muted">{dateTime(e.created_at)}</Td>
                  <Td>
                    <Badge tone={e.event_type === "access.denied" || e.event_type === "member.revoked" ? "danger" : "neutral"}>
                      {e.event_type}
                    </Badge>
                  </Td>
                  <Td className="text-muted">{e.actor_email ?? "system"}</Td>
                  <Td>
                    <Details event={e} />
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
      {more && (
        <div className="mt-4 text-center">
          <Button variant="secondary" onClick={() => load(events[events.length - 1]?.created_at)}>
            Load older events
          </Button>
        </div>
      )}
    </div>
  );
}

function Details({ event }: { event: AuditEvent }) {
  const d = event.details;
  if (event.event_type === "chat.answered") {
    const retrieved = (d.retrieved_documents as string[] | undefined)?.length ?? 0;
    const cited = (d.cited_documents as string[] | undefined)?.length ?? 0;
    return (
      <span className="text-xs text-muted">
        {String(d.model_profile)} ({d.external ? "external" : "local"}) · {plural(retrieved, "document")} searched ·{" "}
        {cited} cited
      </span>
    );
  }
  const entries = Object.entries(d).filter(([, v]) => v !== null && v !== undefined);
  if (entries.length === 0) return <span className="text-xs text-muted">{event.resource_type ?? ""}</span>;
  return <span className="text-xs text-muted">{entries.map(([k, v]) => `${label(k)}: ${value(k, v)}`).join(" · ")}</span>;
}

function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}

function label(key: string): string {
  return key.replace(/_/g, " ");
}

function value(key: string, v: unknown): string {
  if (Array.isArray(v)) return String(v.length);
  if (key === "mime_type") return fileType(String(v));
  if (key === "size_bytes") return bytes(Number(v));
  if (key.endsWith("_id")) return String(v).slice(0, 8);
  return String(v);
}
