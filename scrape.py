import sys
import os
import json
import asyncio
from playwright.async_api import async_playwright
import re

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
            
            # Wait longer for the page to fully load
            await page.wait_for_timeout(10000)
            
            # Try to extract device data from the HTML
            print("Attempting to extract devices from page content...")
            
            # Wait for any device listings to appear
            try:
                await page.wait_for_selector(".equipment-card, .device-item, .equipment-row", timeout=5000)
                print("Found device elements on page")
            except:
                print("No specific device elements found, trying generic extraction...")
            
            # Get page content
            content = await page.content()
            print(f"Page content length: {len(content)} characters")
            
            # Try to find JSON data in the page
            json_matches = re.findall(r'("data":\s*\[.*?\])', content)
            print(f"Found {len(json_matches)} potential JSON data blocks")
            
            for match in json_matches:
                try:
                    # Try to extract device data from JSON blocks
                    json_data = json.loads("{" + match + "}")
                    if "data" in json_data:
                        print(f"Found JSON data with {len(json_data['data'])} items")
                        for item in json_data["data"]:
                            if isinstance(item, dict) and item.get("subType") == "Cellular Mobile":
                                devices.append(item)
                except:
                    continue
            
            # Alternative: Look for device information in script tags
            script_content = await page.evaluate("""
                () => {
                    const scripts = document.querySelectorAll('script');
                    let allContent = '';
                    for (let script of scripts) {
                        if (script.textContent && script.textContent.includes('equipment')) {
                            allContent += script.textContent;
                        }
                    }
                    return allContent;
                }
            """)
            
            print(f"Script content length: {len(script_content)} characters")
            if "equipment" in script_content.lower():
                print("Found equipment-related content in scripts")
            
            await browser.close()
            print(f"Browser closed. Total collected devices: {len(devices)}")
            return devices
            
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
        print("ERROR: Telegram credentials not set. Skipping notification.")
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
            print(f"ERROR: Telegram API failed. Response: {resp.text}")
    except Exception as e:
        print(f"ERROR: Failed to send Telegram message: {e}")

async def main():
    print("=== STARTING NBTC DEVICE SCRAPER ===")
    
    seen_ids = load_seen_ids()
    is_first_run = len(seen_ids) == 0
    new_ids = set()
    new_devices = []

    # Add some test devices if this is a debugging run
    if is_first_run:
        print("First run detected - adding test data to verify system works...")
        test_devices = [
            {
                "id": "test_001",
                "brand": "TEST_BRAND",
                "model": "TEST_MODEL",
                "subType": "Cellular Mobile",
                "certificate_no": "TEST_CERT_001"
            }
        ]
        
        # Add test devices to simulate finding new devices
        for device in test_devices:
            device_id = device.get("id")
            if device_id and device_id not in seen_ids:
                new_devices.append(device)
                new_ids.add(device_id)

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
    
    # Send notification logic
    if new_devices:
        print(f"Saving {len(new_devices)} new devices to file...")
        with open("new_devices.json", "w", encoding="utf-8") as f:
            json.dump(new_devices, f, ensure_ascii=False, indent=2)
        
        msg = f"📱 {len(new_devices)} new Cellular Mobile devices found!\n\n"
        for i, d in enumerate(new_devices[:5]):
            brand = d.get('brand', 'Unknown')
            model = d.get('model', 'Unknown')
            cert = d.get('certificate_no', 'Unknown')
            device_id = d.get('id', '')
            if brand == "TEST_BRAND":
                msg += f"{i+1}. 🧪 TEST: System working! (This is test data)\n\n"
            else:
                link = f"https://mocheck.nbtc.go.th/equipment-detail/{device_id}" if device_id else "No link"
                msg += f"{i+1}. Brand: {brand}\nModel: {model}\nCert: {cert}\nLink: {link}\n\n"
        
        if len(new_devices) > 5:
            msg += f"...and {len(new_devices)-5} more devices."
        
        send_telegram_message(msg)
    else:
        print("No new devices found.")

    # Update seen IDs
    all_ids = seen_ids.union(new_ids)
    save_seen_ids(all_ids)
    print("=== SCRAPING COMPLETED ===")

if __name__ == "__main__":
    asyncio.run(main())
