import Link from "next/link";

import { LockIcon } from "@/components/ui";
import { locationLabel } from "@/lib/format";
import type { Citation } from "@/lib/types";

export function SourceList({
  citations,
  selected,
  onSelect,
}: {
  citations: Citation[];
  selected: Citation | null;
  onSelect: (c: Citation) => void;
}) {
  if (citations.length === 0) return null;
  return (
    <ul className="mt-3 flex flex-wrap gap-2">
      {citations.map((c) => (
        <li key={c.marker}>
          <button
            type="button"
            onClick={() => onSelect(c)}
            className={`flex max-w-72 items-center gap-2 rounded-lg border px-2.5 py-1.5 text-left text-xs transition ${
              selected?.marker === c.marker ? "border-accent bg-accent-soft" : "border-border bg-surface hover:border-accent"
            }`}
          >
            <span className="font-semibold text-accent">{c.marker}</span>
            {c.restricted ? (
              <span className="flex items-center gap-1 text-muted">
                <LockIcon /> Restricted document
              </span>
            ) : (
              <span className="truncate">
                {c.document_title}
                {locationLabel(c.location) && <span className="text-muted"> · {locationLabel(c.location)}</span>}
              </span>
            )}
          </button>
        </li>
      ))}
    </ul>
  );
}

export function SourceDetail({ citation, onClose }: { citation: Citation; onClose: () => void }) {
  return (
    <div className="rounded-xl border border-border bg-surface">
      <div className="flex items-start justify-between gap-3 border-b border-border px-4 py-3">
        <div className="min-w-0">
          <div className="text-xs font-semibold uppercase tracking-wide text-muted">Source {citation.marker}</div>
          <div className="mt-0.5 font-medium">{citation.restricted ? "Restricted document" : citation.document_title}</div>
          {locationLabel(citation.location) && (
            <div className="text-sm text-muted">{locationLabel(citation.location)}</div>
          )}
        </div>
        <button onClick={onClose} className="text-muted hover:text-text" aria-label="Close source">
          ✕
        </button>
      </div>
      <div className="px-4 py-3 text-sm">
        {citation.restricted ? (
          <p className="flex gap-2 text-muted">
            <LockIcon className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            You had access to this document when the answer was written, but not anymore, so its content and title
            are hidden.
          </p>
        ) : (
          <>
            <blockquote className="max-h-80 overflow-y-auto whitespace-pre-wrap border-l-2 border-accent pl-3 leading-relaxed text-muted">
              {citation.quote}
            </blockquote>
            {citation.document_id && (
              <Link href={`/app/knowledge/${citation.document_id}`} className="mt-3 inline-block text-accent underline">
                Open document
              </Link>
            )}
          </>
        )}
      </div>
    </div>
  );
}
