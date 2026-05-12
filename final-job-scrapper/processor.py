import os
import re
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()
supabase: Client = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))

# Master Dictionary (You can expand this massively later)
MASTER_SKILLS = {
    "languages": ["python", "javascript", "typescript", "java", "c++", "go", "rust"],
    "frontend": ["react", "next.js", "vue", "angular", "tailwind"],
    "backend": ["node.js", "express", "django", "fastapi", "spring boot"],
    "database": ["sql", "postgresql", "mongodb", "mysql", "redis", "supabase"],
    "cloud": ["aws", "docker", "kubernetes", "linux", "git", "ci/cd", "azure"]
}

FLAT_SKILLS = [skill for category in MASTER_SKILLS.values() for skill in category]

def extract_skills(description_text, skills_raw_array):
    found_skills = []
    text_lower = str(description_text).lower() if description_text else ""
    raw_lower = [str(s).lower() for s in skills_raw_array] if skills_raw_array else []

    for skill in FLAT_SKILLS:
        is_in_tags = any(skill == tag or skill in tag.split() for tag in raw_lower)
        # Using regex word boundaries \b so "go" doesn't trigger on "good"
        is_in_text = bool(re.search(rf"\b{re.escape(skill)}\b", text_lower))

        if is_in_tags:
            found_skills.append({"name": skill, "is_explicit": True})
        elif is_in_text:
            found_skills.append({"name": skill, "is_explicit": False})
            
    return found_skills

def normalize_salary(salary_string):
    if not salary_string or "disclosed" in salary_string.lower():
        return None, None
    
    clean_string = salary_string.replace(",", "")
    numbers = [int(n) for n in re.findall(r'\d+', clean_string)]
    
    if not numbers:
        return None, None

    min_val = numbers[0]
    max_val = numbers[1] if len(numbers) > 1 else min_val

    # Convert large rupee values to LPA standard (e.g., 1500000 -> 15)
    if min_val > 1000:
        min_val = min_val / 100000
    if max_val > 1000:
        max_val = max_val / 100000

    return int(min_val), int(max_val)

def tag_seniority(experience_string):
    if not experience_string:
        return "Unknown"
    
    exp_lower = experience_string.lower()
    numbers = [int(n) for n in re.findall(r'\d+', exp_lower)]
    
    if not numbers:
        if "senior" in exp_lower or "lead" in exp_lower:
            return "Senior"
        return "Mid"
        
    min_exp = numbers[0]
    
    if min_exp <= 2:
        return "Junior"
    elif min_exp <= 5:
        return "Mid"
    else:
        return "Senior"

def run_pipeline():
    print("Fetching unprocessed jobs from Supabase...")
    # Grab only the jobs that haven't been processed yet
    response = supabase.table('raw_jobs').select('*').eq('is_processed', False).execute()
    jobs = response.data

    if not jobs:
        print("Queue is empty. No new jobs to process.")
        return

    print(f"Found {len(jobs)} jobs. Running extraction pipeline...")

    for job in jobs:
        job_id = job['id']
        
        # Transform
        skills = extract_skills(job.get('description'), job.get('skills_raw'))
        min_sal, max_sal = normalize_salary(job.get('salary'))
        seniority = tag_seniority(job.get('experience'))
        
        try:
            # Load: Insert the mapped skills into the bridge table
            for skill in skills:
                supabase.table('skill_job_map').insert({
                    "job_id": job_id,
                    "skill_name": skill["name"],
                    "is_explicit": skill["is_explicit"]
                }).execute()
            
            # Load: Mark the original row as processed so we don't scan it again tomorrow
            supabase.table('raw_jobs').update({
                "is_processed": True
            }).eq('id', job_id).execute()
            
            print(f"✅ Processed: {job.get('title')[:30]}... -> Found {len(skills)} skills | Level: {seniority}")
            
        except Exception as e:
            print(f"❌ Failed to process job {job_id}: {e}")

if __name__ == "__main__":
    run_pipeline()