"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { use, useCallback, useEffect, useState } from "react";

import { UploadForm } from "@/components/UploadForm";
import { Button, Card, Empty, ErrorNotice, Table, Td, Th, VersionStatusBadge } from "@/components/ui";
import { api, ApiError, errorMessage } from "@/lib/api";
import { bytes, dateTime, fileType } from "@/lib/format";
import type { DocumentDetail } from "@/lib/types";

export default function DocumentPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [doc, setDoc] = useState<DocumentDetail | null>(null);
  const [missing, setMissing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const load = useCallback(() => {
    api<DocumentDetail>(`/documents/${id}`)
      .then(setDoc)
      .catch((e) => (e instanceof ApiError && e.status === 404 ? setMissing(true) : setError(errorMessage(e))));
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const indexing = doc?.versions.some((v) => v.status === "pending" || v.status === "processing");
  useEffect(() => {
    if (!indexing) return;
    const timer = setInterval(load, 2000);
    return () => clearInterval(timer);
  }, [indexing, load]);

  async function remove() {
    try {
      await api(`/documents/${id}`, { method: "DELETE" });
      router.push("/app/knowledge");
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  if (missing) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
        <Empty title="Document not found">
          It doesn&apos;t exist, or you don&apos;t have access to it. SovereignAI doesn&apos;t say which, so document IDs
          can&apos;t be probed.
        </Empty>
      </div>
    );
  }
  if (!doc) return <p className="px-6 py-8 text-sm text-muted">{error ?? "Loading…"}</p>;

  return (
    <div className="mx-auto max-w-5xl space-y-6 px-4 py-8 sm:px-6">
      <div>
        <Link href="/app/knowledge" className="text-sm text-muted hover:text-text">
          ← Knowledge
        </Link>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold">{doc.title}</h1>
          <VersionStatusBadge status={doc.status} />
        </div>
        <p className="mt-1 text-sm text-muted">{doc.space_name}</p>
      </div>
      {error && <ErrorNotice message={error} />}

      <Card title="Versions" padded={false}>
        <Table>
          <thead>
            <tr>
              <Th>Version</Th>
              <Th>File</Th>
              <Th>Status</Th>
              <Th>Indexed</Th>
              <Th className="text-right">Uploaded</Th>
            </tr>
          </thead>
          <tbody>
            {doc.versions.map((v) => (
              <tr key={v.id}>
                <Td>
                  v{v.version_no}
                  {v.id === doc.current_version_id && <span className="ml-2 text-xs text-accent">in use</span>}
                </Td>
                <Td>
                  <div>{v.filename}</div>
                  <div className="text-xs text-muted">
                    {fileType(v.mime_type)} · {bytes(v.size_bytes)}
                  </div>
                </Td>
                <Td>
                  <VersionStatusBadge status={v.status} />
                  {v.error && <div className="mt-1 max-w-xs text-xs text-danger">{v.error}</div>}
                </Td>
                <Td className="text-muted">
                  {v.status === "ready" ? (
                    <>
                      {v.chunk_count} chunks
                      <div className="text-xs">{v.embedding_model}</div>
                    </>
                  ) : (
                    "-"
                  )}
                </Td>
                <Td className="text-right text-muted">{dateTime(v.created_at)}</Td>
              </tr>
            ))}
          </tbody>
        </Table>
      </Card>

      {doc.can_edit && (
        <div className="grid gap-6 md:grid-cols-2">
          <Card title="Upload a new version">
            <p className="mb-4 text-sm text-muted">
              Answers switch to the new version once it&apos;s indexed. Earlier answers keep citing the version they used.
            </p>
            <UploadForm documentId={doc.id} onDone={load} />
          </Card>
          <Card title="Delete document">
            <p className="mb-4 text-sm text-muted">
              Removes every version and its search index. Past answers keep their text, but their citations to this
              document can no longer be opened.
            </p>
            {confirmDelete ? (
              <div className="flex gap-2">
                <Button variant="danger" onClick={remove}>
                  Delete permanently
                </Button>
                <Button variant="secondary" onClick={() => setConfirmDelete(false)}>
                  Cancel
                </Button>
              </div>
            ) : (
              <Button variant="danger" onClick={() => setConfirmDelete(true)}>
                Delete…
              </Button>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
