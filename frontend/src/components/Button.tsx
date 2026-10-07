import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "ghost" | "destructive";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

const VARIANT_CLASS: Record<Variant, string> = {
  primary: "bg-[var(--color-accent)] text-[var(--color-surface-0)] hover:brightness-110 disabled:opacity-40",
  secondary:
    "bg-[var(--color-surface-2)] text-[var(--color-text-primary)] border border-[var(--color-border-strong)] hover:border-[var(--color-text-secondary)] disabled:opacity-40",
  ghost:
    "bg-transparent text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] disabled:opacity-40",
  destructive:
    "bg-transparent text-[var(--color-sev-critical)] border border-[var(--color-sev-critical)] hover:bg-[var(--color-sev-critical)] hover:text-[var(--color-surface-0)] disabled:opacity-40",
};

export function Button({ variant = "secondary", className = "", ...rest }: ButtonProps) {
  return (
    <button
      className={`rounded-sm px-3 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed ${VARIANT_CLASS[variant]} ${className}`}
      {...rest}
    />
  );
}
