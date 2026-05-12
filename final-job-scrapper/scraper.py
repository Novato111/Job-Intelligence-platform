import os
import hashlib
import asyncio
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from supabase import create_client, Client
from datetime import datetime, timezone

# Load environment variables
load_dotenv()

# Initialize Supabase client
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

def generate_job_hash(title, company, location):
    """Generates an MD5 hash to prevent duplicate job entries in Supabase."""
    hash_string = f"{title.lower().strip()}|{company.lower().strip()}|{location.lower().strip()}"
    return hashlib.md5(hash_string.encode()).hexdigest()

async def scrape_naukri():
    print("Launching Playwright...")
    async with async_playwright() as p:
        # Launching in non-headless mode initially is highly recommended for bot-heavy sites
        browser = await p.chromium.launch(headless=False) 
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )
        page = await context.new_page()

        search_query = "software developer"
        url = f"https://www.naukri.com/{search_query.replace(' ', '-')}-jobs"
        
        print(f"Navigating to: {url}")
        await page.goto(url, wait_until="domcontentloaded")
        
        # Wait for the job cards to load in the DOM
        try:
            await page.wait_for_selector('.srp-jobtuple-wrapper', timeout=15000)
            await page.wait_for_timeout(2000) # Human-like pause
        except Exception as e:
            print("Timeout waiting for job cards. You might be facing a CAPTCHA.")
            await browser.close()
            return

        print("Extracting job data...")
        # Get all job card elements
        job_cards = await page.query_selector_all('.srp-jobtuple-wrapper')
        
        # Only process the first 10 to keep the volume low and safe
        jobs_to_process = job_cards[:10]
        extracted_jobs = []

        for card in jobs_to_process:
            # Safely extract text, defaulting to 'N/A' if the element is missing
            title_el = await card.query_selector('.title')
            title = await title_el.inner_text() if title_el else "N/A"
            
            comp_el = await card.query_selector('.comp-name')
            company = await comp_el.inner_text() if comp_el else "N/A"
            
            exp_el = await card.query_selector('.exp')
            experience = await exp_el.inner_text() if exp_el else "N/A"
            
            loc_el = await card.query_selector('.loc')
            location = await loc_el.inner_text() if loc_el else "N/A"
            
            sal_el = await card.query_selector('.sal')
            salary = await sal_el.inner_text() if sal_el else "Not Disclosed"
            
            # Extract skills into a raw string array
            skill_elements = await card.query_selector_all('.tags-gt .tag-li')
            skills_raw = [await skill.inner_text() for skill in skill_elements]

            # Generate the unique hash
            job_hash = generate_job_hash(title, company, location)

            job_data = {
                "title": title.strip(),
                "company": company.strip(),
                "location": location.strip(),
                "experience": experience.strip(),
                "salary": salary.strip(),
                "skills_raw": skills_raw,
                "query_used": search_query,
                "source": "naukri",
                "scraped_at": datetime.now(timezone.utc).isoformat(),
                "is_processed": False,
                "job_hash": job_hash
            }
            extracted_jobs.append(job_data)

        print(f"Successfully extracted {len(extracted_jobs)} jobs. Pushing to Supabase...")

        # Push to Supabase raw_jobs table
        for job in extracted_jobs:
            try:
                # The upsert function will insert the row, or update it if the job_hash already exists
                response = supabase.table('raw_jobs').upsert(job, on_conflict='job_hash').execute()
                print(f"Stored: {job['title']} at {job['company']}")
            except Exception as e:
                print(f"Error storing job {job['job_hash']}: {e}")

        await browser.close()

if __name__ == "__main__":
    # Run the async loop
    asyncio.run(scrape_naukri())