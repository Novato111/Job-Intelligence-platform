"""
import_hf_dataset.py
────────────────────
Fetches the muhammetakkurt/naukri-jobs-dataset from HuggingFace Datasets
Server and imports it into our Supabase raw_jobs table.

Column mapping:
  HuggingFace field   →  raw_jobs column
  ─────────────────────────────────────
  title               →  title
  companyName         →  company
  location            →  location  (first city if multiple given)
  jobDescription      →  description
  tagsAndSkills       →  skills_raw (comma-split → JSON array)
  salary              →  salary
  experience          →  experience

Run:
  cd final-job-scrapper
  source venv/bin/activate
  python import_hf_dataset.py
"""

import os
import json
import hashlib
import requests
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()
supabase: Client = create_client(
    os.environ.get("SUPABASE_URL"),
    os.environ.get("SUPABASE_KEY"),
)

HF_API = (
    "https://datasets-server.huggingface.co/first-rows"
    "?dataset=muhammetakkurt%2Fnaukri-jobs-dataset"
    "&config=default&split=train"
)


def generate_hash(title: str, company: str, location: str) -> str:
    s = f"{title.lower().strip()}|{company.lower().strip()}|{location.lower().strip()}"
    return hashlib.md5(s.encode()).hexdigest()


def clean_location(loc: str) -> str:
    """Take only the first city when multiple are listed."""
    if not loc or loc == "None":
        return "India"
    return loc.split(",")[0].strip()


def clean_skills(tags: str) -> list:
    """Convert comma-separated skills string to a list."""
    if not tags or tags == "None":
        return []
    return [s.strip() for s in tags.split(",") if s.strip()]


def clean_value(val) -> str | None:
    """Return None for empty / 'None' strings."""
    if val is None or str(val).strip() in ("None", "none", ""):
        return None
    return str(val).strip()


def fetch_dataset() -> list:
    print("Fetching dataset from HuggingFace...")
    resp = requests.get(HF_API, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    rows = [r["row"] for r in data.get("rows", [])]
    print(f"  → {len(rows)} rows fetched.")
    return rows


def import_rows(rows: list):
    inserted = 0
    skipped  = 0
    errors   = 0

    for row in rows:
        title    = clean_value(row.get("title"))    or "Unknown Role"
        company  = clean_value(row.get("companyName")) or "Unknown Company"
        location = clean_location(row.get("location", ""))
        desc     = clean_value(row.get("jobDescription"))
        skills   = clean_skills(row.get("tagsAndSkills", ""))
        salary   = clean_value(row.get("salary"))
        exp      = clean_value(row.get("experience"))

        job_hash = generate_hash(title, company, location)

        # Skip if already imported (same title + company + location)
        existing = supabase.table("raw_jobs") \
            .select("id") \
            .eq("job_hash", job_hash) \
            .execute()

        if existing.data:
            skipped += 1
            continue

        try:
            supabase.table("raw_jobs").insert({
                "title":       title,
                "company":     company,
                "location":    location,
                "description": desc,
                "skills_raw":  skills,          # stored as JSON array
                "salary":      salary,
                "experience":  exp,
                "job_hash":    job_hash,
                "is_processed": False,
            }).execute()

            inserted += 1
            print(f"  ✅  {title[:45]:<45} | {company[:25]:<25} | {location}")

        except Exception as e:
            errors += 1
            print(f"  ❌  {title[:45]} — {e}")

    print()
    print(f"Done. {inserted} inserted, {skipped} already existed, {errors} errors.")
    return inserted


def main():
    rows    = fetch_dataset()
    total   = import_rows(rows)

    if total > 0:
        print()
        print("Next steps:")
        print("  python processor.py   ← extract skills + co-occurrence")
        print("  python scoring.py     ← recalculate demand scores")
        print("  OR: POST http://localhost:8000/pipeline/run")


if __name__ == "__main__":
    main()
