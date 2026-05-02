import { MessageSquare, Users, Check } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";

const STEPS: Array<{
  num: string;
  title: string;
  desc: string;
  Icon: LucideIcon;
}> = [
  {
    num: "01",
    title: "Contanos qué te pasa",
    desc: "Describí tus síntomas en lenguaje natural. Como si le contaras a un amigo médico. Podés adjuntar análisis, recetas o fotos.",
    Icon: MessageSquare,
  },
  {
    num: "02",
    title: "La mesa médica delibera",
    desc: "Un equipo de hasta 10 especialistas analiza tu caso en paralelo: neurología, cardiología, dermatología, pediatría y más.",
    Icon: Users,
  },
  {
    num: "03",
    title: "Recibís una orientación clara",
    desc: "Te decimos qué podría ser, qué señales mirar, cuándo consultar y a qué especialista ir. Con fuentes citadas.",
    Icon: Check,
  },
];

export function LandingHow() {
  return (
    <section
      id="como-funciona"
      data-testid="landing-how"
      className="px-8 py-24"
      style={{ background: "var(--tm-bg)" }}
    >
      <div className="mx-auto max-w-[1200px]">
        <div className="mx-auto mb-14 max-w-[720px] text-center">
          <Badge variant="outline">Cómo funciona</Badge>
          <h2
            className="mt-5 mb-4 font-normal leading-[1.1] tracking-[-0.02em]"
            style={{
              fontFamily: "var(--font-instrument-serif)",
              fontSize: "clamp(2rem, 4vw, 3.5rem)",
              color: "var(--tm-text)",
            }}
          >
            Tres pasos para una consulta{" "}
            <em style={{ color: "var(--tm-blue-600)" }}>en serio</em>.
          </h2>
          <p
            className="m-0 text-[1.0625rem] leading-[1.55]"
            style={{ color: "var(--tm-text-muted)" }}
          >
            No es un chat genérico. Es un protocolo médico estructurado, con
            triage, contexto y deliberación entre especialistas.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
          {STEPS.map((s) => (
            <div
              key={s.num}
              className="relative p-8"
              style={{
                background: "var(--tm-surface)",
                border: "1px solid var(--tm-border)",
                borderRadius: "var(--tm-radius-lg)",
              }}
            >
              <div
                className="text-xs font-medium"
                style={{
                  fontFamily: "var(--font-geist-mono)",
                  color: "var(--tm-blue-600)",
                }}
              >
                {s.num}
              </div>
              <div
                className="my-5 flex size-12 items-center justify-center rounded-xl"
                style={{
                  background: "var(--tm-blue-50)",
                  color: "var(--tm-blue-700)",
                }}
              >
                <s.Icon className="size-[22px]" strokeWidth={2} />
              </div>
              <h3 className="mb-2.5 text-xl font-semibold tracking-[-0.01em]">
                {s.title}
              </h3>
              <p
                className="m-0 text-sm leading-[1.6]"
                style={{ color: "var(--tm-text-muted)" }}
              >
                {s.desc}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
