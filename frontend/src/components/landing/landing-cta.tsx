import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function LandingCTA() {
  return (
    <section
      data-testid="landing-cta"
      className="px-8 py-[88px]"
      style={{ background: "var(--tm-bg-soft)" }}
    >
      <div
        className="relative mx-auto max-w-[880px] overflow-hidden px-12 py-16 text-center text-white"
        style={{
          background:
            "linear-gradient(135deg, var(--tm-blue-700) 0%, var(--tm-blue-950) 100%)",
          borderRadius: "var(--tm-radius-xl)",
        }}
      >
        <div
          className="pointer-events-none absolute inset-0"
          style={{
            backgroundImage:
              "radial-gradient(circle at 20% 30%, rgba(252,211,77,0.18), transparent 50%)",
          }}
        />

        <div className="relative">
          <h2
            className="mb-4 font-normal leading-[1.1] tracking-[-0.02em]"
            style={{
              fontFamily: "var(--font-instrument-serif)",
              fontSize: "clamp(1.75rem, 4vw, 3.25rem)",
            }}
          >
            Tu salud merece{" "}
            <em style={{ color: "var(--tm-yellow-300)" }}>una mesa médica</em>.
          </h2>

          <p className="mx-auto mb-8 max-w-[560px] text-lg leading-[1.55] opacity-85">
            Empezá gratis ahora. Sin tarjeta, sin compromiso. En 60 segundos
            tenés tu primera consulta resuelta.
          </p>

          <Link
            href="/register"
            className={cn(
              buttonVariants({ size: "lg" }),
              "bg-white text-[var(--tm-blue-900)] hover:bg-white/90",
            )}
          >
            Crear mi cuenta gratis <ArrowRight className="size-4" />
          </Link>

          <div className="mt-6 text-xs opacity-70">
            Más de 400 personas en Lima, Arequipa, Cusco y Trujillo ya están
            usando TukiMedic.
          </div>
        </div>
      </div>
    </section>
  );
}
