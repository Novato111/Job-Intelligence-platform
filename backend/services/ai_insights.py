# backend/services/ai_insights.py
import os
import json
import google.generativeai as genai

genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

def generate_market_insights(top_skills_data):
    # 🚨 THE KILL SWITCH: Save credits during UI development
    if os.environ.get("USE_MOCK_AI", "True") == "True":
        print("🧠 USE_MOCK_AI is True. Returning free local data...")
        return {
            "rising": {"title": "Vector Databases (MOCK)", "description": "High demand for Pinecone and Weaviate expertise."},
            "risk": {"title": "Legacy PHP (MOCK)", "description": "Maintenance roles declining; migration skills are key."},
            "emerging": {"title": "Agentic Workflows (MOCK)", "description": "AutoGPT and CrewAI becoming critical for internal ops."}
        }

    # If USE_MOCK_AI is False, run the actual Gemini API
    try:
        print("🚀 Calling Gemini API for live insights...")
        context = f"Current top tech skills based on our job scraper: {top_skills_data}"
        
        prompt = f"""
        You are an elite Tech Job Market Analyst. Based on this live data: {context}
        Generate 3 concise market insights:
        1. A 'Rising Signal' (a booming technology)
        2. A 'Risk Signal' (a declining or threatened technology)
        3. An 'Emerging Signal' (a brand new, cutting-edge technology)
        
        Return ONLY valid JSON in this exact format:
        {{
            "rising": {{"title": "Short Title", "description": "One sentence explanation."}},
            "risk": {{"title": "Short Title", "description": "One sentence explanation."}},
            "emerging": {{"title": "Short Title", "description": "One sentence explanation."}}
        }}
        """

        model = genai.GenerativeModel('gemini-1.5-flash', generation_config={"response_mime_type": "application/json"})
        response = model.generate_content(prompt)
        return json.loads(response.text)

    except Exception as e:
        print(f"Gemini API Generation Failed: {e}")
        return {
            "rising": {"title": "API Error", "description": "Could not connect to Gemini."},
            "risk": {"title": "API Error", "description": "Could not connect to Gemini."},
            "emerging": {"title": "API Error", "description": "Could not connect to Gemini."}
        }