interface ComparativeBarProps {
  label: string;
  /** 0-1 fraction, straight from the backend — never fabricated or guessed. */
  value: number;
  highlight?: boolean;
}

/** Horizontal comparative confidence bar — the required replacement for
 * circular confidence rings (DESIGN_SYSTEM.md §14). Caller is responsible
 * for sorting a candidate list before rendering a stack of these. */
export function ComparativeBar({ label, value, highlight = false }: ComparativeBarProps) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-baseline justify-between gap-3">
        <span
          className="truncate text-sm"
          style={{ color: highlight ? "var(--color-text-primary)" : "var(--color-text-secondary)" }}
        >
          {label}
        </span>
        <span className="font-mono text-sm" style={{ color: "var(--color-text-primary)" }}>
          {pct.toFixed(1)}%
        </span>
      </div>
      <div
        className="h-[6px] w-full overflow-hidden rounded-sm"
        style={{ backgroundColor: "var(--color-surface-3)" }}
      >
        <div
          className="h-full rounded-sm"
          style={{
            width: `${pct}%`,
            backgroundColor: highlight ? "var(--color-accent)" : "var(--color-border-strong)",
          }}
        />
      </div>
    </div>
  );
}
