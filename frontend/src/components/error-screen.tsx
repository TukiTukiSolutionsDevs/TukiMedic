"use client";

import { useEffect } from "react";
import Link from "next/link";
import { AlertTriangle, RotateCw, Home } from "lucide-react";

export interface ErrorScreenProps {
  /** The error thrown by the boundary. */
  error: Error & { digest?: string };
  /** Reset callback provided by Next.js boundary. */
  reset: () => void;
  /** Title to show. Defaults to a generic message. */
  title?: string;
  /** Whether to show the "Volver al inicio" link. */
  showHomeLink?: boolean;
}

/**
 * Shared error UI for Next.js App Router error boundaries.
 *
 * Renders inside `error.tsx` route segments. Logs the error to the console
 * with the digest so it can be correlated with server logs.
 */
export function ErrorScreen({
  error,
  reset,
  title = "Algo salió mal",
  showHomeLink = true,
}: ErrorScreenProps) {
  useEffect(() => {
    // Surface to console for browser debugging; production logging happens
    // server-side via the digest.
    console.error("[ErrorBoundary]", error);
  }, [error]);

  return (
    <div
      data-testid="error-screen"
      role="alert"
      aria-live="polite"
      className="flex min-h-[60vh] flex-1 flex-col items-center justify-center gap-4 px-6 py-10 text-center"
    >
      <div
        aria-hidden
        className="flex h-14 w-14 items-center justify-center rounded-full"
        style={{
          background: "var(--tm-red-50)",
          color: "var(--tm-red-700)",
        }}
      >
        <AlertTriangle size={28} strokeWidth={2} />
      </div>
      <h2 className="text-xl font-semibold tracking-tight text-foreground">
        {title}
      </h2>
      <p className="max-w-md text-sm leading-relaxed text-[var(--tm-text-muted)]">
        Algo no salió como esperábamos. Podés reintentar o volver al inicio.
        {error.digest && (
          <>
            {" "}
            <span
              className="font-mono text-xs text-[var(--tm-text-subtle)]"
              data-testid="error-digest"
            >
              (ref: {error.digest})
            </span>
          </>
        )}
      </p>
      <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
        <button
          type="button"
          onClick={reset}
          data-testid="error-reset"
          className="inline-flex items-center gap-2 rounded-md bg-[var(--tm-blue-600)] px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-[var(--tm-blue-700)]"
        >
          <RotateCw size={14} aria-hidden /> Reintentar
        </button>
        {showHomeLink && (
          <Link
            href="/dashboard"
            data-testid="error-home"
            className="inline-flex items-center gap-2 rounded-md border border-[var(--tm-border-strong)] bg-[var(--tm-surface)] px-4 py-2 text-sm font-medium text-foreground hover:bg-[var(--tm-bg-soft)]"
          >
            <Home size={14} aria-hidden /> Ir al inicio
          </Link>
        )}
      </div>
    </div>
  );
}
