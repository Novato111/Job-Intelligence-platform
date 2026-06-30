"""
import_kaggle_dataset.py
────────────────────────
Imports the Kaggle "India Tech Jobs 2024-2026" dataset into Supabase raw_jobs.

Dataset file: /tmp/india-tech-jobs/india_job_market_2024_2026.csv
              (5000 rows — we import first 500 in this run)

Column mapping:
  Kaggle field        →  raw_jobs column
  ──────────────────────────────────────────
  Job_Title           →  title
  Company             →  company
  City                →  location
  Skills_Required     →  skills_raw (comma-split → list)
  Salary_LPA          →  salary  ("X.X LPA")
  Experience_Level    →  experience
  Job_Title+Skills    →  description (synthesised — no raw JD in this dataset)

Run:
  cd final-job-scrapper
  source venv/bin/activate
  python import_kaggle_dataset.py
"""

import os
import csv
import hashlib
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()
supabase: Client = create_client(
    os.environ.get("SUPABASE_URL"),
    os.environ.get("SUPABASE_KEY"),
)

CSV_PATH     = "/tmp/india-tech-jobs/india_job_market_2024_2026.csv"
IMPORT_START = 1945  # demo batch — DO NOT run pipeline on these
IMPORT_END   = 2000  # 55 jobs stay as is_processed=False for live demo


def generate_hash(title: str, company: str, location: str) -> str:
    s = f"{title.lower().strip()}|{company.lower().strip()}|{location.lower().strip()}"
    return hashlib.md5(s.encode()).hexdigest()


def clean(val: str) -> str | None:
    v = str(val).strip()
    return v if v and v.lower() not in ("none", "nan", "") else None


def parse_skills(raw: str) -> list[str]:
    if not raw or raw.strip().lower() in ("none", "nan", ""):
        return []
    return [s.strip() for s in raw.split(",") if s.strip()]


def make_description(row: dict) -> str:
    """Synthesise a description from available fields since the dataset has no raw JD."""
    parts = [
        f"Role: {row['Job_Title']} at {row['Company']}.",
        f"Industry: {row['Industry']}." if row.get("Industry") else "",
        f"Work mode: {row['Work_Mode']}." if row.get("Work_Mode") else "",
        f"Job type: {row['Job_Type']}." if row.get("Job_Type") else "",
        f"Education required: {row['Education_Required']}." if row.get("Education_Required") else "",
        f"Required skills: {row['Skills_Required']}." if row.get("Skills_Required") else "",
    ]
    return " ".join(p for p in parts if p)


def import_rows(rows: list[dict]) -> tuple[int, int, int]:
    inserted = skipped = errors = 0

    for row in rows:
        title    = clean(row.get("Job_Title"))    or "Unknown Role"
        company  = clean(row.get("Company"))      or "Unknown Company"
        location = clean(row.get("City"))         or "India"
        skills   = parse_skills(row.get("Skills_Required", ""))
        salary   = f"{row['Salary_LPA']} LPA" if row.get("Salary_LPA") else None
        exp      = clean(row.get("Experience_Level"))
        desc     = make_description(row)
        job_hash = generate_hash(title, company, location)

        # Dedup check
        try:
            existing = supabase.table("raw_jobs") \
                .select("id") \
                .eq("job_hash", job_hash) \
                .execute()
            if existing.data:
                skipped += 1
                continue
        except Exception:
            pass  # if check fails, try to insert anyway

        try:
            supabase.table("raw_jobs").insert({
                "title":        title,
                "company":      company,
                "location":     location,
                "description":  desc,
                "skills_raw":   skills,
                "salary":       salary,
                "experience":   exp,
                "job_hash":     job_hash,
                "is_processed": False,
            }).execute()
            inserted += 1
            print(f"  ✅  {title[:40]:<40} | {company[:22]:<22} | {location}")
        except Exception as e:
            errors += 1
            print(f"  ❌  {title[:40]} — {e}")

    return inserted, skipped, errors


def main():
    print(f"Reading {CSV_PATH} ...")
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    total_available = len(rows)
    rows = rows[IMPORT_START:IMPORT_END]
    print(f"  → {total_available} rows in dataset, importing rows {IMPORT_START}–{IMPORT_END} ({len(rows)} rows)\n")

    inserted, skipped, errors = import_rows(rows)

    print()
    print(f"Done.  ✅ {inserted} inserted  |  ⏭  {skipped} already existed  |  ❌ {errors} errors")
    print()
    if inserted > 0:
        print("Next steps:")
        print("  python processor.py      ← NLP skill extraction + co-occurrence")
        print("  python scoring.py        ← recalculate demand scores")
        print("  OR:  POST http://localhost:8000/pipeline/run")


if __name__ == "__main__":
    main()
