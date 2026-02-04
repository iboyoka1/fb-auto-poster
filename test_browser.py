"""Simple test to check if browser and cookies work"""
from playwright.sync_api import sync_playwright
import json
import os
import time

print("Starting simple browser test...")

playwright = sync_playwright().start()
browser = playwright.chromium.launch(
    headless=False,
    args=[
        '--disable-blink-features=AutomationControlled',
        '--disable-dev-shm-usage',
        '--no-sandbox',
    ]
)
context = browser.new_context(
    viewport={'width': 1280, 'height': 720},
    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    locale='fr-FR',
)
page = context.new_page()

# Load cookies
cookie_path = os.path.join(os.path.dirname(__file__), 'sessions', 'facebook-cookies.json')
if os.path.exists(cookie_path):
    print(f"Loading cookies from: {cookie_path}")
    with open(cookie_path, 'r', encoding='utf-8') as f:
        cookies = json.load(f)
    
    # Filter valid cookies
    valid_cookies = []
    for c in cookies:
        cookie = {
            'name': c.get('name'),
            'value': c.get('value'),
            'domain': c.get('domain', '.facebook.com'),
            'path': c.get('path', '/'),
        }
        if c.get('expires'):
            cookie['expires'] = c.get('expires')
        if c.get('secure') is not None:
            cookie['secure'] = c.get('secure')
        if c.get('httpOnly') is not None:
            cookie['httpOnly'] = c.get('httpOnly')
        # Fix sameSite - must be Strict, Lax, or None
        sameSite = c.get('sameSite', '')
        if sameSite in ['Strict', 'Lax', 'None']:
            cookie['sameSite'] = sameSite
        # Skip invalid sameSite values
        valid_cookies.append(cookie)
    
    context.add_cookies(valid_cookies)
    print(f"Loaded {len(valid_cookies)} cookies")
else:
    print("No cookies found!")

# Navigate to Facebook
print("Navigating to Facebook...")
page.goto('https://www.facebook.com/', timeout=60000)
page.wait_for_load_state('domcontentloaded')
time.sleep(3)

# Check what we got
current_url = page.url
title = page.title()
print(f"URL: {current_url}")
print(f"Title: {title}")

# Check if logged in
if 'login' in current_url.lower():
    print("❌ NOT LOGGED IN - cookies may be expired")
else:
    print("✅ LOGGED IN (not on login page)")

# Take screenshot
screenshot_path = os.path.join(os.path.dirname(__file__), 'test_screenshot.png')
page.screenshot(path=screenshot_path)
print(f"Screenshot saved: {screenshot_path}")

input("\nPress Enter to close browser...")
browser.close()
playwright.stop()
print("Done!")
