import {
  Stethoscope,
  Heart,
  Brain,
  Baby,
  Sparkles,
  Pill,
  Shield,
  Eye,
  Check,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";

const SPECIALTIES: Array<{ key: string; label: string; Icon: LucideIcon }> = [
  { key: "medicina_general", label: "Medicina general", Icon: Stethoscope },
  { key: "cardiologia", label: "Cardiología", Icon: Heart },
  { key: "neurologia", label: "Neurología", Icon: Brain },
  { key: "pediatria", label: "Pediatría", Icon: Baby },
  { key: "dermatologia", label: "Dermatología", Icon: Sparkles },
  { key: "gastroenterologia", label: "Gastroenterología", Icon: Pill },
  { key: "ginecologia", label: "Ginecología", Icon: Heart },
  { key: "traumatologia", label: "Traumatología", Icon: Shield },
  { key: "psiquiatria", label: "Psiquiatría", Icon: Brain },
  { key: "oftalmologia", label: "Oftalmología", Icon: Eye },
];

const FEATURES = [
  {
    title: "Triage primero",
    desc: "Verde rutina · amarillo atención · rojo emergencia.",
  },
  {
    title: "Ruteo inteligente",
    desc: "Solo se activan las especialidades relevantes a tu caso.",
  },
  {
    title: "Devil's advocate",
    desc: "Una segunda opinión que busca lo que se pudo pasar.",
  },
  {
    title: "Respuesta unificada",
    desc: "No 10 opiniones sueltas — una sola síntesis clara.",
  },
] as const;

export function LandingMesa() {
  return (
    <section
      id="mesa-medica"
      data-testid="landing-mesa"
      className="relative overflow-hidden px-8 py-24 text-white"
      style={{
        background:
          "linear-gradient(180deg, var(--tm-blue-900) 0%, var(--tm-blue-950) 100%)",
      }}
    >
      {/* Radial glows */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          backgroundImage:
            "radial-gradient(circle at 20% 20%, rgba(252,211,77,0.1), transparent 40%), radial-gradient(circle at 80% 80%, rgba(96,165,250,0.15), transparent 50%)",
        }}
      />

      <div className="relative mx-auto grid max-w-[1200px] grid-cols-1 items-center gap-16 md:grid-cols-2">
        {/* Left: copy */}
        <div>
          <Badge
            variant="outline"
            className="border-[rgba(252,211,77,0.3)] text-xs"
            style={{
              background: "rgba(252,211,77,0.15)",
              color: "var(--tm-yellow-300)",
            }}
          >
            Mesa médica
          </Badge>

          <h2
            className="mt-5 mb-4 font-normal leading-[1.1] tracking-[-0.02em]"
            style={{
              fontFamily: "var(--font-instrument-serif)",
              fontSize: "clamp(2rem, 4vw, 3.5rem)",
            }}
          >
            Diez cabezas piensan{" "}
            <em style={{ color: "var(--tm-yellow-300)" }}>mejor</em> que una.
          </h2>

          <p className="mb-6 text-[1.0625rem] leading-[1.6] opacity-85">
            Tu caso pasa por triage, se enruta a las especialidades relevantes
            y un sintetizador final te entrega una respuesta unificada. Si algo
            huele raro, un{" "}
            <strong style={{ color: "var(--tm-yellow-300)" }}>
              devil&apos;s advocate
            </strong>{" "}
            cuestiona la conclusión antes de mostrártela.
          </p>

          <div className="flex flex-col gap-3.5">
            {FEATURES.map((f) => (
              <div key={f.title} className="flex items-start gap-3">
                <Check
                  className="mt-0.5 size-[18px] shrink-0"
                  strokeWidth={2.5}
                  style={{ color: "var(--tm-yellow-300)" }}
                />
                <div>
                  <div className="text-sm font-semibold">{f.title}</div>
                  <div className="mt-0.5 text-[0.84375rem] opacity-75">
                    {f.desc}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right: specialty grid */}
        <div className="grid grid-cols-2 gap-3">
          {SPECIALTIES.map((s) => (
            <div
              key={s.key}
              className="flex items-center gap-3 rounded-xl px-[18px] py-4"
              style={{
                background: "rgba(255,255,255,0.06)",
                border: "1px solid rgba(255,255,255,0.1)",
                backdropFilter: "blur(8px)",
              }}
            >
              <div
                className="flex size-9 shrink-0 items-center justify-center rounded-lg"
                style={{
                  background: "rgba(252,211,77,0.15)",
                  color: "var(--tm-yellow-300)",
                }}
              >
                <s.Icon className="size-[18px]" />
              </div>
              <div>
                <div className="text-sm font-semibold">{s.label}</div>
                <div
                  className="mt-0.5 text-[11px] opacity-60"
                  style={{ fontFamily: "var(--font-geist-mono)" }}
                >
                  {s.key}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
