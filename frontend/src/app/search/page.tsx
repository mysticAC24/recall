"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { toast } from "sonner";
import { searchFaces, getPhotoStats } from "@/lib/api";

export default function SearchPage() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [eventReady, setEventReady] = useState<boolean | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  const ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/webp"];
  const MAX_SIZE = 10 * 1024 * 1024; // 10MB

  // Check if there's a completed event
  useEffect(() => {
    getPhotoStats()
      .then((stats) => {
        setEventReady(stats.status === "completed" && stats.total_photos > 0);
      })
      .catch(() => setEventReady(false));
  }, []);

  const processFile = useCallback((f: File) => {
    if (!ACCEPTED_TYPES.includes(f.type)) {
      toast.error("Please upload a JPEG, PNG, or WebP image");
      return;
    }
    if (f.size > MAX_SIZE) {
      toast.error("File size must be under 10MB");
      return;
    }
    setFile(f);
    const reader = new FileReader();
    reader.onload = () => setPreview(reader.result as string);
    reader.readAsDataURL(f);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const f = e.dataTransfer.files[0];
      if (f) processFile(f);
    },
    [processFile]
  );

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) processFile(f);
  };

  const handleRemove = () => {
    setFile(null);
    setPreview(null);
    if (inputRef.current) inputRef.current.value = "";
  };

  const handleSearch = async () => {
    if (!file) {
      toast.error("Please upload a selfie first");
      return;
    }

    setIsSearching(true);
    try {
      // Discover the latest completed event
      const stats = await getPhotoStats();
      if (!stats.event_id || stats.status !== "completed") {
        toast.error("No indexed event found. Ask your organizer to process photos first.");
        setIsSearching(false);
        return;
      }

      const response = await searchFaces(stats.event_id, file);
      sessionStorage.setItem("recall_results", JSON.stringify(response));
      router.push("/results");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Search failed. Please try again.";
      toast.error(message);
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <main className="flex-1 flex items-center justify-center min-h-screen p-4 bokeh-bg">
      <div className="w-full max-w-lg mx-auto space-y-6 relative z-10">
        {/* Back link */}
        <Link href="/" className="text-sm text-muted-foreground hover:text-foreground transition-colors inline-flex items-center gap-1">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
          </svg>
          Back to home
        </Link>

        {/* Header */}
        <div className="text-center">
          <h1
            className="text-3xl sm:text-4xl font-bold mb-3"
            style={{ fontFamily: "var(--font-heading), var(--font-sans), sans-serif" }}
          >
            <span className="text-gradient">Find Your Photos</span>
          </h1>
          <p className="text-muted-foreground">
            Upload a clear selfie and we&apos;ll find all your photos from the event
          </p>
        </div>

        {/* Event not ready warning */}
        {eventReady === false && (
          <div className="flex items-center gap-3 p-4 rounded-xl border border-amber-500/30 bg-amber-500/5 text-sm">
            <svg className="w-5 h-5 text-amber-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
            </svg>
            <p className="text-amber-200/80">
              No photos have been indexed yet. Ask your event organizer to process photos first.
            </p>
          </div>
        )}

        {/* Upload area */}
        <Card className="glass border-border/50 overflow-hidden">
          <CardContent className="p-6">
            {!preview ? (
              <div
                role="button"
                tabIndex={0}
                className={`
                  relative flex flex-col items-center justify-center p-12 rounded-xl border-2 border-dashed
                  transition-all duration-300 cursor-pointer
                  ${isDragging
                    ? "border-primary bg-primary/5 scale-[1.02]"
                    : "border-border/60 hover:border-primary/50 hover:bg-primary/5"
                  }
                `}
                onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={handleDrop}
                onClick={() => inputRef.current?.click()}
                onKeyDown={(e) => { if (e.key === "Enter") inputRef.current?.click(); }}
                id="upload-zone"
              >
                <input
                  ref={inputRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  onChange={handleChange}
                  className="hidden"
                  id="selfie-input"
                />

                <div className={`
                  w-20 h-20 rounded-full flex items-center justify-center mb-4 transition-all duration-300
                  ${isDragging ? "bg-primary/20 scale-110" : "bg-primary/10"}
                `}>
                  <svg
                    className={`w-10 h-10 transition-all duration-300 ${isDragging ? "text-primary scale-110" : "text-primary/70"}`}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={1.5}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z"
                    />
                  </svg>
                </div>

                <p className="font-medium text-foreground/80 mb-1">
                  {isDragging ? "Drop your selfie here" : "Drag & drop your selfie"}
                </p>
                <p className="text-sm text-muted-foreground">
                  or click to browse · JPEG, PNG, WebP · Max 10MB
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                {/* Preview */}
                <div className="relative rounded-xl overflow-hidden">
                  <img
                    src={preview}
                    alt="Your selfie preview"
                    className="w-full max-h-80 object-cover rounded-xl"
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-black/40 to-transparent rounded-xl" />

                  {/* Face detection indicator */}
                  <div className="absolute bottom-3 left-3 flex items-center gap-2 px-3 py-1.5 rounded-lg bg-black/50 backdrop-blur-sm">
                    <svg className="w-4 h-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <span className="text-xs text-white font-medium">Photo ready</span>
                  </div>

                  {/* Remove button */}
                  <button
                    onClick={handleRemove}
                    className="absolute top-3 right-3 w-8 h-8 rounded-full bg-black/50 backdrop-blur-sm flex items-center justify-center text-white/80 hover:text-white hover:bg-black/70 transition-all"
                    id="remove-photo-btn"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>

                {/* File info */}
                <div className="flex items-center justify-between text-sm text-muted-foreground">
                  <span className="truncate max-w-[200px]">{file?.name}</span>
                  <span>{file ? (file.size / 1024 / 1024).toFixed(1) : 0} MB</span>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Search button */}
        <Button
          size="lg"
          className="w-full text-lg py-6 glow-amber-hover"
          onClick={handleSearch}
          disabled={!file || isSearching || eventReady === false}
          id="search-btn"
        >
          {isSearching ? (
            <>
              <svg className="w-5 h-5 mr-2 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Searching across all photos...
            </>
          ) : (
            <>
              <svg className="w-5 h-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
              </svg>
              Find My Photos
            </>
          )}
        </Button>

        {/* Tips */}
        <div className="flex items-start gap-3 p-4 rounded-xl glass text-sm">
          <svg className="w-5 h-5 text-primary shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18" />
          </svg>
          <div>
            <p className="font-medium text-foreground/80 mb-1">Tips for best results</p>
            <ul className="text-muted-foreground space-y-0.5">
              <li>• Use a clear, well-lit photo of your face</li>
              <li>• Face the camera directly</li>
              <li>• Avoid sunglasses or heavy filters</li>
            </ul>
          </div>
        </div>
      </div>
    </main>
  );
}
