import type { Metadata } from "next";
import { Inter, Outfit } from "next/font/google";
import { Toaster } from "@/components/ui/sonner";
import { Navbar } from "@/components/ui/navbar";
import "./globals.css";

const inter = Inter({
  variable: "--font-sans",
  subsets: ["latin"],
  display: "swap",
});

const outfit = Outfit({
  variable: "--font-heading",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Recall — Student Alumni Relations, IIT Delhi",
  description:
    "AI-powered photo finder by Student Alumni Relations, IIT Delhi. Upload a selfie and instantly find all your photos from the event.",
  keywords: ["photo finder", "face recognition", "IIT Delhi", "SAR", "college events", "AI photos"],
  openGraph: {
    title: "Recall — SAR IIT Delhi Photo Finder",
    description:
      "Upload a selfie. Find every photo of you from the event. By Student Alumni Relations, IIT Delhi.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${outfit.variable} h-full antialiased dark`}
    >
      <body className="min-h-full flex flex-col bg-background text-foreground">
        <Navbar />
        <div className="pt-14">
        {children}
        </div>
        <Toaster
          position="bottom-right"
          toastOptions={{
            style: {
              background: "oklch(0.18 0.02 260)",
              border: "1px solid oklch(1 0 0 / 0.1)",
              color: "oklch(0.95 0.01 260)",
            },
          }}
        />
      </body>
    </html>
  );
}
