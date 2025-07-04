import sys
import os
import json
import asyncio
from playwright.async_api import async_playwright

os.environ["PYTHONIOENCODING"] = "utf-8"

import requests

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

async def test_direct_api():
    """Test direct API call with different approaches"""
    print("=== TESTING DIRECT API CALLS ===")
    
    approaches = [
        # Approach 1: Original
        {
            "name": "Original API call",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
            "payload": {
                "status": "อนุญาต",
                "page": 1,
                "perPage": 5,
                "search": "",
                "subType": "Cellular Mobile"
            }
        },
        # Approach 2: Without subType filter
        {
            "name": "Without subType filter",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
            "payload": {
                "status": "อนุญาต",
                "page": 1,
                "perPage": 5,
                "search": ""
            }
        },
        # Approach 3: Different User-Agent
        {
            "name": "Different User-Agent",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15"
            },
            "payload": {
                "status": "อนุญาต",
                "page": 1,
                "perPage": 5,
                "search": ""
            }
        }
    ]
    
    for approach in approaches:
        print(f"\nTrying: {approach['name']}")
        try:
            response = requests.post(
                "https://mocheck.nbtc.go.th/api/equipments/search",
                json=approach["payload"],
                headers=approach["headers"],
                timeout=30
            )
            
            print(f"Status Code: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                devices = data.get("data", [])
                print(f"SUCCESS! Found {len(devices)} devices")
                
                # Show first 5 devices
                for i, device in enumerate(devices[:5]):
                    print(f"  {i+1}. {device.get('brand', 'Unknown')} - {device.get('model', 'Unknown')} - {device.get('subType', 'Unknown')}")
                
                return devices[:5]  # Return first 5 for testing
            else:
                print(f"Failed: {response.status_code} - {response.text[:200]}")
        except Exception as e:
            print(f"Error: {e}")
    
    return []

async def test_browser_scraping():
    """Test browser-based scraping"""
    print("\n=== TESTING BROWSER SCRAPING ===")
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            
            print("Setting up browser...")
            await page.set_extra_http_headers({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate"
            })
            
            collected_devices = []
            
            # Monitor network requests
            async def handle_response(response):
                print(f"Network: {response.url} - {response.status}")
                if response.status == 200 and "equipment" in response.url:
                    try:
                        if "application/json" in response.headers.get("content-type", ""):
                            data = await response.json()
                            if "data" in data:
                                collected_devices.extend(data["data"][:5])
                                print(f"Found {len(data['data'])} devices via network interception")
                    except:
                        pass
            
            page.on("response", handle_response)
            
            print("Navigating to website...")
            await page.goto("https://mocheck.nbtc.go.th/search-equipments", wait_until="networkidle")
            
            print("Waiting for page to load...")
            await page.wait_for_timeout(8000)
            
            # Try to trigger search
            try:
                # Look for search or submit buttons
                buttons = await page.query_selector_all("button, input[type='submit']")
                if buttons:
                    print(f"Found {len(buttons)} buttons, trying to click...")
                    await buttons[0].click()
                    await page.wait_for_timeout(3000)
            except:
                pass
            
            await browser.close()
            return collected_devices[:5]
    
    except Exception as e:
        print(f"Browser error: {e}")
        return []

def send_test_results(devices):
    """Send test results via Telegram"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("No Telegram credentials - skipping notification")
        return
    
    if devices:
        msg = f"🧪 TEST RESULTS: Found {len(devices)} devices!\n\n"
        for i, device in enumerate(devices):
            brand = device.get('brand', 'Unknown')
            model = device.get('model', 'Unknown')
            subtype = device.get('subType', 'Unknown')
            cert = device.get('certificate_no', 'Unknown')
            msg += f"{i+1}. {brand} {model}\n   Type: {subtype}\n   Cert: {cert}\n\n"
        msg += "✅ Real data retrieval is working!"
    else:
        msg = "🧪 TEST RESULTS: No devices found\n\n❌ Website is still blocking our requests\n\nWill keep trying daily at 7 AM IST"
    
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
    print("=== NBTC SCRAPER TEST ===")
    print("Testing if we can get ANY real device data...\n")
    
    # Try direct API first
    devices = await test_direct_api()
    
    # If that fails, try browser scraping
    if not devices:
        devices = await test_browser_scraping()
    
    print(f"\n=== FINAL RESULTS ===")
    print(f"Total devices found: {len(devices)}")
    
    if devices:
        print("SUCCESS! Here are the devices:")
        for i, device in enumerate(devices):
            print(f"{i+1}. {device.get('brand')} {device.get('model')} - {device.get('subType')}")
    else:
        print("No devices found - website is blocking requests")
    
    # Send results via Telegram
    send_test_results(devices)

if __name__ == "__main__":
    asyncio.run(main())
