"use client";

import Link from "next/link";
import { Check, ArrowRight, Play, ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const SPECIALISTS = [
  {
    name: "Neurología",
    status: "Revisando características de la cefalea",
    done: true,
  },
  {
    name: "Medicina general",
    status: "Buscando signos de alarma",
    done: true,
  },
  {
    name: "Oftalmología",
    status: "Evaluando si requiere derivación...",
    done: false,
  },
] as const;

const ASSURANCES = ["Sin tarjeta", "Datos cifrados", "Cancelás cuando quieras"] as const;

function HeroChatPreview() {
  return (
    <div className="relative">
      <div
        className="relative z-[2] p-5"
        style={{
          background: "var(--tm-surface)",
          border: "1px solid var(--tm-border)",
          borderRadius: "var(--tm-radius-lg)",
          boxShadow: "var(--tm-shadow-lg)",
        }}
      >
        {/* Mock browser chrome */}
        <div
          className="mb-3.5 flex items-center gap-2 pb-3.5"
          style={{ borderBottom: "1px solid var(--tm-border)" }}
        >
          <span className="size-2.5 rounded-full" style={{ background: "#FF5F57" }} />
          <span className="size-2.5 rounded-full" style={{ background: "#FEBC2E" }} />
          <span className="size-2.5 rounded-full" style={{ background: "#28C840" }} />
          <span
            className="ml-3 text-xs"
            style={{
              color: "var(--tm-text-muted)",
              fontFamily: "var(--font-geist-mono)",
            }}
          >
            tukimedic.pe / consulta
          </span>
        </div>

        {/* User message */}
        <div className="mb-3.5 flex justify-end">
          <div
            className="max-w-[85%] rounded-[14px_14px_4px_14px] px-3.5 py-2.5 text-sm leading-snug text-white"
            style={{ background: "var(--tm-blue-600)" }}
          >
            Hace 3 días tengo dolor de cabeza fuerte que no me deja dormir, sobre
            todo del lado derecho.
          </div>
        </div>

        {/* Specialists deliberating */}
        <div
          className="mb-3.5 rounded-xl p-3"
          style={{ background: "var(--tm-bg-soft)" }}
        >
          <div
            className="mb-2.5 text-[11px] font-semibold uppercase tracking-widest"
            style={{ color: "var(--tm-text-muted)" }}
          >
            Mesa médica · 3 especialistas analizando
          </div>
          <div className="flex flex-col gap-2">
            {SPECIALISTS.map((s) => (
              <div
                key={s.name}
                className="flex items-center gap-2.5 text-[12.5px]"
              >
                <div
                  className="flex size-[18px] shrink-0 items-center justify-center rounded-full"
                  style={{
                    background: s.done
                      ? "var(--tm-green-500)"
                      : "var(--tm-blue-100)",
                  }}
                >
                  {s.done ? (
                    <Check className="size-[11px] stroke-[3] text-white" />
                  ) : (
                    <span
                      className="size-1.5 rounded-full"
                      style={{ background: "var(--tm-blue-600)" }}
                    />
                  )}
                </div>
                <strong className="font-semibold">{s.name}</strong>
                <span style={{ color: "var(--tm-text-muted)" }}>
                  · {s.status}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Verdict */}
        <div
          className="rounded-xl p-3.5"
          style={{
            background: "linear-gradient(135deg, var(--tm-amber-50), transparent)",
            border: "1px solid rgba(245, 158, 11, 0.3)",
          }}
        >
          <div className="mb-2 flex items-center gap-2">
            <span
              className="size-2.5 rounded-full"
              style={{ background: "var(--tm-amber-500)" }}
            />
            <span
              className="text-xs font-semibold uppercase tracking-wide"
              style={{ color: "var(--tm-amber-700)" }}
            >
              Atención · ver médico esta semana
            </span>
          </div>
          <p
            className="m-0 text-[13.5px] leading-relaxed"
            style={{ color: "var(--tm-text)" }}
          >
            Lo que describís es compatible con cefalea tensional o migraña. Como
            lleva 3 días, te conviene consultar con tu médico de cabecera o un
            neurólogo en los próximos días.
          </p>
        </div>
      </div>

      {/* Floating: response time */}
      <div
        className="absolute -right-3.5 -top-3.5 z-[3] flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold"
        style={{
          background: "var(--tm-surface)",
          border: "1px solid var(--tm-border)",
          boxShadow: "var(--tm-shadow)",
        }}
      >
        <span
          className="size-2 rounded-full"
          style={{ background: "var(--tm-green-500)" }}
        />
        Respuesta en 47s
      </div>

      {/* Floating: audit chain */}
      <div
        className="absolute -bottom-4 -left-4 z-[3] flex items-center gap-2 rounded-xl px-3.5 py-2.5 text-xs text-white"
        style={{
          background: "var(--tm-blue-900)",
          boxShadow: "var(--tm-shadow-lg)",
        }}
      >
        <ShieldCheck
          className="size-3.5 shrink-0"
          style={{ color: "var(--tm-yellow-300)" }}
        />
        <span>
          <strong>Audit chain</strong> SHA-256 · cada respuesta firmada
        </span>
      </div>
    </div>
  );
}

export function LandingHero() {
  return (
    <section
      data-testid="landing-hero"
      className="relative overflow-hidden"
      style={{
        background:
          "linear-gradient(180deg, var(--tm-bg) 0%, var(--tm-bg-soft) 100%)",
      }}
    >
      {/* Decorative grid */}
      <div
        className="pointer-events-none absolute inset-0 opacity-40"
        style={{
          backgroundImage:
            "linear-gradient(var(--tm-border) 1px, transparent 1px), linear-gradient(90deg, var(--tm-border) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
          maskImage:
            "radial-gradient(ellipse at top, black 0%, transparent 60%)",
        }}
      />

      <div className="relative mx-auto grid max-w-[1200px] grid-cols-1 items-center gap-16 px-8 pb-24 pt-[88px] md:grid-cols-[1.1fr_1fr]">
        <div>
          <Badge variant="outline">Mesa médica con IA · 10 especialidades</Badge>

          <h1
            className="my-5 mb-6 font-normal leading-[1.02] tracking-[-0.025em]"
            style={{
              fontFamily: "var(--font-instrument-serif)",
              fontSize: "clamp(2.5rem, 5vw, 4.75rem)",
              color: "var(--tm-text)",
            }}
          >
            Tu salud, en{" "}
            <em style={{ color: "var(--tm-blue-600)" }}>buenas manos</em>{" "}
            desde el primer síntoma.
          </h1>

          <p
            className="mb-8 max-w-[560px] text-[1.1875rem] leading-[1.55]"
            style={{ color: "var(--tm-text-muted)" }}
          >
            Contanos qué te pasa. Diez especialistas analizan tu caso, deliberan
            entre ellos y te entregan una orientación clara — en menos de 60
            segundos, cualquier hora, desde cualquier lugar del Perú.
          </p>

          <div className="mb-6 flex flex-wrap gap-3">
            <Link
              href="/register"
              className={cn(buttonVariants({ size: "lg" }))}
            >
              Probar gratis ahora <ArrowRight className="size-4" />
            </Link>
            <button
              type="button"
              className={cn(buttonVariants({ variant: "secondary", size: "lg" }))}
            >
              <Play className="size-4" />
              Ver demo (1:30)
            </button>
          </div>

          <div
            className="flex flex-wrap gap-6 text-xs"
            style={{ color: "var(--tm-text-subtle)" }}
          >
            {ASSURANCES.map((text) => (
              <span key={text} className="inline-flex items-center gap-1.5">
                <Check
                  className="size-3.5"
                  style={{ color: "var(--tm-green-600)" }}
                />
                {text}
              </span>
            ))}
          </div>
        </div>

        <HeroChatPreview />
      </div>
    </section>
  );
}
