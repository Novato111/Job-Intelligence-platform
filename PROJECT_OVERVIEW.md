# SkillMap — Career Intelligence Platform
### MCA Project Documentation · 2025–2026

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Problem Statement](#2-problem-statement)
3. [Objectives](#3-objectives)
4. [System Architecture](#4-system-architecture)
5. [Tech Stack](#5-tech-stack)
6. [Data Sources](#6-data-sources)
7. [Database Schema](#7-database-schema)
8. [Backend Pipeline — Detailed](#8-backend-pipeline--detailed)
9. [NLP Processing](#9-nlp-processing)
10. [REST API Endpoints](#10-rest-api-endpoints)
11. [Frontend Dashboard](#11-frontend-dashboard)
12. [Key Features](#12-key-features)
13. [Live Statistics](#13-live-statistics)
14. [Project Structure](#14-project-structure)
15. [How to Run](#15-how-to-run)
16. [Pending Features](#16-pending-features)

---

## 1. Project Overview

**SkillMap** is a real-time career intelligence platform that scrapes, processes, and visualises tech job market data for the Indian job market. It answers a fundamental question every tech professional and student faces:

> *"Which skills are actually in demand right now, which are rising, and which are becoming obsolete?"*

The platform combines **web scraping**, **NLP-based text mining**, **statistical demand scoring**, **skill co-occurrence graph analysis**, and **AI-generated market insights** — all surfaced through a live, interactive dashboard.

---

## 2. Problem Statement

The Indian tech job market is dynamic and opaque. Students graduating from programs like MCA often lack visibility into:

- Which skills recruiters actually demand (vs. which skills colleges teach)
- How demand for a skill has changed over the past months
- Which skills co-occur in the same job (i.e., what to learn alongside Python)
- Where in India a particular skill is most valued
- What salary to expect for a given skill set

Existing platforms like LinkedIn or Naukri show individual job listings but do **no aggregate intelligence** — SkillMap fills that gap.

---

## 3. Objectives

| # | Objective | Status |
|---|---|---|
| O1 | Build an automated job scraper targeting Naukri.com | ✅ Done |
| O2 | Implement NLP pipeline to extract skills from raw job descriptions | ✅ Done |
| O3 | Calculate a quantitative demand score per skill from live data | ✅ Done |
| O4 | Track skill demand trends over time (growth rate) | ✅ Done |
| O5 | Build a skill co-occurrence graph (which skills appear together) | ✅ Done |
| O6 | Visualise findings on a real-time interactive dashboard | ✅ Done |
| O7 | Integrate AI-generated market insights (Gemini LLM) | ✅ Done |
| O8 | Build a geographic demand density map for India | ✅ Done |
| O9 | Enable skill-vs-skill comparison tool | ✅ Done |
| O10 | AI Disruption Index per skill | 🔄 Pending |
| O11 | Salary prediction via regression model | 🔄 Pending |

---

## 4. System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DATA INGESTION LAYER                         │
│                                                                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │  Playwright      │  │  HuggingFace     │  │  Kaggle Dataset  │  │
│  │  Web Scraper     │  │  Naukri Dataset  │  │  India Jobs      │  │
│  │  (Naukri.com)    │  │  (82 jobs)       │  │  2024–2026       │  │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘  │
│           └──────────────────────┼──────────────────────┘           │
│                                  ▼                                   │
│                    ┌─────────────────────────┐                      │
│                    │   raw_jobs (Supabase)   │                      │
│                    │   is_processed = False  │                      │
│                    └────────────┬────────────┘                      │
└─────────────────────────────────┼───────────────────────────────────┘
                                  │
┌─────────────────────────────────▼───────────────────────────────────┐
│                       PROCESSING LAYER                              │
│                                                                     │
│   processor.py                                                      │
│   ┌──────────────────────────────────────────────────────────────┐  │
│   │  1. Fetch unprocessed jobs (is_processed = False)            │  │
│   │  2. spaCy PhraseMatcher → extract 200+ skills from JD text  │  │
│   │  3. Tag matching on skills_raw array (explicit skills)       │  │
│   │  4. Alias normalization (reactjs→react, golang→go)          │  │
│   │  5. Salary normalization → LPA                               │  │
│   │  6. Seniority tagging (Junior/Mid/Senior)                    │  │
│   │  7. Co-occurrence pairs → skill_cooccurrence table           │  │
│   │  8. Mark job as is_processed = True                          │  │
│   └──────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│   scoring.py                 ▼                                      │
│   ┌──────────────────────────────────────────────────────────────┐  │
│   │  1. Count skill occurrences across all processed jobs        │  │
│   │  2. demand_score = (count / total_jobs) × 100               │  │
│   │  3. growth_rate = new_score − previous_score (delta)        │  │
│   │  4. Upsert into skills table                                 │  │
│   │  5. Snapshot into skill_history (one row/skill/day)          │  │
│   └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────┼───────────────────────────────────┘
                                  │
┌─────────────────────────────────▼───────────────────────────────────┐
│                          DATABASE LAYER                             │
│                         Supabase (PostgreSQL)                       │
│                                                                     │
│   raw_jobs          skill_job_map      skills                       │
│   skill_cooccurrence    skill_history                               │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
┌─────────────────────────────────▼───────────────────────────────────┐
│                           API LAYER                                 │
│                    FastAPI (Python) — port 8000                     │
│                                                                     │
│  GET /skills/top       GET /skills/trending   GET /skill/{name}     │
│  GET /skill/{name}/related  GET /stats        GET /stats/location   │
│  GET /insights/market  POST /pipeline/run                           │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
┌─────────────────────────────────▼───────────────────────────────────┐
│                        PRESENTATION LAYER                           │
│                   Next.js 16 (React) — port 3000                    │
│                                                                     │
│  / (Market Pulse)   /skills   /roles   /compare   /skill/[name]    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 5. Tech Stack

### Backend
| Component | Technology | Purpose |
|---|---|---|
| Web Scraper | Python + Playwright | Headless browser scraping of Naukri.com |
| NLP Engine | spaCy (`en_core_web_sm`) | Skill extraction from job descriptions |
| API Framework | FastAPI | RESTful API with automatic OpenAPI docs |
| Task Scheduler | APScheduler | Automated daily pipeline execution |
| AI/LLM | Google Gemini 2.0 Flash | Market insight generation |

### Database
| Component | Technology | Purpose |
|---|---|---|
| Primary DB | Supabase (PostgreSQL) | All persistent storage |
| ORM | supabase-py | Python client for DB operations |

### Frontend
| Component | Technology | Purpose |
|---|---|---|
| Framework | Next.js 16 (App Router) | SSR + client rendering |
| Styling | Tailwind CSS v4 | Utility-first styling |
| Charts | Recharts | Skill demand bar charts |
| Maps | react-simple-maps | India demand heatmap |
| Fonts | Manrope + Inter | Typography |
| Icons | Material Symbols | UI icons |

### Data Sources
| Source | Type | Records |
|---|---|---|
| Naukri.com (Playwright) | Live scraping | ~20 |
| HuggingFace Naukri Dataset | CSV via API | 82 |
| Kaggle India Tech Jobs 2024–2026 | CSV import | 500 (5000 available) |
| **Total processed** | | **~600** |

---

## 6. Data Sources

### 6.1 Naukri.com Web Scraper
**File:** `final-job-scrapper/scraper.py`

Uses Playwright (Chromium, non-headless) to navigate Naukri.com, bypass bot detection via realistic user-agent and viewport settings, and extract job cards. Each listing captures: title, company, location, salary, experience, skills tags, and job description. An MD5 hash of `(title + company + location)` prevents duplicate imports.

### 6.2 HuggingFace Dataset
**File:** `final-job-scrapper/import_hf_dataset.py`
**Source:** `muhammetakkurt/naukri-jobs-dataset`

Fetched via HuggingFace Datasets Server API. Contains 88 real Naukri listings (Data Science focused). Maps: `tagsAndSkills` → `skills_raw`, `jobDescription` → `description`, `companyName` → `company`.

### 6.3 Kaggle India Tech Jobs 2024–2026
**File:** `final-job-scrapper/import_kaggle_dataset.py`
**Source:** `sridipbasu/india-tech-jobs-2024-2026-salary-and-skills`

5,000 rows covering 20+ job titles (Software Engineer, Data Scientist, ML Engineer, Backend Developer, React Developer, etc.) across all major Indian cities. Clean salary as float (LPA). Currently importing first 500 rows.

**Key columns:**

| Kaggle Column | raw_jobs Column | Notes |
|---|---|---|
| `Job_Title` | `title` | Direct map |
| `Company` | `company` | Direct map |
| `City` | `location` | Direct map |
| `Skills_Required` | `skills_raw` | Comma-split → list |
| `Salary_LPA` | `salary` | Float → "X.X LPA" string |
| `Experience_Level` | `experience` | e.g. "Junior (1-3 yrs)" |
| `Job_Title + Skills` | `description` | Synthesised (no raw JD) |

---

## 7. Database Schema

### `raw_jobs` — Raw job listings (staging table)
```sql
id           UUID PRIMARY KEY DEFAULT gen_random_uuid()
title        TEXT NOT NULL
company      TEXT
location     TEXT
description  TEXT
skills_raw   JSONB          -- array of skill tag strings
salary       TEXT
experience   TEXT
job_hash     TEXT UNIQUE    -- MD5(title+company+location) for dedup
is_processed BOOLEAN DEFAULT FALSE
created_at   TIMESTAMPTZ DEFAULT NOW()
```

### `skill_job_map` — Bridge table (skill ↔ job)
```sql
id          UUID PRIMARY KEY
job_id      UUID REFERENCES raw_jobs(id)
skill_name  TEXT
is_explicit BOOLEAN   -- TRUE = from tags, FALSE = extracted from description
```

### `skills` — Aggregated skill intelligence
```sql
id              UUID PRIMARY KEY
name            TEXT UNIQUE
demand_score    INTEGER     -- (skill_count / total_jobs) × 100
job_count       INTEGER     -- raw listing count
growth_rate     INTEGER     -- delta from previous scoring run
growth_rate     INTEGER
salary_index    FLOAT       -- pending
ai_threat_level FLOAT       -- pending
top_roles       JSONB
connected_skills JSONB
last_updated    TIMESTAMPTZ
```

### `skill_cooccurrence` — Co-occurrence graph edges
```sql
id           UUID PRIMARY KEY
skill_a      TEXT
skill_b      TEXT
count        INTEGER        -- how many jobs contain both skills
last_updated TIMESTAMPTZ
UNIQUE(skill_a, skill_b)
```

### `skill_history` — Daily trend snapshots
```sql
id            UUID PRIMARY KEY
skill_name    TEXT
demand_score  INTEGER
job_count     INTEGER
snapshot_date DATE
created_at    TIMESTAMPTZ
UNIQUE(skill_name, snapshot_date)
```

---

## 8. Backend Pipeline — Detailed

The pipeline has **4 sequential stages**, each a standalone Python script. They can be triggered manually or automatically via the APScheduler (runs daily at 02:00 AM).

```
Stage 1         Stage 2           Stage 3         Stage 4
scraper.py  →  processor.py  →  scoring.py  →  main.py (API)
   │               │                │               │
Crawls         NLP Extract       Calculates      Serves results
Naukri.com     200+ skills       demand scores   to frontend
               + Co-occur        + growth rate
               + Seniority       + history
```

### Stage 1 — Scrape (`scraper.py`)
1. Launches Playwright Chromium with realistic browser fingerprint
2. Navigates to `naukri.com/{query}-jobs` for multiple search queries
3. Waits for `.srp-jobtuple-wrapper` elements to load (15s timeout)
4. Extracts per listing: title, company, location, description, skills, salary, experience
5. Generates MD5 dedup hash
6. Inserts into `raw_jobs` with `is_processed = False`

### Stage 2 — Process (`processor.py`)

**Skill Extraction — Two signals:**

```python
# Signal 1: Explicit (from skill tag chips on the listing)
for tag in skills_raw_array:
    canonical = NORMALIZATION.get(tag.lower(), tag.lower())
    if canonical in FLAT_SKILLS_SET:
        found[canonical] = {"is_explicit": True}

# Signal 2: Implicit (NLP extraction from description body)
doc = nlp(description_text[:50000])
matches = phrase_matcher(doc)          # spaCy PhraseMatcher
for match_id, start, end in matches:
    skill_name = nlp.vocab.strings[match_id]
    if skill_name not in found:
        found[skill_name] = {"is_explicit": False}
```

**Alias Normalization table (sample):**

| Raw input | Canonical skill |
|---|---|
| reactjs, react.js | react |
| nodejs, node | node.js |
| golang | go |
| postgres, pg | postgresql |
| k8s | kubernetes |
| sklearn, sk-learn | scikit-learn |
| ml | machine learning |

**Co-occurrence recording:**
```python
from itertools import combinations
pairs = combinations(sorted(extracted_skill_names), 2)
# Insert/increment count in skill_cooccurrence table
```

**Seniority tagging:**
```
"0-2 Yrs"  → Junior
"3-5 Yrs"  → Mid
"6+ Yrs"   → Senior
"Senior/Lead" in text → Senior
```

### Stage 3 — Score (`scoring.py`)

**Demand Score formula:**
```
demand_score = ⌊ (occurrences_of_skill / total_processed_jobs) × 100 ⌋
```

Example: Python appears in 83 of 102 jobs → `demand_score = ⌊(83/102)×100⌋ = 81`

**Growth Rate (trend tracking):**
```
growth_rate = new_demand_score − previous_demand_score
```
Stored as signed integer. `+5` = rose 5 points. `−3` = declined 3 points.

**Daily snapshot:**
One row inserted per skill per day into `skill_history`. Used for time-series trend charts.

### Stage 4 — Serve (`main.py` / FastAPI)

FastAPI application with:
- CORS configured for Next.js frontend
- APScheduler background job (02:00 AM daily pipeline trigger)
- Supabase client for all DB queries
- Gemini AI client for market insights

---

## 9. NLP Processing

### Skill Dictionary
**200+ skills** across 11 categories defined in `processor.py`:

| Category | Example Skills |
|---|---|
| Languages | python, javascript, typescript, java, c++, go, rust, kotlin |
| Frontend | react, next.js, vue, angular, svelte, tailwind css |
| Backend | node.js, django, fastapi, spring boot, flask, rails |
| Database | sql, postgresql, mongodb, redis, elasticsearch |
| Cloud/DevOps | aws, azure, docker, kubernetes, terraform, github actions |
| AI/ML | machine learning, deep learning, tensorflow, pytorch, nlp, bert, langchain |
| Data | data science, pandas, apache spark, kafka, airflow, dbt |
| Practices | agile, microservices, rest api, system design, ci/cd |
| Testing | pytest, jest, selenium, cypress, postman |
| Security | cybersecurity, oauth, jwt |
| Mobile | android, ios, react native, flutter |

### spaCy PhraseMatcher

```python
import spacy
from spacy.matcher import PhraseMatcher

nlp = spacy.load("en_core_web_sm")
phrase_matcher = PhraseMatcher(nlp.vocab, attr="LOWER")

for skill in FLAT_SKILLS:
    phrase_matcher.add(skill, [nlp.make_doc(skill)])
```

**Why PhraseMatcher over regex:**
- Handles multi-word phrases: `"machine learning"`, `"spring boot"`, `"rest api"`
- Word boundary aware — `"go"` won't match inside `"good"` or `"agile"`
- 10–20× faster than regex for large vocabularies
- Language-model backed tokenisation

---

## 10. REST API Endpoints

Base URL: `http://localhost:8000`

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Health check — API version |
| GET | `/stats` | Total processed job count |
| GET | `/skills/top?limit=N` | Top N skills by demand score |
| GET | `/skills/trending` | Skills with positive growth rate |
| GET | `/skill/{name}` | Full intelligence profile for a skill |
| GET | `/skill/{name}/related` | Co-occurring skills (co-occurrence graph) |
| GET | `/search?q={query}` | Autocomplete — skill name suggestions |
| GET | `/stats/location` | City-wise demand density data |
| GET | `/insights/market` | Gemini AI-generated market signals |
| POST | `/pipeline/run` | Manually trigger processor + scorer |

### Sample Responses

**`GET /skill/python`**
```json
{
  "name": "python",
  "demand_score": 81,
  "job_count": 83,
  "growth_rate": 66,
  "last_updated": "2026-06-05T10:32:00Z"
}
```

**`GET /skill/python/related`**
```json
{
  "skill": "python",
  "related": [
    { "name": "machine learning", "count": 54 },
    { "name": "sql",              "count": 41 },
    { "name": "docker",           "count": 28 }
  ]
}
```

**`GET /insights/market`** *(Gemini-powered)*
```json
{
  "rising":   { "title": "Vector Databases",  "description": "High demand for Pinecone and Weaviate across FinTech." },
  "emerging": { "title": "Agentic Workflows", "description": "AutoGPT and CrewAI becoming critical for internal ops." },
  "risk":     { "title": "Legacy PHP",        "description": "Maintenance roles declining; migration skills are key." }
}
```

---

## 11. Frontend Dashboard

**URL:** `http://localhost:3000`

### Pages

| Route | Page | Data Source |
|---|---|---|
| `/` | Market Pulse Dashboard | All API endpoints |
| `/skills` | Skills Database (filterable grid) | `/skills/top?limit=60` |
| `/roles` | Tech Role Profiles | Static + skill links |
| `/compare` | Skill Comparison Tool | `/skill/{name}` × 2 |
| `/skill/[name]` | Skill Intelligence Profile | `/skill/{name}` + `/skill/{name}/related` |

### Dashboard Sections

**Stats Strip (5 cards)**
- Total Jobs Analyzed (live from DB)
- Hottest Skill (top by demand score)
- Fastest Rising Skill (top trending)
- Peak Demand Score (with progress bar)
- AI Disruption Index *(pending)*

**Bento Grid**
1. **Fastest Growing Skills** — scrollable ranked list (up to 20 skills) with demand bars, all clickable
2. **Skill Demand Heatmap** — colour-coded grid (green = peak demand, cyan = high, dark = emerging), all clickable
3. **AI Market Signals** — Gemini-generated Rising / Emerging / Risk signals
4. **India Demand Density** — react-simple-maps choropleth with hover tooltips (city name, job count, intensity tier)
5. **Salary Pulse** — salary band visualization by seniority
6. **Top Hiring Entities** — company table

### Skill Intelligence Page (`/skill/[name]`)

Each skill page shows:
- Demand score with visual bar
- Job count and growth rate
- AI threat level *(pending)*
- 6-month demand trend chart
- Connected ecosystem — clickable bubble clusters from co-occurrence data
- AI Intelligence Analyst — contextual paragraph generated from data
- Salary by seniority
- Seniority split donut chart
- Top hiring companies
- Role distribution percentages

### Skills Database Page (`/skills`)

- **Category filter tabs**: All, Languages, Frontend, Backend, Database, Cloud/DevOps, AI/ML, Data, Testing, Security
- **Sort options**: Demand Score, Job Count, Growth Rate, A–Z
- **Inline search filter**
- Grid of skill cards — each shows demand bar, job count, growth delta, category, and links to skill profile

### Compare Page (`/compare`)

- Two real-time skill search boxes
- Side-by-side stat comparison (demand score, job count, growth)
- Winner highlighted with ▲ indicator
- Auto-generated verdict paragraph
- Links to both full skill profiles

---

## 12. Key Features

### Automated Pipeline
The FastAPI server runs APScheduler in the background. Every day at 02:00 AM it automatically executes `processor.py → scoring.py` on any newly scraped/imported jobs. No manual intervention required after setup.

### Deduplication
Every job insertion computes `MD5(title + company + location)`. Before insert, the hash is checked against existing rows — prevents counting the same job twice even across multiple scrape runs or dataset imports.

### Graceful Degradation
All API fetch functions on the frontend are wrapped in try/catch with safe fallback returns (`{ data: [] }`, `null`). If the backend is down, the frontend renders with empty states rather than crashing.

### Co-occurrence Graph
After skill extraction, every pair of skills found in the same job listing is recorded in `skill_cooccurrence`. This builds a weighted undirected graph where edge weight = number of jobs containing both skills. Powers the "Often Paired With" section on skill pages.

### Trend Tracking
Before each scoring run, the current demand scores are fetched. After recalculation, `growth_rate = new − old` is stored. A daily snapshot is written to `skill_history` enabling time-series analysis.

---

## 13. Live Statistics

*As of project build date (June 2026):*

| Metric | Value |
|---|---|
| Total jobs in database | ~600 |
| Total processed | ~390 |
| Unique skills tracked | 25+ |
| Top skill | Machine Learning (82/100) |
| #2 skill | Python (81/100) |
| #3 skill | Data Science (76/100) |
| Cities mapped | 8 major Indian tech hubs |
| API endpoints | 10 |
| Frontend routes | 5 |

---

## 14. Project Structure

```
skillmap/
│
├── final-job-scrapper/          # Data ingestion layer
│   ├── scraper.py               # Playwright Naukri scraper
│   ├── processor.py             # spaCy NLP + co-occurrence
│   ├── scoring.py               # Demand score + trend calculation
│   ├── import_hf_dataset.py     # HuggingFace dataset importer
│   ├── import_kaggle_dataset.py # Kaggle dataset importer
│   └── requirements.txt
│
├── backend/                     # API layer
│   ├── main.py                  # FastAPI app + APScheduler
│   ├── migrations.sql           # Supabase table creation SQL
│   ├── services/
│   │   └── ai_insights.py       # Gemini LLM integration
│   └── requirements.txt
│
└── frontend/                    # Presentation layer
    ├── app/
    │   ├── page.tsx             # Market Pulse dashboard
    │   ├── skills/page.tsx      # Skills database
    │   ├── roles/page.tsx       # Role profiles
    │   ├── compare/page.tsx     # Skill comparison
    │   └── skill/[name]/page.tsx # Skill intelligence profile
    ├── components/
    │   ├── LocationHeatmap.tsx  # react-simple-maps heatmap
    │   ├── MapWrapper.tsx       # SSR-safe map wrapper
    │   ├── TopSkillsChart.tsx   # Recharts horizontal bar chart
    │   ├── TrendingPanel.tsx    # Trending skills table
    │   ├── SkillsGrid.tsx       # Filterable skills grid
    │   ├── SearchBar.tsx        # Debounced skill search
    │   └── LiveClock.tsx        # Real-time clock
    ├── lib/
    │   └── api.ts               # All API fetch functions
    └── package.json
```

---

## 15. How to Run

### Prerequisites
- Python 3.12+
- Node.js 18+
- Supabase account (free tier works)
- Google Gemini API key (free tier)

### Step 1 — Database setup
Run `backend/migrations.sql` in your Supabase SQL Editor to create the two additional tables (`skill_cooccurrence`, `skill_history`).

### Step 2 — Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# Copy .env and fill in SUPABASE_URL, SUPABASE_KEY, GEMINI_API_KEY
uvicorn main:app --port 8000 --reload
```

### Step 3 — Data ingestion

```bash
cd final-job-scrapper
source venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# Option A: Import from Kaggle CSV (recommended)
python import_kaggle_dataset.py   # imports 500 jobs

# Option B: Import from HuggingFace API
python import_hf_dataset.py

# Option C: Live scrape Naukri.com
python scraper.py
```

### Step 4 — Run the pipeline

```bash
python processor.py    # NLP extraction + co-occurrence
python scoring.py      # Demand scoring + trend tracking
# OR trigger via API:
curl -X POST http://localhost:8000/pipeline/run
```

### Step 5 — Frontend

```bash
cd frontend
npm install
# .env.local: NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
# Open http://localhost:3000
```

---

## 16. Pending Features

### AI Disruption Index
**Planned formula:**
```
AI_Disruption_Score (0–10) =
  (Base_Threat_Score × 0.5)
  + (Demand_Decline_Factor × 0.3)
  − (AI_CoOccurrence_Protection × 0.2)
```

- **Base Threat**: Curated scores per skill (e.g. manual testing = 8/10, ML engineering = 1/10) based on automation research
- **Demand Decline**: Negative growth_rate → higher disruption risk
- **AI Co-occurrence Protection**: High co-occurrence with AI/ML skills = skill is augmented by AI, not replaced

Will populate the `ai_threat_level` column already present in the `skills` table and display on the dashboard's "AI Disruption Index" stat card and each skill's profile page.

### Salary Prediction Model
**Planned approach:** Multi-label Linear Regression using scikit-learn

```
Features : Binary skill vector (skill_a=1, skill_b=0, ...)
Target   : Salary_LPA (from Kaggle dataset — clean float)
Output   : Predicted salary + skill salary coefficients
```

Skill salary coefficients show *how much each skill contributes to salary* (e.g. Kubernetes → +₹8L premium). Will power a "Salary Predictor" tool on the dashboard and show "Avg salary with this skill" on each skill profile page.

---

*Built with FastAPI · Next.js · spaCy · Supabase · Google Gemini · Playwright*
*MCA Project — Career Intelligence Platform · 2025–2026*
