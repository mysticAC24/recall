"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import type { SearchResponse, MatchedPhoto } from "@/lib/api";

function PhotoCard({ result, index }: { result: MatchedPhoto; index: number }) {
  const [loaded, setLoaded] = useState(false);
  const [showOverlay, setShowOverlay] = useState(false);

  const similarity = Math.round(result.similarity * 100);

  const handleDownload = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (result.image_url) {
      window.open(result.image_url, "_blank");
    }
  };

  return (
    <div
      className="group relative rounded-xl overflow-hidden bg-card border border-border/30 opacity-0 animate-scale-in"
      style={{ animationDelay: `${Math.min(index * 0.05, 0.5)}s` }}
      onMouseEnter={() => setShowOverlay(true)}
      onMouseLeave={() => setShowOverlay(false)}
    >
      {/* Skeleton placeholder */}
      {!loaded && (
        <Skeleton className="absolute inset-0 w-full h-full" />
      )}

      {/* Image */}
      <img
        src={result.thumbnail_url || result.image_url || ""}
        alt={result.filename || "Matched photo"}
        loading="lazy"
        className={`
          w-full aspect-[4/3] object-cover transition-all duration-500
          ${loaded ? "opacity-100" : "opacity-0"}
          group-hover:scale-105
        `}
        onLoad={() => setLoaded(true)}
      />

      {/* Hover overlay */}
      <div
        className={`
          absolute inset-0 bg-gradient-to-t from-black/70 via-black/20 to-transparent
          transition-opacity duration-300
          ${showOverlay ? "opacity-100" : "opacity-0"}
        `}
      >
        {/* Match badge */}
        <div className="absolute top-3 left-3">
          <Badge
            className={`
              font-mono text-xs
              ${similarity >= 80
                ? "bg-emerald-500/80 text-white border-emerald-400/50"
                : similarity >= 65
                  ? "bg-amber-500/80 text-white border-amber-400/50"
                  : "bg-blue-500/80 text-white border-blue-400/50"
              }
            `}
            variant="outline"
          >
            {similarity}% match
          </Badge>
        </div>

        {/* Download button */}
        <div className="absolute bottom-3 right-3">
          <button
            onClick={handleDownload}
            className="w-10 h-10 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center text-white hover:bg-white/30 transition-all hover:scale-110"
            title="Download full resolution"
            id={`download-${result.photo_id}`}
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
            </svg>
          </button>
        </div>

        {/* Filename */}
        <div className="absolute bottom-3 left-3">
          <p className="text-xs text-white/70 truncate max-w-[150px]">
            {result.filename}
          </p>
        </div>
      </div>
    </div>
  );
}

export default function ResultsPage() {
  const [data, setData] = useState<SearchResponse | null>(null);
  const [isDownloadingAll, setIsDownloadingAll] = useState(false);

  useEffect(() => {
    const stored = sessionStorage.getItem("recall_results");
    if (stored) {
      try {
        setData(JSON.parse(stored));
      } catch {
        // Invalid data
      }
    }
  }, []);

  const handleDownloadAll = useCallback(async () => {
    if (!data || data.matches.length === 0) return;

    setIsDownloadingAll(true);
    toast.info(`Opening ${data.matches.length} photos for download...`);

    for (let i = 0; i < data.matches.length; i++) {
      const url = data.matches[i].image_url;
      if (url) window.open(url, "_blank");
      if (i < data.matches.length - 1) {
        await new Promise((resolve) => setTimeout(resolve, 300));
      }
    }

    setIsDownloadingAll(false);
    toast.success("All photos opened! Save them from your browser.");
  }, [data]);

  // No data at all
  if (!data) {
    return (
      <main className="flex-1 flex items-center justify-center min-h-screen p-4 bokeh-bg">
        <div className="text-center space-y-4 relative z-10">
          <div className="w-20 h-20 rounded-full bg-muted/50 flex items-center justify-center mx-auto">
            <svg className="w-10 h-10 text-muted-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5a2.25 2.25 0 002.25-2.25V6.75a2.25 2.25 0 00-2.25-2.25H3.75A2.25 2.25 0 001.5 6.75v12a2.25 2.25 0 002.25 2.25z" />
            </svg>
          </div>
          <h2 className="text-xl font-semibold">No search results</h2>
          <p className="text-muted-foreground">Upload a selfie to find your photos</p>
          <Link href="/search">
            <Button size="lg">
              <svg className="w-4 h-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
              </svg>
              Search Photos
            </Button>
          </Link>
        </div>
      </main>
    );
  }

  // Zero matches
  if (data.matches.length === 0) {
    return (
      <main className="flex-1 flex items-center justify-center min-h-screen p-4 bokeh-bg">
        <div className="text-center space-y-4 relative z-10">
          <div className="w-20 h-20 rounded-full bg-amber-500/10 flex items-center justify-center mx-auto">
            <svg className="w-10 h-10 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.182 16.318A4.486 4.486 0 0012.016 15a4.486 4.486 0 00-3.198 1.318M21 12a9 9 0 11-18 0 9 9 0 0118 0zM9.75 9.75c0 .414-.168.75-.375.75S9 10.164 9 9.75 9.168 9 9.375 9s.375.336.375.75zm-.375 0h.008v.015h-.008V9.75zm5.625 0c0 .414-.168.75-.375.75s-.375-.336-.375-.75.168-.75.375-.75.375.336.375.75zm-.375 0h.008v.015h-.008V9.75z" />
            </svg>
          </div>
          <h2 className="text-xl font-semibold">No matches found</h2>
          <p className="text-muted-foreground max-w-md">
            We couldn&apos;t find any matching photos. Try uploading a clearer selfie with good lighting.
          </p>
          <Link href="/search">
            <Button size="lg" variant="outline">
              Try Again
            </Button>
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className="flex-1 min-h-screen p-4 sm:p-8">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <Link href="/search" className="text-sm text-muted-foreground hover:text-foreground transition-colors inline-flex items-center gap-1 mb-2">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
              </svg>
              Search again
            </Link>
            <h1
              className="text-3xl sm:text-4xl font-bold"
              style={{ fontFamily: "var(--font-heading), var(--font-sans), sans-serif" }}
            >
              Found{" "}
              <span className="text-gradient">{data.total} photo{data.total !== 1 ? "s" : ""}</span>
              {" "}of you!
            </h1>
            <p className="text-muted-foreground mt-1 text-sm">
              Similarity threshold: {Math.round(data.threshold * 100)}%
            </p>
          </div>

          <div className="flex items-center gap-3">
            <Link href="/search">
              <Button variant="outline" size="sm" id="search-again-btn">
                <svg className="w-4 h-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
                </svg>
                New Search
              </Button>
            </Link>
            <Button
              onClick={handleDownloadAll}
              disabled={isDownloadingAll}
              size="sm"
              className="glow-amber-hover"
              id="download-all-btn"
            >
              {isDownloadingAll ? (
                <>
                  <svg className="w-4 h-4 mr-1 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Downloading...
                </>
              ) : (
                <>
                  <svg className="w-4 h-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                  </svg>
                  Download All
                </>
              )}
            </Button>
          </div>
        </div>

        {/* Photo grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {data.matches.map((match, index) => (
            <PhotoCard key={match.photo_id} result={match} index={index} />
          ))}
        </div>
      </div>
    </main>
  );
}
