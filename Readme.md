# NBTC Device Scraper

This repository contains a Python script to scrape new cellular devices from the NBTC MoCheck website (https://mocheck.nbtc.go.th/search-equipments) where approval date is "not specified" (in Thai: 'ไม่ระบุ').

## Features
- Scrapes devices using Playwright for browser automation.
- Filters for cellular devices.
- Runs automatically daily at 5 AM and 6 AM IST via GitHub Actions.
- Saves results to `output.json` and commits to the repo.
- Sends Telegram notifications on completion (requires secrets: TELEGRAM_TOKEN and TELEGRAM_CHAT_ID).

## Setup
1. Install dependencies: `pip install -r requirements.txt`
2. Install Playwright browsers: `playwright install`
3. Test locally: `python scrape_devices.py`
4. Adjust selectors in `scrape_devices.py` based on inspecting the website (form fields, table columns – site is in Thai).
5. For GitHub Actions: Set secrets for Telegram in repo settings.

## Files
- `scrape_devices.py`: Main scraper script.
- `.github/workflows/scrape.yml`: GitHub Actions workflow.
- `output.json`: Generated file with scraped data (updated automatically).
- `requirements.txt`: Dependencies.

Note: The script is a template; verify and update Playwright locators (e.g., for device type filter and table) as the site structure may change. If errors occur, check browser dev tools.
