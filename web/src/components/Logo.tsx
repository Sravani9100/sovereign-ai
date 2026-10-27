export function Logo({ className = "" }: { className?: string }) {
  return (
    <span className={`flex items-center gap-2 font-semibold ${className}`}>
      <span aria-hidden className="grid h-7 w-7 place-items-center rounded-lg bg-accent text-white dark:text-bg">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" className="h-4 w-4">
          <path d="M12 3 4.5 6v5.5c0 4.6 3.2 8.4 7.5 9.5 4.3-1.1 7.5-4.9 7.5-9.5V6L12 3Z" strokeLinejoin="round" />
          <path d="m9 12 2 2 4-4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
      SovereignAI
    </span>
  );
}
