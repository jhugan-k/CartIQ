// CartIQ wordmark + SVG cart mark (no emoji — per design checklist).

export function LogoMark({ className = "h-7 w-7" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      className={className}
      aria-hidden="true"
    >
      <rect width="24" height="24" rx="7" fill="var(--primary)" />
      <path
        d="M6 7h1.4l1.1 6.2a1.2 1.2 0 0 0 1.18.98h4.9a1.2 1.2 0 0 0 1.17-.92l.86-3.5H8.2"
        stroke="var(--primary-fg)"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="10" cy="17.2" r="1.15" fill="var(--primary-fg)" />
      <circle cx="15" cy="17.2" r="1.15" fill="var(--primary-fg)" />
    </svg>
  );
}

export function Logo({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2 font-semibold tracking-tight ${className}`}>
      <LogoMark />
      <span className="text-[17px]">
        Cart<span className="text-primary">IQ</span>
      </span>
    </span>
  );
}
