# backend/main.py
import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from dotenv import load_dotenv

# Import our new AI service
from services.ai_insights import generate_market_insights

# Load environment variables
load_dotenv()
supabase: Client = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))

# Initialize FastAPI App
app = FastAPI(title="SkillMap Intelligence API", version="1.0")

# Setup CORS so your Next.js localhost (3000) can talk to this API (8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this to your Vercel domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def health_check():
    """Simple check to ensure the API is live."""
    return {"status": "SkillMap API is running", "version": "1.0"}


@app.get("/stats")
def get_platform_stats():
    """Returns global platform statistics like total jobs scraped."""
    try:
        # Count all rows in raw_jobs where is_processed is True
        response = supabase.table('raw_jobs').select('id', count='exact').eq('is_processed', True).execute()
        
        return {
            "total_jobs_analyzed": response.count or 0
        }
    except Exception as e:
        return {"total_jobs_analyzed": 0}
    
@app.get("/skills/top")
def get_top_skills(limit: int = 10):
    """Fetches the highest-scoring skills to display on the Market Pulse dashboard."""
    try:
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
# Add this to the bottom of backend/main.py

@app.get("/stats/location")
def get_location_stats():
    """Returns geographical demand density for the heatmap."""
    # In the future, this will be: SELECT location, count(*) FROM raw_jobs GROUP BY location
    # For now, we serve a realistic live-feed proxy for the Indian subcontinent
    return [
        {"city": "Bangalore", "lng": 77.5946, "lat": 12.9716, "count": 1240, "intensity": 98},
        {"city": "Hyderabad", "lng": 78.4867, "lat": 17.3850, "count": 890, "intensity": 92},
        {"city": "Pune",      "lng": 73.8567, "lat": 18.5204, "count": 760, "intensity": 88},
        {"city": "Gurgaon",   "lng": 77.0266, "lat": 28.4595, "count": 650, "intensity": 85},
        {"city": "Mumbai",    "lng": 72.8777, "lat": 19.0760, "count": 520, "intensity": 82},
        {"city": "Chennai",   "lng": 80.2707, "lat": 13.0827, "count": 480, "intensity": 80},
        {"city": "Noida",     "lng": 77.3260, "lat": 28.5355, "count": 310, "intensity": 75},
        {"city": "Kolkata",   "lng": 88.3639, "lat": 22.5726, "count": 180, "intensity": 65}
    ]
@app.get("/skill/{name}")
def get_skill_intelligence(name: str):
    """Fetches the complete intelligence profile for a specific skill."""
    try:
        response = supabase.table('skills') \
            .select('*') \
            .ilike('name', name) \
            .execute()
            
        if not response.data:
            raise HTTPException(status_code=404, detail="Skill not found in database")
            
        return response.data[0]
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/insights/market")
def get_market_insights():
    """Generates real-time AI insights based on the current top skills in the database."""
    try:
        # 1. Fetch the top 10 skills from Supabase
        response = supabase.table('skills').select('name, demand_score').order('demand_score', desc=True).limit(10).execute()
        top_skills = response.data
        
        # 2. Pass those skills to the AI to generate the report
        insights = generate_market_insights(top_skills)
        
        return insights
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))