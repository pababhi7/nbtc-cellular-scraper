from playwright.sync_api import sync_playwright
import json

# Template script - adjust selectors based on site inspection.
def scrape_new_cellular_devices():
    devices = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)  # Headless for GitHub Actions
        page = browser.new_page()
        page.goto('https://mocheck.nbtc.go.th/search-equipments')
        
        # Adjust: Filter for cellular type (likely a select; find exact value/label).
        # Example: page.select_option('select[name="equipmentType"]', label='อุปกรณ์ผู้ใช้ในบริการเคลื่อนที่เซลลูลาร์')
        page.fill('input[name="type"]', 'cellular')  # Placeholder - update to actual
        
        # Submit form (adjust selector, e.g., 'button:has-text("ค้นหา")').
        page.click('button[type="submit"]')
        
        page.wait_for_selector('table', timeout=30000)
        
        while True:
            table = page.locator('table')  # Adjust e.g., 'table.table-responsive'
            rows = table.locator('tr')
            
            for i in range(1, rows.count()):
                row = rows.nth(i)
                cols = row.locator('td')
                if cols.count() < 6: continue
                
                # Adjust column indices based on headers:
                # Assume: 0=Approval, 1=Brand, 2=Model, 3=Type, 4=Importer, 5=Date
                approval = cols.nth(0).inner_text().strip()
                brand = cols.nth(1).inner_text().strip()
                model = cols.nth(2).inner_text().strip()
                device_type = cols.nth(3).inner_text().strip()
                importer = cols.nth(4).inner_text().strip()
                date = cols.nth(5).inner_text().strip()
                
                if 'ไม่ระบุ' in date:  # 'Not specified' in Thai
                    if 'เซลลูลาร์' in device_type or 'cellular' in device_type.lower():
                        devices.append({
                            'approval_number': approval,
                            'brand': brand,
                            'model': model,
                            'type': device_type,
                            'importer': importer,
                            'approval_date': date
                        })
            
            # Pagination (adjust, e.g., 'a:has-text("ถัดไป")')
            next_button = page.locator('a >> text="ถัดไป"')
            if next_button.count() > 0 and next_button.is_enabled():
                next_button.click()
                page.wait_for_load_state('networkidle')
            else:
                break
        
        browser.close()
    
    # Output JSON to stdout (captured in workflow)
    print(json.dumps(devices, ensure_ascii=False, indent=4))

if __name__ == "__main__":
    scrape_new_cellular_devices()
