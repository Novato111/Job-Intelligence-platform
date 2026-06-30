-- Run these in your Supabase SQL Editor (Database → SQL Editor)

-- Skill co-occurrence: tracks which skills appear together in job listings
CREATE TABLE IF NOT EXISTS skill_cooccurrence (
  id           UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  skill_a      TEXT NOT NULL,
  skill_b      TEXT NOT NULL,
  count        INTEGER NOT NULL DEFAULT 1,
  last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- Unique constraint so we can safely upsert pairs
CREATE UNIQUE INDEX IF NOT EXISTS idx_cooccurrence_pair ON skill_cooccurrence (skill_a, skill_b);

-- Skill history: one row per skill per day for trend tracking
CREATE TABLE IF NOT EXISTS skill_history (
  id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  skill_name    TEXT NOT NULL,
  demand_score  INTEGER NOT NULL,
  job_count     INTEGER NOT NULL,
  snapshot_date DATE NOT NULL DEFAULT CURRENT_DATE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_history_skill_date ON skill_history (skill_name, snapshot_date);

-- Insights cache: stores Gemini-generated findings to avoid repeated API calls
CREATE TABLE IF NOT EXISTS insights_cache (
  cache_key    TEXT PRIMARY KEY,
  content      JSONB NOT NULL,
  generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
