import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MedAgent — Plataforma Clínica Conversacional",
  description: "Sistema de análisis clínico coordinado multi-agente",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es">
      <body className="min-h-screen bg-background antialiased">
        <div className="flex h-screen">
          {/* Sidebar */}
          <aside className="hidden w-64 border-r bg-muted/40 md:block">
            <div className="flex h-14 items-center border-b px-4">
              <h1 className="text-lg font-semibold">MedAgent</h1>
            </div>
            <nav className="p-4 space-y-2">
              <p className="text-sm text-muted-foreground">Casos recientes</p>
              {/* Case list will go here */}
            </nav>
          </aside>

          {/* Main content */}
          <main className="flex-1 flex flex-col">{children}</main>
        </div>
      </body>
    </html>
  );
}
