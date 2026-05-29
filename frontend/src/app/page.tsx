import { Hero } from "@/components/landing/hero";
import { Features } from "@/components/landing/features";
import { Footer } from "@/components/landing/footer";

export default function HomePage() {
  return (
    <main className="flex-1">
      <Hero />
      <Features />
      <Footer />
    </main>
  );
}
