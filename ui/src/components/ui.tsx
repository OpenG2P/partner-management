"use client";

import Link from "next/link";

export function PageHeader({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex items-start justify-between mb-6">
      <div>
        <h1 className="text-2xl">{title}</h1>
        {subtitle && (
          <p className="text-[color:var(--color-text-muted)] mt-1">{subtitle}</p>
        )}
      </div>
      {action}
    </div>
  );
}

export function StatusPill({ status }: { status: string }) {
  return <span className={`status-pill status-${status}`}>{status}</span>;
}

export function BackLink({ href, label }: { href: string; label: string }) {
  return (
    <Link
      href={href}
      className="text-sm text-[color:var(--color-text-muted)] hover:underline"
    >
      ← {label}
    </Link>
  );
}

export function ErrorBanner({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div className="card mb-4 border-[color:var(--color-danger)] text-[color:var(--color-danger)]">
      {message}
    </div>
  );
}

export function Empty({ message }: { message: string }) {
  return (
    <div className="card text-center text-[color:var(--color-text-muted)]">
      {message}
    </div>
  );
}

export function fmtDate(iso?: string | null) {
  if (!iso) return "—";
  const d = new Date(iso);
  return isNaN(d.getTime()) ? iso : d.toLocaleString();
}
