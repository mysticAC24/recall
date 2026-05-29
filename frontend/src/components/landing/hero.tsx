"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getPhotoStats, type PhotoStats } from "@/lib/api";
import { SARLogo } from "@/components/ui/sar-logo";

export function Hero() {
  const [stats, setStats] = useState<PhotoStats | null>(null);

  useEffect(() => {
    getPhotoStats()
      .then(setStats)
      .catch(() => {});
  }, []);

  return (
    <section className="relative min-h-screen flex items-center justify-center overflow-hidden bokeh-bg">
      {/* Extra bokeh orbs */}
      <div className="absolute inset-0 pointer-events-none">
        <div
          className="absolute w-[300px] h-[300px] rounded-full opacity-20 blur-[100px]"
          style={{
            background: "oklch(0.82 0.15 75)",
            top: "20%",
            left: "60%",
            animation: "bokeh-drift 20s ease-in-out infinite",
            animationDelay: "-5s",
          }}
        />
        <div
          className="absolute w-[250px] h-[250px] rounded-full opacity-15 blur-[80px]"
          style={{
            background: "oklch(0.70 0.18 330)",
            top: "60%",
            left: "30%",
            animation: "bokeh-drift 18s ease-in-out infinite",
            animationDelay: "-10s",
          }}
        />
      </div>

      {/* Content */}
      <div className="relative z-10 text-center px-4 max-w-4xl mx-auto">

        {/* Badge */}
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full glass text-sm text-muted-foreground mb-8 animate-fade-in">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span>AI-Powered Face Recognition</span>
        </div>

        {/* Heading */}
        <h1
          className="text-5xl sm:text-6xl md:text-7xl lg:text-8xl font-bold tracking-tight mb-6 opacity-0 animate-slide-up"
          style={{ fontFamily: "var(--font-heading), var(--font-sans), sans-serif" }}
        >
          <span className="text-gradient">Find yourself</span>
          <br />
          <span className="text-foreground/90">in every memory</span>
        </h1>

        {/* Subtitle */}
        <p className="text-lg sm:text-xl text-muted-foreground max-w-2xl mx-auto mb-10 opacity-0 animate-slide-up stagger-2">
          Upload a selfie and let AI find all your photos from the event.
          No more endless scrolling through hundreds of images.
        </p>

        {/* CTA Buttons */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 opacity-0 animate-slide-up stagger-3">
          <Link
            href="/search"
            className="group relative inline-flex items-center gap-2 px-8 py-4 rounded-xl bg-primary text-primary-foreground font-semibold text-lg transition-all duration-300 hover:scale-105 glow-amber hover:glow-amber"
          >
            <svg
              className="w-5 h-5 transition-transform group-hover:rotate-12"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"
              />
            </svg>
            Find My Photos
            <svg
              className="w-4 h-4 transition-transform group-hover:translate-x-1"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
            </svg>
          </Link>

          <Link
            href="/admin"
            className="inline-flex items-center gap-2 px-8 py-4 rounded-xl glass glass-hover font-medium text-foreground/80 text-lg"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M10.5 6h9.75M10.5 6a1.5 1.5 0 11-3 0m3 0a1.5 1.5 0 10-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-9.75 0h9.75"
              />
            </svg>
            Admin Panel
          </Link>
        </div>

        {/* Stats */}
        {stats && stats.total_photos > 0 && (
          <div className="mt-12 inline-flex items-center gap-6 px-6 py-3 rounded-2xl glass opacity-0 animate-fade-in stagger-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-gradient">{stats.total_photos.toLocaleString()}</div>
              <div className="text-xs text-muted-foreground">Photos Indexed</div>
            </div>
            <div className="w-px h-8 bg-border" />
            <div className="text-center">
              <div className="text-2xl font-bold text-gradient">{stats.total_faces.toLocaleString()}</div>
              <div className="text-xs text-muted-foreground">Faces Detected</div>
            </div>
            {stats.event_name && (
              <>
                <div className="w-px h-8 bg-border" />
                <div className="text-center">
                  <div className="text-sm font-medium text-foreground/80">{stats.event_name}</div>
                  <div className="text-xs text-muted-foreground">Current Event</div>
                </div>
              </>
            )}
          </div>
        )}
      </div>

      {/* Bottom gradient fade */}
      <div className="absolute bottom-0 left-0 right-0 h-32 bg-gradient-to-t from-background to-transparent" />
    </section>
  );
}
