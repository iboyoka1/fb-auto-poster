"""Test if cookies are actually being used"""
from playwright.sync_api import sync_playwright
import json
import time

print("Starting fresh browser...")
playwright = sync_playwright().start()
browser = playwright.chromium.launch(headless=False)

# Create context with same settings as main.py
context = browser.new_context(
    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    viewport={'width': 1280, 'height': 720},
    locale='en-US',
)

page = context.new_page()

# Load cookies
print("Loading cookies...")
with open('sessions/facebook-cookies.json', 'r') as f:
    cookies = json.load(f)

# Sanitize cookies
sanitized = []
for c in cookies:
    cookie = dict(c)
    # Fix sameSite
    ss = cookie.get('sameSite', 'Lax')
    if ss not in ('Strict', 'Lax', 'None'):
        if ss.lower() in ('none', 'no_restriction', ''):
            cookie['sameSite'] = 'None'
        else:
            cookie['sameSite'] = 'Lax'
    # Ensure domain
    if not cookie.get('domain'):
        cookie['domain'] = '.facebook.com'
    # Only keep allowed fields
    allowed = {'name', 'value', 'domain', 'path', 'expires', 'httpOnly', 'secure', 'sameSite'}
    cookie = {k: v for k, v in cookie.items() if k in allowed}
    sanitized.append(cookie)

print(f"Adding {len(sanitized)} cookies...")
context.add_cookies(sanitized)

# Verify cookies
loaded = context.cookies(['https://www.facebook.com'])
print(f"Loaded cookies: {[c['name'] for c in loaded]}")

# First go to facebook.com to establish session
print("\nNavigating to facebook.com...")
page.goto('https://www.facebook.com/', timeout=30000)
page.wait_for_load_state('networkidle', timeout=30000)
time.sleep(3)

print(f"URL: {page.url}")
print(f"Title: {page.title()}")

# Check if logged in
if 'login' in page.url.lower() or 'login' in page.title().lower():
    print("!!! NOT LOGGED IN - on login page !!!")
else:
    print("Appears to be logged in!")

# Now try group
print("\nNavigating to group...")
page.goto('https://www.facebook.com/groups/992342774597629', timeout=30000)
page.wait_for_load_state('networkidle', timeout=30000)
time.sleep(3)

print(f"URL: {page.url}")
print(f"Title: {page.title()}")

# Save screenshot
page.screenshot(path='logs/debug/cookie-test.png', full_page=True)
print("Screenshot saved to logs/debug/cookie-test.png")

# Look for the composer now
print("\nLooking for composer elements...")
buttons = page.locator('div[role="button"]')
print(f"Found {buttons.count()} role=button elements")

# Get visible text on page for clues
page.screenshot(path='logs/debug/cookie-test-group.png')

input("\nCheck the browser. Are you logged in? Press Enter to close...")
browser.close()
playwright.stop()
