# SkillMap — Complete Project Understanding
### Everything you need to know, top to bottom

---

## What Is This Project?

SkillMap is a **real-time career intelligence platform** for the Indian tech job market. It answers one question:

> *"Which skills are actually in demand right now, which are rising, and which are becoming obsolete?"*

You scrape job listings → extract skills from job descriptions using NLP → calculate how demanded each skill is → display everything on a live dashboard with charts, maps, and AI-generated insights.

It is an **end-to-end data engineering + ML + full-stack web** project.

---

## Folder Structure

```
skillmap/
├── final-job-scrapper/       ← Data ingestion (scraping + importing datasets)
│   ├── scraper.py            ← Playwright live scraper (Naukri.com)
│   ├── processor.py          ← NLP skill extraction pipeline
│   ├── scoring.py            ← Demand score calculator
│   ├── import_kaggle_dataset.py  ← Import Kaggle CSV (500 jobs)
│   ├── import_hf_dataset.py  ← Import HuggingFace dataset (82 jobs)
│   ├── requirements.txt
│   └── .env                  ← SUPABASE_URL, SUPABASE_KEY
│
├── backend/                  ← FastAPI REST API
│   ├── main.py               ← All API endpoints (10+ routes)
│   ├── migrations.sql        ← SQL to create tables in Supabase
│   ├── services/
│   │   └── ai_insights.py    ← Gemini API integration
│   ├── requirements.txt
│   └── .env                  ← SUPABASE_URL, SUPABASE_KEY, GEMINI_API_KEY
│
└── frontend/                 ← Next.js 16 dashboard
    ├── app/
    │   ├── page.tsx           ← Market Pulse dashboard (home)
    │   ├── skills/page.tsx    ← Skills database grid
    │   ├── roles/page.tsx     ← Job roles breakdown
    │   ├── compare/page.tsx   ← Skill vs skill comparison
    │   ├── skill/[name]/page.tsx  ← Individual skill profile
    │   └── findings/page.tsx  ← AI-generated research findings
    ├── components/
    │   ├── Navbar.tsx
    │   ├── SearchBar.tsx
    │   ├── LocationHeatmap.tsx
    │   ├── MapWrapper.tsx
    │   ├── TopSkillsChart.tsx
    │   ├── TrendingPanel.tsx
    │   ├── SkillsGrid.tsx
    │   └── LiveClock.tsx
    ├── lib/
    │   └── api.ts             ← All fetch functions for the API
    └── .env.local             ← NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## How to Run (Mac + VS Code)

### Prerequisites
- Python 3.12+ (check: `python3 --version`)
- Node.js 18+ (check: `node --version`)
- Supabase account (free tier works)
- Google Gemini API key (free at aistudio.google.com)

### Step 1 — Database setup (one time only)

1. Go to your Supabase project → SQL Editor
2. Paste and run the contents of `backend/migrations.sql`
3. This creates: `skill_cooccurrence`, `skill_history`, `insights_cache` tables
   (The main tables `raw_jobs`, `skills`, `skill_job_map` already exist)

### Step 2 — Backend

Open a terminal in VS Code (`Ctrl + `` ` ``):

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Edit .env with your keys
uvicorn main:app --port 8000 --reload
```

Backend is now live at **http://localhost:8000**
You can see all routes at **http://localhost:8000/docs** (auto-generated Swagger UI)

### Step 3 — Import data (one time)

Open a second terminal:

```bash
cd final-job-scrapper
source venv/bin/activate        # uses its own venv
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# Import jobs into raw_jobs table
python import_kaggle_dataset.py   # 500 jobs from Kaggle
python import_hf_dataset.py       # 82 jobs from HuggingFace

# (Optional) Live scrape from Naukri.com
python scraper.py
```

### Step 4 — Run the pipeline

```bash
python processor.py    # extracts skills from all unprocessed jobs
python scoring.py      # calculates demand scores for all skills
```

### Step 5 — Frontend

Open a third terminal:

```bash
cd frontend
npm install
# .env.local already has: NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

Frontend is live at **http://localhost:3000**

### Step 6 — Enable Gemini AI (optional)

In `backend/.env`:
```
USE_MOCK_AI=False
GEMINI_API_KEY=your_key_here
```
Restart the backend. Gemini is now active for market signals and findings generation.

---

## The 4-Stage Pipeline

This is the core of the project. Data flows through 4 stages:

```
Stage 1          Stage 2            Stage 3          Stage 4
scraper.py   →  processor.py   →  scoring.py   →  main.py (API)
    ↓                ↓                 ↓                ↓
