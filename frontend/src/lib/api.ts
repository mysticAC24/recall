const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ─────────────────────────────────────────────────────────
// Types — aligned with backend Pydantic schemas
// ─────────────────────────────────────────────────────────

export interface EventResponse {
  id: string;
  name: string;
  drive_folder_id: string;
  status: string;
  total_photos: number;
  indexed_photos: number;
  created_at: string;
  updated_at: string;
}

export interface EventStatusResponse {
  id: string;
  status: string;
  total_photos: number;
  indexed_photos: number;
  failed_photos: number;
  progress_pct: number;
}

export interface MatchedPhoto {
  photo_id: string;
  similarity: number;
  drive_file_id: string;
  thumbnail_url: string | null;
  image_url: string | null;
  filename: string;
}

export interface SearchResponse {
  matches: MatchedPhoto[];
  total: number;
  event_id: string;
  threshold: number;
}

export interface PhotoStats {
  total_photos: number;
  total_faces: number;
  event_name: string | null;
  event_id: string | null;
  status: string | null;
}

// ─────────────────────────────────────────────────────────
// Error handling
// ─────────────────────────────────────────────────────────

class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.text();
    let message = `Request failed with status ${response.status}`;
    try {
      const json = JSON.parse(body);
      message = json.detail || json.message || message;
    } catch {
      // body wasn't JSON
    }
    throw new ApiError(message, response.status);
  }
  return response.json();
}

// ─────────────────────────────────────────────────────────
// Admin endpoints
// ─────────────────────────────────────────────────────────

/** Verify the admin password */
export async function adminLogin(password: string): Promise<{ authenticated: boolean }> {
  const response = await fetch(`${API_BASE}/admin/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });
  return handleResponse(response);
}

/** Create a new event and start background indexing */
export async function createEvent(
  name: string,
  driveFolderUrl: string,
  password: string,
): Promise<EventResponse> {
  const response = await fetch(`${API_BASE}/admin/events`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Admin-Password": password,
    },
    body: JSON.stringify({ name, drive_folder_url: driveFolderUrl }),
  });
  return handleResponse<EventResponse>(response);
}

/** List all events */
export async function listEvents(password: string): Promise<EventResponse[]> {
  const response = await fetch(`${API_BASE}/admin/events`, {
    headers: { "X-Admin-Password": password },
  });
  return handleResponse<EventResponse[]>(response);
}

/** Get indexing status for a specific event */
export async function getEventStatus(
  eventId: string,
  password: string,
): Promise<EventStatusResponse> {
  const response = await fetch(`${API_BASE}/admin/events/${eventId}`, {
    headers: { "X-Admin-Password": password },
  });
  return handleResponse<EventStatusResponse>(response);
}

/** Cancel a processing event */
export async function cancelEvent(
  eventId: string,
  password: string,
): Promise<{ message: string }> {
  const response = await fetch(`${API_BASE}/admin/events/${eventId}/cancel`, {
    method: "POST",
    headers: { "X-Admin-Password": password },
  });
  return handleResponse(response);
}

/** Reset a stuck/failed event and restart indexing */
export async function resetEvent(
  eventId: string,
  password: string,
): Promise<{ message: string }> {
  const response = await fetch(`${API_BASE}/admin/events/${eventId}/reset`, {
    method: "POST",
    headers: { "X-Admin-Password": password },
  });
  return handleResponse(response);
}

/** Delete an event and all associated data */
export async function deleteEvent(
  eventId: string,
  password: string,
): Promise<{ message: string }> {
  const response = await fetch(`${API_BASE}/admin/events/${eventId}`, {
    method: "DELETE",
    headers: { "X-Admin-Password": password },
  });
  return handleResponse(response);
}

// ─────────────────────────────────────────────────────────
// Search endpoints
// ─────────────────────────────────────────────────────────

/** Upload a selfie and search for matching photos in an event */
export async function searchFaces(
  eventId: string,
  file: File,
): Promise<SearchResponse> {
  const formData = new FormData();
  formData.append("selfie", file);

  const response = await fetch(`${API_BASE}/search/${eventId}`, {
    method: "POST",
    body: formData,
  });
  return handleResponse<SearchResponse>(response);
}

// ─────────────────────────────────────────────────────────
// Public endpoints
// ─────────────────────────────────────────────────────────

/** Get public stats for the landing page */
export async function getPhotoStats(): Promise<PhotoStats> {
  const response = await fetch(`${API_BASE}/photos/stats`);
  return handleResponse<PhotoStats>(response);
}
