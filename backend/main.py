import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from dotenv import load_dotenv
from fastapi import Query
# Load environment variables
load_dotenv()
supabase: Client = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))

# Initialize FastAPI App
app = FastAPI(title="SkillMap Intelligence API", version="1.0")

# Setup CORS so your Next.js localhost can talk to this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this to your Vercel URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def health_check():
    """Simple check to ensure the API is live."""
    return {"status": "SkillMap API is running", "version": "1.0"}

@app.get("/search")
def search_skills(q: str = Query(..., min_length=1, description="Search query")):
    """Powers the autocomplete search bar on the frontend."""
    try:
        # Use ilike for case-insensitive partial matching
        response = supabase.table('skills') \
            .select('name') \
            .ilike('name', f'%{q}%') \
            .limit(5) \
            .execute()
        
        # Format as a simple list of strings for the frontend UI
        suggestions = [item['name'] for item in response.data]
        return {"suggestions": suggestions}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/skill/{name}")
def get_skill_intelligence(name: str):
    """Fetches the complete intelligence profile for a specific skill."""
    try:
        # Case-insensitive exact match for the skill
        response = supabase.table('skills') \
            .select('*') \
            .ilike('name', name) \
            .execute()
            
        if not response.data:
            raise HTTPException(status_code=404, detail="Skill not found in database")
            
        skill_data = response.data[0]
        
        # In the future, we will also fetch the connected skills from the skill_job_map here
        
        return skill_data
        
    except Exception as e:
        # If it's our custom 404, pass it through
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))
@app.get("/skills/top")
def get_top_skills(limit: int = 10):
    """Fetches the highest-scoring skills to display on the Market Pulse dashboard."""
    try:
        # Query Supabase: Select all, order by demand_score descending, limit results
        response = supabase.table('skills') \
            .select('*') \
            .order('demand_score', desc=True) \
            .limit(limit) \
            .execute()
        
        return {
            "count": len(response.data),
            "data": response.data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))