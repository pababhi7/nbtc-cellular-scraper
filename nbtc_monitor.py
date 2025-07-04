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

def parse_devices_from_text(text):
    """
    Parse all likely cellular device lines from NBTC page text.
    This will match any line that looks like a device model, regardless of brand.
    """
    devices = []
    found_ids = set()
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if not line or len(line) < 5:
            continue
        # Match lines with a model code and "Mobile" or "Cellular" or Thai keywords
        m = re.match(
            r"^(.*?)([A-Z]{1,5}\d{3,}[A-Z0-9\-]*)\s*(.*?)(Mobile|Cellular|โทรศัพท์|สมาร์ทโฟน|Smartphone)?(.*)$",
            line, re.IGNORECASE)
        if m:
            before, model_code, between, device_type, after = m.groups()
            if model_code and len(model_code) >= 4 and model_code not in found_ids:
                # Try to guess brand from before/between/after
                brand_guess = ""
                for part in [before, between, after]:
                    if part:
                        word = part.strip().split()[0]
                        if word and word.isalpha() and len(word) > 2:
                            brand_guess = word
                            break
                if not brand_guess:
                    brand_guess = "Unknown"
                devices.append({
                    "id": model_code,
                    "brand": brand_guess,
                    "model": model_code,
                    "description": line,
                    "subType": "Cellular Mobile",
                    "certificate_no": model_code
                })
                found_ids.add(model_code)
    return devices

async def extract_all_devices_with_pagination():
    """Extract all devices by paginating through the NBTC site, with debug output."""
    print("=== EXTRACTING ALL DEVICES WITH PAGINATION (DEBUG MODE) ===")
    all_devices = []
    seen_ids = set()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
        page = await browser.new_page()
        await page.goto("https://mocheck.nbtc.go.th/search-equipments?status=อนุญาต", wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(15000)  # Wait longer for JS to load
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(2000)
        page_num = 1
        while True:
            print(f"Scraping page {page_num}...")
            page_text = await page.evaluate("document.body.innerText")
            page_html = await page.content()
            print("=== PAGE TEXT SAMPLE ===")
            print(page_text[:2000])
            print("=== PAGE HTML SAMPLE ===")
            print(page_html[:2000])
            devices = parse_devices_from_text(page_text)
            new_this_page = 0
            for d in devices:
                if d['id'] not in seen_ids:
                    all_devices.append(d)
                    seen_ids.add(d['id'])
                    new_this_page += 1
            print(f"Found {new_this_page} new devices on page {page_num}")
            # Try to click "Next" or "ถัดไป"
            next_button = await page.query_selector("button:has-text('ถัดไป'), button:has-text('Next'), .pagination-next")
            if next_button:
                try:
                    await next_button.click()
                    await page.wait_for_timeout(3000)
                    page_num += 1
                except Exception as e:
                    print(f"Could not click next: {e}")
                    break
            else:
                break
        await browser.close()
    print(f"Total unique devices scraped: {len(all_devices)}")
    return all_devices

def load_seen_devices():
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                print(f"Loaded {len(data)} previously seen device IDs")
                return set(data)
        except Exception as e:
            print(f"Error loading seen devices: {e}")
            return set()
    else:
        print("No seen_devices.json file found - this is the first run!")
        return set()

def save_seen_devices(device_ids):
    try:
        with open(SEEN_FILE, "w", encoding="utf-8") as f:
            json.dump(list(device_ids), f, ensure_ascii=False, indent=2)
        print(f"Saved {len(device_ids)} device IDs to {SEEN_FILE}")
    except Exception as e:
        print(f"Error saving seen devices: {e}")

def find_new_devices(current_devices, seen_device_ids):
    new_devices = []
    for device in current_devices:
        device_id = device.get("id")
        if device_id and device_id not in seen_device_ids:
            new_devices.append(device)
            print(f"NEW DEVICE FOUND: {device['brand']} {device['model']}")
    print(f"Found {len(new_devices)} NEW devices out of {len(current_devices)} total")
    return new_devices

def send_new_device_notification(new_devices, is_first_run=False):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("ERROR: Telegram credentials not set.")
        return
    if is_first_run:
        msg = f"🎉 <b>NBTC Monitor Setup Complete!</b>\n\n"
        msg += f"✅ Found {len(new_devices)} devices on first scan\n"
        msg += f"📅 Now monitoring for NEW devices daily at 7 AM IST\n\n"
        msg += f"Sample devices found:\n"
        for i, d in enumerate(new_devices[:3]):
            msg += f"{i+1}. {d['brand']} {d['model']}\n"
        msg += f"\n🚀 You'll only get notified about NEW devices from now on!"
    elif new_devices:
        msg = f"📱 <b>{len(new_devices)} NEW Cellular Mobile devices found!</b>\n\n"
        for i, device in enumerate(new_devices[:5]):
            brand = device.get('brand', 'Unknown')
            model = device.get('model', 'Unknown')
            desc = device.get('description', '')
            msg += f"{i+1}. <b>{brand} {model}</b>\n"
            if desc and desc != model:
                msg += f"   📝 {desc}\n"
            msg += f"   🔍 Model: <code>{model}</code>\n\n"
        if len(new_devices) > 5:
            msg += f"...and {len(new_devices)-5} more devices!\n\n"
        msg += f"🎉 <b>These devices are newly approved by NBTC!</b>\n"
        msg += f"🔗 Search them at: <a href='https://mocheck.nbtc.go.th/search-equipments'>NBTC Search</a>"
    else:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        resp = requests.post(url, data=payload, timeout=15)
        if resp.status_code == 200:
            print("✅ Notification sent!")
        else:
            print(f"❌ Telegram failed: {resp.status_code}")
    except Exception as e:
        print(f"❌ Failed to send notification: {e}")

async def main():
    print("=== NBTC NEW DEVICE MONITOR (PAGINATION, DEBUG MODE) ===")
    seen_device_ids = load_seen_devices()
    is_first_run = len(seen_device_ids) == 0
    current_devices = await extract_all_devices_with_pagination()
    if not current_devices:
        print("❌ No devices extracted - website might be blocking or structure changed")
        return
    new_devices = find_new_devices(current_devices, seen_device_ids)
    if is_first_run or new_devices:
        send_new_device_notification(new_devices, is_first_run=is_first_run)
        with open("new_devices.json", "w", encoding="utf-8") as f:
            json.dump(new_devices, f, ensure_ascii=False, indent=2)
    else:
        print("✅ No new devices found - no notification sent")
    all_current_ids = {device.get("id") for device in current_devices if device.get("id")}
    updated_seen_ids = seen_device_ids.union(all_current_ids)
    save_seen_devices(updated_seen_ids)
    print(f"\n=== SUMMARY ===")
    print(f"Total devices found: {len(current_devices)}")
    print(f"New devices: {len(new_devices)}")
    print(f"Previously seen: {len(seen_device_ids)}")
    print(f"Updated seen list: {len(updated_seen_ids)}")
    print("=== MONITORING COMPLETED ===")

if __name__ == "__main__":
    asyncio.run(main())
