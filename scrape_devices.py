from playwright.sync_api import sync_playwright
import json

def scrape_new_cellular_devices():
    devices = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        # Set user-agent to mimic real browser
        page.set_extra_http_headers({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
        })
        page.goto('https://mocheck.nbtc.go.th/search-equipments', timeout=60000)
        
        # Wait for the form to load
        page.wait_for_selector('select.form-control', timeout=60000)
        
        # Select cellular type using label (safer, as value might change)
        page.select_option('select.form-control', label='อุปกรณ์ผู้ใช้ในบริการเคลื่อนที่เซลลูลาร์')
        
        # Assume dates are blank by default; if needed, clear them (adjust IDs if known)
        # page.fill('input#startApproveDate', '')
        # page.fill('input#endApproveDate', '')
        
        # Submit form
        page.click('button.btn-primary:has-text("ค้นหา")')
        
        # Wait for results
        page.wait_for_selector('table.table-striped', timeout=60000)
        
        while True:
            table = page.locator('table.table-striped')
            rows = table.locator('tbody tr')
            
            for i in range(rows.count()):
                row = rows.nth(i)
                cols = row.locator('td')
                if cols.count() < 6: continue
                
                approval = cols.nth(0).inner_text().strip()
                brand = cols.nth(1).inner_text().strip()
                model = cols.nth(2).inner_text().strip()
                device_type = cols.nth(3).inner_text().strip()
                importer = cols.nth(4).inner_text().strip()
                date = cols.nth(5).inner_text().strip()
                
                if 'ไม่ระบุ' in date and 'เซลลูลาร์' in device_type:
                    devices.append({
                        'approval_number': approval,
                        'brand': brand,
                        'model': model,
                        'type': device_type,
                        'importer': importer,
                        'approval_date': date
                    })
            
            # Pagination
            next_button = page.locator('a:has-text("ถัดไป")')
            if next_button.count() > 0 and next_button.is_visible():
                next_button.click()
                page.wait_for_load_state('networkidle', timeout=30000)
            else:
                break
        
        browser.close()
    
    print(json.dumps(devices, ensure_ascii=False, indent=4))

if __name__ == "__main__":
    scrape_new_cellular_devices()
