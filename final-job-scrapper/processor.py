import os
import re
from itertools import combinations
from datetime import datetime, timezone
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()
supabase: Client = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))

# --- NLP Setup ---
try:
    import spacy
    from spacy.matcher import PhraseMatcher
    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        print("Downloading spaCy model en_core_web_sm...")
        from spacy.cli import download
        download("en_core_web_sm")
        nlp = spacy.load("en_core_web_sm")
    SPACY_AVAILABLE = True
    print("spaCy loaded — using NLP extraction")
except ImportError:
    SPACY_AVAILABLE = False
    print("spaCy not installed — falling back to regex extraction")

# --- Skill Dictionary (200+ skills) ---
MASTER_SKILLS = {
    "languages": [
        "python", "javascript", "typescript", "java", "c++", "c#", "go", "rust",
        "kotlin", "swift", "scala", "ruby", "php", "r", "dart", "matlab", "perl",
        "haskell", "lua", "elixir", "clojure", "fortran", "cobol",
    ],
    "frontend": [
        "react", "next.js", "vue", "angular", "svelte", "tailwind css", "bootstrap",
        "webpack", "vite", "redux", "graphql", "html", "css", "sass", "jquery",
        "storybook", "figma",
    ],
    "backend": [
        "node.js", "express", "django", "fastapi", "spring boot", "flask", "rails",
        "laravel", "asp.net", "gin", "nest.js", "fastify", "grpc", "celery",
    ],
    "database": [
        "sql", "postgresql", "mongodb", "mysql", "redis", "elasticsearch",
        "cassandra", "dynamodb", "firebase", "sqlite", "oracle", "supabase",
        "mariadb", "cockroachdb", "neo4j", "influxdb",
    ],
    "cloud": [
        "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "ansible",
        "jenkins", "linux", "nginx", "vercel", "heroku", "cloudflare",
        "github actions", "gitlab ci", "circleci",
    ],
    "ml_ai": [
        "machine learning", "deep learning", "tensorflow", "pytorch", "scikit-learn",
        "pandas", "numpy", "nlp", "computer vision", "bert", "langchain",
        "keras", "xgboost", "opencv", "matplotlib", "scipy", "hugging face",
        "llm", "generative ai", "stable diffusion", "reinforcement learning",
        "random forest", "neural network",
    ],
    "data": [
        "data science", "power bi", "tableau", "apache spark", "hadoop", "kafka",
        "airflow", "dbt", "snowflake", "bigquery", "data engineering", "etl",
        "looker", "databricks", "data warehousing", "data pipeline",
    ],
    "practices": [
        "agile", "scrum", "devops", "microservices", "rest api", "system design",
        "object oriented programming", "data structures", "algorithms", "ci/cd",
        "test driven development", "api design", "software architecture",
        "design patterns", "domain driven design",
    ],
    "testing": [
        "jest", "pytest", "selenium", "cypress", "junit", "mocha", "postman",
        "unit testing", "integration testing", "playwright",
    ],
    "security": [
        "cybersecurity", "oauth", "jwt", "cryptography", "penetration testing",
        "ssl", "zero trust",
    ],
    "mobile": [
        "android", "ios", "react native", "flutter", "xamarin",
    ],
}

FLAT_SKILLS = [skill for category in MASTER_SKILLS.values() for skill in category]
FLAT_SKILLS_SET = set(FLAT_SKILLS)

# Normalize common aliases → canonical skill name
NORMALIZATION = {
    "reactjs": "react", "react.js": "react",
    "nodejs": "node.js", "node": "node.js",
    "postgres": "postgresql", "pg": "postgresql",
    "k8s": "kubernetes",
    "golang": "go",
    "js": "javascript",
    "ts": "typescript",
    "py": "python",
    "ml": "machine learning", "dl": "deep learning",
    "tf": "tensorflow",
    "sklearn": "scikit-learn", "sk-learn": "scikit-learn",
    "spring": "spring boot",
    "vue.js": "vue", "vuejs": "vue",
    "angular.js": "angular", "angularjs": "angular",
    "gen ai": "generative ai",
}

# Build spaCy PhraseMatcher over all known skills
if SPACY_AVAILABLE:
    phrase_matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
    for skill in FLAT_SKILLS:
        phrase_matcher.add(skill, [nlp.make_doc(skill)])


