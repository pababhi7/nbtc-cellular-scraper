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

async def extract_recent_devices():
    """Extract the most recent devices for verification"""
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
            
            print("Loading NBTC page (devices are usually sorted by newest first)...")
            await page.goto("https://mocheck.nbtc.go.th/search-equipments?status=อนุญาต", 
                           wait_until="domcontentloaded", timeout=60000)
            
            await page.wait_for_timeout(15000)  # Wait for full page load
            
            # Try to get the page structure first
            print("Analyzing page structure...")
            
            # Check if there are any data tables or structured content
            structured_elements = await page.evaluate("""
                () => {
                    const elements = [];
                    
                    // Look for tables
                    const tables = document.querySelectorAll('table');
                    tables.forEach((table, index) => {
                        const rows = table.querySelectorAll('tr');
                        if (rows.length > 1) {
                            elements.push({
                                type: 'table',
                                index: index,
                                rows: rows.length,
                                hasHeaders: table.querySelector('th') !== null
                            });
                        }
                    });
                    
                    // Look for cards or items
                    const cards = document.querySelectorAll('.card, .item, .equipment, .device');
                    elements.push({
                        type: 'cards',
                        count: cards.length
                    });
                    
                    // Look for lists
                    const lists = document.querySelectorAll('ul, ol');
                    lists.forEach((list, index) => {
                        const items = list.querySelectorAll('li');
                        if (items.length > 5) {
                            elements.push({
                                type: 'list',
                                index: index,
                                items: items.length
                            });
                        }
                    });
                    
                    return elements;
                }
            """)
            
            print(f"Found structured elements: {structured_elements}")
            
            # Get all page text
            page_text = await page.evaluate("document.body.innerText")
            print(f"Page text length: {len(page_text)} characters")
            
            # Try to extract table data if tables exist
            recent_devices = []
            
            if any(elem['type'] == 'table' for elem in structured_elements):
                print("Extracting data from tables...")
                recent_devices = await extract_from_tables(page)
            
            # If no table data, parse from text
            if not recent_devices:
                print("No table data found, parsing from text...")
                recent_devices = parse_recent_from_text(page_text)
            
            await browser.close()
            return recent_devices[:5]  # Return only top 5
    
    except Exception as e:
        print(f"Extraction error: {e}")
        return []

async def extract_from_tables(page):
    """Extract device data from HTML tables"""
    print("Attempting to extract from HTML tables...")
    
    try:
        table_data = await page.evaluate("""
            () => {
                const devices = [];
                const tables = document.querySelectorAll('table');
                
                for (let table of tables) {
                    const rows = table.querySelectorAll('tr');
                    
                    // Skip if too few rows
                    if (rows.length < 2) continue;
                    
                    // Get headers if they exist
                    const headerRow = table.querySelector('tr:first-child');
                    const headers = [];
                    if (headerRow) {
                        headerRow.querySelectorAll('th, td').forEach(cell => {
                            headers.push(cell.innerText.trim());
                        });
                    }
                    
                    // Extract data rows
                    for (let i = 1; i < Math.min(rows.length, 6); i++) {
                        const row = rows[i];
                        const cells = row.querySelectorAll('td');
                        
                        if (cells.length >= 2) {
                            const rowData = [];
                            cells.forEach(cell => {
                                rowData.push(cell.innerText.trim());
                            });
                            
                            // Look for device-like data
                            const rowText = rowData.join(' ');
                            if (rowText.match(/(CPH|SM-|A\\d{4}|\\d{10}[A-Z]|vivo|OPPO|Samsung|Apple|Xiaomi)/i)) {
                                devices.push({
                                    headers: headers,
                                    data: rowData,
                                    fullText: rowText
                                });
                            }
                        }
                    }
                }
                
                return devices;
            }
        """)
        
        print(f"Extracted {len(table_data)} potential device rows from tables")
        
        # Convert table data to device objects
        devices = []
        for item in table_data:
            device = parse_table_row_to_device(item)
            if device:
                devices.append(device)
        
        return devices
    
    except Exception as e:
        print(f"Table extraction error: {e}")
        return []

def parse_table_row_to_device(table_item):
    """Convert table row data to device object"""
    try:
        data = table_item['data']
        full_text = table_item['fullText']
        
        # Try to identify brand and model from the data
        brand = "Unknown"
        model = "Unknown"
        description = ""
        device_id = ""
        
        # Look for known patterns in the row data
        for cell in data:
            cell_upper = cell.upper()
            
            # Check for brand names
            if any(b in cell_upper for b in ['OPPO', 'SAMSUNG', 'APPLE', 'XIAOMI', 'VIVO', 'HUAWEI']):
                brand = next(b for b in ['OPPO', 'SAMSUNG', 'APPLE', 'XIAOMI', 'VIVO', 'HUAWEI'] if b in cell_upper)
            
            # Check for model patterns
            if re.search(r'CPH\d+', cell):
                model = re.search(r'CPH\d+', cell).group()
                device_id = model
                brand = "OPPO"
            elif re.search(r'SM-[A-Z0-9]+', cell):
                model = re.search(r'SM-[A-Z0-9]+', cell).group()
                device_id = model
                brand = "Samsung"
            elif re.search(r'A\d{4}', cell):
                model = re.search(r'A\d{4}', cell).group()
                device_id = model
                brand = "Apple"
            elif re.search(r'\d{10,}[A-Z]+', cell):
                model = re.search(r'\d{10,}[A-Z]+', cell).group()
                device_id = model
                brand = "Xiaomi"
        
        if device_id:
            device = {
                "id": device_id,
                "brand": brand,
                "model": model,
                "description": description,
                "subType": "Cellular Mobile",
                "certificate_no": device_id,
                "link": f"https://mocheck.nbtc.go.th/search-equipments?search={device_id}",
                "source": "table_extraction",
                "table_data": data,
                "verification_status": "extracted_from_table"
            }
            return device
    
    except Exception as e:
        print(f"Error parsing table row: {e}")
    
    return None

