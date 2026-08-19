import asyncio
import os
import sys
import re
from playwright.async_api import async_playwright
from services.langgraph_agent import call_sarvam_ai

# Ensure logs and outputs are UTF-8 safe for Windows CMD/PowerShell
if sys.platform.startswith("win"):
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.detach())

async def get_editor_fields(page) -> list:
    """
    Scans the FlowCV editor page to locate textareas and associate them
    with nearby Job Title and Company inputs using relative DOM traversal.
    """
    js_scraper = """
    () => {
        const fields = [];
        const textareas = document.querySelectorAll('textarea');
        
        textareas.forEach((ta, idx) => {
            const val = ta.value || "";
            // Ignore very short or empty fields
            if (val.trim().length < 15) return;
            
            let container = ta.parentElement;
            let title = "";
            let company = "";
            
            // Traverse up up to 6 levels to find parent containers that group inputs
            for (let i = 0; i < 6; i++) {
                if (!container) break;
                const inputs = container.querySelectorAll('input[type="text"]');
                inputs.forEach(input => {
                    const placeholder = (input.placeholder || "").toLowerCase();
                    const name = (input.name || "").toLowerCase();
                    const value = input.value || "";
                    
                    // Match Job Title inputs
                    if (placeholder.includes('title') || placeholder.includes('role') || name.includes('title')) {
                        title = value;
                    }
                    // Match Company/Employer inputs
                    if (placeholder.includes('employer') || placeholder.includes('company') || placeholder.includes('organization') || name.includes('company')) {
                        company = value;
                    }
                });
                if (title || company) break;
                container = container.parentElement;
            }
            
            fields.push({
                index: idx,
                title: title.trim() || "Professional Summary / General",
                company: company.trim() || "",
                original_text: val.trim()
            });
        });
        return fields;
    }
    """
    try:
        return await page.evaluate(js_scraper)
    except Exception as e:
        print(f"Error scraping fields from page DOM: {str(e)}")
        return []

async def tailor_section(original_text: str, title: str, company: str, jd_text: str) -> str:
    """
    Calls Sarvam AI to tailor a single work experience or summary block to the JD.
    """
    comp_str = f" at {company}" if company else ""
    prompt = f"""
    You are an expert ATS Resume Writer.
    Your task is to tailor a specific section of the candidate's resume (e.g. work experience description or professional summary) to better align with the Target Job Description.

    TARGET JOB DESCRIPTION:
    {jd_text}

    CURRENT SECTION DETAILS:
    - Role/Section: {title}{comp_str}
    - Current Content:
    {original_text}

    INSTRUCTIONS:
    1. Tailor the content to incorporate missing keywords, highlight relevant achievements, and use action-oriented verbs.
    2. Keep the output length, structure (e.g. bullet points), and professional tone similar to the original text.
    3. Do NOT hallucinate entirely new jobs or false accomplishments. Tailor the existing achievements to match the JD keywords.
    4. Respond ONLY with the tailored content. Do not add any conversational filler, quotes, or markdown wrappers.
    """
    try:
        tailored = await call_sarvam_ai(prompt, temperature=0.3)
        return tailored.strip()
    except Exception as e:
        print(f"Error communicating with AI: {str(e)}")
        return original_text

async def apply_changes_to_field(page, index: int, new_text: str):
    """
    Writes the tailored text back into the FlowCV editor textarea and dispatches
    native input events to trigger React state binding updates.
    """
    js_writer = """
    (data) => {
        const textareas = document.querySelectorAll('textarea');
        const ta = textareas[data.index];
        if (ta) {
            ta.focus();
            ta.value = data.text;
            // Dispatch input and change events so React registers the new value
            ta.dispatchEvent(new Event('input', { bubbles: true }));
            ta.dispatchEvent(new Event('change', { bubbles: true }));
            ta.blur();
            return true;
        }
        return false;
    }
    """
    try:
        success = await page.evaluate(js_writer, {"index": index, "text": new_text})
        return success
    except Exception as e:
        print(f"Error writing to textarea index {index}: {str(e)}")
        return False

