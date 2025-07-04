import sys
import os
import json
import asyncio
from playwright.async_api import async_playwright
import re
from datetime import datetime
import urllib.parse

os.environ["PYTHONIOENCODING"] = "utf-8"

import requests

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

async def extract_devices_with_working_links():
    """Extract devices and find one working link format"""
    print("=== EXTRACTING DEVICES WITH WORKING LINKS ===")
    
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
            
            print("Loading NBTC page and finding working link format...")
            await page.goto("https://mocheck.nbtc.go.th/search-equipments?status=อนุญาต", 
                           wait_until="domcontentloaded", timeout=60000)
            
            await page.wait_for_timeout(15000)
            
            # Try to find the actual working link format by looking for detail links
            working_link_format = await find_working_link_format(page)
            
            # Get page text for device extraction
            page_text = await page.evaluate("document.body.innerText")
            
            # Try to perform a search on the page to see the URL format
            try:
                print("Testing search functionality to find URL format...")
                
                # Look for search input
                search_input = await page.query_selector("input[type='text'], input[name*='search'], input[placeholder*='search']")
                if search_input:
                    await search_input.fill("CPH2755")  # Test with a known device
                    
                    # Look for search button
                    search_button = await page.query_selector("button[type='submit'], input[type='submit'], button:has-text('ค้นหา'), button:has-text('Search')")
                    if search_button:
                        # Monitor URL changes
                        await search_button.click()
                        await page.wait_for_timeout(3000)
                        
                        current_url = page.url
                        print(f"Search resulted in URL: {current_url}")
                        if '?' in current_url:
                            working_link_format = current_url.split('?')[0] + "?{param}={value}"
            except Exception as e:
                print(f"Search test failed: {e}")
            
            await browser.close()
            
            # Parse devices with the working link format
            devices = parse_devices_with_single_link(page_text, working_link_format)
            return devices[:5]
    
    except Exception as e:
        print(f"Extraction error: {e}")
        return []

async def find_working_link_format(page):
    """Try to find the actual working link format from the page"""
    try:
        # Look for any links that might be device details
        device_links = await page.evaluate("""
            () => {
                const links = [];
                const allLinks = document.querySelectorAll('a[href]');
                
                allLinks.forEach(link => {
                    const href = link.href;
                    const text = link.innerText.trim();
                    
                    // Look for links that might be device details
                    if (href && href !== window.location.href && (
                        href.includes('detail') ||
                        href.includes('equipment') ||
                        href.includes('=') ||
                        text.match(/CPH\\d+|SM-[A-Z0-9]+|\\d{10}[A-Z]+/)
                    )) {
                        links.push({
                            url: href,
                            text: text
                        });
                    }
                });
                
                return links;
            }
        """)
        
        if device_links:
            print(f"Found {len(device_links)} potential device links")
            # Use the first device link as template
            sample_url = device_links[0]['url']
            print(f"Sample device URL: {sample_url}")
            
            # Extract the pattern
            if '?' in sample_url:
                base_url = sample_url.split('?')[0]
                params = sample_url.split('?')[1]
                # Find the parameter that might contain the device ID
                if '=' in params:
                    param_name = params.split('=')[0]
                    return f"{base_url}?{param_name}={{value}}"
        
        print("No device detail links found, using default format")
        return None
        
    except Exception as e:
        print(f"Error finding link format: {e}")
        return None

