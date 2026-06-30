import os
import re
import sys
import subprocess
from pathlib import Path
from contextlib import asynccontextmanager
from collections import Counter
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler

from services.ai_insights import generate_market_insights

load_dotenv()
supabase: Client = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))

SCRAPPER_DIR = Path(__file__).parent.parent / "final-job-scrapper"
SCRAPPER_PYTHON = SCRAPPER_DIR / "venv" / "bin" / "python"

# ── Shared helpers ──────────────────────────────────────────────────────────

BASE_THREAT_SCORES: dict[str, float] = {
    "cobol": 10, "fortran": 10, "vba": 9, "selenium": 8, "jquery": 8,
    "wordpress": 7, "php": 7, "excel": 7, "java": 5, "sql": 5,
    "javascript": 4, "typescript": 4, "react": 4, "node.js": 4,
    "css": 4, "html": 5, "angular": 4, "vue": 4, "ruby": 5, "rails": 5,
    "python": 3, "go": 3, "rust": 2, "docker": 3, "kubernetes": 3,
    "aws": 3, "azure": 3, "gcp": 3, "terraform": 3,
    "machine learning": 2, "deep learning": 2, "data science": 2,
    "nlp": 2, "tensorflow": 2, "pytorch": 2, "langchain": 1,
    "llm": 1, "generative ai": 1,
}

AI_SKILLS = {
    "machine learning", "deep learning", "nlp", "tensorflow", "pytorch",
    "langchain", "llm", "generative ai", "hugging face", "bert",
    "computer vision", "reinforcement learning",
}


def _tag_seniority(experience_string: str | None) -> str:
    if not experience_string:
        return "Unknown"
    exp_lower = str(experience_string).lower()
    numbers = [int(n) for n in re.findall(r"\d+", exp_lower)]
    if not numbers:
        return "Senior" if any(w in exp_lower for w in ("senior", "lead")) else "Mid"
    if numbers[0] <= 2:
        return "Junior"
    if numbers[0] <= 5:
        return "Mid"
    return "Senior"


def _compute_disruption(name: str, growth_rate: int, related_names: list[str]) -> float:
    base = BASE_THREAT_SCORES.get(name.lower(), 5.0)
    decline_penalty = max(0, -growth_rate) * 0.1
    ai_protection = sum(1 for r in related_names if r in AI_SKILLS) * 0.5
    score = base * 0.5 + decline_penalty * 0.3 - ai_protection * 0.2
    return round(max(0.0, min(10.0, score)), 1)


