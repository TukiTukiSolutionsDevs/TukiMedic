"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Logo } from "@/components/logo";
import { ThemeToggle } from "@/components/theme/theme-toggle";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function LandingNav() {
  return (
    <header
      data-testid="landing-nav"
      className="sticky top-0 z-50 border-b"
      style={{
        background: "rgba(251, 252, 253, 0.85)",
        backdropFilter: "saturate(180%) blur(12px)",
        WebkitBackdropFilter: "saturate(180%) blur(12px)",
        borderColor: "var(--tm-border)",
      }}
    >
      <div className="mx-auto flex max-w-[1200px] items-center justify-between gap-4 px-8 py-3.5">
        {/* Brand */}
        <div className="flex items-center gap-2.5">
          <Logo asLink size={32} showText />
          <Badge variant="outline" className="ml-1.5 text-xs">
            Peru · Beta
          </Badge>
        </div>

        {/* Anchor nav */}
        <nav className="hidden items-center gap-7 text-sm md:flex">
          {(
            [
              { label: "Cómo funciona", href: "#como-funciona" },
              { label: "Mesa médica", href: "#mesa-medica" },
              { label: "Planes", href: "#planes" },
              { label: "Preguntas", href: "#faq" },
            ] as const
          ).map(({ label, href }) => (
            <a
              key={href}
              href={href}
              className="font-medium no-underline transition-colors"
              style={{ color: "var(--tm-text-muted)" }}
            >
              {label}
            </a>
          ))}
        </nav>

        {/* Actions */}
        <div className="flex items-center gap-2.5">
          <ThemeToggle />
          <Link
            href="/login"
            className={cn(buttonVariants({ variant: "ghost", size: "sm" }))}
          >
            Ingresar
          </Link>
          <Link
            href="/register"
            className={cn(buttonVariants({ size: "sm" }))}
          >
            Crear cuenta <ArrowRight className="size-3.5" />
          </Link>
        </div>
      </div>
    </header>
  );
}
