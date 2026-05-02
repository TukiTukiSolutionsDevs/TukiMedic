import Image from "next/image";
import Link from "next/link";
import { cn } from "@/lib/utils";

interface LogoProps {
  /** Pixel size of the logo image (square). Default 32. */
  size?: number;
  /** Show the brand text next to the logo. */
  showText?: boolean;
  /** Wrap in a link to `/`. */
  asLink?: boolean;
  /** Override the text content. */
  text?: string;
  className?: string;
}

/**
 * Brand logo for TukiMedic. Renders the bitmap from /logo.png plus optional
 * wordmark in Instrument Serif. When `asLink` is true, wraps in a Next.js
 * Link to the landing/home route.
 */
export function Logo({
  size = 32,
  showText = true,
  asLink = false,
  text = "TukiMedic",
  className,
}: LogoProps) {
  const content = (
    <span
      className={cn(
        "inline-flex items-center gap-2 font-serif",
        className,
      )}
      data-testid="tm-logo"
    >
      <Image
        src="/logo.png"
        alt="TukiMedic"
        width={size}
        height={size}
        priority
        className="rounded-md"
      />
      {showText && (
        <span
          className="text-xl font-medium tracking-tight"
          style={{ fontFamily: "var(--font-instrument-serif)" }}
        >
          {text}
        </span>
      )}
    </span>
  );

  if (asLink) {
    return (
      <Link href="/" className="inline-flex items-center" aria-label="TukiMedic">
        {content}
      </Link>
    );
  }
  return content;
}
