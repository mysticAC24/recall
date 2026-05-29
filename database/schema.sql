-- Recall: AI-Powered Batch Photo Finder
-- Database Schema for Supabase PostgreSQL with pgvector
-- Run this in the Supabase SQL Editor

-- ============================================
-- 1. Enable Required Extensions
-- ============================================
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- 2. Events Table
-- ============================================
CREATE TABLE IF NOT EXISTS events (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  name VARCHAR(500) NOT NULL,
  drive_folder_id VARCHAR(500) NOT NULL,
  status VARCHAR(50) DEFAULT 'pending'
    CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
  total_photos INTEGER DEFAULT 0,
  indexed_photos INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- 3. Photos Table
-- ============================================
CREATE TABLE IF NOT EXISTS photos (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  drive_file_id VARCHAR(500) NOT NULL UNIQUE,
  filename VARCHAR(1000) NOT NULL,
  thumbnail_url TEXT,
  image_url TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_photos_event_id ON photos(event_id);
CREATE INDEX IF NOT EXISTS idx_photos_drive_file_id ON photos(drive_file_id);

-- ============================================
-- 4. Face Embeddings Table
-- ============================================
CREATE TABLE IF NOT EXISTS face_embeddings (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  photo_id UUID NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
  embedding VECTOR(512) NOT NULL,
  bbox JSONB,  -- {x1, y1, x2, y2} bounding box
  det_score FLOAT,  -- detection confidence
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_face_embeddings_photo_id ON face_embeddings(photo_id);

-- HNSW index for fast cosine similarity search
CREATE INDEX IF NOT EXISTS idx_face_embeddings_hnsw 
  ON face_embeddings USING hnsw (embedding vector_cosine_ops);

-- ============================================
-- 5. RPC Function: Face Similarity Search
-- ============================================
CREATE OR REPLACE FUNCTION match_faces(
  query_embedding VECTOR(512),
  match_threshold FLOAT DEFAULT 0.55,
  match_count INT DEFAULT 50
)
RETURNS TABLE (
  photo_id UUID,
  similarity FLOAT,
  drive_file_id VARCHAR,
  thumbnail_url TEXT,
  image_url TEXT,
  filename VARCHAR
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
  RETURN QUERY
  SELECT
    p.id AS photo_id,
    (1 - (fe.embedding <=> query_embedding))::FLOAT AS similarity,
    p.drive_file_id,
    p.thumbnail_url,
    p.image_url,
    p.filename
  FROM face_embeddings fe
  JOIN photos p ON fe.photo_id = p.id
  WHERE 1 - (fe.embedding <=> query_embedding) > match_threshold
  ORDER BY fe.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;

-- ============================================
-- 6. Helper: Updated_at Trigger
-- ============================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER events_updated_at
  BEFORE UPDATE ON events
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at();
