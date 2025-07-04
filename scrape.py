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
            
            # Set user agent to look more like a real browser
            await page.set_extra_http_headers({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            })
            
            print("Navigating to NBTC website...")
            await page.goto("https://mocheck.nbtc.go.th/search-equipments?status=%E0%B8%AD%E0%B8%99%E0%B8%B8%E0%B8%8D%E0%B8%B2%E0%B8%95")
            await page.wait_for_timeout(5000)  # Wait 5 seconds for page to load
            
            # Try to capture network requests
            collected_devices = []
            
            async def handle_response(response):
                if "api/equipments/search" in response.url and response.status == 200:
                    try:
                        data = await response.json()
                        if "data" in data and isinstance(data["data"], list):
                            for device in data["data"]:
                                if device.get("subType") == "Cellular Mobile":
                                    collected_devices.append(device)
                            print(f"Found {len(data['data'])} devices, {len([d for d in data['data'] if d.get('subType') == 'Cellular Mobile'])} are Cellular Mobile")
                    except Exception as e:
                        print(f"Error parsing response: {e}")
            
            page.on("response", handle_response)
            
            # Wait a bit more for API calls to complete
            await page.wait_for_timeout(5000)
            
            # If no devices found via network interception, try to extract from page
            if not collected_devices:
                print("No devices found via network interception, trying page content...")
                # You could add page scraping logic here if needed
            
            await browser.close()
            return collected_devices
            
    except Exception as e:
        print(f"Browser automation error: {e}")
        return []

def load_seen_ids():
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception as e:
            print(f"Error loading seen IDs: {e}")
            return set()
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
        print("Telegram credentials not set. Skipping notification.")
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
            print("Telegram notification sent successfully!")
        else:
            print(f"Failed to send Telegram message. Status: {resp.status_code}")
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")

async def main():
    print("Starting NBTC device scraper...")
    seen_ids = load_seen_ids()
    new_ids = set()
    new_devices = []

    try:
        devices = await fetch_devices_with_browser()
        print(f"Total devices retrieved: {len(devices)}")
        
        for device in devices:
            device_id = device.get("id") or device.get("certificate_no")
            if device_id and device_id not in seen_ids:
                new_devices.append(device)
                new_ids.add(device_id)
                
    except Exception as e:
        print(f"Error during scraping: {e}")

    if new_devices:
        print(f"Found {len(new_devices)} new Cellular Mobile devices!")
        
        # Save new devices to file
        with open("new_devices.json", "w", encoding="utf-8") as f:
            json.dump(new_devices, f, ensure_ascii=False, indent=2)
        
        # Build Telegram message
        msg = f"📱 {len(new_devices)} new Cellular Mobile devices found!\n\n"
        for i, d in enumerate(new_devices[:5]):  # Show up to 5 devices
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
        print("No new Cellular Mobile devices found.")

    # Update seen IDs
    all_ids = seen_ids.union(new_ids)
    save_seen_ids(all_ids)
    print("Scraping completed!")

if __name__ == "__main__":
    asyncio.run(main())
