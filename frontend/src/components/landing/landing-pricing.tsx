import Link from "next/link";
import { Check, X, ArrowRight, Info } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface PlanFeature {
  yes: boolean;
  text: string;
}

interface PriceCardProps {
  name: string;
  price: string;
  period: string;
  desc: string;
  features: PlanFeature[];
  ctaText: string;
  featured?: boolean;
}

function PriceCard({
  name,
  price,
  period,
  desc,
  features,
  ctaText,
  featured = false,
}: PriceCardProps) {
  return (
    <div
      className="relative flex flex-col p-8"
      style={{
        background: featured
          ? "linear-gradient(180deg, var(--tm-blue-700) 0%, var(--tm-blue-900) 100%)"
          : "var(--tm-surface)",
        color: featured ? "#fff" : "var(--tm-text)",
        border: featured ? "none" : "1px solid var(--tm-border)",
        borderRadius: "var(--tm-radius-lg)",
        boxShadow: featured ? "var(--tm-shadow-lg)" : "var(--tm-shadow-sm)",
        transform: featured ? "translateY(-12px)" : "none",
      }}
    >
      {featured && (
        <div
          className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full px-3.5 py-1 text-[11px] font-bold uppercase tracking-wider"
          style={{
            background: "var(--tm-yellow-400)",
            color: "var(--tm-blue-950)",
          }}
        >
          Mas popular
        </div>
      )}

      <div
        className="text-sm font-semibold uppercase tracking-wider"
        style={{ opacity: featured ? 0.85 : 0.7 }}
      >
        {name}
      </div>

      <div className="mt-3 mb-2">
        <div
          className="leading-none tracking-[-0.02em]"
          style={{
            fontFamily: "var(--font-instrument-serif)",
            fontSize: "3rem",
            fontWeight: 400,
          }}
        >
          {price}
        </div>
        <div className="mt-1.5 text-xs opacity-70">{period}</div>
      </div>

      <p
        className="mb-6 min-h-[44px] text-sm leading-[1.55]"
        style={{
          opacity: featured ? 0.85 : 1,
          color: featured ? "inherit" : "var(--tm-text-muted)",
          margin: "0 0 1.5rem",
        }}
      >
        {desc}
      </p>

      <div className="mb-6 flex flex-1 flex-col gap-2.5">
        {features.map((f) => (
          <div
            key={f.text}
            className="flex items-start gap-2.5 text-[13.5px]"
            style={{ opacity: f.yes ? 1 : 0.45 }}
          >
            {f.yes ? (
              <Check
                className="mt-0.5 size-3.5 shrink-0"
                strokeWidth={2.5}
                style={{
                  color: featured
                    ? "var(--tm-yellow-300)"
                    : "var(--tm-green-600)",
                }}
              />
            ) : (
              <X className="mt-0.5 size-3.5 shrink-0" strokeWidth={2.5} />
            )}
            <span>{f.text}</span>
          </div>
        ))}
      </div>

      <Link
        href="/register"
        className={cn(
          buttonVariants({ size: "lg" }),
          "w-full justify-center",
          featured ? "bg-white text-[var(--tm-blue-900)] hover:bg-white/90" : "",
        )}
      >
        {ctaText} <ArrowRight className="size-4" />
      </Link>
    </div>
  );
}

export function LandingPricing() {
  return (
    <section
      id="planes"
      data-testid="landing-pricing"
      className="px-8 py-24"
      style={{ background: "var(--tm-bg)" }}
    >
      <div className="mx-auto max-w-[1200px]">
        <div className="mx-auto mb-14 max-w-[640px] text-center">
          <Badge variant="outline">Planes</Badge>
          <h2
            className="mt-5 mb-4 font-normal leading-[1.1] tracking-[-0.02em]"
            style={{
              fontFamily: "var(--font-instrument-serif)",
              fontSize: "clamp(2rem, 4vw, 3.5rem)",
              color: "var(--tm-text)",
            }}
          >
            Empezá gratis.{" "}
            <em style={{ color: "var(--tm-blue-600)" }}>
              Crecé cuando quieras.
            </em>
          </h2>
          <p className="m-0 text-[1.0625rem]" style={{ color: "var(--tm-text-muted)" }}>
            Precios en soles peruanos (PEN). Sin permanencia, cancelás cuando
            quieras.
          </p>
        </div>

        <div className="grid grid-cols-1 items-stretch gap-5 md:grid-cols-3">
          <PriceCard
            name="Gratis"
            price="S/ 0"
            period="para siempre"
            desc="Para conocer la herramienta y consultas puntuales."
            features={[
              { yes: true, text: "Triage + 1 especialidad por consulta" },
              { yes: true, text: "5 consultas al mes" },
              { yes: true, text: "Historial últimas 5 consultas" },
              { yes: true, text: "3 documentos por mes" },
              { yes: false, text: "Mesa médica completa (10 esp.)" },
              { yes: false, text: "Devil's advocate" },
              { yes: false, text: "Foto upload (derma)" },
              { yes: false, text: "Export PDF para tu médico" },
            ]}
            ctaText="Empezar gratis"
          />

          <PriceCard
            name="Pro"
            price="S/ 29"
            period="por mes"
            featured
            desc="Para quien usa TukiMedic seguido y quiere todo el poder."
            features={[
              { yes: true, text: "Triage + 10 especialidades en paralelo" },
              { yes: true, text: "Consultas ilimitadas" },
              { yes: true, text: "Mesa médica completa" },
              { yes: true, text: "Devil's advocate" },
              { yes: true, text: "Historial completo + búsqueda" },
              { yes: true, text: "Documentos ilimitados + foto derma" },
              { yes: true, text: "Export PDF profesional" },
              { yes: true, text: "Soporte prioritario por WhatsApp" },
            ]}
            ctaText="Probar Pro 7 días gratis"
          />

          <PriceCard
            name="Familia"
            price="S/ 59"
            period="por mes"
            desc="Vos y hasta 4 familiares (papá, mamá, hijos, pareja)."
            features={[
              { yes: true, text: "Todo lo de Pro x 5 personas" },
              { yes: true, text: "5 fichas clínicas independientes" },
              { yes: true, text: "Modo pediátrico (dosis por peso)" },
              { yes: true, text: "Recordatorios de medicación" },
              { yes: true, text: "Calendario de controles" },
              { yes: true, text: "Export consolidado familiar" },
              { yes: true, text: "Soporte prioritario WhatsApp" },
              { yes: true, text: "Hasta 4 dispositivos por persona" },
            ]}
            ctaText="Probar Familia"
          />
        </div>

        <div
          className="mt-8 flex flex-wrap items-center justify-center gap-4 rounded-xl p-5"
          style={{ background: "var(--tm-bg-soft)" }}
        >
          <Info
            className="size-[18px]"
            style={{ color: "var(--tm-text-muted)" }}
          />
          <span className="text-sm" style={{ color: "var(--tm-text-muted)" }}>
            Pago con tarjeta, Yape, Plin o transferencia BCP / Interbank.
            Facturación electrónica disponible.
          </span>
        </div>
      </div>
    </section>
  );
}
