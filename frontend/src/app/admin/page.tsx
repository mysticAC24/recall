"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import {
  adminLogin,
  createEvent,
  listEvents,
  getEventStatus,
  deleteEvent,
  resetEvent,
  cancelEvent,
  type EventResponse,
  type EventStatusResponse,
} from "@/lib/api";

export default function AdminPage() {
  const [password, setPassword] = useState("");
  const [authenticated, setAuthenticated] = useState(false);
  const [folderUrl, setFolderUrl] = useState("");
  const [eventName, setEventName] = useState("");
  const [events, setEvents] = useState<EventResponse[]>([]);
  const [activeStatus, setActiveStatus] = useState<EventStatusResponse | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isResetting, setIsResetting] = useState<string | null>(null);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);

  const fetchEvents = useCallback(async () => {
    if (!authenticated) return;
    try {
      const data = await listEvents(password);
      setEvents(data);

      // If there's a processing event, poll its status
      const processingEvent = data.find((e) => e.status === "processing");
      if (processingEvent) {
        const status = await getEventStatus(processingEvent.id, password);
        setActiveStatus(status);
      } else {
        setActiveStatus(null);
      }
    } catch {
      // Backend might not be running
    }
  }, [authenticated, password]);

  useEffect(() => {
    fetchEvents();
  }, [fetchEvents]);

  // Poll during processing
  useEffect(() => {
    if (!activeStatus || activeStatus.status !== "processing") return;
    const interval = setInterval(async () => {
      try {
        const status = await getEventStatus(activeStatus.id, password);
        setActiveStatus(status);
        if (status.status !== "processing") {
          fetchEvents();
        }
      } catch {
        // ignore
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [activeStatus, password, fetchEvents]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!password.trim()) return;
    try {
      await adminLogin(password);
      setAuthenticated(true);
      toast.success("Authenticated successfully");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Invalid password");
    }
  };

  const handleProcess = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!folderUrl.trim()) {
      toast.error("Please enter a Google Drive folder URL");
      return;
    }
    if (!eventName.trim()) {
      toast.error("Please enter an event name");
      return;
    }

    setIsProcessing(true);
    try {
      const event = await createEvent(eventName, folderUrl, password);
      toast.success("Photo indexing started!");
      setFolderUrl("");
      setEventName("");
      // Start polling the new event
      const status = await getEventStatus(event.id, password);
      setActiveStatus(status);
      fetchEvents();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to start processing");
    } finally {
      setIsProcessing(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteTargetId) return;
    setIsDeleting(true);
    try {
      await deleteEvent(deleteTargetId, password);
      toast.success("Event deleted");
      setShowDeleteDialog(false);
      setDeleteTargetId(null);
      fetchEvents();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to delete");
    } finally {
      setIsDeleting(false);
    }
  };

  const handleCancel = async (eventId: string) => {
    try {
      await cancelEvent(eventId, password);
      toast.success("Processing stopped");
      setActiveStatus(null);
      fetchEvents();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to cancel");
    }
  };

  const handleReset = async (eventId: string) => {
    setIsResetting(eventId);
    try {
      await resetEvent(eventId, password);
      toast.success("Event reset — indexing restarted");
      fetchEvents();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to reset event");
    } finally {
      setIsResetting(null);
    }
  };

  const statusColor = (s: string) => {
    switch (s) {
      case "completed": return "bg-emerald-500/20 text-emerald-400 border-emerald-500/30";
      case "processing": return "bg-amber-500/20 text-amber-400 border-amber-500/30";
      case "failed": return "bg-red-500/20 text-red-400 border-red-500/30";
      default: return "bg-muted text-muted-foreground border-border";
    }
  };

  // ── Password gate ──────────────────────────────────────────────
  if (!authenticated) {
    return (
      <main className="flex-1 flex items-center justify-center min-h-screen p-4 bokeh-bg">
        <Card className="w-full max-w-md glass border-border/50">
          <CardHeader className="text-center">
            <div className="mx-auto w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center mb-4">
              <svg className="w-7 h-7 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
              </svg>
            </div>
            <CardTitle className="text-2xl" style={{ fontFamily: "var(--font-heading), var(--font-sans), sans-serif" }}>
              Admin Access
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleLogin} className="space-y-4">
              <Input
                type="password"
                placeholder="Enter admin password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="bg-background/50"
                id="admin-password"
              />
              <Button type="submit" className="w-full" size="lg" id="admin-login-btn">
                Access Dashboard
              </Button>
            </form>
            <div className="mt-4 text-center">
              <Link href="/" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                ← Back to home
              </Link>
            </div>
          </CardContent>
        </Card>
      </main>
    );
  }

  // ── Dashboard ──────────────────────────────────────────────────
  return (
    <main className="flex-1 min-h-screen p-4 sm:p-8 bokeh-bg">
      <div className="max-w-3xl mx-auto space-y-8 relative z-10">
        {/* Header */}
        <div>
          <Link href="/" className="text-sm text-muted-foreground hover:text-foreground transition-colors mb-2 inline-block">
            ← Back to home
          </Link>
          <h1
            className="text-3xl font-bold"
            style={{ fontFamily: "var(--font-heading), var(--font-sans), sans-serif" }}
          >
            Admin Dashboard
          </h1>
        </div>

        {/* Active processing status */}
        {activeStatus && activeStatus.status === "processing" && (
          <Card className="glass border-border/50 animate-pulse-glow">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg">Indexing in Progress</CardTitle>
                <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="text-red-400 border-red-500/30 hover:bg-red-500/10 hover:text-red-300"
                  onClick={() => activeStatus && handleCancel(activeStatus.id)}
                >
                  <svg className="w-4 h-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                  Stop
                </Button>
                <Badge className={statusColor("processing")} variant="outline">
                  <svg className="w-3 h-3 mr-1 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  processing
                </Badge>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Progress</span>
                  <span className="font-mono text-primary">
                    {activeStatus.indexed_photos} / {activeStatus.total_photos} photos
                    {activeStatus.failed_photos > 0 && (
                      <span className="text-amber-400 ml-2">({activeStatus.failed_photos} failed)</span>
                    )}
                  </span>
                </div>
                <Progress value={activeStatus.progress_pct} className="h-3" />
                <p className="text-xs text-muted-foreground text-right">
                  {activeStatus.progress_pct.toFixed(1)}% complete
                </p>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Create event form */}
        <Card className="glass border-border/50">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <svg className="w-5 h-5 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 16.5V9.75m0 0l3 3m-3-3l-3 3M6.75 19.5a4.5 4.5 0 01-1.41-8.775 5.25 5.25 0 0110.233-2.33 3 3 0 013.758 3.848A3.752 3.752 0 0118 19.5H6.75z" />
              </svg>
              Index Photos from Google Drive
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleProcess} className="space-y-4">
              <div className="space-y-2">
                <label htmlFor="event-name" className="text-sm font-medium">
                  Event Name
                </label>
                <Input
                  id="event-name"
                  placeholder="e.g., Graduation 2025"
                  value={eventName}
                  onChange={(e) => setEventName(e.target.value)}
                  className="bg-background/50"
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="folder-url" className="text-sm font-medium">
                  Google Drive Folder URL
                </label>
                <Input
                  id="folder-url"
                  placeholder="https://drive.google.com/drive/folders/..."
                  value={folderUrl}
                  onChange={(e) => setFolderUrl(e.target.value)}
                  className="bg-background/50"
                />
                <p className="text-xs text-muted-foreground">
                  Make sure the folder is shared with the service account email.
                </p>
              </div>
              <Button
                type="submit"
                className="w-full"
                size="lg"
                disabled={isProcessing || activeStatus?.status === "processing"}
                id="process-btn"
              >
                {isProcessing ? (
                  <>
                    <svg className="w-4 h-4 mr-2 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Starting...
                  </>
                ) : activeStatus?.status === "processing" ? (
                  "Processing in progress..."
                ) : (
                  <>
                    <svg className="w-4 h-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.347a1.125 1.125 0 010 1.972l-11.54 6.347a1.125 1.125 0 01-1.667-.986V5.653z" />
                    </svg>
                    Process Photos
                  </>
                )}
              </Button>
            </form>
          </CardContent>
        </Card>

        {/* Events list */}
        {events.length > 0 && (
          <Card className="glass border-border/50">
            <CardHeader>
              <CardTitle className="text-lg">Events</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {events.map((event) => (
                <div
                  key={event.id}
                  className="flex items-center justify-between p-4 rounded-lg bg-background/30 border border-border/30"
                >
                  <div className="space-y-1 flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium">{event.name}</span>
                      <Badge className={statusColor(event.status)} variant="outline">
                        {event.status}
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {event.indexed_photos} / {event.total_photos} photos indexed ·{" "}
                      {new Date(event.created_at).toLocaleDateString()}
                    </p>
                    {event.status === "completed" && event.indexed_photos < event.total_photos && (
                      <p className="text-xs text-amber-400">
                        ⚠ {event.total_photos - event.indexed_photos} photo(s) failed — check backend logs
                      </p>
                    )}
                    {event.status === "failed" && (
                      <p className="text-xs text-red-400">
                        ✗ Indexing failed — folder may be inaccessible or no images found
                      </p>
                    )}
                  </div>

                  <div className="flex items-center gap-1 shrink-0">
                    {(event.status === "failed" || event.status === "processing") && (
                      <button
                        onClick={() => handleReset(event.id)}
                        disabled={isResetting === event.id}
                        className="inline-flex items-center justify-center rounded-md px-2 py-1.5 text-xs text-muted-foreground hover:text-primary hover:bg-primary/10 transition-colors cursor-pointer disabled:opacity-50"
                        title="Reset and retry indexing"
                        id={`reset-event-${event.id}`}
                      >
                        {isResetting === event.id ? (
                          <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                          </svg>
                        ) : (
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
                          </svg>
                        )}
                        <span className="ml-1">Retry</span>
                      </button>
                    )}

                  <Dialog
                    open={showDeleteDialog && deleteTargetId === event.id}
                    onOpenChange={(open) => {
                      setShowDeleteDialog(open);
                      if (!open) setDeleteTargetId(null);
                    }}
                  >
                    <DialogTrigger
                      className="inline-flex items-center justify-center rounded-md p-2 text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors cursor-pointer"
                      onClick={() => setDeleteTargetId(event.id)}
                      id={`delete-event-${event.id}`}
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                      </svg>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>Delete Event</DialogTitle>
                        <DialogDescription>
                          Delete &quot;{event.name}&quot; and all its photos and face data? This cannot be undone.
                        </DialogDescription>
                      </DialogHeader>
                      <DialogFooter>
                        <Button variant="outline" onClick={() => setShowDeleteDialog(false)}>
                          Cancel
                        </Button>
                        <Button variant="destructive" onClick={handleDelete} disabled={isDeleting} id="confirm-delete-btn">
                          {isDeleting ? "Deleting..." : "Delete"}
                        </Button>
                      </DialogFooter>
                    </DialogContent>
                  </Dialog>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        )}
      </div>
    </main>
  );
}