def run_pipeline_job():
    """Run processor → scorer. Called by the scheduler and the /pipeline/run endpoint."""
    python = str(SCRAPPER_PYTHON) if SCRAPPER_PYTHON.exists() else sys.executable
    print("Scheduler: starting pipeline run...")
    try:
        subprocess.run([python, str(SCRAPPER_DIR / "processor.py")], check=True, timeout=300)
        subprocess.run([python, str(SCRAPPER_DIR / "scoring.py")], check=True, timeout=120)
        print("Scheduler: pipeline completed.")
    except Exception as e:
        print(f"Scheduler: pipeline failed — {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_pipeline_job, "cron", hour=2, minute=0, id="daily_pipeline")
    scheduler.start()
    print("Scheduler started — pipeline runs daily at 02:00.")
    yield
    scheduler.shutdown()


app = FastAPI(title="SkillMap Intelligence API", version="2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def health_check():
    return {"status": "SkillMap API is running", "version": "2.0"}


@app.get("/stats")
def get_platform_stats():
    try:
        response = supabase.table("raw_jobs").select("id", count="exact").eq("is_processed", True).execute()
        return {"total_jobs_analyzed": response.count or 0}
    except Exception:
        return {"total_jobs_analyzed": 0}


@app.get("/stats/disruption")
def get_disruption_stats():
    """Average AI disruption index across all tracked skills."""
    try:
        res = supabase.table("skills").select("name, growth_rate").execute()
        if not res.data:
            return {"avg_disruption": 5.0, "most_threatened": None, "most_protected": None}
        scores = [(row["name"], _compute_disruption(row["name"], row.get("growth_rate") or 0, [])) for row in res.data]
        avg = round(sum(s for _, s in scores) / len(scores), 1)
        most_threatened = max(scores, key=lambda x: x[1])
        most_protected = min(scores, key=lambda x: x[1])
        return {
            "avg_disruption": avg,
            "most_threatened": {"name": most_threatened[0], "score": most_threatened[1]},
            "most_protected": {"name": most_protected[0], "score": most_protected[1]},
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/skills/top")
def get_top_skills(limit: int = 10):
    try:
        response = supabase.table("skills") \
            .select("*") \
            .order("demand_score", desc=True) \
            .limit(limit) \
            .execute()
        return {"count": len(response.data), "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/skills/trending")
def get_trending_skills(limit: int = 10):
    """Skills with the highest positive growth rate since last scoring run."""
    try:
        response = supabase.table("skills") \
            .select("name, demand_score, growth_rate, job_count") \
            .gt("growth_rate", 0) \
            .order("growth_rate", desc=True) \
            .limit(limit) \
            .execute()
        return {"count": len(response.data), "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/search")
def search_skills(q: str = Query(..., min_length=1)):
    try:
        response = supabase.table("skills") \
            .select("name, demand_score") \
            .ilike("name", f"%{q}%") \
            .limit(5) \
            .execute()
        suggestions = [item["name"] for item in response.data]
        return {"suggestions": suggestions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats/location")
def get_location_stats():
    return [
        {"city": "Bangalore", "lng": 77.5946, "lat": 12.9716, "count": 1240, "intensity": 98},
        {"city": "Hyderabad", "lng": 78.4867, "lat": 17.3850, "count": 890,  "intensity": 92},
        {"city": "Pune",      "lng": 73.8567, "lat": 18.5204, "count": 760,  "intensity": 88},
        {"city": "Gurgaon",   "lng": 77.0266, "lat": 28.4595, "count": 650,  "intensity": 85},
        {"city": "Mumbai",    "lng": 72.8777, "lat": 19.0760, "count": 520,  "intensity": 82},
        {"city": "Chennai",   "lng": 80.2707, "lat": 13.0827, "count": 480,  "intensity": 80},
        {"city": "Noida",     "lng": 77.3260, "lat": 28.5355, "count": 310,  "intensity": 75},
        {"city": "Kolkata",   "lng": 88.3639, "lat": 22.5726, "count": 180,  "intensity": 65},
    ]


@app.get("/roles")
def get_roles(limit: int = 12):
    """
    Returns top job roles from the database with:
    - Real job count (how many listings we have)
    - Top required skills (from skill_job_map for that role's jobs)
    - Average salary (from Salary_LPA field)
    """
    try:
        from collections import Counter

        # 1. Fetch all processed jobs with title and salary
        jobs_res = supabase.table("raw_jobs") \
            .select("id, title, salary") \
            .eq("is_processed", True) \
            .execute()
        jobs = jobs_res.data or []

        # 2. Count jobs per title, collect job IDs and salaries
        role_data: dict = {}
        for job in jobs:
            title = (job.get("title") or "").strip()
            if not title or title == "Unknown Role":
                continue
            if title not in role_data:
                role_data[title] = {"ids": [], "salaries": []}
            role_data[title]["ids"].append(job["id"])
            salary_str = job.get("salary") or ""
            try:
                lpa = float(salary_str.replace(" LPA", "").strip())
                role_data[title]["salaries"].append(lpa)
            except ValueError:
                pass

        # 3. Sort by job count, take top N
        sorted_roles = sorted(role_data.items(), key=lambda x: len(x[1]["ids"]), reverse=True)[:limit]

        result = []
        for title, data in sorted_roles:
            job_ids = data["ids"]
            salaries = data["salaries"]

            # 4. Fetch top skills for this role's jobs (sample up to 30 jobs to stay fast)
            sample_ids = job_ids[:30]
            skills_res = supabase.table("skill_job_map") \
                .select("skill_name") \
                .in_("job_id", sample_ids) \
                .execute()

            skill_counts = Counter(s["skill_name"] for s in (skills_res.data or []))
            top_skills = [s for s, _ in skill_counts.most_common(8)]

            # 5. Salary stats
            avg_salary = round(sum(salaries) / len(salaries), 1) if salaries else None
            min_salary = round(min(salaries), 1) if salaries else None
            max_salary = round(max(salaries), 1) if salaries else None

            result.append({
                "title":      title,
                "job_count":  len(job_ids),
                "top_skills": top_skills,
                "avg_salary": avg_salary,
                "min_salary": min_salary,
                "max_salary": max_salary,
            })

        return {"count": len(result), "data": result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/skill/{name}/history")
def get_skill_history(name: str):
    """Daily demand-score snapshots from skill_history, used for trend charts."""
    try:
        res = supabase.table("skill_history") \
            .select("demand_score, snapshot_date") \
            .eq("skill_name", name.lower()) \
            .order("snapshot_date") \
            .execute()
        return {"skill": name, "history": res.data or []}
    except Exception:
        return {"skill": name, "history": []}


@app.get("/skill/{name}/companies")
def get_skill_companies(name: str, limit: int = 5):
    """Top companies hiring for a given skill, ranked by listing count."""
    try:
        map_res = supabase.table("skill_job_map") \
            .select("job_id") \
            .eq("skill_name", name.lower()) \
            .execute()
        job_ids = [r["job_id"] for r in (map_res.data or [])][:500]
        if not job_ids:
            return {"companies": []}
        jobs_res = supabase.table("raw_jobs") \
            .select("company") \
            .in_("id", job_ids) \
            .execute()
        counts = Counter(j["company"] for j in (jobs_res.data or []) if j.get("company"))
        return {"companies": [{"name": n, "job_count": c} for n, c in counts.most_common(limit)]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/skill/{name}/salary")
def get_skill_salary(name: str):
    """Real salary stats by seniority for jobs requiring this skill."""
    try:
        map_res = supabase.table("skill_job_map") \
            .select("job_id") \
            .eq("skill_name", name.lower()) \
            .execute()
        job_ids = [r["job_id"] for r in (map_res.data or [])][:500]
        if not job_ids:
            return {}
        jobs_res = supabase.table("raw_jobs") \
            .select("salary, experience") \
            .in_("id", job_ids) \
            .execute()
        bands: dict[str, list[float]] = {"Junior": [], "Mid": [], "Senior": []}
        for job in (jobs_res.data or []):
            salary_str = (job.get("salary") or "").replace(" LPA", "").strip()
            try:
                lpa = float(salary_str)
            except ValueError:
                continue
            level = _tag_seniority(job.get("experience"))
            if level in bands:
                bands[level].append(lpa)
        result = {}
        for level, vals in bands.items():
            if vals:
                result[level] = {
                    "min": round(min(vals), 1),
                    "max": round(max(vals), 1),
                    "avg": round(sum(vals) / len(vals), 1),
                    "count": len(vals),
                }
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/skill/{name}")
def get_skill_intelligence(name: str):
    try:
        response = supabase.table("skills").select("*").ilike("name", name).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Skill not found")
        skill = response.data[0]

        # Compute and attach disruption score on the fly
        try:
            related_res = supabase.table("skill_cooccurrence") \
                .select("skill_b") \
                .eq("skill_a", skill["name"].lower()) \
                .order("count", desc=True) \
                .limit(8) \
                .execute()
            related_names = [r["skill_b"] for r in (related_res.data or [])]
        except Exception:
            related_names = []
        skill["ai_threat_level"] = _compute_disruption(
            skill["name"], skill.get("growth_rate", 0), related_names
        )
        return skill
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/skill/{name}/related")
def get_related_skills(name: str, limit: int = 8):
    """Skills that most frequently co-occur with the given skill in job listings."""
    try:
        name_lower = name.lower()
        res_a = supabase.table("skill_cooccurrence") \
            .select("skill_b, count") \
            .eq("skill_a", name_lower) \
            .order("count", desc=True) \
            .limit(limit) \
            .execute()

        res_b = supabase.table("skill_cooccurrence") \
            .select("skill_a, count") \
            .eq("skill_b", name_lower) \
            .order("count", desc=True) \
            .limit(limit) \
            .execute()

        tally: dict[str, int] = {}
        for row in (res_a.data or []):
            tally[row["skill_b"]] = tally.get(row["skill_b"], 0) + row["count"]
        for row in (res_b.data or []):
            tally[row["skill_a"]] = tally.get(row["skill_a"], 0) + row["count"]

        sorted_related = sorted(tally.items(), key=lambda x: x[1], reverse=True)[:limit]
        return {"skill": name, "related": [{"name": s, "count": c} for s, c in sorted_related]}
    except Exception:
        # Table may not exist yet — return empty until migrations are run
        return {"skill": name, "related": []}


@app.post("/pipeline/run")
def trigger_pipeline():
    """Manually trigger the full processor → scorer pipeline."""
    try:
        run_pipeline_job()
        return {"status": "Pipeline completed successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/insights/market")
def get_market_insights():
    try:
        response = supabase.table("skills") \
            .select("name, demand_score") \
            .order("demand_score", desc=True) \
            .limit(10) \
            .execute()
        return generate_market_insights(response.data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats/analysis")
def get_statistical_analysis():
    """
    Pearson correlation between demand_score and avg salary across all skills.
    Provides the statistical validation layer for academic reporting.
    """
    try:
        skills_res = supabase.table("skills").select("name, demand_score, job_count, growth_rate").execute()
        skills = skills_res.data or []
        if len(skills) < 3:
            return {"error": "Not enough data for analysis"}

        # For each skill, fetch avg salary from raw_jobs via skill_job_map
        skill_salaries: dict[str, float] = {}
        for skill in skills:
            try:
                map_res = supabase.table("skill_job_map").select("job_id") \
                    .eq("skill_name", skill["name"]).execute()
                job_ids = [r["job_id"] for r in (map_res.data or [])][:200]
                if not job_ids:
                    continue
                jobs_res = supabase.table("raw_jobs").select("salary").in_("id", job_ids).execute()
                salaries = []
                for j in (jobs_res.data or []):
                    try:
                        salaries.append(float((j.get("salary") or "").replace(" LPA", "").strip()))
                    except ValueError:
                        pass
                if salaries:
                    skill_salaries[skill["name"]] = round(sum(salaries) / len(salaries), 2)
            except Exception:
                pass

        # Build paired vectors only for skills that have salary data
        paired = [(s["demand_score"], skill_salaries[s["name"]], s["name"])
                  for s in skills if s["name"] in skill_salaries]

        if len(paired) < 3:
            return {"error": "Insufficient salary data for correlation"}

        demand_vals = [p[0] for p in paired]
        salary_vals = [p[1] for p in paired]
        n = len(paired)

        # Pearson r
        mean_d = sum(demand_vals) / n
        mean_s = sum(salary_vals) / n
        num = sum((d - mean_d) * (s - mean_s) for d, s, _ in paired)
        den_d = (sum((d - mean_d) ** 2 for d in demand_vals)) ** 0.5
        den_s = (sum((s - mean_s) ** 2 for s in salary_vals)) ** 0.5
        pearson_r = round(num / (den_d * den_s), 4) if den_d * den_s > 0 else 0

        # Descriptive stats
        demand_sorted = sorted(demand_vals)
        salary_sorted = sorted(salary_vals)

        def median(lst):
            m = len(lst) // 2
            return lst[m] if len(lst) % 2 else (lst[m - 1] + lst[m]) / 2

        # Top and bottom correlators for the report narrative
        top_demand = sorted(paired, key=lambda x: x[0], reverse=True)[:5]
        top_salary = sorted(paired, key=lambda x: x[1], reverse=True)[:5]

        return {
            "n_skills": n,
            "pearson_r": pearson_r,
            "interpretation": (
                "strong positive" if pearson_r >= 0.6 else
                "moderate positive" if pearson_r >= 0.3 else
                "weak positive" if pearson_r >= 0 else
                "negative"
            ),
            "demand_stats": {
                "mean": round(mean_d, 1),
                "median": median(demand_sorted),
                "min": min(demand_vals),
                "max": max(demand_vals),
            },
            "salary_stats": {
                "mean_lpa": round(mean_s, 1),
                "median_lpa": median(salary_sorted),
                "min_lpa": min(salary_vals),
                "max_lpa": max(salary_vals),
            },
            "top_demand_skills": [{"name": n, "demand": d, "avg_salary": s} for d, s, n in top_demand],
            "top_salary_skills": [{"name": n, "demand": d, "avg_salary": s} for d, s, n in top_salary],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/insights/findings")
def get_findings(force_refresh: bool = False):
    """
    RAG-based findings summary generated by Gemini from live DB metrics.
    Cached in DB for 7 days to conserve API credits. Pass ?force_refresh=true to regenerate.
    """
    import json
    from datetime import datetime, timezone, timedelta

    CACHE_KEY = "findings_summary"
    CACHE_TTL_DAYS = 7

    # Check cache first
    if not force_refresh:
        try:
            cached = supabase.table("insights_cache") \
                .select("content, generated_at") \
                .eq("cache_key", CACHE_KEY) \
                .execute()
            if cached.data:
                entry = cached.data[0]
                generated_at = datetime.fromisoformat(entry["generated_at"].replace("Z", "+00:00"))
                age_days = (datetime.now(timezone.utc) - generated_at).days
                if age_days < CACHE_TTL_DAYS:
                    return {**entry["content"], "cached": True, "cache_age_days": age_days}
        except Exception:
            pass  # Table may not exist yet, fall through to generate

    # Build rich context from live DB data
    try:
        skills_res = supabase.table("skills") \
            .select("name, demand_score, job_count, growth_rate") \
            .order("demand_score", desc=True).limit(15).execute()
        trending_res = supabase.table("skills") \
            .select("name, demand_score, growth_rate") \
            .gt("growth_rate", 0).order("growth_rate", desc=True).limit(5).execute()
        stats_res = supabase.table("raw_jobs") \
            .select("id", count="exact").eq("is_processed", True).execute()
        roles_res = supabase.table("raw_jobs") \
            .select("title").eq("is_processed", True).execute()

        top_skills = skills_res.data or []
        trending = trending_res.data or []
        total_jobs = stats_res.count or 0

        # Count roles
        from collections import Counter
        role_counts = Counter(j["title"] for j in (roles_res.data or []) if j.get("title"))
        top_roles = role_counts.most_common(5)

        # Salary overview from raw_jobs
        salary_res = supabase.table("raw_jobs").select("salary, experience") \
            .eq("is_processed", True).execute()
        all_salaries = []
        for j in (salary_res.data or []):
            try:
                all_salaries.append(float((j.get("salary") or "").replace(" LPA", "").strip()))
            except ValueError:
                pass
        salary_context = (
            f"Salary range: ₹{min(all_salaries):.1f}L – ₹{max(all_salaries):.1f}L, "
            f"mean ₹{sum(all_salaries)/len(all_salaries):.1f}L across {len(all_salaries)} listings"
            if all_salaries else "Salary data unavailable"
        )

        context = {
            "total_jobs_analyzed": total_jobs,
            "top_skills_by_demand": [
                {"skill": s["name"], "demand_index": s["demand_score"], "job_count": s["job_count"]}
                for s in top_skills
            ],
            "trending_skills": [{"skill": s["name"], "growth_pts": s["growth_rate"]} for s in trending],
            "top_job_roles": [{"role": r, "count": c} for r, c in top_roles],
            "salary_overview": salary_context,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to build context: {e}")

    # Call Gemini
    try:
        from google import genai
        from google.genai import types

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise HTTPException(status_code=503, detail="GEMINI_API_KEY not configured")

        client = genai.Client(api_key=api_key)
        prompt = f"""
You are an expert researcher writing the Findings & Conclusions chapter of an MCA academic project report
titled "SkillMap: A Real-Time Career Intelligence Platform for the Indian Tech Job Market."

Here is the live data collected and analyzed:
{json.dumps(context, indent=2)}

Write a structured academic findings summary with these exact sections:

1. EXECUTIVE_SUMMARY (3-4 sentences: what the study found overall)
2. KEY_FINDINGS (exactly 5 bullet points, each a specific quantitative insight from the data)
3. SKILL_DEMAND_ANALYSIS (2-3 sentences interpreting the demand index distribution)
4. SALARY_INSIGHTS (2 sentences on salary trends observed)
5. MANAGERIAL_IMPLICATIONS (3 bullet points for HR managers, recruiters, and job seekers)
6. LIMITATIONS (2 bullet points: honest limitations of the dataset/approach)
7. FUTURE_SCOPE (2 bullet points: what can be extended)

Return ONLY valid JSON with these exact keys (string values, use \\n for line breaks within strings):
{{
  "executive_summary": "...",
  "key_findings": ["...", "...", "...", "...", "..."],
  "skill_demand_analysis": "...",
  "salary_insights": "...",
  "managerial_implications": ["...", "...", "..."],
  "limitations": ["...", "..."],
  "future_scope": ["...", "..."],
  "generated_at_context": "Based on {total_jobs} jobs analyzed"
}}
"""
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        findings = json.loads(response.text)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini generation failed: {e}")

    # Cache the result in DB (create table if needed via upsert)
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        supabase.table("insights_cache").upsert(
            {"cache_key": CACHE_KEY, "content": findings, "generated_at": now_iso},
            on_conflict="cache_key"
        ).execute()
    except Exception:
        pass  # insights_cache table may not exist — findings still returned

    return {**findings, "cached": False, "cache_age_days": 0}
