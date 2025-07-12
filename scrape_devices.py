from playwright.sync_api import sync_playwright
import json

def scrape_new_cellular_devices():
    devices = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto('https://mocheck.nbtc.go.th/search-equipments', timeout=60000)  # Longer initial load timeout
        
        # Select cellular type (adjust value/label if needed - '1' is common for cellular)
        page.select_option('select[name="equipType"]', value='1')  # Or label='อุปกรณ์ผู้ใช้ในบริการเคลื่อนที่เซลลูลาร์'
        
        # Clear/leave date fields blank (assume names 'startDate' and 'endDate')
        page.fill('input[name="startDate"]', '')
        page.fill('input[name="endDate"]', '')
        
        # Submit form (button with text "ค้นหา")
        page.click('button:has-text("ค้นหา")')
        
        page.wait_for_selector('table#dataTable', timeout=60000)  # Wait for results table (likely ID 'dataTable' from DataTables)
        
        while True:
            table = page.locator('table.table-striped')  # Bootstrap/DataTables class
            rows = table.locator('tbody tr')  # Target tbody for data rows
            
            for i in range(rows.count()):
                row = rows.nth(i)
                cols = row.locator('td')
                if cols.count() < 6: continue
                
                # Columns (adjust indices: 0=Approval No, 1=Brand, 2=Model, 3=Type, 4=Importer, 5=Date)
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
            
            # Pagination (next link with text "ถัดไป", often in ul.pagination)
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
