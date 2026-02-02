"""Test posting to Facebook group - visible browser"""
from playwright.sync_api import sync_playwright
import json
import time

print("Opening browser...")
pw = sync_playwright().start()
browser = pw.chromium.launch(headless=False, slow_mo=100)
ctx = browser.new_context(viewport={'width': 1280, 'height': 720}, locale='en-US')
page = ctx.new_page()

# Load cookies
print("Loading cookies...")
cookies = json.load(open('sessions/facebook-cookies.json'))
for c in cookies:
    if c.get('sameSite') not in ('Strict', 'Lax', 'None'):
        c['sameSite'] = 'Lax'
ctx.add_cookies(cookies)

# Go to group
print("Going to group...")
page.goto('https://www.facebook.com/groups/992342774597629', timeout=60000)
time.sleep(5)
print(f"Page: {page.title()}")

# Click composer area
print("Clicking composer...")
try:
    page.click('div[role="button"]:has-text("Write")', timeout=10000)
except:
    print("Trying alternative selector...")
    page.get_by_text("Write something").first.click()
time.sleep(3)

# Type message
print("Typing message...")
page.keyboard.type("Test post from automation! 🚀", delay=50)
time.sleep(2)

# Click Post
print("Clicking Post button...")
try:
    page.click('div[aria-label="Post"]', timeout=10000)
except:
    page.get_by_role("button", name="Post").click()
time.sleep(5)

print("✅ Done!")
input("Press Enter to close browser...")
browser.close()
pw.stop()
