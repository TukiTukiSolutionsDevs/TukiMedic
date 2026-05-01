import type { Metadata } from "next";
import { Geist, Geist_Mono, Instrument_Serif } from "next/font/google";
import { ThemeProvider } from "@/components/theme/theme-provider";
import { themeScript } from "@/components/theme/theme-provider";
import "./globals.css";

const geist = Geist({
  subsets: ["latin"],
  variable: "--font-geist",
});

const geistMono = Geist_Mono({
  subsets: ["latin"],
  variable: "--font-geist-mono",
});

const instrumentSerif = Instrument_Serif({
  subsets: ["latin"],
  weight: "400",
  style: ["normal", "italic"],
  variable: "--font-instrument-serif",
});

export const metadata: Metadata = {
  title: "TukiMedic — Plataforma Clínica Conversacional",
  description: "Sistema de análisis clínico coordinado multi-agente",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="es"
      suppressHydrationWarning
      className={`${geist.variable} ${geistMono.variable} ${instrumentSerif.variable}`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="min-h-screen bg-background antialiased">
        <ThemeProvider>
          <div className="flex h-screen">
            {/* Sidebar */}
            <aside className="hidden w-64 border-r bg-muted/40 md:block">
              <div className="flex h-14 items-center border-b px-4">
                <h1 className="text-lg font-semibold">TukiMedic</h1>
              </div>
              <nav className="p-4 space-y-2">
                <p className="text-sm text-muted-foreground">Casos recientes</p>
                {/* Case list will go here */}
              </nav>
            </aside>

            {/* Main content */}
            <main className="flex-1 flex flex-col">{children}</main>
          </div>
        </ThemeProvider>
      </body>
    </html>
  );
}
