import type { Classification, VersionStatus } from "@/lib/types";

export function Card({
  title,
  action,
  children,
  className = "",
  padded = true,
}: {
  title?: React.ReactNode;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  padded?: boolean;
}) {
  return (
    <section className={`rounded-xl border border-border bg-surface ${className}`}>
      {title && (
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-3">
          <h2 className="font-semibold">{title}</h2>
          {action}
        </div>
      )}
      <div className={padded ? "p-5" : ""}>{children}</div>
    </section>
  );
}

export function PageHeader({
  title,
  description,
  action,
}: {
  title: string;
  description?: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold">{title}</h1>
        {description && <p className="mt-1 max-w-2xl text-sm text-muted">{description}</p>}
      </div>
      {action}
    </div>
  );
}

export function Button({
  children,
  variant = "primary",
  size = "md",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "danger" | "ghost";
  size?: "sm" | "md";
}) {
  const styles = {
    primary: "bg-accent text-white hover:opacity-90 dark:text-bg",
    secondary: "border border-border bg-surface hover:bg-surface-2",
    danger: "border border-danger/40 text-danger hover:bg-danger-soft",
    ghost: "text-muted hover:bg-surface-2 hover:text-text",
  }[variant];
  const sizes = size === "sm" ? "px-2.5 py-1 text-xs" : "px-3.5 py-2 text-sm";
  return (
    <button
      {...props}
      className={`inline-flex items-center justify-center gap-2 rounded-lg font-medium transition disabled:cursor-not-allowed disabled:opacity-50 ${sizes} ${styles} ${props.className ?? ""}`}
    >
      {children}
    </button>
  );
}

export const controlClass =
  "rounded-lg border border-border bg-surface px-3 py-2 text-sm outline-none focus:border-accent focus:ring-2 focus:ring-accent/20";

export const inputClass = `w-full ${controlClass}`;

export function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block font-medium">{label}</span>
      {children}
    </label>
  );
}

export function ErrorNotice({ message }: { message: string }) {
  return (
    <div role="alert" className="rounded-lg border border-danger/30 bg-danger-soft px-4 py-3 text-sm text-danger">
      {message}
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-border px-6 py-12 text-center">
      <p className="font-medium">{title}</p>
      {children && <div className="mx-auto mt-2 max-w-lg text-sm text-muted">{children}</div>}
    </div>
  );
}

export function Badge({ children, tone = "neutral" }: { children: React.ReactNode; tone?: Tone }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ${TONES[tone]}`}>
      {children}
    </span>
  );
}

type Tone = "neutral" | "accent" | "ok" | "danger" | "warn" | "secret";

const TONES: Record<Tone, string> = {
  neutral: "bg-surface-2 text-muted",
  accent: "bg-accent-soft text-accent",
  ok: "bg-ok-soft text-ok",
  danger: "bg-danger-soft text-danger",
  warn: "bg-warn-soft text-warn",
  secret: "bg-secret-soft text-secret",
};

export function ClassificationBadge({ value }: { value: Classification }) {
  return value === "confidential" ? (
    <Badge tone="secret">
      <LockIcon /> Confidential
    </Badge>
  ) : (
    <Badge>Internal</Badge>
  );
}

const VERSION_STATUS: Record<VersionStatus, [string, Tone]> = {
  pending: ["Queued", "neutral"],
  processing: ["Indexing", "accent"],
  ready: ["Ready", "ok"],
  failed: ["Failed", "danger"],
};

export function VersionStatusBadge({ status }: { status: VersionStatus }) {
  const [label, tone] = VERSION_STATUS[status];
  return (
    <Badge tone={tone}>
      {status === "processing" && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />}
      {label}
    </Badge>
  );
}

export function LockIcon({ className = "h-3 w-3" }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="currentColor" aria-hidden className={className}>
      <path d="M8 1a3.5 3.5 0 0 0-3.5 3.5V6H4a1.5 1.5 0 0 0-1.5 1.5v6A1.5 1.5 0 0 0 4 15h8a1.5 1.5 0 0 0 1.5-1.5v-6A1.5 1.5 0 0 0 12 6h-.5V4.5A3.5 3.5 0 0 0 8 1Zm2 5H6V4.5a2 2 0 1 1 4 0V6Z" />
    </svg>
  );
}

export function Table({ children }: { children: React.ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">{children}</table>
    </div>
  );
}

export function Th({ children, className = "" }: { children?: React.ReactNode; className?: string }) {
  return (
    <th className={`border-b border-border px-5 py-2.5 text-xs font-medium uppercase tracking-wide text-muted ${className}`}>
      {children}
    </th>
  );
}

export function Td({ children, className = "" }: { children?: React.ReactNode; className?: string }) {
  return <td className={`border-b border-border px-5 py-3 align-middle ${className}`}>{children}</td>;
}
