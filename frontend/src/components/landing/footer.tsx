import { SARLogo } from "@/components/ui/sar-logo";

export function Footer() {
  return (
    <footer className="relative py-10 px-4 border-t border-border/50">
      <div className="max-w-5xl mx-auto space-y-6">
        {/* SAR branding row */}
        <div className="flex flex-col sm:flex-row items-start justify-between gap-6">
          <SARLogo />
          <p className="text-xs text-muted-foreground/70 sm:text-right max-w-xs leading-relaxed">
            For any queries, reach out to{" "}
            <a
              href="mailto:student.coordinator@alumni.iitd.ac.in"
              className="text-muted-foreground hover:text-foreground transition-colors underline underline-offset-2"
            >
              student.coordinator@alumni.iitd.ac.in
            </a>
          </p>
        </div>

        {/* Bottom row */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-2 pt-4 border-t border-border/30">
          <p className="text-xs text-muted-foreground/60">
            Made with ♥ by{" "}
            <span className="text-primary/80 font-medium">Student Alumni Relations, IIT Delhi</span>
          </p>
          <p className="text-xs text-muted-foreground/60">
            © {new Date().getFullYear()} Recall
          </p>
        </div>
      </div>
    </footer>
  );
}
