"""Open browser for manual Facebook login and save cookies"""
from playwright.sync_api import sync_playwright
import json
import os
import time

print("Opening browser for manual login...")
print("Please login to Facebook manually.")
print("After login, press Enter in this terminal to save cookies.\n")

playwright = sync_playwright().start()
browser = playwright.chromium.launch(headless=False)
context = browser.new_context(
    viewport={'width': 1280, 'height': 720},
    locale='en-US',
)
page = context.new_page()

# Go to Facebook
page.goto('https://www.facebook.com/')
page.wait_for_load_state('networkidle')

print("=" * 50)
print("Browser is open. Please login to Facebook.")
print("After you're logged in, come back here and press Enter.")
print("=" * 50)

input("\nPress Enter after you've logged in...")

# Save cookies
cookies = context.cookies(['https://www.facebook.com', 'https://facebook.com'])
cookie_names = [c['name'] for c in cookies]
print(f"\nFound cookies: {cookie_names}")

if 'c_user' in cookie_names and 'xs' in cookie_names:
    # Save to file
    os.makedirs('sessions', exist_ok=True)
    with open('sessions/facebook-cookies.json', 'w', encoding='utf-8') as f:
        json.dump(cookies, f, indent=2)
    print("\n✅ Cookies saved to sessions/facebook-cookies.json")
    print("You can now use the app to post to groups!")
else:
    print("\n❌ Login cookies not found. Make sure you're fully logged in.")

browser.close()
playwright.stop()
