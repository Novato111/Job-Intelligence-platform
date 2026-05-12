import os
from dotenv import load_dotenv
from supabase import create_client, Client
from datetime import datetime, timezone

load_dotenv()
supabase: Client = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))

def calculate_skill_scores():
    print("Fetching data for scoring...")
    
    # 1. Get total number of processed jobs to calculate percentages
    # We only count processed jobs so our math is accurate
    jobs_response = supabase.table('raw_jobs').select('id', count='exact').eq('is_processed', True).execute()
    total_jobs = jobs_response.count
    
    if total_jobs == 0:
        print("No processed jobs found. Run processor.py first.")
        return

    print(f"Calculating scores against a baseline of {total_jobs} total jobs.")

    # 2. Fetch all skill mappings
    map_response = supabase.table('skill_job_map').select('*').execute()
    mappings = map_response.data

    # 3. Tally up the occurrences of each skill
    skill_counts = {}
    for row in mappings:
        skill = row['skill_name']
        if skill in skill_counts:
            skill_counts[skill] += 1
        else:
            skill_counts[skill] = 1

    # 4. Calculate Demand Score and Upsert into the Database
    # Formula: (skill_job_count / total_jobs) * 100 [cite: 79]
    print(f"Found {len(skill_counts)} unique skills. Pushing scores to DB...")
    
    for skill_name, count in skill_counts.items():
        # Calculate percentage out of 100, rounded to nearest integer
        demand_score = int(round((count / total_jobs) * 100))
        
        skill_data = {
            "name": skill_name,
            "job_count": count,
            "demand_score": demand_score,
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
        
        try:
            # Upsert updates the row if the skill name already exists
            supabase.table('skills').upsert(skill_data, on_conflict='name').execute()
            print(f"📊 Scored {skill_name.upper()}: Demand={demand_score}/100 | Count={count}")
        except Exception as e:
            print(f"❌ Failed to update score for {skill_name}: {e}")

if __name__ == "__main__":
    calculate_skill_scores()
    