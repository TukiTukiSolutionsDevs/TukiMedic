import {
  FileText,
  ShieldCheck,
  Heart,
  Download,
  MessageSquare,
  Lock,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";

const FEATURES: Array<{ Icon: LucideIcon; title: string; desc: string }> = [
  {
    Icon: FileText,
    title: "Subís tus análisis",
    desc: "PDF de laboratorio, recetas, ecografías. Hasta 20 MB por archivo.",
  },
  {
    Icon: ShieldCheck,
    title: "Audit chain SHA-256",
    desc: "Cada respuesta queda firmada en una cadena verificable. Trazabilidad real.",
  },
  {
    Icon: Heart,
    title: "Ficha clínica que aprende",
    desc: "Recordamos tus alergias, medicación y condiciones para no preguntar dos veces.",
  },
  {
    Icon: Download,
    title: "Export para tu médico",
    desc: "PDF profesional con todo el contexto para llevar a tu consulta presencial.",
  },
  {
    Icon: MessageSquare,
    title: "En español, así como hablamos",
    desc: "Conversacional, sin tecnicismos. Te explicamos cada palabra rara.",
  },
  {
    Icon: Lock,
    title: "Privacidad por diseño",
    desc: "Cifrado AES-256-GCM. Tus datos no se venden, no se comparten, no se entrenan modelos públicos.",
  },
];

export function LandingFeatures() {
  return (
    <section
      data-testid="landing-features"
      className="px-8 py-24"
      style={{ background: "var(--tm-bg-soft)" }}
    >
      <div className="mx-auto max-w-[1200px]">
        <div className="mb-12 max-w-[720px]">
          <Badge variant="outline">Capacidades</Badge>
          <h2
            className="mt-5 mb-4 font-normal leading-[1.1] tracking-[-0.02em]"
            style={{
              fontFamily: "var(--font-instrument-serif)",
              fontSize: "clamp(1.75rem, 3.5vw, 3rem)",
              color: "var(--tm-text)",
            }}
          >
            Construido para acompañarte{" "}
            <em style={{ color: "var(--tm-blue-600)" }}>en serio</em>.
          </h2>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <div
              key={f.title}
              className="p-6"
              style={{
                background: "var(--tm-surface)",
                border: "1px solid var(--tm-border)",
                borderRadius: "var(--tm-radius)",
              }}
            >
              <div
                className="mb-4 flex size-10 items-center justify-center rounded-[10px]"
                style={{
                  background: "var(--tm-blue-50)",
                  color: "var(--tm-blue-700)",
                }}
              >
                <f.Icon className="size-5" />
              </div>
              <h3 className="mb-1.5 text-base font-semibold">{f.title}</h3>
              <p
                className="m-0 text-sm leading-[1.55]"
                style={{ color: "var(--tm-text-muted)" }}
              >
                {f.desc}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
