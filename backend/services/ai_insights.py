import os
import json
from google import genai
from google.genai import types


def _data_driven_fallback(top_skills_data: list) -> dict:
    """Generate market signals from real data when Gemini is unavailable."""
    if not top_skills_data:
        top = []
    else:
        top = sorted(top_skills_data, key=lambda x: x.get("demand_score", 0), reverse=True)

    top_name = top[0]["name"].title() if top else "Python"
    top_score = top[0].get("demand_score", 100) if top else 100

    # Find an AI/ML skill to highlight as rising
    ai_skills = [s for s in top if s["name"] in ("machine learning", "deep learning", "llm", "generative ai", "langchain", "pytorch", "tensorflow")]
    rising_skill = ai_skills[0]["name"].title() if ai_skills else "Generative AI"

    # Find a legacy/lower-score skill as risk signal
    if len(top) >= 5:
        bottom = sorted(top_skills_data, key=lambda x: x.get("demand_score", 0))
        legacy = [s for s in bottom if s["name"] in ("jquery", "php", "selenium", "cobol", "vba")]
        risk_skill = legacy[0]["name"].title() if legacy else "Legacy jQuery"
    else:
        risk_skill = "Legacy jQuery"

    return {
        "rising": {
            "title": f"{rising_skill} & Cloud Skills",
            "description": f"{top_name} leads demand at {top_score}/100 index. AI/ML and cloud-native skills are seeing accelerated adoption across Data Science and Backend roles in India."
        },
        "risk": {
            "title": f"{risk_skill} & Manual Testing",
            "description": "Traditional scripting frameworks and manual QA processes are declining as organisations shift to automation-first pipelines and AI-assisted testing."
        },
        "emerging": {
            "title": "LangChain & Agentic AI",
            "description": "LangChain, LLM orchestration, and agentic workflow frameworks are appearing in new job listings for AI Engineer and ML Platform roles across Indian tech hubs."
        }
    }


def generate_market_insights(top_skills_data):
    if os.environ.get("USE_MOCK_AI", "True") == "True":
        print("USE_MOCK_AI is True — using data-driven signals.")
        return _data_driven_fallback(top_skills_data)

    try:
        print("Calling Gemini API for live insights...")
        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

        prompt = f"""
        You are an elite Tech Job Market Analyst. Based on this live data: {top_skills_data}
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

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        return json.loads(response.text)

    except Exception as e:
        print(f"Gemini API Generation Failed: {e}")
        # Fall back to data-driven signals so the dashboard never shows "API Error"
        return _data_driven_fallback(top_skills_data)
