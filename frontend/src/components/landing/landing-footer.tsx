import { Logo } from "@/components/logo";

const FOOTER_COLS = [
  {
    title: "Producto",
    links: ["Cómo funciona", "Mesa médica", "Planes", "Para empresas"],
  },
  {
    title: "Compañía",
    links: ["Sobre nosotros", "Equipo médico", "Blog", "Prensa"],
  },
  {
    title: "Legal",
    links: ["Términos", "Privacidad", "Aviso médico", "Reclamaciones"],
  },
] as const;

function FooterCol({
  title,
  links,
}: {
  title: string;
  links: readonly string[];
}) {
  return (
    <div>
      <div
        className="mb-3.5 text-xs font-semibold uppercase tracking-wider"
        style={{ color: "var(--tm-text-muted)" }}
      >
        {title}
      </div>
      <ul className="m-0 flex list-none flex-col gap-2.5 p-0">
        {links.map((l) => (
          <li key={l}>
            <a
              href="#"
              className="text-sm no-underline transition-colors"
              style={{ color: "var(--tm-text)" }}
            >
              {l}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function LandingFooter() {
  return (
    <footer
      data-testid="landing-footer"
      className="border-t px-8 pb-8 pt-12"
      style={{
        background: "var(--tm-bg)",
        borderColor: "var(--tm-border)",
      }}
    >
      <div className="mx-auto grid max-w-[1200px] grid-cols-1 gap-12 pb-10 md:grid-cols-[2fr_1fr_1fr_1fr]">
        <div>
          <div className="mb-3">
            <Logo size={32} showText />
          </div>
          <p
            className="m-0 max-w-[320px] text-sm leading-[1.6]"
            style={{ color: "var(--tm-text-muted)" }}
          >
            Salud en buenas manos, cuando la necesitas. Hecho en Perú con
            cariño.
          </p>
          <div
            className="mt-4 text-xs leading-[1.6]"
            style={{ color: "var(--tm-text-subtle)" }}
          >
            TukiMedic no diagnostica ni receta. En emergencia:{" "}
            <strong style={{ color: "var(--tm-red-600)" }}>SAMU 106</strong>.
          </div>
        </div>

        {FOOTER_COLS.map((col) => (
          <FooterCol key={col.title} title={col.title} links={col.links} />
        ))}
      </div>

      <div
        className="mx-auto flex max-w-[1200px] flex-wrap items-center justify-between gap-3 border-t pt-6 text-xs"
        style={{
          borderColor: "var(--tm-border)",
          color: "var(--tm-text-subtle)",
        }}
      >
        <div>
          © 2025 TukiMedic SAC · RUC 20612345678 · Av. Javier Prado 1234, San
          Isidro, Lima
        </div>
        <div className="flex gap-4">
          <span>Peru</span>
          <span>·</span>
          <span>Version 0.4.2 beta</span>
        </div>
      </div>
    </footer>
  );
}
