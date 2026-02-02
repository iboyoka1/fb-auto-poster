"""Test posting in headless mode like Render"""
from playwright.sync_api import sync_playwright
import json
import time
import os

print("Testing HEADLESS mode (like Render)...")

pw = sync_playwright().start()
browser = pw.chromium.launch(
    headless=True,  # Same as Render
    args=[
        '--disable-blink-features=AutomationControlled',
        '--disable-dev-shm-usage',
        '--no-sandbox',
        '--disable-gpu',
    ]
)
ctx = browser.new_context(
    viewport={'width': 1280, 'height': 720},
    locale='en-US',
    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
)
page = ctx.new_page()

# Add stealth
page.add_init_script("""
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
""")

# Load cookies
print("Loading cookies...")
cookies = json.load(open('sessions/facebook-cookies.json'))
for c in cookies:
    if c.get('sameSite') not in ('Strict', 'Lax', 'None'):
        c['sameSite'] = 'Lax'
ctx.add_cookies(cookies)

# Warmup
print("Warming up session...")
page.goto('https://www.facebook.com/', timeout=60000)
time.sleep(5)
print(f"Warmup URL: {page.url}")
print(f"Warmup Title: {page.title()}")

# Go to group
print("\nGoing to group...")
page.goto('https://www.facebook.com/groups/992342774597629', timeout=60000)
time.sleep(5)
print(f"Group URL: {page.url}")
print(f"Group Title: {page.title()}")

# Save screenshot
os.makedirs('logs/debug', exist_ok=True)
page.screenshot(path='logs/debug/headless-group.png', full_page=True)
print("Screenshot saved to logs/debug/headless-group.png")

# Try selectors
print("\nTrying selectors...")

selectors_to_try = [
    ('div[role="button"]:has-text("Write")', 'Write button'),
    ('span:has-text("Write")', 'Write span'),
    ('div:has-text("Write something")', 'Write something div'),
]

for selector, name in selectors_to_try:
    try:
        el = page.locator(selector)
        count = el.count()
        print(f"  {name}: {count} found")
        if count > 0:
            print(f"    -> Clicking...")
            el.first.click(timeout=5000)
            print(f"    -> Clicked!")
            time.sleep(3)
            
            # Try typing
            print(f"    -> Typing message...")
            page.keyboard.type("Test from headless!", delay=50)
            time.sleep(2)
            
            # Save screenshot of composer
            page.screenshot(path='logs/debug/headless-composer.png')
            print("    -> Composer screenshot saved")
            
            # Try post button
            print(f"    -> Looking for Post button...")
            try:
                page.click('div[aria-label="Post"]', timeout=5000)
                print("    -> Posted!")
                time.sleep(5)
                page.screenshot(path='logs/debug/headless-posted.png')
            except Exception as e:
                print(f"    -> Post button failed: {e}")
            
            break
    except Exception as e:
        print(f"  {name}: Failed - {e}")

print("\nDone!")
browser.close()
pw.stop()
