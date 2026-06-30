import os
from datetime import datetime, timezone, date
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()
supabase: Client = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))


def calculate_skill_scores():
    print("Fetching data for scoring...")

    jobs_response = supabase.table("raw_jobs").select("id", count="exact").eq("is_processed", True).execute()
    total_jobs = jobs_response.count

    if total_jobs == 0:
        print("No processed jobs found. Run processor.py first.")
        return

    print(f"Baseline: {total_jobs} processed jobs.")

    # Tally skill occurrences — count distinct jobs per skill (not raw map rows)
    map_response = supabase.table("skill_job_map").select("skill_name, job_id").execute()
    skill_jobs: dict[str, set] = {}
    for row in map_response.data:
        skill = row["skill_name"]
        if skill not in skill_jobs:
            skill_jobs[skill] = set()
        skill_jobs[skill].add(row["job_id"])

    skill_counts = {skill: len(job_ids) for skill, job_ids in skill_jobs.items()}

    if not skill_counts:
        print("No skill mappings found. Run processor.py first.")
        return

    # Normalized demand index: top skill = 100, others scale proportionally.
    # This is more meaningful than raw penetration rate when skill dictionary
    # is a subset of the full job corpus.
    max_count = max(skill_counts.values())

    # Fetch previous normalized scores for growth_rate delta
    prev_scores: dict[str, int] = {}
    try:
        prev = supabase.table("skills").select("name, demand_score").execute()
        prev_scores = {row["name"]: row["demand_score"] for row in (prev.data or [])}
    except Exception:
        pass

    today = date.today().isoformat()
    now = datetime.now(timezone.utc).isoformat()

    print(f"Scoring {len(skill_counts)} unique skills (max occurrences: {max_count} jobs)...")

    for skill_name, count in skill_counts.items():
        # Normalized index: top skill scores 100, rest scale proportionally
        new_score = int(round((count / max_count) * 100))
        # Also store raw penetration rate for reference
        penetration = round((count / total_jobs) * 100, 1)

        old_score = prev_scores.get(skill_name, 0)
        growth_rate = new_score - old_score

        skill_data = {
            "name": skill_name,
            "job_count": count,
            "demand_score": new_score,
            "growth_rate": growth_rate,
            "last_updated": now,
        }

        try:
            supabase.table("skills").upsert(skill_data, on_conflict="name").execute()

            try:
                existing = supabase.table("skill_history") \
                    .select("id") \
                    .eq("skill_name", skill_name) \
                    .eq("snapshot_date", today) \
                    .execute()
                if not existing.data:
                    supabase.table("skill_history").insert({
                        "skill_name": skill_name,
                        "demand_score": new_score,
                        "job_count": count,
                        "snapshot_date": today,
                    }).execute()
            except Exception:
                pass

            arrow = "↑" if growth_rate > 0 else ("↓" if growth_rate < 0 else "→")
            print(f"  📊 {skill_name.upper():<22} {new_score:>3}/100  ({penetration}% penetration)  {arrow} {growth_rate:+d}pts")

        except Exception as e:
            print(f"  ❌ Failed to score {skill_name}: {e}")


if __name__ == "__main__":
    calculate_skill_scores()
