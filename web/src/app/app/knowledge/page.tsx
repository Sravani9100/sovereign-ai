"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { UploadForm } from "@/components/UploadForm";
import {
  Button,
  Card,
  ClassificationBadge,
  Empty,
  ErrorNotice,
  LockIcon,
  PageHeader,
  Table,
  Td,
  Th,
  VersionStatusBadge,
} from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { timeAgo } from "@/lib/format";
import { useSession } from "@/lib/session";
import type { DocumentSummary, Space } from "@/lib/types";

export default function KnowledgePage() {
  const { me } = useSession();
  const [spaces, setSpaces] = useState<Space[]>([]);
  const [documents, setDocuments] = useState<DocumentSummary[] | null>(null);
  const [filter, setFilter] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [s, d] = await Promise.all([api<Space[]>("/knowledge/spaces"), api<DocumentSummary[]>("/documents")]);
      setSpaces(s);
      setDocuments(d);
    } catch (e) {
      setError(errorMessage(e));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Poll while anything is still being indexed.
  const indexing = documents?.some((d) => d.status === "pending" || d.status === "processing");
  useEffect(() => {
    if (!indexing) return;
    const timer = setInterval(load, 2000);
    return () => clearInterval(timer);
  }, [indexing, load]);

  const readable = spaces.filter((s) => s.can_read);
  const editable = me.read_only ? [] : spaces.filter((s) => s.can_edit);
  const hidden = spaces.filter((s) => !s.can_read);
  const shown = documents?.filter((d) => !filter || d.space_id === filter) ?? [];

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
      <PageHeader
        title="Knowledge"
        description="Documents you can read, grouped into spaces. Access is granted per space to everyone, a team, or a person."
        action={
          editable.length > 0 && (
            <Button onClick={() => setUploading((u) => !u)} variant={uploading ? "secondary" : "primary"}>
              {uploading ? "Close" : "Upload document"}
            </Button>
          )
        }
      />
      {error && <ErrorNotice message={error} />}

      {uploading && (
        <Card title="Upload a document" className="mb-6">
          <UploadForm
            spaces={editable}
            onDone={() => {
              setUploading(false);
              load();
            }}
          />
        </Card>
      )}

      <div className="mb-4 flex flex-wrap gap-2">
        <SpaceChip active={!filter} onClick={() => setFilter(null)} label="All spaces" count={documents?.length} />
        {readable.map((s) => (
          <SpaceChip
            key={s.id}
            active={filter === s.id}
            onClick={() => setFilter(s.id)}
            label={s.name}
            count={s.document_count}
            confidential={s.classification === "confidential"}
          />
        ))}
      </div>

      <Card padded={false}>
        {documents === null ? (
          <p className="p-5 text-sm text-muted">Loading…</p>
        ) : shown.length === 0 ? (
          <div className="p-5">
            <Empty title="No documents here yet">
              {editable.length > 0 ? "Upload a PDF, DOCX, or Markdown file to get started." : "Ask an editor to add documents."}
            </Empty>
          </div>
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>Document</Th>
                <Th>Space</Th>
                <Th>Status</Th>
                <Th className="text-right">Added</Th>
              </tr>
            </thead>
            <tbody>
              {shown.map((d) => {
                const space = spaces.find((s) => s.id === d.space_id);
                return (
                  <tr key={d.id} className="hover:bg-surface-2/50">
                    <Td>
                      <Link href={`/app/knowledge/${d.id}`} className="font-medium hover:text-accent">
                        {d.title}
                      </Link>
                    </Td>
                    <Td>
                      <span className="flex items-center gap-2">
                        {d.space_name}
                        {space?.classification === "confidential" && <ClassificationBadge value="confidential" />}
                      </span>
                    </Td>
                    <Td>
                      <VersionStatusBadge status={d.status} />
                    </Td>
                    <Td className="text-right text-muted">{timeAgo(d.created_at)}</Td>
                  </tr>
                );
              })}
            </tbody>
          </Table>
        )}
      </Card>

      {hidden.length > 0 && (
        <p className="mt-4 flex items-center gap-2 text-sm text-muted">
          <LockIcon className="h-3.5 w-3.5" />
          {hidden.length} other {hidden.length === 1 ? "space exists" : "spaces exist"} that you manage but can&apos;t read
          ({hidden.map((s) => s.name).join(", ")}). Admins read through grants like everyone else.
        </p>
      )}
    </div>
  );
}

function SpaceChip({
  label,
  count,
  active,
  confidential,
  onClick,
}: {
  label: string;
  count?: number;
  active: boolean;
  confidential?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm transition ${
        active ? "border-accent bg-accent-soft text-accent" : "border-border bg-surface hover:border-accent"
      }`}
    >
      {confidential && <LockIcon className="h-3 w-3 text-secret" />}
      {label}
      {count !== undefined && <span className="text-xs text-muted">{count}</span>}
    </button>
  );
}