def parse_recent_from_text(text):
    """Parse recent devices from page text (fallback method)"""
    devices = []
    
    print("Parsing recent devices from text (taking first matches as most recent)...")
    
    # Track found devices to avoid duplicates
    found_devices = set()
    
    # Pattern matching for different brands (take first few matches as "recent")
    patterns = [
        (r'(CPH\d+)\s*\((.*?)\)', "OPPO"),
        (r'(\d{10,}[A-Z]+)\s*\((Xiaomi.*?)\)', "Xiaomi"),
        (r'(SM-[A-Z0-9]+)\s*(?:\((.*?)\))?', "Samsung"),
        (r'(A\d{4})\s*(?:\((.*?)\))?', "Apple"),
        (r'(vivo \d+[A-Z]*)\s*(?:\((.*?)\))?', "vivo")
    ]
    
    for pattern, brand in patterns:
        matches = re.findall(pattern, text)
        for match in matches[:2]:  # Take first 2 of each brand as "recent"
            if isinstance(match, tuple) and len(match) >= 2:
                model_code, description = match[0], match[1]
            else:
                model_code, description = match, ""
            
            if model_code not in found_devices:
                device = {
                    "id": model_code.replace(" ", "_"),
                    "brand": brand,
                    "model": model_code,
                    "description": description,
                    "subType": "Cellular Mobile",
                    "certificate_no": model_code.replace(" ", "_"),
                    "link": f"https://mocheck.nbtc.go.th/search-equipments?search={model_code.replace(' ', '%20')}",
                    "source": "text_extraction",
                    "verification_status": "needs_manual_verification"
                }
                devices.append(device)
                found_devices.add(model_code)
                
                if len(devices) >= 5:
                    break
        
        if len(devices) >= 5:
            break
    
    return devices

def send_verification_notification(devices):
    """Send verification notification with recent devices"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("No Telegram credentials")
        return
    
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    msg = f"🔍 VERIFICATION TEST - {current_time}\n\n"
    msg += f"📋 Found {len(devices)} devices for authenticity check:\n\n"
    
    for i, device in enumerate(devices):
        brand = device.get('brand', 'Unknown')
        model = device.get('model', 'Unknown')
        desc = device.get('description', '')
        link = device.get('link', '')
        source = device.get('source', 'unknown')
        
        msg += f"{i+1}. <b>{brand} {model}</b>\n"
        if desc and desc != model and desc.strip():
            msg += f"   📝 {desc}\n"
        msg += f"   🔗 <a href='{link}'>Verify on NBTC Site</a>\n"
        msg += f"   📊 Source: {source}\n\n"
    
    msg += f"✅ <b>VERIFICATION STEPS:</b>\n"
    msg += f"1. Click each device link above\n"
    msg += f"2. Check if it opens NBTC's official page\n"
    msg += f"3. Verify device details match\n\n"
    msg += f"🎯 <b>If all links work → Our scraper is authentic!</b>"
    
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
            print("✅ Verification notification sent!")
        else:
            print(f"❌ Telegram failed: {resp.status_code}")
    except Exception as e:
        print(f"❌ Telegram error: {e}")

async def main():
    print("=== NBTC RECENT DEVICES VERIFICATION ===")
    print("Extracting recent devices for authenticity check...\n")
    
    devices = await extract_recent_devices()
    
    print(f"\n=== VERIFICATION RESULTS ===")
    print(f"Found {len(devices)} recent devices for verification")
    
    if devices:
        print("\nRecent devices found:")
        for i, device in enumerate(devices):
            print(f"{i+1}. {device['brand']} {device['model']}")
            print(f"   Description: {device.get('description', 'N/A')}")
            print(f"   Link: {device['link']}")
            print(f"   Source: {device.get('source', 'unknown')}")
            print()
        
        send_verification_notification(devices)
        
        # Save verification data
        with open("verification_devices.json", "w", encoding="utf-8") as f:
            json.dump(devices, f, ensure_ascii=False, indent=2)
        print("✅ Verification data saved to verification_devices.json")
        
        print("\n🔍 NEXT STEPS:")
        print("1. Check your Telegram for the verification message")
        print("2. Click each device link to verify it exists on NBTC")
        print("3. If all links work, our scraper is getting real data!")
        
    else:
        print("❌ No recent devices found - may need to adjust extraction method")

if __name__ == "__main__":
    asyncio.run(main())
