import sys
import os
import json
import asyncio
from playwright.async_api import async_playwright
import re
from datetime import datetime

os.environ["PYTHONIOENCODING"] = "utf-8"

import requests

SEEN_FILE = "seen_devices.json"
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

class NBTCMonitor:
    def __init__(self):
        self.devices = []
        self.new_devices = []
        self.seen_devices = set()
        
    async def method_1_direct_api(self):
        """Fetch all cellular devices using paginated API, all statuses."""
        print("🚀 Method 1: API with pagination (all statuses)...")
        endpoint = "https://mocheck.nbtc.go.th/api/equipments/search"
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://mocheck.nbtc.go.th",
            "Referer": "https://mocheck.nbtc.go.th/search-equipments"
        }
        all_devices = []
        page = 1
        per_page = 50
        while True:
            # status: "" means all statuses (approved, testing, etc)
            payload = {"status": "", "page": page, "perPage": per_page, "search": "", "subType": "Cellular Mobile"}
            try:
                response = requests.post(endpoint, json=payload, headers=headers, timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    if "data" in data and data["data"]:
                        devices = [d for d in data["data"] if self.is_cellular_device(d)]
                        all_devices.extend(devices)
                        print(f"  - Page {page}: {len(devices)} devices")
                        if len(data["data"]) < per_page:
                            break  # Last page
                        page += 1
                    else:
                        break
                else:
                    break
            except Exception as e:
                print(f"❌ API error: {e}")
                break
        print(f"✅ API Success: Found {len(all_devices)} devices")
        return all_devices
    
    async def method_2_optimized_browser(self):
        """Fallback: Scrape using browser automation."""
        print("🌐 Method 2: Browser scraping...")
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
                context = await browser.new_context(
                    viewport={'width': 1366, 'height': 768},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                )
                page = await context.new_page()
                await page.goto("https://mocheck.nbtc.go.th/search-equipments", wait_until="domcontentloaded", timeout=45000)
                await page.wait_for_timeout(10000)
                page_text = await page.evaluate("document.body.innerText")
                await browser.close()
                devices = self.parse_devices_from_text(page_text)
                if devices:
                    print(f"✅ Browser Text: Found {len(devices)} devices")
                    return devices
        except Exception as e:
            print(f"❌ Browser method failed: {e}")
        return []
    
    async def method_3_mobile_endpoint(self):
        """Fallback: Try mobile/lite endpoints."""
        print("📱 Method 3: Mobile endpoints...")
        mobile_urls = [
            "https://mocheck.nbtc.go.th/m/search",
            "https://mocheck.nbtc.go.th/mobile/equipments",
            "https://mocheck.nbtc.go.th/lite/search",
            "https://m.mocheck.nbtc.go.th/search"
        ]
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15",
            "Accept": "application/json, text/html, */*"
        }
        for url in mobile_urls:
            try:
                response = requests.get(url, headers=headers, timeout=30)
                if response.status_code == 200:
                    if "application/json" in response.headers.get("content-type", ""):
                        data = response.json()
                        if "data" in data:
                            devices = [d for d in data["data"] if self.is_cellular_device(d)]
                            if devices:
                                print(f"✅ Mobile API: Found {len(devices)} devices")
                                return devices
                    devices = self.parse_devices_from_text(response.text)
                    if devices:
                        print(f"✅ Mobile HTML: Found {len(devices)} devices")
                        return devices
            except:
                continue
        print("❌ Mobile endpoints failed")
        return []
    
    def parse_devices_from_text(self, text):
        """Generic pattern: extract anything like CODE (description)."""
        devices = []
        found_ids = set()
        pattern = r'([A-Z0-9\-]{4,})\s*\(([^)]{3,})\)'
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            model_code, description = match[0].strip(), match[1].strip()
            if model_code and model_code not in found_ids:
                device = {
                    "id": model_code,
                    "brand": "",
                    "model": model_code,
                    "description": description,
                    "subType": "Cellular Mobile",
                    "certificate_no": model_code
                }
                devices.append(device)
                found_ids.add(model_code)
        return devices
    
    def is_cellular_device(self, device):
        """Check if device is cellular mobile (very generic)."""
        if not isinstance(device, dict):
            return False
        sub_type = device.get("subType", "").lower()
        if "cellular" in sub_type or "mobile" in sub_type:
            return True
        for field in ["type", "category", "description"]:
            value = str(device.get(field, "")).lower()
            if any(keyword in value for keyword in ["mobile", "cellular", "phone", "smartphone"]):
                return True
        return False
    
    def load_seen_devices(self):
        """Load previously seen device IDs."""
        if os.path.exists(SEEN_FILE):
            try:
                with open(SEEN_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.seen_devices = set(data)
                    print(f"📚 Loaded {len(self.seen_devices)} previously seen devices")
            except Exception as e:
                print(f"❌ Error loading seen devices: {e}")
                self.seen_devices = set()
        else:
            print("📝 First run - no previous devices")
            self.seen_devices = set()
    
    def save_seen_devices(self):
        """Save all seen device IDs to file."""
        try:
            for d in self.devices:
                if d.get("id"):
                    self.seen_devices.add(d.get("id"))
            with open(SEEN_FILE, "w", encoding="utf-8") as f:
                json.dump(list(self.seen_devices), f, ensure_ascii=False, indent=2)
            print(f"💾 Saved {len(self.seen_devices)} device IDs")
        except Exception as e:
            print(f"❌ Error saving seen devices: {e}")
    
    def find_new_devices(self):
        """Find devices that are NEW (never seen before)."""
        self.new_devices = []
        for device in self.devices:
            device_id = device.get("id")
            if device_id and device_id not in self.seen_devices:
                self.new_devices.append(device)
                print(f"🆕 NEW: {device.get('model')} ({device.get('description')})")
        print(f"📊 Found {len(self.new_devices)} new devices out of {len(self.devices)} total")
    
    def send_notification(self, is_first_run=False):
        """Send Telegram notification."""
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            print("❌ No Telegram credentials")
            return
        if is_first_run:
            msg = f"🎉 <b>NBTC Monitor Started!</b>\n\n"
            msg += f"✅ Found {len(self.devices)} devices on first scan\n"
            msg += f"📅 Monitoring for NEW devices daily at 7 AM IST\n\n"
            msg += f"🚀 <b>You'll only get notified about NEW devices!</b>"
        elif self.new_devices:
            msg = f"📱 <b>{len(self.new_devices)} NEW cellular devices found!</b>\n\n"
            for i, device in enumerate(self.new_devices[:5]):
                model = device.get('model', 'Unknown')
                desc = device.get('description', '')
                msg += f"{i+1}. <b>{model}</b>\n"
                if desc and desc != model:
                    msg += f"   📝 {desc}\n"
                msg += f"   🔍 Model: <code>{model}</code>\n\n"
            if len(self.new_devices) > 5:
                msg += f"...and {len(self.new_devices)-5} more!\n\n"
            msg += f"🔗 <a href='https://mocheck.nbtc.go.th/search-equipments'>NBTC Search</a>"
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
            print(f"❌ Notification error: {e}")
    
    async def run_monitoring(self):
        """Main monitoring function with multiple methods."""
        print("=== 🔍 NBTC DEVICE MONITOR ===")
        print(f"⏰ Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        self.load_seen_devices()
        is_first_run = len(self.seen_devices) == 0
        methods = [
            self.method_1_direct_api,
            self.method_2_optimized_browser,
            self.method_3_mobile_endpoint
        ]
        for i, method in enumerate(methods, 1):
            print(f"\n--- Trying Method {i} ---")
            try:
                devices = await method()
                if devices:
                    self.devices = devices
                    print(f"✅ Success with Method {i}")
                    break
            except Exception as e:
                print(f"❌ Method {i} failed: {e}")
                continue
        if not self.devices:
            print("❌ All methods failed - no devices found")
            return
        self.find_new_devices()
        if self.new_devices:
            with open("new_devices.json", "w", encoding="utf-8") as f:
                json.dump(self.new_devices, f, ensure_ascii=False, indent=2)
        self.send_notification(is_first_run)
        self.save_seen_devices()
        print(f"\n=== 📊 SUMMARY ===")
        print(f"Total devices found: {len(self.devices)}")
        print(f"New devices: {len(self.new_devices)}")
        print(f"Previously seen: {len(self.seen_devices) - len(self.new_devices)}")
        print("=== ✅ MONITORING COMPLETE ===")

async def main():
    monitor = NBTCMonitor()
    await monitor.run_monitoring()

if __name__ == "__main__":
    asyncio.run(main())
