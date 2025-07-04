import sys
import os
import json
import asyncio
from playwright.async_api import async_playwright
import re

os.environ["PYTHONIOENCODING"] = "utf-8"

import requests

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

async def extract_devices_from_html():
    """Extract device data directly from page HTML"""
    print("=== HTML EXTRACTION METHOD ===")
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-web-security'
                ]
            )
            
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            page = await context.new_page()
            
            # Hide automation indicators
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            """)
            
            print("Loading page with status filter...")
            # Go directly to the page with status filter
            await page.goto("https://mocheck.nbtc.go.th/search-equipments?status=อนุญาต", 
                           wait_until="domcontentloaded", timeout=60000)
            
            # Wait for Cloudflare and page to fully load
            await page.wait_for_timeout(15000)
            
            # Check if we have device data in the page
            print("Analyzing page content...")
            
            # Method 1: Look for table rows or card elements
            device_elements = await page.query_selector_all(
                "tr, .card, .equipment-item, .device-card, .equipment-row, .item-row"
            )
            print(f"Found {len(device_elements)} potential device elements")
            
            devices = []
            
            # Method 2: Extract all text and look for patterns
            page_text = await page.evaluate("document.body.innerText")
            print(f"Page text length: {len(page_text)} characters")
            
            # Look for device patterns in text
            lines = page_text.split('\n')
            device_info = []
            
            for i, line in enumerate(lines):
                line = line.strip()
                if line and any(keyword in line.upper() for keyword in ['SAMSUNG', 'APPLE', 'XIAOMI', 'OPPO', 'VIVO', 'HUAWEI', 'NOKIA']):
                    # Found a potential device line, get context
                    context_lines = lines[max(0, i-2):i+3]
                    device_info.append('\n'.join(context_lines))
                    print(f"Found potential device: {line}")
            
            # Method 3: Look for JSON data in script tags
            script_content = await page.evaluate("""
                () => {
                    let allScripts = '';
                    document.querySelectorAll('script').forEach(script => {
                        if (script.textContent && (
                            script.textContent.includes('equipment') || 
                            script.textContent.includes('device') ||
                            script.textContent.includes('data')
                        )) {
                            allScripts += script.textContent + '\\n\\n';
                        }
                    });
                    return allScripts;
                }
            """)
            
            print(f"Script content length: {len(script_content)} characters")
            
            # Try to extract JSON from scripts
            json_matches = re.findall(r'\{[^{}]*"data"\s*:\s*\[[^\]]*\][^{}]*\}', script_content)
            print(f"Found {len(json_matches)} potential JSON data blocks")
            
            for match in json_matches:
                try:
                    data = json.loads(match)
                    if "data" in data and isinstance(data["data"], list):
                        devices.extend(data["data"])
                        print(f"Extracted {len(data['data'])} devices from JSON")
                except:
                    continue
            
            # Method 4: Try to trigger data loading with different approaches
            if not devices and not device_info:
                print("No devices found yet, trying to trigger data loading...")
                
                # Try clicking different elements
                clickable_elements = await page.query_selector_all(
                    "button, a, .btn, .link, input[type='submit']"
                )
                
                for element in clickable_elements[:5]:  # Try first 5 clickable elements
                    try:
                        element_text = await element.inner_text()
                        print(f"Trying to click: {element_text}")
                        await element.click()
                        await page.wait_for_timeout(3000)
                        
                        # Check if new content appeared
                        new_elements = await page.query_selector_all(".equipment-item, .device-card")
                        if new_elements:
                            print(f"Found {len(new_elements)} new elements after clicking")
                            break
                    except:
                        continue
            
            # Method 5: Check for any tables with data
            tables = await page.query_selector_all("table")
            print(f"Found {len(tables)} tables")
            
            for table in tables:
                try:
                    table_text = await table.inner_text()
                    if any(keyword in table_text.upper() for keyword in ['BRAND', 'MODEL', 'CERTIFICATE', 'TYPE']):
                        print("Found table with device-like headers")
                        rows = await table.query_selector_all("tr")
                        print(f"Table has {len(rows)} rows")
                        
                        for row in rows[1:6]:  # Skip header, get first 5 data rows
                            try:
                                cells = await row.query_selector_all("td")
                                if len(cells) >= 3:
                                    cell_texts = []
                                    for cell in cells:
                                        cell_text = await cell.inner_text()
                                        cell_texts.append(cell_text.strip())
                                    
                                    if cell_texts[0]:  # If first cell has content
                                        device = {
                                            "brand": cell_texts[0] if len(cell_texts) > 0 else "Unknown",
                                            "model": cell_texts[1] if len(cell_texts) > 1 else "Unknown",
                                            "subType": "Cellular Mobile",
                                            "certificate_no": cell_texts[2] if len(cell_texts) > 2 else "Unknown",
                                            "id": f"html_extracted_{len(devices)}"
                                        }
                                        devices.append(device)
                                        print(f"Extracted from table: {device['brand']} {device['model']}")
                            except:
                                continue
                except:
                    continue
            
            await browser.close()
            
            print(f"Total devices extracted: {len(devices)}")
            return devices[:5]  # Return first 5 for testing
    
    except Exception as e:
        print(f"HTML extraction error: {e}")
        return []

def send_test_results(devices, method=""):
    """Send test results via Telegram"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("No Telegram credentials - skipping notification")
        return
    
    if devices:
        msg = f"🎉 BREAKTHROUGH! Found {len(devices)} devices!\n"
        msg += f"Method: {method}\n\n"
        for i, device in enumerate(devices):
            brand = device.get('brand', 'Unknown')
            model = device.get('model', 'Unknown')
            subtype = device.get('subType', 'Unknown')
            cert = device.get('certificate_no', 'Unknown')
            msg += f"{i+1}. {brand} {model}\n   Type: {subtype}\n   Cert: {cert}\n\n"
        msg += "🚀 SUCCESS! We can now extract real device data!\n"
        msg += "Your daily scraper will start working!"
    else:
        msg = f"🔍 TEST RESULTS: HTML extraction attempted\n"
        msg += f"❌ No device data found in page HTML\n\n"
        msg += f"The page loads but device data might be:\n"
        msg += f"• Loaded dynamically after user interaction\n"
        msg += f"• Requires authentication\n"
        msg += f"• Hidden in complex JavaScript\n\n"
        msg += f"📅 Will keep trying daily at 7 AM IST"
    
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
    print("=== HTML EXTRACTION TEST ===")
    print("Trying to extract device data directly from page HTML...\n")
    
    devices = await extract_devices_from_html()
    
    print(f"\n=== FINAL RESULTS ===")
    print(f"Total devices found: {len(devices)}")
    
    if devices:
        print("SUCCESS! Here are the devices:")
        for i, device in enumerate(devices):
            print(f"{i+1}. {device.get('brand')} {device.get('model')} - {device.get('subType')}")
        method_used = "HTML Extraction"
    else:
        print("No devices found - trying different extraction approach needed")
        method_used = "HTML Extraction (failed)"
    
    # Send results via Telegram
    send_test_results(devices, method_used)

if __name__ == "__main__":
    asyncio.run(main())