def extract_skills(description_text: str, skills_raw_array: list) -> list:
    found = {}  # skill_name -> is_explicit

    # 1. Raw tags from the job listing (highest confidence — explicit signals)
    for tag in [str(s).lower().strip() for s in (skills_raw_array or [])]:
        canonical = NORMALIZATION.get(tag, tag)
        if canonical in FLAT_SKILLS_SET:
            found[canonical] = True

    # 2. NLP extraction from description body
    text = str(description_text or "")
    if SPACY_AVAILABLE and text:
        doc = nlp(text[:50000])  # cap to avoid memory issues on huge JDs
        for match_id, start, end in phrase_matcher(doc):
            skill_name = nlp.vocab.strings[match_id]
            if skill_name not in found:
                found[skill_name] = False
    else:
        # Regex fallback with word boundaries (no spaCy)
        text_lower = text.lower()
        for skill in FLAT_SKILLS:
            if skill not in found:
                if re.search(rf"\b{re.escape(skill)}\b", text_lower):
                    found[skill] = False

    return [{"name": name, "is_explicit": is_explicit} for name, is_explicit in found.items()]


def update_cooccurrence(skill_names: list):
    """Record which skills appear together in the same job posting."""
    if len(skill_names) < 2:
        return

    now = datetime.now(timezone.utc).isoformat()
    for skill_a, skill_b in combinations(sorted(skill_names), 2):
        try:
            existing = supabase.table("skill_cooccurrence") \
                .select("id, count") \
                .eq("skill_a", skill_a) \
                .eq("skill_b", skill_b) \
                .execute()

            if existing.data:
                supabase.table("skill_cooccurrence").update({
                    "count": existing.data[0]["count"] + 1,
                    "last_updated": now,
                }).eq("id", existing.data[0]["id"]).execute()
            else:
                supabase.table("skill_cooccurrence").insert({
                    "skill_a": skill_a,
                    "skill_b": skill_b,
                    "count": 1,
                    "last_updated": now,
                }).execute()
        except Exception:
            # Table may not exist yet — skip silently
            pass


def normalize_salary(salary_string):
    if not salary_string or "disclosed" in str(salary_string).lower():
        return None, None
    clean = str(salary_string).replace(",", "")
    numbers = [int(n) for n in re.findall(r"\d+", clean)]
    if not numbers:
        return None, None
    min_val, max_val = numbers[0], numbers[1] if len(numbers) > 1 else numbers[0]
    if min_val > 1000:
        min_val = min_val / 100000
    if max_val > 1000:
        max_val = max_val / 100000
    return int(min_val), int(max_val)


def tag_seniority(experience_string):
    if not experience_string:
        return "Unknown"
    exp_lower = str(experience_string).lower()
    numbers = [int(n) for n in re.findall(r"\d+", exp_lower)]
    if not numbers:
        return "Senior" if any(w in exp_lower for w in ("senior", "lead")) else "Mid"
    min_exp = numbers[0]
    if min_exp <= 2:
        return "Junior"
    elif min_exp <= 5:
        return "Mid"
    return "Senior"


def run_pipeline():
    print("Fetching unprocessed jobs from Supabase...")
    response = supabase.table("raw_jobs").select("*").eq("is_processed", False).execute()
    jobs = response.data

    if not jobs:
        print("Queue is empty. No new jobs to process.")
        return

    print(f"Found {len(jobs)} jobs. Running NLP extraction pipeline...")

    for job in jobs:
        job_id = job["id"]
        skills = extract_skills(job.get("description"), job.get("skills_raw"))
        seniority = tag_seniority(job.get("experience"))

        try:
            for skill in skills:
                supabase.table("skill_job_map").insert({
                    "job_id": job_id,
                    "skill_name": skill["name"],
                    "is_explicit": skill["is_explicit"],
                }).execute()

            # Co-occurrence: record which skills appear together
            update_cooccurrence([s["name"] for s in skills])

            supabase.table("raw_jobs").update({"is_processed": True}).eq("id", job_id).execute()

            title = str(job.get("title", ""))[:30]
            print(f"  ✅ {title}... → {len(skills)} skills | {seniority}")

        except Exception as e:
            print(f"  ❌ Job {job_id}: {e}")


if __name__ == "__main__":
    run_pipeline()
