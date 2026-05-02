const STATS = [
  { value: "10", label: "Especialidades médicas" },
  { value: "< 60s", label: "Tiempo de respuesta promedio" },
  { value: "96%", label: "Concordancia clínica en eval" },
  { value: "24/7", label: "Disponible siempre" },
] as const;

export function LandingTrust() {
  return (
    <section
      data-testid="landing-trust"
      className="border-y py-8"
      style={{
        borderColor: "var(--tm-border)",
        background: "var(--tm-surface)",
      }}
    >
      <div className="mx-auto grid max-w-[1200px] grid-cols-2 gap-4 px-8 text-center md:grid-cols-4">
        {STATS.map((s) => (
          <div key={s.label}>
            <div
              className="font-normal leading-none tracking-[-0.02em]"
              style={{
                fontFamily: "var(--font-instrument-serif)",
                fontSize: "2.375rem",
                color: "var(--tm-blue-700)",
              }}
            >
              {s.value}
            </div>
            <div
              className="mt-1 text-xs"
              style={{ color: "var(--tm-text-muted)" }}
            >
              {s.label}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
