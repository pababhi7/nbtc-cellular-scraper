import sys
import os
import json
import asyncio
from playwright.async_api import async_playwright

os.environ["PYTHONIOENCODING"] = "utf-8"

import requests

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

async def test_enhanced_browser():
    """Enhanced browser scraping with Cloudflare bypass"""
    print("=== ENHANCED BROWSER SCRAPING ===")
    
    try:
        async with async_playwright() as p:
            # Use chromium with stealth mode
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor'
                ]
            )
            
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            page = await context.new_page()
            
            # Hide automation indicators
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            """)
            
            collected_devices = []
            api_calls_made = []
            
            # Monitor ALL network requests
            async def handle_response(response):
                url = response.url
                status = response.status
                print(f"Network: {url} - {status}")
                
                # Capture any API calls
                if "api" in url or "search" in url or "equipment" in url:
                    api_calls_made.append(f"{url} - {status}")
                    
                    if status == 200 and "equipment" in url:
                        try:
                            content_type = response.headers.get("content-type", "")
                            if "application/json" in content_type:
                                data = await response.json()
                                print(f"API Response: {data}")
                                if "data" in data and isinstance(data["data"], list):
                                    collected_devices.extend(data["data"])
                                    print(f"Collected {len(data['data'])} devices from {url}")
                        except Exception as e:
                            print(f"Error parsing {url}: {e}")
            
            page.on("response", handle_response)
            
            print("Navigating to NBTC website...")
            response = await page.goto("https://mocheck.nbtc.go.th/search-equipments", 
                                      wait_until="domcontentloaded", timeout=60000)
            print(f"Initial page load: {response.status}")
            
            # Wait for Cloudflare challenge to complete
            print("Waiting for Cloudflare challenge...")
            await page.wait_for_timeout(10000)
            
            # Check if we're still on a challenge page
            title = await page.title()
            print(f"Page title: {title}")
            
            if "Just a moment" in title or "Please wait" in title:
                print("Still on Cloudflare challenge, waiting longer...")
                await page.wait_for_timeout(15000)
            
            # Try to find and interact with search elements
            print("Looking for search interface...")
            
            try:
                # Wait for page to be fully loaded
                await page.wait_for_load_state("networkidle", timeout=30000)
                
                # Look for search/filter forms
                search_forms = await page.query_selector_all("form, .search-form, .filter-form")
                print(f"Found {len(search_forms)} forms")
                
                # Look for specific search buttons
                search_buttons = await page.query_selector_all(
                    "button:has-text('ค้นหา'), button:has-text('Search'), input[type='submit'], .btn-search, .search-btn"
                )
                print(f"Found {len(search_buttons)} search buttons")
                
                # Try to click a search button
                if search_buttons:
                    print("Clicking search button...")
                    await search_buttons[0].click()
                    await page.wait_for_timeout(5000)
                
                # Look for any dropdowns or selects
                selects = await page.query_selector_all("select, .dropdown, .filter-select")
                print(f"Found {len(selects)} select elements")
                
                # Try to trigger data loading by scrolling
                print("Scrolling to trigger data loading...")
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(3000)
                await page.evaluate("window.scrollTo(0, 0)")
                await page.wait_for_timeout(3000)
                
            except Exception as e:
                print(f"Error interacting with page: {e}")
            
            # Final wait for any delayed API calls
            print("Final wait for API calls...")
            await page.wait_for_timeout(10000)
            
            print(f"API calls detected: {api_calls_made}")
            
            await browser.close()
            return collected_devices
    
    except Exception as e:
        print(f"Enhanced browser error: {e}")
        return []

async def test_direct_requests_with_session():
    """Try direct requests with session and cookies"""
    print("\n=== TESTING WITH SESSION ===")
    
    try:
        session = requests.Session()
        
        # First, get the main page to establish session
        print("Getting main page for session...")
        main_page = session.get(
            "https://mocheck.nbtc.go.th/search-equipments",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            },
            timeout=30
        )
        print(f"Main page status: {main_page.status_code}")
        
        # Extract any tokens or cookies
        cookies = session.cookies
        print(f"Received {len(cookies)} cookies")
        
        # Now try the API call with the session
        api_response = session.post(
            "https://mocheck.nbtc.go.th/api/equipments/search",
            json={
                "status": "อนุญาต",
                "page": 1,
                "perPage": 5,
                "search": ""
            },
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://mocheck.nbtc.go.th/search-equipments"
            },
            timeout=30
        )
        
        print(f"API call status: {api_response.status_code}")
        if api_response.status_code == 200:
            data = api_response.json()
            devices = data.get("data", [])
            print(f"Found {len(devices)} devices via session!")
            return devices[:5]
        else:
            print(f"Session API failed: {api_response.text[:200]}")
            
    except Exception as e:
        print(f"Session approach error: {e}")
    
    return []

def send_test_results(devices, method=""):
    """Send test results via Telegram"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("No Telegram credentials - skipping notification")
        return
    
    if devices:
        msg = f"🎉 SUCCESS! Found {len(devices)} devices!\n"
        msg += f"Method: {method}\n\n"
        for i, device in enumerate(devices):
            brand = device.get('brand', 'Unknown')
            model = device.get('model', 'Unknown')
            subtype = device.get('subType', 'Unknown')
            cert = device.get('certificate_no', 'Unknown')
            msg += f"{i+1}. {brand} {model}\n   Type: {subtype}\n   Cert: {cert}\n\n"
        msg += "✅ Real data collection is working!\n🚀 Your daily scraper will now find new devices!"
    else:
        msg = f"🧪 TEST RESULTS: No devices found\n"
        msg += f"Method tested: {method}\n\n"
        msg += f"❌ Cloudflare protection is blocking access\n\n"
        msg += f"📅 Will keep trying daily at 7 AM IST\n"
        msg += f"💡 Consider alternative approaches or manual checking"
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "disable_web_page_preview": True
    }
    
    try:
        resp = requests.post(url, data=payload, timeout=15)
        if resp.status_code == 200:
            print("Test results sent to Telegram!")
        else:
            print(f"Telegram failed: {resp.status_code}")
    except Exception as e:
        print(f"Telegram error: {e}")

async def main():
    print("=== ENHANCED NBTC SCRAPER TEST ===")
    print("Testing enhanced methods to bypass Cloudflare...\n")
    
    devices = []
    method_used = ""
    
    # Method 1: Enhanced browser with Cloudflare bypass
    devices = await test_enhanced_browser()
    if devices:
        method_used = "Enhanced Browser"
    
    # Method 2: Session-based requests (if browser failed)
    if not devices:
        devices = await test_direct_requests_with_session()
        if devices:
            method_used = "Session-based Requests"
    
    print(f"\n=== FINAL RESULTS ===")
    print(f"Total devices found: {len(devices)}")
    print(f"Method that worked: {method_used or 'None'}")
    
    if devices:
        print("SUCCESS! Here are the devices:")
        for i, device in enumerate(devices):
            print(f"{i+1}. {device.get('brand')} {device.get('model')} - {device.get('subType')}")
    else:
        print("No devices found - Cloudflare protection is very strong")
    
    # Send results via Telegram
    send_test_results(devices, method_used or "All methods failed")

if __name__ == "__main__":
    asyncio.run(main())
