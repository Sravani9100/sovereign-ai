"use client";

import { useState } from "react";

import { Button, ErrorNotice, Field, inputClass } from "@/components/ui";
import { errorMessage, request } from "@/lib/api";
import type { Space } from "@/lib/types";

const ACCEPT = ".pdf,.docx,.md,.markdown,.txt";

/** Upload a new document, or a new version when `documentId` is given. */
export function UploadForm({
  spaces = [],
  documentId,
  onDone,
}: {
  spaces?: Space[];
  documentId?: string;
  onDone: () => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [spaceId, setSpaceId] = useState(spaces[0]?.id ?? "");
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setError(null);
    const form = new FormData();
    form.append("file", file);
    if (!documentId) {
      form.append("space_id", spaceId);
      if (title.trim()) form.append("title", title.trim());
    }
    try {
      await request(documentId ? `/documents/${documentId}/versions` : "/documents", { method: "POST", body: form });
      setFile(null);
      setTitle("");
      onDone();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <label
        className="flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-border px-4 py-6 text-center text-sm transition hover:border-accent"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          setFile(e.dataTransfer.files[0] ?? null);
        }}
      >
        <input type="file" accept={ACCEPT} className="sr-only" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        {file ? (
          <span className="font-medium">{file.name}</span>
        ) : (
          <>
            <span className="font-medium">Drop a file or click to choose</span>
            <span className="mt-1 text-xs text-muted">PDF (with a text layer), DOCX, Markdown, or text · up to 20 MB</span>
          </>
        )}
      </label>
      {!documentId && (
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Space">
            <select className={inputClass} value={spaceId} onChange={(e) => setSpaceId(e.target.value)}>
              {spaces.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                  {s.classification === "confidential" ? " (confidential)" : ""}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Title (optional)">
            <input className={inputClass} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="From the file name" />
          </Field>
        </div>
      )}
      {error && <ErrorNotice message={error} />}
      <Button type="submit" disabled={!file || busy || (!documentId && !spaceId)}>
        {busy ? "Uploading…" : documentId ? "Upload new version" : "Upload"}
      </Button>
    </form>
  );
}
