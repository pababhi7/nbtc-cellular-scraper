import sys
import os
import json
import asyncio
from playwright.async_api import async_playwright
import re
from datetime import datetime

os.environ["PYTHONIOENCODING"] = "utf-8"

import requests

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

async def extract_recent_devices_simple():
    """Extract recent devices for simple verification"""
    print("=== EXTRACTING RECENT DEVICES FOR VERIFICATION ===")
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-blink-features=AutomationControlled']
            )
            
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            page = await context.new_page()
            
            await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
            
            print("Loading NBTC page...")
            await page.goto("https://mocheck.nbtc.go.th/search-equipments?status=อนุญาต", 
                           wait_until="domcontentloaded", timeout=60000)
            
            await page.wait_for_timeout(15000)
            
            # Get page text for device extraction
            page_text = await page.evaluate("document.body.innerText")
            print(f"Page text length: {len(page_text)} characters")
            
            await browser.close()
            
            # Parse recent devices
            devices = parse_recent_devices_simple(page_text)
            return devices[:5]
    
    except Exception as e:
        print(f"Extraction error: {e}")
        return []

def parse_recent_devices_simple(text):
    """Parse recent devices with simple approach"""
    devices = []
    
    print("Parsing recent devices...")
    
    # Device patterns with more specific matching
    patterns = [
        (r'(CPH\d{4})\s*\((.*?)\)', "OPPO"),
        (r'(\d{10,}[A-Z]+)\s*\((Xiaomi.*?)\)', "Xiaomi"),
        (r'(SM-[A-Z]\d{3}[A-Z]*)\s*(?:\((.*?)\))?', "Samsung"),
        (r'(A\d{4})\s*(?:\((.*?)\))?', "Apple"),
        (r'(V\d{4})\s*\((vivo.*?)\)', "vivo")
    ]
    
    found_devices = set()
    
    for pattern, brand in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches[:3]:  # Take first 3 of each brand
            if isinstance(match, tuple) and len(match) >= 2:
                model_code, description = match[0], match[1]
            else:
                model_code, description = match, ""
            
            # Clean up the data
            model_code = model_code.strip()
            description = description.strip()
            
            if model_code and model_code not in found_devices and len(model_code) >= 4:
                device = {
                    "id": model_code,
                    "brand": brand,
                    "model": model_code,
                    "description": description,
                    "subType": "Cellular Mobile",
                    "certificate_no": model_code,
                    "verification_instructions": f"Search for '{model_code}' on NBTC website",
                    "source": "text_extraction"
                }
                devices.append(device)
                found_devices.add(model_code)
                print(f"Found: {brand} {model_code} - {description}")
                
                if len(devices) >= 5:
                    break
        
        if len(devices) >= 5:
            break
    
    return devices

def send_simple_verification_notification(devices):
    """Send simple verification notification without problematic links"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("No Telegram credentials")
        return
    
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    msg = f"🔍 <b>DATA VERIFICATION TEST</b>\n"
    msg += f"🕒 {current_time}\n\n"
    
    if devices:
        msg += f"✅ <b>Found {len(devices)} devices from NBTC:</b>\n\n"
        
        for i, device in enumerate(devices):
            brand = device.get('brand', 'Unknown')
            model = device.get('model', 'Unknown')
            desc = device.get('description', '')
            
            msg += f"{i+1}. <b>{brand} {model}</b>\n"
            if desc and desc != model:
                msg += f"   📝 {desc}\n"
            msg += f"   🔍 Model Code: <code>{model}</code>\n\n"
        
        msg += f"📋 <b>MANUAL VERIFICATION:</b>\n"
        msg += f"1. Go to: mocheck.nbtc.go.th/search-equipments\n"
        msg += f"2. Search for any model code above (copy/paste)\n"
        msg += f"3. If you find the device → our scraper is authentic!\n\n"
        
        msg += f"🎯 <b>This proves our scraper extracts real NBTC data!</b>"
        
    else:
        msg += f"❌ No devices found in current extraction\n\n"
        msg += f"This might mean:\n"
        msg += f"• Website structure changed\n"
        msg += f"• Extraction patterns need adjustment\n"
        msg += f"• Website is blocking our requests\n\n"
        msg += f"🔄 Will try again on next run"
    
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
            print("✅ Simple verification notification sent!")
        else:
            print(f"❌ Telegram failed: {resp.status_code}")
            print(f"Response: {resp.text}")
    except Exception as e:
        print(f"❌ Telegram error: {e}")

async def main():
    print("=== SIMPLE DATA VERIFICATION ===")
    print("Extracting device data for manual verification...\n")
    
    devices = await extract_recent_devices_simple()
    
    print(f"\n=== RESULTS ===")
    print(f"Extracted {len(devices)} devices")
    
    if devices:
        print("\nDevices found:")
        for device in devices:
            print(f"• {device['brand']} {device['model']} - {device.get('description', '')}")
        
        send_simple_verification_notification(devices)
        
        # Save verification data
        with open("simple_verification.json", "w", encoding="utf-8") as f:
            json.dump(devices, f, ensure_ascii=False, indent=2)
        print("\n✅ Verification data saved to simple_verification.json")
        
        print("\n🎯 VERIFICATION STEPS:")
        print("1. Check your Telegram for device model codes")
        print("2. Go to mocheck.nbtc.go.th/search-equipments")  
        print("3. Search for any model code manually")
        print("4. If you find the device → our data is authentic!")
        
    else:
        print("❌ No devices extracted - need to check extraction method")
        send_simple_verification_notification([])

if __name__ == "__main__":
    asyncio.run(main())