Crawls          NLP extracts      Calculates       Serves to
Naukri.com      200+ skills       demand scores    frontend
or imports      + seniority       + growth rate
CSV datasets    + co-occurrence   + history snap
```

---

## Stage 1 — Scraper (`scraper.py`)

**What it does:** Uses Playwright (headless Chromium browser) to open Naukri.com, search for tech jobs, and scrape listing data.

**What it captures per listing:**
- Job title, company name, location
- Job description (full text)
- Skills tags (the chips shown on Naukri listings)
- Salary string, experience string

**Deduplication:** Before inserting, it computes `MD5(title + company + location)` and checks if that hash already exists in `raw_jobs`. If yes, skip. This prevents counting the same job twice across multiple scrape runs.

**Where data goes:** `raw_jobs` table in Supabase with `is_processed = False`

**Reality check:** The live scraper got ~20 jobs before Naukri's bot detection kicked in. The bulk of the 1,622 jobs came from the CSV imports below.

---

## Stage 1b — Dataset Importers

### `import_kaggle_dataset.py`
- Source: `sridipbasu/india-tech-jobs-2024-2026-salary-and-skills` on Kaggle
- Imports first 500 rows from a CSV
- Key columns: `Job_Title`, `Company`, `City`, `Skills_Required`, `Salary_LPA`, `Experience_Level`
- Salary is stored as `"8.5 LPA"` string format
- Skills are stored as a JSON array in `skills_raw` column

### `import_hf_dataset.py`
- Source: `muhammetakkurt/naukri-jobs-dataset` on HuggingFace
- 82 real Naukri listings (Data Science focused)
- Fetched via HuggingFace Datasets Server API (no download needed)

---

## Stage 2 — Processor (`processor.py`)

This is the NLP engine. It processes every job where `is_processed = False`.

### Skill Extraction — Two signals

**Signal 1: Explicit (from skill tag chips)**
```python
for tag in skills_raw_array:
    canonical = NORMALIZATION.get(tag.lower(), tag.lower())
    if canonical in FLAT_SKILLS_SET:
        found[canonical] = is_explicit: True
```
These are the tags Naukri shows on listings. High confidence.

**Signal 2: Implicit (NLP from description text)**
```python
doc = nlp(description_text[:50000])   # cap at 50k chars
matches = phrase_matcher(doc)          # spaCy PhraseMatcher
for match_id, start, end in matches:
    skill_name = nlp.vocab.strings[match_id]
    found[skill_name] = is_explicit: False
```
spaCy's PhraseMatcher scans the full job description for 200+ known skill names. It's word-boundary aware — "go" won't match inside "good".

### Why spaCy over regex?
- Handles multi-word phrases: "machine learning", "spring boot", "rest api"
- 10–20x faster than regex for large vocabularies
- Language-model backed tokenisation

### Alias Normalization
Before matching, aliases are converted to canonical names:
| Raw input | Canonical |
|---|---|
| reactjs, react.js | react |
| nodejs, node | node.js |
| postgres, pg | postgresql |
| k8s | kubernetes |
| golang | go |
| sklearn, sk-learn | scikit-learn |
| gen ai | generative ai |

### Skill Dictionary (200+ skills across 11 categories)
Languages, Frontend, Backend, Database, Cloud/DevOps, AI/ML, Data, Practices, Testing, Security, Mobile

### Co-occurrence Recording
After extracting skills from a job, every **pair** of skills is recorded:
```python
from itertools import combinations
for skill_a, skill_b in combinations(sorted(skill_names), 2):
    # increment count in skill_cooccurrence table
