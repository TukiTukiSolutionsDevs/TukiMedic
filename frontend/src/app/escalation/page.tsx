"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  MapPin,
  Phone,
} from "lucide-react";

const DEFAULT_RED_FLAGS = [
  "Dolor torácico agudo con irradiación al brazo",
  "Diaforesis (sudoración fría)",
  "Inicio reciente (<30 min)",
];

const SAMU_NUMBER = "106"; // Perú; configurable later via env

interface EscalationPayload {
  caseId?: string | null;
  redFlags?: string[];
  userMessage?: string;
  at?: string;
}

function readPayload(): EscalationPayload | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem("tm-escalation");
    if (!raw) return null;
    return JSON.parse(raw) as EscalationPayload;
  } catch {
    return null;
  }
}

export default function EscalationPage() {
  const router = useRouter();
  const [payload, setPayload] = useState<EscalationPayload | null>(null);

  useEffect(() => {
    setPayload(readPayload());
  }, []);

  const redFlags =
    payload?.redFlags && payload.redFlags.length > 0
      ? payload.redFlags
      : DEFAULT_RED_FLAGS;

  function handleNewCase() {
    if (typeof window !== "undefined") {
      window.sessionStorage.removeItem("tm-escalation");
    }
    router.push("/chat");
  }

  return (
    <div
      data-testid="escalation-page"
      role="alert"
      aria-live="assertive"
      className="flex min-h-screen flex-col gap-6 px-6 py-8 md:px-10"
      style={{
        background:
          "linear-gradient(180deg, var(--tm-red-50) 0%, var(--tm-bg) 60%)",
      }}
    >
      <div className="flex items-center justify-between">
        <Link
          href="/dashboard"
          className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs text-[var(--tm-text-muted)] hover:bg-[var(--tm-bg-soft)]"
          data-testid="escalation-back"
        >
          <ArrowLeft size={14} aria-hidden /> Volver
        </Link>
        <span
          data-testid="escalation-badge"
          className="inline-flex items-center gap-1.5 rounded-full border border-[var(--tm-red-500)]/30 bg-[var(--tm-red-50)] px-2.5 py-1 text-xs font-medium text-[var(--tm-red-700)]"
        >
          <AlertTriangle size={12} aria-hidden /> Triage RED · Acción inmediata
        </span>
      </div>

      <section
        className="relative overflow-hidden rounded-3xl px-8 py-10 text-white shadow-2xl md:px-11"
        style={{
          background:
            "linear-gradient(135deg, var(--tm-red-600) 0%, var(--tm-red-700) 60%, #7F1D1D 100%)",
          boxShadow: "0 24px 60px -16px rgba(220,38,38,0.45)",
        }}
      >
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{
            backgroundImage:
              "radial-gradient(circle at 90% 10%, rgba(255,255,255,0.12), transparent 40%)",
          }}
        />
        <div className="relative flex flex-col items-start gap-5 md:flex-row">
          <div
            aria-hidden
            className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full border-2 border-white/30 bg-white/15"
            style={{ animation: "tm-pulse-dot 1.6s ease-in-out infinite" }}
          >
            <AlertTriangle size={32} strokeWidth={2.2} />
          </div>
          <div className="flex-1">
            <div className="mb-2 text-[11px] font-semibold uppercase tracking-widest text-white/85">
              Atención · esto requiere ayuda médica ahora
            </div>
            <h1
              className="text-4xl leading-tight md:text-5xl"
              style={{
                fontFamily: "var(--font-instrument-serif)",
                fontWeight: 400,
                letterSpacing: "-0.015em",
              }}
            >
              Buscá atención médica
              <br />
              <em
                className="not-italic"
                style={{ color: "var(--tm-yellow-300)", fontStyle: "italic" }}
              >
                de inmediato
              </em>
              .
            </h1>
            <p className="mt-4 max-w-2xl text-base leading-relaxed text-white/90">
              Detectamos señales que requieren evaluación médica presencial
              urgente.{" "}
              <strong>TukiMedic no puede atender emergencias.</strong> Si estás
              en peligro inmediato, llamá al número de emergencias.
            </p>
          </div>
        </div>

        <div className="relative mt-8 grid gap-3.5 md:grid-cols-2">
          <a
            href={`tel:${SAMU_NUMBER}`}
            data-testid="escalation-call"
            className="flex items-center gap-4 rounded-xl bg-white px-6 py-5 text-[var(--tm-red-700)] shadow-lg transition-transform hover:-translate-y-0.5"
          >
            <span
              aria-hidden
              className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-[var(--tm-red-50)] text-[var(--tm-red-700)]"
            >
              <Phone size={22} strokeWidth={2.2} />
            </span>
            <span className="block">
              <span className="block text-[11px] font-semibold uppercase tracking-widest opacity-70">
                SAMU · Perú
              </span>
              <span
                className="mt-1 block text-2xl font-bold leading-none md:text-3xl"
                style={{ fontFamily: "var(--font-geist-mono)" }}
              >
                Llamar {SAMU_NUMBER}
              </span>
            </span>
          </a>

          <a
            href="https://www.google.com/maps/search/hospital+cerca/"
            target="_blank"
            rel="noopener noreferrer"
            data-testid="escalation-hospitals"
            className="flex items-center gap-4 rounded-xl border border-white/25 bg-white/15 px-6 py-5 backdrop-blur transition-colors hover:bg-white/20"
          >
            <span
              aria-hidden
              className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-white/15"
            >
              <MapPin size={22} strokeWidth={2.2} />
            </span>
            <span className="block">
              <span className="block text-[11px] font-semibold uppercase tracking-widest opacity-85">
                Hospitales
              </span>
              <span className="mt-1 block text-base font-semibold leading-tight md:text-lg">
                Buscar el más cercano
              </span>
            </span>
            <ArrowRight
              size={20}
              className="ml-auto opacity-70"
              aria-hidden
            />
          </a>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        <div
          data-testid="escalation-redflags"
          className="rounded-xl border bg-[var(--tm-surface)] p-6 shadow-sm"
        >
          <div className="mb-3.5 flex items-center gap-2">
            <AlertTriangle
              size={16}
              className="text-[var(--tm-red-600)]"
              aria-hidden
            />
            <h2 className="text-sm font-semibold uppercase tracking-widest text-[var(--tm-red-700)]">
              Señales detectadas
            </h2>
          </div>
          <ul className="flex flex-col gap-2.5">
            {redFlags.map((flag, i) => (
              <li
                key={`${flag}-${i}`}
                data-testid="escalation-redflag-item"
                className="flex items-start gap-2 text-sm leading-relaxed"
              >
                <span
                  aria-hidden
                  className="mt-2 inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--tm-red-500)]"
                />
                <span>{flag}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="rounded-xl border bg-[var(--tm-surface)] p-6 shadow-sm">
          <h2 className="mb-3.5 text-sm font-semibold uppercase tracking-widest text-[var(--tm-text-muted)]">
            Mientras esperás ayuda
          </h2>
          <ul className="flex flex-col gap-2.5 text-sm leading-relaxed text-[var(--tm-text)]">
            <li className="flex items-start gap-2">
              <span
                aria-hidden
                className="mt-2 inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--tm-blue-500)]"
              />
              <span>
                No comas ni tomes nada hasta que te evalúe el médico.
              </span>
            </li>
            <li className="flex items-start gap-2">
              <span
                aria-hidden
                className="mt-2 inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--tm-blue-500)]"
              />
              <span>
                Si tomás medicación regular, anotá nombres y dosis para mostrar
                en urgencias.
              </span>
            </li>
            <li className="flex items-start gap-2">
              <span
                aria-hidden
                className="mt-2 inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--tm-blue-500)]"
              />
              <span>
                Si podés, andá acompañado o avisá a alguien dónde vas.
              </span>
            </li>
          </ul>
        </div>
      </section>

      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          onClick={handleNewCase}
          data-testid="escalation-new-case"
          className="rounded-md bg-[var(--tm-blue-600)] px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-[var(--tm-blue-700)]"
        >
          Iniciar consulta nueva
        </button>
        <Link
          href="/dashboard"
          data-testid="escalation-go-dashboard"
          className="rounded-md border border-[var(--tm-border-strong)] bg-[var(--tm-surface)] px-4 py-2 text-sm font-medium text-[var(--tm-text)] hover:bg-[var(--tm-bg-soft)]"
        >
          Volver al inicio
        </Link>
      </div>
    </div>
  );
}
