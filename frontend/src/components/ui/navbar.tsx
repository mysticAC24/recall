import Link from "next/link";
import { SARLogo } from "@/components/ui/sar-logo";

export function Navbar() {
  return (
    <nav className="fixed top-0 left-0 right-0 z-50 px-4 py-3 border-b border-white/5 bg-background/80 backdrop-blur-md">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        <Link href="/">
          <SARLogo className="opacity-90 hover:opacity-100 transition-opacity" />
        </Link>
        <Link
          href="/search"
          className="text-sm text-muted-foreground hover:text-foreground transition-colors hidden sm:block"
        >
          Find My Photos →
        </Link>
      </div>
    </nav>
  );
}
