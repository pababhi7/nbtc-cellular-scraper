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

async def fetch_devices_with_browser():
    devices = []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            
            print("Setting up browser...")
            await page.set_extra_http_headers({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            })
            
            print("Navigating to NBTC website...")
            await page.goto("https://mocheck.nbtc.go.th/search-equipments?status=%E0%B8%AD%E0%B8%99%E0%B8%B8%E0%B8%8D%E0%B8%B2%E0%B8%95")
            print("Page loaded, waiting for content...")
            await page.wait_for_timeout(5000)
            
            collected_devices = []
            
            async def handle_response(response):
                print(f"Response intercepted: {response.url} - Status: {response.status}")
                if "api/equipments/search" in response.url and response.status == 200:
                    try:
                        data = await response.json()
                        print(f"API response received with {len(data.get('data', []))} total devices")
                        if "data" in data and isinstance(data["data"], list):
                            cellular_count = 0
                            for device in data["data"]:
                                if device.get("subType") == "Cellular Mobile":
                                    collected_devices.append(device)
                                    cellular_count += 1
                            print(f"Found {cellular_count} Cellular Mobile devices out of {len(data['data'])} total")
                    except Exception as e:
                        print(f"Error parsing response: {e}")
            
            page.on("response", handle_response)
            
            print("Waiting for API calls...")
            await page.wait_for_timeout(10000)
            
            await browser.close()
            print(f"Browser closed. Total collected devices: {len(collected_devices)}")
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
    print(f"Telegram Bot Token exists: {'Yes' if TELEGRAM_BOT_TOKEN else 'No'}")
    print(f"Telegram Chat ID exists: {'Yes' if TELEGRAM_CHAT_ID else 'No'}")
    
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("ERROR: Telegram credentials not set. Skipping notification.")
        return
    
    print(f"Sending message to chat ID: {TELEGRAM_CHAT_ID}")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "disable_web_page_preview": True
    }
    try:
        resp = requests.post(url, data=payload, timeout=15)
        print(f"Telegram API response: Status {resp.status_code}")
        if resp.status_code == 200:
            print("SUCCESS: Telegram notification sent!")
        else:
            print(f"ERROR: Telegram API failed. Response: {resp.text}")
    except Exception as e:
        print(f"ERROR: Failed to send Telegram message: {e}")

async def main():
    print("=== STARTING NBTC DEVICE SCRAPER ===")
    
    seen_ids = load_seen_ids()
    is_first_run = len(seen_ids) == 0
    new_ids = set()
    new_devices = []

    try:
        devices = await fetch_devices_with_browser()
        print(f"=== SCRAPING RESULTS ===")
        print(f"Total devices retrieved: {len(devices)}")
        
        for device in devices:
            device_id = device.get("id") or device.get("certificate_no")
            if device_id and device_id not in seen_ids:
                new_devices.append(device)
                new_ids.add(device_id)
                print(f"NEW DEVICE FOUND: {device.get('brand')} {device.get('model')}")
                
    except Exception as e:
        print(f"ERROR during scraping: {e}")

    print(f"=== FINAL RESULTS ===")
    print(f"Is first run: {is_first_run}")
    print(f"New devices found: {len(new_devices)}")
    
    # ALWAYS send notification on first run
    if is_first_run:
        print("🚨 FIRST RUN - Sending setup notification...")
        if new_devices:
            # First run with new devices
            msg = f"🎉 NBTC Scraper Setup Complete!\n\n"
            msg += f"✅ Successfully found {len(new_devices)} devices on first scan\n"
            msg += f"📱 {len([d for d in new_devices if d.get('subType') == 'Cellular Mobile'])} Cellular Mobile devices\n\n"
            msg += f"🤖 Scraper is now monitoring for new devices daily at 7 AM IST\n\n"
            
            # Show first 3 devices as examples
            msg += f"Sample devices found:\n"
            for i, d in enumerate(new_devices[:3]):
                brand = d.get('brand', 'Unknown')
                model = d.get('model', 'Unknown')
                msg += f"{i+1}. {brand} {model}\n"
            
            if len(new_devices) > 3:
                msg += f"...and {len(new_devices)-3} more"
        else:
            # First run with no devices (likely scraping failed)
            msg = f"🤖 NBTC Scraper Setup Complete!\n\n"
            msg += f"⚠️ No devices found on first scan\n"
            msg += f"This might mean:\n"
            msg += f"• The website is blocking our requests\n"
            msg += f"• Network connectivity issues\n"
            msg += f"• The API structure changed\n\n"
            msg += f"📅 Will try again tomorrow at 7 AM IST"
        
        send_telegram_message(msg)
        
        # Save the devices even if empty (marks first run as complete)
        with open("new_devices.json", "w", encoding="utf-8") as f:
            json.dump(new_devices, f, ensure_ascii=False, indent=2)
            
    elif new_devices:
        # Regular run with new devices
        print(f"Saving {len(new_devices)} new devices to file...")
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
        # Regular run with no new devices
        print("No new Cellular Mobile devices found.")

    # Update seen IDs (this will mark first run as complete)
    all_ids = seen_ids.union(new_ids)
    save_seen_ids(all_ids)
    print("=== SCRAPING COMPLETED ===")

if __name__ == "__main__":
    asyncio.run(main())
