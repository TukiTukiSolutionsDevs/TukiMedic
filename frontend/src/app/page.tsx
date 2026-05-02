import { LandingNav } from "@/components/landing/landing-nav";
import { LandingHero } from "@/components/landing/landing-hero";
import { LandingTrust } from "@/components/landing/landing-trust";
import { LandingHow } from "@/components/landing/landing-how";
import { LandingMesa } from "@/components/landing/landing-mesa";
import { LandingFeatures } from "@/components/landing/landing-features";
import { LandingPricing } from "@/components/landing/landing-pricing";
import { LandingFAQ } from "@/components/landing/landing-faq";
import { LandingCTA } from "@/components/landing/landing-cta";
import { LandingFooter } from "@/components/landing/landing-footer";

export default function Home() {
  return (
    <div
      style={{
        minHeight: "100vh",
        background: "var(--tm-bg)",
        color: "var(--tm-text)",
      }}
    >
      <LandingNav />
      <LandingHero />
      <LandingTrust />
      <LandingHow />
      <LandingMesa />
      <LandingFeatures />
      <LandingPricing />
      <LandingFAQ />
      <LandingCTA />
      <LandingFooter />
    </div>
  );
}
