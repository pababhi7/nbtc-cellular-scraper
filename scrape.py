import requests
import json
import os

API_URL = "https://mocheck.nbtc.go.th/api/equipments/search"
HEADERS = {"Content-Type": "application/json"}
SEEN_FILE = "seen_devices.json"

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def fetch_devices(page=1, per_page=20):
    payload = {
        "status": "อนุญาต",
        "page": page,
        "perPage": per_page,
        "search": "",
        "subType": "Cellular Mobile"
    }
    response = requests.post(API_URL, json=payload, headers=HEADERS)
    response.raise_for_status()
    return response.json().get("data", [])

def load_seen_ids():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_seen_ids(ids):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(list(ids), f, ensure_ascii=False, indent=2)

def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram credentials not set. Skipping notification.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")

def main():
    seen_ids = load_seen_ids()
    new_ids = set()
    new_devices = []

    for page in range(1, 6):  # Check first 5 pages
        devices = fetch_devices(page=page, per_page=20)
        if not devices:
            break
        for device in devices:
            device_id = device.get("id") or device.get("certificate_no")
            if device_id and device_id not in seen_ids:
                new_devices.append(device)
                new_ids.add(device_id)
        if len(devices) < 20:
            break

    # Notify even on first run (when seen_ids is empty)
    if new_devices:
        print(f"Found {len(new_devices)} new devices in Cellular Mobile:")
        print(json.dumps(new_devices, ensure_ascii=False, indent=2))
        with open("new_devices.json", "w", encoding="utf-8") as f:
            json.dump(new_devices, f, ensure_ascii=False, indent=2)
        # Build Telegram message
        msg = f"📱 <b>{len(new_devices)} new Cellular Mobile devices found!</b>\n"
        for d in new_devices[:5]:  # Show up to 5 devices in the message
            brand = d.get('brand', '')
            model = d.get('model', '')
            cert = d.get('certificate_no', '')
            device_id = d.get('id', '')
            link = f"https://mocheck.nbtc.go.th/equipment-detail/{device_id}"
            msg += f"\n<b>Brand:</b> {brand}\n<b>Model:</b> {model}\n<b>Cert No:</b> {cert}\n🔗 {link}\n"
        if len(new_devices) > 5:
            msg += f"\n...and {len(new_devices)-5} more."
        send_telegram_message(msg)
    else:
        print("No new devices found in Cellular Mobile.")

    all_ids = seen_ids.union(new_ids)
    save_seen_ids(all_ids)

if __name__ == "__main__":
    main()