def parse_devices_with_single_link(text, link_format):
    """Parse devices and create single working link for each"""
    devices = []
    
    print("Creating devices with single working links...")
    
    # Device patterns
    patterns = [
        (r'(CPH\d+)\s*\((.*?)\)', "OPPO"),
        (r'(\d{10,}[A-Z]+)\s*\((Xiaomi.*?)\)', "Xiaomi"),
        (r'(SM-[A-Z0-9]+)\s*(?:\((.*?)\))?', "Samsung"),
        (r'(A\d{4})\s*(?:\((.*?)\))?', "Apple"),
        (r'(vivo \d+[A-Z]*)\s*(?:\((.*?)\))?', "vivo")
    ]
    
    found_devices = set()
    
    for pattern, brand in patterns:
        matches = re.findall(pattern, text)
        for match in matches[:2]:  # Take first 2 of each brand
            if isinstance(match, tuple) and len(match) >= 2:
                model_code, description = match[0], match[1]
            else:
                model_code, description = match, ""
            
            if model_code not in found_devices:
                # Create the single best link
                device_link = create_single_device_link(model_code, link_format)
                
                device = {
                    "id": model_code.replace(" ", "_"),
                    "brand": brand,
                    "model": model_code,
                    "description": description,
                    "subType": "Cellular Mobile",
                    "certificate_no": model_code.replace(" ", "_"),
                    "link": device_link,
                    "source": "text_extraction"
                }
                devices.append(device)
                found_devices.add(model_code)
                print(f"Added: {brand} {model_code}")
                
                if len(devices) >= 5:
                    break
        
        if len(devices) >= 5:
            break
    
    return devices

def create_single_device_link(model_code, link_format):
    """Create one working link for the device"""
    
    # If we found a working format from the page, use it
    if link_format and '{value}' in link_format:
        return link_format.replace('{value}', urllib.parse.quote(model_code))
    
    # Otherwise, use the most likely working format
    # Based on common Thai government website patterns
    
    # Clean the model code for URL
    clean_model = model_code.strip()
    encoded_model = urllib.parse.quote(clean_model)
    
    # Most likely working format (based on the original URL structure)
    return f"https://mocheck.nbtc.go.th/search-equipments?status=%E0%B8%AD%E0%B8%99%E0%B8%B8%E0%B8%8D%E0%B8%B2%E0%B8%95&search={encoded_model}"

def send_simple_verification(devices):
    """Send simple verification with one link per device"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("No Telegram credentials")
        return
    
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    msg = f"🔍 DEVICE VERIFICATION - {current_time}\n\n"
    msg += f"Found {len(devices)} recent devices. Click links to verify:\n\n"
    
    for i, device in enumerate(devices):
        brand = device.get('brand', 'Unknown')
        model = device.get('model', 'Unknown')
        desc = device.get('description', '')
        link = device.get('link', '')
        
        msg += f"{i+1}. <b>{brand} {model}</b>\n"
        if desc and desc != model and desc.strip():
            msg += f"   📝 {desc}\n"
        msg += f"   🔗 <a href='{link}'>View Device Details</a>\n\n"
    
    msg += f"✅ <b>Verification:</b> Click each link above\n"
    msg += f"📋 Each should open the device's official NBTC page\n"
    msg += f"🎯 If links work → scraper is getting real data!"
    
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
    except Exception as e:
        print(f"❌ Telegram error: {e}")

async def main():
    print("=== SIMPLE DEVICE VERIFICATION ===")
    print("Finding devices with single working links...\n")
    
    devices = await extract_devices_with_working_links()
    
    print(f"\n=== RESULTS ===")
    print(f"Found {len(devices)} devices for verification")
    
    if devices:
        print("\nDevices with single links:")
        for device in devices:
            print(f"• {device['brand']} {device['model']}")
            print(f"  Link: {device['link']}")
            print()
        
        send_simple_verification(devices)
        
        # Save data
        with open("device_verification.json", "w", encoding="utf-8") as f:
            json.dump(devices, f, ensure_ascii=False, indent=2)
        print("✅ Verification data saved")
        
        print("\n🎯 CHECK TELEGRAM:")
        print("• Each device has ONE link")
        print("• Click to verify it opens NBTC device page")
        print("• If all work → our scraper is authentic!")
        
    else:
        print("❌ No devices found")

if __name__ == "__main__":
    asyncio.run(main())
