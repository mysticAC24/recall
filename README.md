# Recall — AI-Powered Batch Photo Finder

> Upload a selfie. Find every photo of you from the event. Powered by AI.

Recall is a production-ready web application that indexes event photos from Google Drive, detects faces using InsightFace AI, and lets students instantly find their photos via selfie-based vector similarity search.

---

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌──────────────────┐
│   Next.js App   │────▶│   FastAPI API    │────▶│ Supabase Postgres│
│   (Vercel)      │     │   (Render)       │     │ + pgvector       │
└─────────────────┘     └────────┬────────┘     └──────────────────┘
                                 │
                        ┌────────▼────────┐
                        │  Google Drive   │
                        │  (Photo Source) │
                        └─────────────────┘
```

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16, TailwindCSS v4, shadcn/ui |
| Backend | FastAPI, InsightFace, ONNX Runtime |
| Database | Supabase PostgreSQL + pgvector |
| Hosting | Vercel (frontend) + Render (backend) |

---

## Quick Start (Local Development)

### Prerequisites

- Node.js 18+
- Python 3.11+
- A [Supabase](https://supabase.com) project (free tier)
- A Google Cloud project with Drive API enabled
- A Google Service Account with a JSON key

### 1. Clone & Setup Database

```bash
# Clone the repository
cd photofinder

# Run the database schema in Supabase SQL Editor
# Copy the contents of database/schema.sql and execute it
```

### 2. Google Cloud Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use existing)
3. Enable the **Google Drive API**
4. Create a **Service Account**:
   - Go to IAM & Admin → Service Accounts
   - Click "Create Service Account"
   - Name it (e.g., `recall-drive-reader`)
   - No roles needed
   - Click "Done"
5. Create a key:
   - Click on the service account
   - Go to "Keys" tab
   - Add Key → Create new key → JSON
   - Download the JSON file
6. **Share your Drive folder** with the service account email (e.g., `recall-drive-reader@project-id.iam.gserviceaccount.com`)

### 3. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your values:
#   DATABASE_URL=postgresql+asyncpg://user:pass@db.xxx.supabase.co:5432/postgres
#   GOOGLE_SERVICE_ACCOUNT_JSON=<base64 encoded JSON key>
#   ADMIN_PASSWORD=your_secure_password
#   FRONTEND_URL=http://localhost:3000

# To base64 encode your service account JSON:
# cat service_account.json | base64 | tr -d '\n'

# Start the backend
uvicorn app.main:app --reload --port 8000
```

> **Note:** On first startup, InsightFace will download the `buffalo_sc` model (~300MB). This may take a few minutes.

### 4. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Configure environment
cp .env.example .env.local
# Edit .env.local:
#   NEXT_PUBLIC_API_URL=http://localhost:8000

# Start the dev server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) — you should see the Recall landing page.

---

## Usage

### Admin Flow

1. Navigate to `/admin`
2. Enter the admin password (from `ADMIN_PASSWORD` env var)
3. Enter an event name and paste a Google Drive folder URL
4. Click **Process Photos** — indexing begins in the background
5. Monitor progress via the real-time progress bar
6. Once complete, students can search for their photos

### Student Flow

1. Navigate to `/search` (or click "Find My Photos" on the landing page)
2. Upload a clear selfie (drag & drop or click to browse)
3. Click **Find My Photos**
4. Browse matching photos in the results grid
5. Download individual photos or click **Download All**

---

## Deployment

### Backend → Render