```
If Python and Machine Learning both appear in a job → their pair count goes up by 1.
This builds a weighted graph: "Python co-occurs with ML in 54 jobs."

### Seniority Tagging
```
"0-2 Yrs"  → Junior
"3-5 Yrs"  → Mid
"6+ Yrs"   → Senior
"Senior/Lead" in text → Senior
```

### Output
- Rows inserted into `skill_job_map` (job_id ↔ skill_name bridge table)
- Rows inserted/updated in `skill_cooccurrence`
- Job marked `is_processed = True` in `raw_jobs`

---

## Stage 3 — Scoring (`scoring.py`)

Calculates how demanded each skill is across all processed jobs.

### Demand Score Formula (NORMALIZED INDEX)
```
demand_score = round( (skill_job_count / max_skill_job_count) × 100 )
```

- `skill_job_count` = number of distinct jobs that contain this skill
- `max_skill_job_count` = the highest count among ALL skills (Python = 56 jobs)
- Python: 56/56 × 100 = **100/100**
- SQL: 28/56 × 100 = **50/100**
- Machine Learning: 27/56 × 100 = **48/100**

**Why normalized instead of raw penetration?**
Raw formula was `(count / total_jobs) × 100` which gave Python 5/100 (56 out of 1,622 jobs = 3.5%). That looked wrong because we only track ~85 skills out of every possible skill. Normalized index makes the top skill = 100 and everything scales proportionally. This is academically defensible as a "demand index."

The raw penetration rate is still printed in logs: `(3.5% penetration)`.

### Growth Rate
```
growth_rate = new_demand_score − previous_demand_score
```
Pulled from the `skills` table before the run. On the very first run, previous score defaults to 0 so every skill shows positive growth.

### Daily History Snapshot
One row per skill per day is inserted into `skill_history`:
```sql
(skill_name, demand_score, job_count, snapshot_date)
```
Used for the trend chart on skill profile pages. Builds up over time as you run scoring daily.

---

## Stage 4 — API (`backend/main.py`)

FastAPI application with 14 endpoints. Auto-restarts daily pipeline via APScheduler at 02:00 AM.

### All Endpoints

| Method | Endpoint | What it returns |
|---|---|---|
| GET | `/` | Health check, version |
| GET | `/stats` | Total processed job count from raw_jobs |
| GET | `/stats/disruption` | Avg AI disruption index across all skills |
| GET | `/stats/analysis` | Pearson r correlation + descriptive stats |
| GET | `/stats/location` | City-wise job density (⚠️ HARDCODED) |
| GET | `/skills/top?limit=N` | Top N skills by demand_score |
| GET | `/skills/trending?limit=N` | Skills with growth_rate > 0 |
| GET | `/search?q=X` | Autocomplete suggestions (ilike match) |
| GET | `/roles?limit=N` | Top job roles with real salary + skills from DB |
| GET | `/skill/{name}` | Full skill profile + ai_threat_level computed live |
| GET | `/skill/{name}/related` | Co-occurring skills from skill_cooccurrence table |
| GET | `/skill/{name}/history` | Daily snapshots from skill_history table |
| GET | `/skill/{name}/companies` | Top companies hiring for this skill (from raw_jobs) |
| GET | `/skill/{name}/salary` | Salary min/max/avg by seniority level |
| GET | `/insights/market` | Gemini-generated market signals (3 cards) |
| GET | `/insights/findings` | Full RAG findings report (cached 7 days) |
| POST | `/pipeline/run` | Manually trigger processor.py → scoring.py |

### How `/roles` works
1. Fetch all processed jobs with title + salary from `raw_jobs`
2. Group by job title, count listings per title
3. Sort by count, take top N
4. For each role: fetch top skills from `skill_job_map` → count most common → take top 8
5. Calculate avg/min/max salary from the salary strings

### How `/skill/{name}/companies` works
1. Query `skill_job_map` for all job_ids where skill_name matches
2. Query `raw_jobs` for company names of those job_ids (capped at 500)
3. Count occurrences per company → return top 5

### How `/skill/{name}/salary` works
1. Get job_ids for this skill from `skill_job_map`
2. Get salary + experience strings from `raw_jobs`
3. Parse salary float from "8.5 LPA" format
4. Tag each job as Junior/Mid/Senior using `_tag_seniority()`
5. Return min/max/avg per seniority band

### APScheduler
The server starts a background scheduler on startup:
```python
scheduler.add_job(run_pipeline_job, "cron", hour=2, minute=0)
```
Every day at 02:00 AM it runs `processor.py` then `scoring.py` automatically.

---

## AI Disruption Index — How It's Calculated

Computed on-the-fly inside `GET /skill/{name}`. Not stored in DB.

```python
score = (base_threat × 0.5) + (demand_decline × 0.3) − (ai_protection × 0.2)
score = clamp(score, 0, 10)
```

**Base threat** — curated lookup table per skill:
```
cobol, fortran → 10    (certain automation)
vba, selenium  → 8-9   (high risk)
php, java, sql → 5-7   (moderate risk)
python, react  → 3-4   (lower risk)
pytorch, llm   → 1-2   (AI-augmented, protected)
langchain      → 1     (actively part of AI ecosystem)
default        → 5
```

**Demand decline penalty:**
```
demand_decline = max(0, -growth_rate) × 0.1
```
If a skill is losing demand (negative growth_rate), its threat score increases.

**AI co-occurrence protection:**
```
ai_protection = count(related skills in AI_SKILLS set) × 0.5
```
If a skill frequently co-occurs with ML/AI skills (from skill_cooccurrence), it gets protection — the skill is being augmented by AI, not replaced.

---

## Statistical Analysis — Pearson Correlation

`GET /stats/analysis` computes:

```
Pearson r = Σ((demand_i - mean_demand) × (salary_i - mean_salary))
            ─────────────────────────────────────────────────────────
            √Σ(demand_i - mean_demand)² × √Σ(salary_i - mean_salary)²
