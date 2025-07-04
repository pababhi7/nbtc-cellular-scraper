import sys
import os
import json
import asyncio
from playwright.async_api import async_playwright

os.environ["PYTHONIOENCODING"] = "utf-8"

import requests

SEEN_FILE = "seen_devices.json"
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

async def try_direct_api_call():
    """Try direct API call first - sometimes it works"""
    print("Attempting direct API call...")
    try:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://mocheck.nbtc.go.th",
            "Referer": "https://mocheck.nbtc.go.th/search-equipments"
        }
        
        payload = {
            "status": "อนุญาต",
            "page": 1,
            "perPage": 20,
            "search": "",
            "subType": "Cellular Mobile"
        }
        
        response = requests.post(
            "https://mocheck.nbtc.go.th/api/equipments/search",
            json=payload,
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            devices = data.get("data", [])
            print(f"Direct API call successful! Found {len(devices)} devices")
            return [d for d in devices if d.get("subType") == "Cellular Mobile"]
        else:
            print(f"Direct API call failed: {response.status_code}")
            return []
    except Exception as e:
        print(f"Direct API call error: {e}")
        return []

async def fetch_devices_with_browser():
    """Browser automation approach"""
    devices = []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            
            print("Setting up browser with realistic settings...")
            await page.set_viewport_size({"width": 1920, "height": 1080})
            await page.set_extra_http_headers({
                "Accept-Language": "en-US,en;q=0.9,th;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
            })
            
            print("Navigating to NBTC website...")
            response = await page.goto("https://mocheck.nbtc.go.th/search-equipments", 
                                      wait_until="networkidle")
            print(f"Page loaded with status: {response.status}")
            
            # Wait for page to fully load
            await page.wait_for_timeout(5000)
            
            # Try to interact with the page to trigger data loading
            print("Looking for search elements...")
            
            # Try to find and click search/filter elements
            try:
                # Look for any search button or filter
                search_elements = await page.query_selector_all("button, input[type='submit'], .search-btn, .btn-search")
                if search_elements:
                    print(f"Found {len(search_elements)} search elements")
                    await search_elements[0].click()
                    await page.wait_for_timeout(3000)
            except Exception as e:
                print(f"Couldn't interact with search elements: {e}")
            
            # Capture any network requests
            collected_devices = []
            
            async def handle_response(response):
                if "equipment" in response.url and response.status == 200:
                    try:
                        if response.headers.get("content-type", "").startswith("application/json"):
                            data = await response.json()
                            if "data" in data and isinstance(data["data"], list):
                                cellular_devices = [d for d in data["data"] if d.get("subType") == "Cellular Mobile"]
                                collected_devices.extend(cellular_devices)
                                print(f"Found {len(cellular_devices)} Cellular Mobile devices from network request")
                    except Exception as e:
                        print(f"Error parsing network response: {e}")
            
            page.on("response", handle_response)
            
            # Wait for any additional requests
            await page.wait_for_timeout(8000)
            
            # Try to extract data from page HTML as backup
            if not collected_devices:
                print("No devices from network requests, trying HTML extraction...")
                page_content = await page.content()
                
                # Look for any device data in the HTML
                if "cellular" in page_content.lower() or "mobile" in page_content.lower():
                    print("Found mobile/cellular related content in HTML")
                    # You could add HTML parsing logic here
            
            await browser.close()
            return collected_devices
            
    except Exception as e:
        print(f"Browser automation error: {e}")
        return []

def load_seen_ids():
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                print(f"Loaded {len(data)} previously seen device IDs")
                return set(data)
        except Exception as e:
            print(f"Error loading seen IDs: {e}")
            return set()
    else:
        print("No seen_devices.json file found - this is the first run!")
        return set()

def save_seen_ids(ids):
    try:
        with open(SEEN_FILE, "w", encoding="utf-8") as f:
            json.dump(list(ids), f, ensure_ascii=False, indent=2)
        print(f"Saved {len(ids)} device IDs to {SEEN_FILE}")
    except Exception as e:
        print(f"Error saving seen IDs: {e}")

def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("ERROR: Telegram credentials not set.")
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "disable_web_page_preview": True
    }
    try:
        resp = requests.post(url, data=payload, timeout=15)
        if resp.status_code == 200:
            print("SUCCESS: Telegram notification sent!")
        else:
            print(f"Telegram API error: {resp.status_code}")
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")

async def main():
    print("=== STARTING NBTC DEVICE SCRAPER ===")
    
    seen_ids = load_seen_ids()
    new_ids = set()
    new_devices = []

    # Try multiple approaches to get data
    print("Trying multiple data collection methods...")
    
    # Method 1: Direct API call
    devices = await try_direct_api_call()
    
    # Method 2: Browser automation (if direct API failed)
    if not devices:
        print("Direct API failed, trying browser automation...")
        devices = await fetch_devices_with_browser()
    
    print(f"Total devices retrieved: {len(devices)}")
    
    # Process devices
    for device in devices:
        device_id = device.get("id") or device.get("certificate_no")
        if device_id and device_id not in seen_ids:
            new_devices.append(device)
            new_ids.add(device_id)
            print(f"NEW DEVICE: {device.get('brand')} {device.get('model')}")

    print(f"New devices found: {len(new_devices)}")
    
    if new_devices:
        with open("new_devices.json", "w", encoding="utf-8") as f:
            json.dump(new_devices, f, ensure_ascii=False, indent=2)
        
        msg = f"📱 {len(new_devices)} new Cellular Mobile devices found!\n\n"
        for i, d in enumerate(new_devices[:5]):
            brand = d.get('brand', 'Unknown')
            model = d.get('model', 'Unknown')
            cert = d.get('certificate_no', 'Unknown')
            device_id = d.get('id', '')
            link = f"https://mocheck.nbtc.go.th/equipment-detail/{device_id}" if device_id else "No link"
            msg += f"{i+1}. Brand: {brand}\nModel: {model}\nCert: {cert}\nLink: {link}\n\n"
        
        if len(new_devices) > 5:
            msg += f"...and {len(new_devices)-5} more devices."
        
        send_telegram_message(msg)
    else:
        print("No new devices found this run.")

    # Update seen IDs
    all_ids = seen_ids.union(new_ids)
    save_seen_ids(all_ids)
    print("=== SCRAPING COMPLETED ===")

if __name__ == "__main__":
    asyncio.run(main())