1. Push the `backend/` directory to a Git repository
2. Create a new **Web Service** on [Render](https://render.com)
3. Connect your repository
4. Set the root directory to `backend`
5. Render will detect the `Dockerfile` automatically
6. Add environment variables:
   - `DATABASE_URL` — Your Supabase connection string
   - `GOOGLE_SERVICE_ACCOUNT_JSON` — Base64-encoded service account JSON
   - `ADMIN_PASSWORD` — Secure admin password
   - `FRONTEND_URL` — Your Vercel deployment URL
   - `SIMILARITY_THRESHOLD` — `0.55` (default)
   - `INSIGHTFACE_MODEL` — `buffalo_sc` (default)

> **Important:** Render free tier has 512MB RAM. The `buffalo_sc` model (~300MB) fits within this limit. For better accuracy, upgrade to a paid plan and use `buffalo_l`.

### Frontend → Vercel

1. Push the `frontend/` directory to a Git repository
2. Import the project on [Vercel](https://vercel.com)
3. Set the root directory to `frontend`
4. Add environment variable:
   - `NEXT_PUBLIC_API_URL` — Your Render backend URL (e.g., `https://recall-api.onrender.com`)
5. Deploy

---

## Project Structure

```
photofinder/
├── frontend/                    # Next.js App Router
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx         # Landing page
│   │   │   ├── admin/page.tsx   # Admin dashboard
│   │   │   ├── search/page.tsx  # Selfie upload
│   │   │   └── results/page.tsx # Results grid
│   │   ├── components/
│   │   │   ├── ui/              # shadcn/ui components
│   │   │   └── landing/         # Landing page components
│   │   └── lib/
│   │       ├── api.ts           # API client
│   │       └── utils.ts         # Utilities
│   └── .env.example
│
├── backend/                     # FastAPI
│   ├── app/
│   │   ├── main.py              # App entry point
│   │   ├── config.py            # Settings
│   │   ├── database.py          # Async SQLAlchemy
│   │   ├── models.py            # ORM models
│   │   ├── schemas.py           # Pydantic schemas
│   │   ├── routers/
│   │   │   ├── admin.py         # Admin endpoints
│   │   │   ├── search.py        # Search endpoint
│   │   │   └── photos.py        # Photo endpoints
│   │   └── services/
│   │       ├── drive.py         # Google Drive integration
│   │       ├── face.py          # InsightFace wrapper
│   │       └── indexer.py       # Background indexing
│   ├── Dockerfile
│   ├── render.yaml
│   ├── requirements.txt
│   └── .env.example
│
├── database/
│   └── schema.sql               # PostgreSQL + pgvector schema
│
└── README.md
```

---

## API Reference

### Public Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/photos/stats` | Landing page stats |
| `POST` | `/search/{event_id}` | Upload selfie, get matches |
| `GET` | `/photos/{photo_id}` | Get photo details |

### Admin Endpoints (requires `X-Admin-Password` header)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/admin/login` | Verify admin password |
| `POST` | `/admin/events` | Create event + start indexing |
| `GET` | `/admin/events` | List all events |
| `GET` | `/admin/events/{id}` | Get event status |
| `DELETE` | `/admin/events/{id}` | Delete event + all data |

---

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | ✅ | — | Supabase PostgreSQL connection string |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | ✅ | — | Base64-encoded service account JSON |
| `ADMIN_PASSWORD` | ✅ | — | Admin dashboard password |
| `FRONTEND_URL` | ✅ | `http://localhost:3000` | Frontend URL for CORS |
| `SIMILARITY_THRESHOLD` | ❌ | `0.55` | Face match threshold (0-1) |
| `INSIGHTFACE_MODEL` | ❌ | `buffalo_sc` | Model: `buffalo_sc` or `buffalo_l` |
| `MAX_PHOTOS` | ❌ | `1500` | Max photos per event |

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "No files found" in Drive | Share the folder with the service account email |
| Model download fails | Check internet connection; InsightFace downloads models on first run |
| Render out of memory | Use `buffalo_sc` model (default) instead of `buffalo_l` |
| CORS errors | Verify `FRONTEND_URL` in backend env matches your Vercel domain |
| No face detected | Ensure the selfie has a clear, well-lit face |
| Low match accuracy | Lower `SIMILARITY_THRESHOLD` (e.g., to `0.45`) |

---

## Tech Stack Details

- **InsightFace** (`buffalo_sc`): Lightweight face detection + 512-d ArcFace embeddings
- **pgvector**: HNSW index for sub-millisecond cosine similarity search
- **Google Drive API v3**: Service account auth, paginated file listing
- **Background processing**: `asyncio.create_task` with semaphore-based concurrency control
- **Image serving**: Direct Google Drive thumbnail/download URLs (no backend proxy needed)

---

Built with ❤️ using Next.js, FastAPI, and InsightFace.
