CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS chunks (
  id        bigserial PRIMARY KEY,
  file      text NOT NULL,
  content   text NOT NULL,
  embedding vector(512)
);
CREATE INDEX IF NOT EXISTS chunks_embedding_idx
  ON chunks USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS sessions (
  session_id   text PRIMARY KEY,
  created_at   timestamptz NOT NULL,
  display_name text,
  nick_name    text NOT NULL,
  nature       text NOT NULL,
  messages     jsonb NOT NULL DEFAULT '[]'::jsonb
);