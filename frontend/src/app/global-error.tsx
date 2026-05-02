"use client";

import "./globals.css";

interface GlobalErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

/**
 * Catastrophic error boundary — fires when the root layout itself fails.
 * Must render its own `<html>` and `<body>` because the layout broke.
 * Keep the markup minimal: no fonts, no theme provider, no shell.
 */
export default function GlobalError({ error, reset }: GlobalErrorProps) {
  return (
    <html lang="es">
      <body
        style={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "2rem",
          fontFamily: "system-ui, sans-serif",
          color: "#0B1220",
          background: "#FBFCFD",
        }}
      >
        <div
          style={{
            maxWidth: 480,
            textAlign: "center",
            display: "flex",
            flexDirection: "column",
            gap: 16,
          }}
          role="alert"
          aria-live="assertive"
        >
          <h1 style={{ fontSize: 24, fontWeight: 600, margin: 0 }}>
            La aplicación no pudo cargar
          </h1>
          <p style={{ fontSize: 14, color: "#5B6573", margin: 0 }}>
            Algo falló al inicializar TukiMedic. Por favor recargá la página.
            {error.digest && (
              <span
                style={{
                  display: "block",
                  marginTop: 8,
                  fontFamily: "monospace",
                  fontSize: 12,
                  color: "#8A94A3",
                }}
              >
                (ref: {error.digest})
              </span>
            )}
          </p>
          <button
            type="button"
            onClick={reset}
            style={{
              alignSelf: "center",
              padding: "10px 20px",
              borderRadius: 8,
              border: "none",
              background: "#2563EB",
              color: "#fff",
              fontSize: 14,
              fontWeight: 500,
              cursor: "pointer",
            }}
          >
            Reintentar
          </button>
        </div>
      </body>
    </html>
  );
}
