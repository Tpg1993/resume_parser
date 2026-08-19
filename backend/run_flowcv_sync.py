import asyncio
import sys
import os
from dotenv import load_dotenv

# Load env variables (for SARVAM_API_KEY)
load_dotenv()

# Add backend folder to import path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.linkedin_scraper import fetch_and_condense_job
from services.flowcv_automation import run_flowcv_sync

# Force UTF-8 safe IO for Windows consoles
if sys.platform.startswith("win"):
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.detach())

async def main():
    print("========================================================")
    print("💼 FlowCV Tailoring Interactive Automation")
    print("========================================================\n")
    
    # 1. Ask for URL or JD text
    print("Options to load the target Job Description (JD):")
    print("1. Enter job posting URL (LinkedIn, Indeed, etc.) [RECOMMENDED - Saves Tokens]")
    print("2. Paste raw Job Description text manually")
    
    choice = input("\nSelect option [1/2]: ").strip()
    
    jd_text = ""
    
    if choice == '1':
        url = input("\nEnter Job URL: ").strip()
        if not url:
            print("❌ URL cannot be empty.", flush=True)
            return
        
        print("\nFetching and condensing job requirements from URL to minimize token cost...", flush=True)
        try:
            result = await fetch_and_condense_job(url)
            scraped_title = result.get('title', '')
            scraped_jd = result.get("condensed_jd", "")
            
            # Check if LinkedIn blocked/redirected us
            if "LinkedIn Login" in scraped_title or len(scraped_jd.strip()) < 150:
                print("❌ LinkedIn blocked the public scraping request (redirected to sign-in page).", flush=True)
                print("We cannot scrape private or collection-bound jobs without an active session.", flush=True)
                print("Switching automatically to manual copy-paste mode...", flush=True)
                choice = '2'
            else:
                print(f"✅ Extracted core requirements from: {scraped_title} at {result.get('company') or 'Unknown'}", flush=True)
                print(f"📉 Reduced text size by {result.get('original_length') - result.get('condensed_length')} characters!", flush=True)
                jd_text = scraped_jd
                
                # Print condensed preview
                print("\n--- Extracted Requirements Preview ---", flush=True)
                print(jd_text[:800] + "..." if len(jd_text) > 800 else jd_text, flush=True)
                print("---------------------------------------\n", flush=True)
        except Exception as e:
            print(f"❌ Failed to scrape URL: {str(e)}", flush=True)
            print("Attempting to fallback to manual entry.", flush=True)
            choice = '2'
            
    if choice != '1':
        print("\nPlease paste the Job Description text. Press Enter and then Ctrl+Z (on Windows) or Ctrl+D (on Linux/Mac) to finish:")
        lines = []
        try:
            while True:
                line = input()
                lines.append(line)
        except EOFError:
            pass
        jd_text = "\n".join(lines).strip()
        
    if not jd_text:
        print("❌ No job description provided. Exiting.")
        return
        
    # 2. Trigger Playwright interactive edit sync
    try:
        await run_flowcv_sync(jd_text)
    except Exception as e:
        print(f"\n❌ Error during interactive sync: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Sync aborted by user. Exiting.")