```

Computed across all skills that have both a demand_score and salary data in the DB.

**Result: r = 0.08 (weak positive correlation)**

Academic interpretation: "High skill demand does not directly translate to proportionally higher salary in the Indian market. Niche skills like LangChain and Kubernetes command salary premiums disproportionate to their listing frequency."

---

## Gemini AI Features

### Market Signals (`GET /insights/market`)
- Sends top 10 skills by demand score to Gemini
- Gets back 3 structured signals: Rising, Risk, Emerging
- If Gemini fails or is mocked → falls back to data-driven signals computed from real DB data
- No caching — called fresh each time

### Findings Report (`GET /insights/findings`)
- Pulls full context from DB: top 15 skills, trending, salary overview, top roles
- Sends structured JSON context to Gemini with detailed academic prompt
- Gemini writes: executive summary, 5 key findings, skill analysis, salary insights, managerial implications, limitations, future scope
- **Cached for 7 days** in `insights_cache` Supabase table — only 1 Gemini call per week
- Pass `?force_refresh=true` to regenerate manually

### Skill Intelligence Analyst (frontend only)
- **Not Gemini.** A template function in `skill/[name]/page.tsx`
- Reads real data (demand_score, growth_rate, job_count, related skills) and builds a contextual paragraph
- Fast, free, no API calls

---

## What Is Hardcoded (Be Honest in Viva)

| Feature | Where | Status | Fix |
|---|---|---|---|
| Location/city stats (India map) | `main.py /stats/location` | ❌ Hardcoded 8 cities with fake counts | Query `raw_jobs.location` and group by city |
| Salary Pulse on dashboard | `app/page.tsx salaryBands` | ❌ Static estimate ranges | Connect to `/skill/{name}/salary` or aggregate |
| Role Distribution % on skill pages | `skill/[name]/page.tsx` | ❌ Calculated from demand_score thresholds only | Real data would need role-skill join query |
| Dashboard company table (fixed) | Was hardcoded, now fixed | ✅ Now uses `/roles` endpoint | Done |
| AI Disruption Index | `main.py _compute_disruption()` | ⚠️ Base threat scores are manually curated | Based on automation research literature |
| Skill analyst text | `skill/[name]/page.tsx aiInsightText()` | ⚠️ Template-based | Intentional — zero API cost |

---

## Frontend Pages

### `/` — Market Pulse Dashboard
- 5 stat cards: total jobs, hottest skill, fastest rising, peak demand score, AI disruption index
- Fastest Growing Skills — scrollable ranked list with demand bars (real data)
- Skill Demand Heatmap — colour-coded grid by demand_score (real data)
- Market Shifts — Gemini AI signals (real or data-driven fallback)
- India Demand Density — react-simple-maps choropleth (⚠️ hardcoded city data)
- Salary Pulse — seniority-based salary bands (⚠️ hardcoded estimates)
- Top Job Roles table — real data from `/roles` (real data)

### `/skills` — Skills Database
- Filterable grid of all 85 tracked skills
- Filter by category (Languages, Frontend, Backend, etc.)
- Sort by demand score, job count, growth rate, A-Z
- Inline search

### `/roles` — Job Roles
- Lists top job titles from processed jobs
- Real job count, top required skills, avg/min/max salary
- All from live DB queries

### `/compare` — Skill Comparison
- Two search boxes, fetch each skill's full profile
- Side-by-side: demand score, job count, growth rate
- Winner highlighted with ▲
- Auto-generated verdict paragraph

### `/skill/[name]` — Skill Intelligence Profile
- Demand score, job count, growth rate (real)
- AI Threat Meter 0-10 (computed live)
- Demand Trend chart — real data from `skill_history` (builds over time)
- Connected Ecosystem — co-occurrence bubbles (real)
- AI Intelligence Analyst — template paragraph (real data, no API)
- Salary by Seniority — real min/max/avg from raw_jobs (real)
- Top Hiring Entities — real companies from DB (real)
- Seniority Split donut — computed from salary data counts (real)
- Role Distribution % — ⚠️ threshold-based estimate

### `/findings` — Research Findings
- Gemini RAG-generated academic summary
- Pearson correlation stats table
- Top demand vs top salary skill tables
- 7-day cache

---

## Database Tables

### `raw_jobs` — Staging table
All scraped/imported jobs land here first.
```
id, title, company, location, description, skills_raw (JSONB array),
salary (text like "8.5 LPA"), experience, job_hash (MD5 dedup), 
is_processed (boolean), created_at
```

### `skill_job_map` — Bridge table
One row per skill per job. Created by processor.py.
```
id, job_id → raw_jobs, skill_name, is_explicit (true = from tags, false = NLP extracted)
```

### `skills` — Aggregated intelligence
One row per unique skill. Updated by scoring.py.
```
id, name, demand_score (0-100 normalized), job_count, growth_rate,
salary_index, ai_threat_level (stored as 0, computed live), 
top_roles (JSONB), connected_skills (JSONB), last_updated
```

### `skill_cooccurrence` — Co-occurrence graph edges
```
id, skill_a, skill_b, count (jobs containing both), last_updated
UNIQUE(skill_a, skill_b)
```

### `skill_history` — Daily trend snapshots
```
id, skill_name, demand_score, job_count, snapshot_date (DATE), created_at
UNIQUE(skill_name, snapshot_date)
```

### `insights_cache` — Gemini output cache
```
cache_key (TEXT PRIMARY KEY), content (JSONB), generated_at (TIMESTAMPTZ)
```

---

## Tech Stack Summary

| Layer | Tech | Why |
|---|---|---|
| Scraper | Python + Playwright | Handles JavaScript-rendered pages, bypasses basic bot detection |
| NLP | spaCy en_core_web_sm | PhraseMatcher is fast and handles multi-word skills |
| API | FastAPI | Auto OpenAPI docs, async support, Pydantic validation |
| Scheduler | APScheduler | Simple cron-style scheduling inside the FastAPI process |
| Database | Supabase (PostgreSQL) | Free tier, REST + Realtime, Python SDK |
| AI | Google Gemini 2.0 Flash | Free tier, JSON mode, fast for structured output |
| Frontend | Next.js 16 App Router | Server components = data fetched at build/request time |
| Styling | Tailwind CSS v4 | Utility classes, no CSS files needed |
| Charts | Recharts | React-native charting |
| Maps | react-simple-maps | Lightweight SVG map of India |

---

## Key Numbers to Know for Viva

| Metric | Value |
|---|---|
| Total jobs in DB | ~1,622 |
| Skills tracked | 85 unique |
| Top skill | Python — 100/100 |
| #2 skill | SQL — 50/100 |
| #3 skill | Machine Learning — 48/100 |
| Pearson r (demand vs salary) | 0.08 (weak positive) |
| Top role by listings | Data Scientist — 86 jobs |
| Top role avg salary | ₹27.8 LPA (Data Scientist) |
| Senior avg salary | ₹41.8 LPA |
| Junior avg salary | ₹8.3 LPA |
| API endpoints | 17 |
| Frontend routes | 6 |
| Gemini cache TTL | 7 days |
| Pipeline auto-runs | 02:00 AM daily |

---

## Common Viva Questions + Answers

**Q: Why is Python 100/100 — is that realistic?**
A: It's a normalized demand index, not an absolute percentage. Python is the most-demanded skill in our dataset (56 jobs), so it becomes the benchmark at 100. SQL is 50/100 meaning it appears in half as many jobs as Python. The raw penetration rate is 3.5% (56/1622 jobs).

**Q: How do you know your NLP extraction is accurate?**
A: We use two signals — explicit skill tags from the job listing (high confidence) and PhraseMatcher extraction from description text. The `is_explicit` flag in `skill_job_map` distinguishes them. PhraseMatcher uses word boundaries so partial matches are avoided.

**Q: What does growth_rate mean?**
A: `growth_rate = current_demand_score − previous_demand_score`. A positive value means the skill appeared in more jobs since the last pipeline run. On first run, previous score defaults to 0 so all skills show positive growth.

**Q: What is the AI Disruption Index based on?**
A: A three-factor formula: base automation threat (curated from automation research literature) + demand decline factor − AI co-occurrence protection. Skills that frequently appear alongside AI/ML technologies get a lower disruption score because they are being augmented, not replaced.

**Q: What is Pearson correlation telling you?**
A: r = 0.08 means there is a weak positive relationship between a skill's demand index and average salary. In practice this means high demand doesn't guarantee high pay — niche skills like Kubernetes command salary premiums disproportionate to their listing count.

**Q: How do you prevent duplicate jobs?**
A: Before every insert, we compute MD5(job_title + company + location) and check if that hash already exists in raw_jobs. If yes, the insert is skipped.

---

*SkillMap · MCA Project 2025–2026 · FastAPI + Next.js + spaCy + Supabase + Gemini*
