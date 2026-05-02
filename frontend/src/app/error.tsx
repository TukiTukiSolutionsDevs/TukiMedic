"use client";

import { ErrorScreen, type ErrorScreenProps } from "@/components/error-screen";

/**
 * Root error boundary for all routes that don't have their own.
 * Triggered by uncaught errors in any client/server component below `app/`.
 */
export default function RootError(props: ErrorScreenProps) {
  return <ErrorScreen {...props} />;
}
