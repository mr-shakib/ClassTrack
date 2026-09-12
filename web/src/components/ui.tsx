"use client";

import type { ReactNode } from "react";

export function Card({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-xl border border-line bg-surface shadow-[0_1px_2px_rgba(15,23,42,0.04)] ${className}`}
    >
      {children}
    </div>
  );
}

export function SummaryCard({
  label,
  value,
  tone = "neutral",
  hint,
}: {
  label: string;
  value: number | string;
  tone?: "neutral" | "ok" | "warn" | "bad" | "gap" | "info";
  hint?: string;
}) {
  const tones = {
    neutral: "text-ink",
    ok: "text-ok",
    warn: "text-warn",
    bad: "text-bad",
    gap: "text-gap",
    info: "text-info",
  };
  return (
    <Card className="p-4">
      <div className="text-xs font-medium uppercase tracking-wide text-ink-faint">
        {label}
      </div>
      <div className={`mt-1 text-3xl font-semibold tabular-nums ${tones[tone]}`}>
        {value}
      </div>
      {hint ? <div className="mt-1 text-xs text-ink-faint">{hint}</div> : null}
    </Card>
  );
}

export function Button({
  children,
  variant = "primary",
  size = "md",
  className = "",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "md" | "lg";
}) {
  const variants = {
    primary: "bg-brand text-white hover:bg-brand/90 active:bg-brand/80",
    secondary:
      "bg-surface text-ink ring-1 ring-inset ring-line hover:bg-canvas active:bg-line/50",
    ghost: "text-ink-soft hover:bg-canvas active:bg-line/50",
    danger: "bg-bad text-white hover:bg-bad/90 active:bg-bad/80",
  };
  const sizes = { md: "px-3 py-2 text-sm", lg: "px-4 py-3 text-base" };
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${variants[variant]} ${sizes[size]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}

export function Field({
  label,
  children,
  hint,
}: {
  label: string;
  children: ReactNode;
  hint?: string;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-ink-soft">{label}</span>
      {children}
      {hint ? <span className="mt-1 block text-xs text-ink-faint">{hint}</span> : null}
    </label>
  );
}

export const inputClass =
  "w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20";

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 py-8 text-sm text-ink-faint">
      <span className="size-4 animate-spin rounded-full border-2 border-line border-t-brand" />
      {label}
    </div>
  );
}

export function EmptyState({
  title,
  body,
}: {
  title: string;
  body?: string;
}) {
  return (
    <div className="py-12 text-center">
      <p className="text-sm font-medium text-ink-soft">{title}</p>
      {body ? <p className="mt-1 text-sm text-ink-faint">{body}</p> : null}
    </div>
  );
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-bad/20 bg-bad-soft px-3 py-2 text-sm text-bad">
      {message}
    </div>
  );
}
