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
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        # Navigate to the search page
        await page.goto("https://mocheck.nbtc.go.th/search-equipments?status=%E0%B8%AD%E0%B8%99%E0%B8%B8%E0%B8%8D%E0%B8%B2%E0%B8%95")
        await page.wait_for_timeout(3000)  # Wait 3 seconds
        
        # Intercept API calls
        devices = []
        
        async def handle_response(response):
            if "api/equipments/search" in response.url:
                try:
                    data = await response.json()
                    if "data" in data:
                        devices.extend(data["data"])
                except:
                    pass
        
        page.on("response", handle_response)
        
        # Trigger the search by interacting with the page
        await page.wait_for_timeout(5000)  # Wait for data to load
        
        await browser.close()
        return devices

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
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        resp = requests.post(url, data=payload, timeout=15)
        if resp.status_code != 200:
            print(f"Failed to send Telegram message. Status: {resp.status_code}")
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")

async def main():
    seen_ids = load_seen_ids()
    new_ids = set()
    new_devices = []

    try:
        devices = await fetch_devices_with_browser()
        print(f"Found {len(devices)} total devices")
        
        for device in devices:
            # Filter for Cellular Mobile devices
            if device.get("subType") == "Cellular Mobile":
                device_id = device.get("id") or device.get("certificate_no")
                if device_id and device_id not in seen_ids:
                    new_devices.append(device)
                    new_ids.add(device_id)
    except Exception as e:
        print(f"Error fetching devices: {e}")
        sys.exit(1)

    if new_devices:
        print(f"Found {len(new_devices)} new devices in Cellular Mobile:")
        with open("new_devices.json", "w", encoding="utf-8") as f:
            json.dump(new_devices, f, ensure_ascii=False, indent=2)
        
        msg = f"📱 {len(new_devices)} new Cellular Mobile devices found!\n"
        for d in new_devices[:5]:
            brand = d.get('brand', '')
            model = d.get('model', '')
            cert = d.get('certificate_no', '')
            device_id = d.get('id', '')
            link = f"https://mocheck.nbtc.go.th/equipment-detail/{device_id}"
            msg += f"\nBrand: {brand}\nModel: {model}\nCert No: {cert}\nLink: {link}\n"
        if len(new_devices) > 5:
            msg += f"\n...and {len(new_devices)-5} more."
        send_telegram_message(msg)
    else:
        print("No new devices found in Cellular Mobile.")

    all_ids = seen_ids.union(new_ids)
    save_seen_ids(all_ids)

if __name__ == "__main__":
    asyncio.run(main())
