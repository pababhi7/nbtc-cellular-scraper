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

    if new_devices:
        print(f"Found {len(new_devices)} new devices in Cellular Mobile:")
        # Use ensure_ascii=True to avoid Unicode printing issues in GitHub Actions
        print(json.dumps(new_devices, ensure_ascii=True, indent=2))
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
