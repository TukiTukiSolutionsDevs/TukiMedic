"use client";

import { useState } from "react";
import { Plus, Minus } from "lucide-react";
import { Badge } from "@/components/ui/badge";

const FAQ_ITEMS = [
  {
    q: "¿TukiMedic reemplaza al médico?",
    a: "No. TukiMedic orienta, no diagnostica ni receta. Es como tener una segunda opinión ilustrada para saber qué hacer: si esperar, si ir al médico esta semana o si correr a emergencia. Las decisiones clínicas siempre las toma un profesional presencial.",
  },
  {
    q: "¿Mis datos están seguros?",
    a: "Sí. Toda tu información se guarda cifrada con AES-256-GCM. Cada acción queda firmada en una cadena de auditoría SHA-256 verificable. No vendemos datos, no entrenamos modelos públicos con tu historial y podés pedir que olvidemos cualquier cosa cuando quieras.",
  },
  {
    q: "¿Funciona en provincia, no solo Lima?",
    a: "Funciona en todo el Perú con cualquier conexión a internet. Las recomendaciones de derivación toman en cuenta tu ubicación: si estás en Lima sugerimos hospitales de referencia, si estás en provincia priorizamos lo que tenés más cerca.",
  },
  {
    q: "¿Para qué edades sirve?",
    a: "Adultos a partir de 18 años. Para menores de edad usamos el modo pediátrico (incluido en planes Pro y Familia) con dosis ajustadas por peso y un tono apropiado.",
  },
  {
    q: "¿Qué pasa si tengo una emergencia?",
    a: "Si el triage detecta señales de alarma rojas, te derivamos inmediatamente al SAMU 106, te damos instrucciones de qué hacer mientras esperás la ambulancia y te indicamos los hospitales más cercanos. TukiMedic no atiende emergencias — te ayuda a llegar al lugar correcto, rápido.",
  },
  {
    q: "¿Cómo cancelo si no me sirve?",
    a: "Desde tu perfil, en un click. Sin llamadas, sin retención, sin letra chica. Si te suscribiste con Yape o Plin, basta con cancelar el cobro recurrente. Conservás acceso hasta el final del período pagado.",
  },
  {
    q: "¿Puedo subir resultados de análisis?",
    a: "Sí: PDFs de laboratorio, recetas, ecografías e imágenes. Hasta 20 MB por archivo. La mesa médica los lee y los incorpora al análisis. En plan gratuito permitimos 3 documentos al mes; en Pro y Familia es ilimitado.",
  },
  {
    q: "¿Aceptan EsSalud, SIS o seguros privados?",
    a: "TukiMedic no está integrado con seguros — somos un servicio de orientación independiente. El export en PDF está pensado para que lo lleves a tu cita en EsSalud, SIS o tu clínica privada como contexto previo.",
  },
] as const;

export function LandingFAQ() {
  const [open, setOpen] = useState<number>(-1);

  return (
    <section
      id="faq"
      data-testid="landing-faq"
      className="px-8 py-24"
      style={{ background: "var(--tm-bg)" }}
    >
      <div className="mx-auto max-w-[880px]">
        <div className="mb-14 text-center">
          <Badge variant="outline">Preguntas frecuentes</Badge>
          <h2
            className="mt-5 font-normal leading-[1.1] tracking-[-0.02em]"
            style={{
              fontFamily: "var(--font-instrument-serif)",
              fontSize: "clamp(1.75rem, 3.5vw, 3rem)",
              color: "var(--tm-text)",
            }}
          >
            Las dudas{" "}
            <em style={{ color: "var(--tm-blue-600)" }}>de siempre</em>.
          </h2>
        </div>

        <div className="flex flex-col gap-2">
          {FAQ_ITEMS.map((item, i) => (
            <div
              key={item.q}
              className="overflow-hidden"
              style={{
                background: "var(--tm-surface)",
                border: "1px solid var(--tm-border)",
                borderRadius: "var(--tm-radius)",
              }}
            >
              <button
                type="button"
                onClick={() => setOpen(open === i ? -1 : i)}
                className="flex w-full cursor-pointer items-center justify-between gap-4 border-0 bg-transparent px-6 py-5 text-left text-base font-semibold"
                style={{ color: "var(--tm-text)" }}
              >
                <span>{item.q}</span>
                {open === i ? (
                  <Minus
                    className="size-[18px] shrink-0"
                    style={{ color: "var(--tm-text-muted)" }}
                  />
                ) : (
                  <Plus
                    className="size-[18px] shrink-0"
                    style={{ color: "var(--tm-text-muted)" }}
                  />
                )}
              </button>

              {open === i && (
                <div
                  className="px-6 pb-[22px] text-[0.9375rem] leading-[1.65]"
                  style={{ color: "var(--tm-text-muted)" }}
                >
                  {item.a}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