async def run_flowcv_sync(jd_text: str):
    """
    Main interactive Playwright loop for FlowCV sync.
    """
    print("\n========================================================")
    print("🚀 STARTING FLOWCV INTERACTIVE RESUME SYNC PIPELINE")
    print("========================================================\n")
    
    async with async_playwright() as p:
        # Automatically close and restart Chrome in remote debugging mode
        import subprocess
        print("Forcing Google Chrome to close completely to enable debugging...")
        subprocess.run("taskkill /F /IM chrome.exe", shell=True, capture_output=True)
        await asyncio.sleep(2)
        
        print("Starting your regular Google Chrome with remote debugging on port 9222...")
        chrome_paths = [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            "chrome.exe"
        ]
        
        chrome_started = False
        for path in chrome_paths:
            try:
                subprocess.Popen([path, "--remote-debugging-port=9222"])
                chrome_started = True
                break
            except Exception:
                continue
                
        if chrome_started:
            print("✅ Google Chrome restarted successfully! Please click 'Restore' in Chrome if prompted.")
            # Give Chrome 3 seconds to start listening on port 9222
            await asyncio.sleep(3)
        else:
            print("⚠️ Could not launch Chrome automatically. Attempting manual connection fallback.")
            
        # Launch visible browser: Triple-Layer Strategy
        context = None
        browser = None
        page = None
        
        # Layer 1: Connect to existing Chrome running with remote debugging (CDP)
        try:
            print("Attempting to connect to your existing Chrome browser via remote debugging (port 9222)...")
            browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            print("✅ Successfully connected to your active Chrome browser session!")
            
            # Find open tab with flowcv.com
            pages = browser.contexts[0].pages
            for p_obj in pages:
                if "flowcv.com" in p_obj.url:
                    page = p_obj
                    break
            
            if page:
                print(f"✅ Found active FlowCV tab: '{await page.title()}'")
            else:
                print("⚠️ Connected to Chrome, but couldn't find an open tab with 'flowcv.com'.")
                page = await browser.contexts[0].new_page()
                print("Opening a new tab in your Chrome and navigating to FlowCV...")
                await page.goto("https://flowcv.com/resumes")
        except Exception as e_cdp:
            print(f"ℹ️ Could not connect to Chrome via port 9222: {str(e_cdp)}")
            print("Proceeding to launch browser profile...")
            
            # Layer 2: Launch actual Chrome profile (works if Chrome is closed)
            local_appdata = os.getenv("LOCALAPPDATA", r"C:\Users\Tejas\AppData\Local")
            actual_chrome_profile = os.path.join(local_appdata, r"Google\Chrome\User Data")
            try:
                print(f"Attempting to launch your actual Google Chrome profile at: {actual_chrome_profile}")
                context = await p.chromium.launch_persistent_context(
                    user_data_dir=actual_chrome_profile,
                    channel="chrome",
                    headless=False
                )
                print("✅ Successfully opened your Google Chrome profile!")
                page = context.pages[0] if context.pages else await context.new_page()
            except Exception as e_profile:
                print(f"ℹ️ Could not open actual Chrome profile (profile folder locked: {str(e_profile)})")
                
                # Layer 3: Fallback to local persistent profile
                profile_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".flowcv_profile")
                print(f"Launching a separate browser with local profile at: {profile_path}")
                print("Note: This local profile will remember your login session once you sign in once.")
                context = await p.chromium.launch_persistent_context(
                    user_data_dir=profile_path,
                    headless=False
                )
                page = context.pages[0] if context.pages else await context.new_page()
        
        # Navigate to FlowCV Resumes page if launched freshly
        if page and (not page.url or "about:blank" in page.url):
            print("Navigating to FlowCV...")
            await page.goto("https://flowcv.com/resumes")
        
        print("\n👉 ACTION REQUIRED:")
        print("1. Log in manually on the browser window.")
        print("2. Open your resume editor (e.g. click Edit content).")
        print("3. Ensure the text fields you want to edit are loaded in view.")
        print("4. Come back here and press Enter when ready.")
        
        # Wait for user input in terminal
        input("\nPress ENTER here once you have landed on the CV edit page...")
        
        print("\nScanning active resume fields from FlowCV...")
        fields = await get_editor_fields(page)
        
        if not fields:
            print("⚠️ No text fields detected on the page! Make sure you are in the editor.")
            print("Press Enter to scan again, or Ctrl+C to abort.")
            input("Scan again? Press Enter...")
            fields = await get_editor_fields(page)
            if not fields:
                print("Aborting. No text areas found.")
                if browser:
                    await browser.close()
                elif context:
                    await context.close()
                return

        print(f"Found {len(fields)} sections to review.\n")
        
        for field in fields:
            idx = field["index"]
            title = field["title"]
            comp = field["company"]
            orig_text = field["original_text"]
            
            comp_label = f" at {comp}" if comp else ""
            print("========================================================")
            print(f"📋 Reviewing: {title}{comp_label}")
            print("========================================================")
            print(f"Original Text:\n{orig_text}\n")
            
            print("Querying AI to tailor this section...")
            tailored_text = await tailor_section(orig_text, title, comp, jd_text)
            
            print(f"Suggested Tailored Text:\n{tailored_text}\n")
            print("--------------------------------------------------------")
            
            choice = input(f"👉 Apply this tailored text to FlowCV? [y/N]: ").strip().lower()
            if choice in ['y', 'yes']:
                print(f"Applying change to FlowCV...")
                success = await apply_changes_to_field(page, idx, tailored_text)
                if success:
                    print("✅ Successfully updated in browser!")
                else:
                    print("❌ Failed to update textarea in browser.")
            else:
                print("⏭️ Section skipped. Keeping original text.")
            print("\n")
            
        print("========================================================")
        print("🎉 FlowCV Tailoring Sync complete!")
        print("Review the browser, download your PDF, and press Enter to exit.")
        print("========================================================")
        input("Press ENTER to close the browser and complete the script...")
        if browser:
            await browser.close()
        elif context:
            await context.close()
