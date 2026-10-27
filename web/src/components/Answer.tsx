import ReactMarkdown from "react-markdown";

import { LockIcon } from "@/components/ui";
import type { Citation } from "@/lib/types";

/**
 * Model-written markdown with [n] markers turned into citation chips.
 * react-markdown escapes raw HTML, so an answer can't inject markup.
 */
export function Answer({
  content,
  citations,
  onCite,
  selected,
}: {
  content: string;
  citations: Citation[];
  onCite: (citation: Citation) => void;
  selected?: Citation | null;
}) {
  const byMarker = new Map(citations.map((c) => [c.marker, c]));
  const linked = content.replace(/\[(\d+)\]/g, "[$1](#cite-$1)");

  return (
    <div className="markdown text-[0.94rem] leading-relaxed">
      <ReactMarkdown
        components={{
          a: ({ href, children }) => {
            const marker = href?.startsWith("#cite-") ? Number(href.slice(6)) : null;
            if (marker === null) {
              return (
                <a href={href} className="text-accent underline" target="_blank" rel="noreferrer">
                  {children}
                </a>
              );
            }
            const citation = byMarker.get(marker);
            if (!citation) {
              // Still streaming, or a marker the server dropped: show it inert.
              return <sup className="mx-0.5 text-xs text-muted">[{marker}]</sup>;
            }
            const active = selected?.marker === marker;
            return (
              <button
                type="button"
                onClick={() => onCite(citation)}
                title={citation.restricted ? "You no longer have access to this source" : citation.document_title}
                className={`mx-0.5 inline-flex -translate-y-px items-center gap-0.5 rounded-md px-1.5 align-middle text-xs font-medium transition ${
                  citation.restricted
                    ? "bg-surface-2 text-muted"
                    : active
                      ? "bg-accent text-white dark:text-bg"
                      : "bg-accent-soft text-accent hover:bg-accent hover:text-white dark:hover:text-bg"
                }`}
              >
                {citation.restricted && <LockIcon className="h-2.5 w-2.5" />}
                {marker}
              </button>
            );
          },
        }}
      >
        {linked}
      </ReactMarkdown>
    </div>
  );
}
