"""Debug - find clickable post area on Facebook group"""
from main import FacebookGroupSpam
import time
import os

print("Starting browser (visible)...")
poster = FacebookGroupSpam(post_content='Test post content', headless=False)
poster.start_browser()

print("Loading cookies...")
poster.load_cookie()

# Go to a group
group_id = "992342774597629"
group_url = f"https://www.facebook.com/groups/{group_id}"

print(f"Navigating to: {group_url}")
poster.page.goto(group_url, timeout=30000)
poster.page.wait_for_load_state('networkidle', timeout=15000)
time.sleep(5)

print(f"Current URL: {poster.page.url}")

# Try clicking different things
print("\n--- Trying different click strategies ---")

# Strategy 1: Click on profile picture area (sometimes opens composer)
print("\nTrying to find composer trigger...")

# Try various selectors that might work for the new Facebook
strategies = [
    # New FB uses these
    ('Placeholder with Write', 'span:has-text("Write something...")'),
    ('Placeholder text', '[data-visualcompletion="ignore-dynamic"]:has-text("Write")'),
    ('Create post span', 'span:has-text("Create")'),
    ('Avatar area', 'div[role="button"] image'),
    # Generic approach
    ('First role=button with text', 'div[role="button"]'),
]

for name, selector in strategies:
    try:
        els = poster.page.locator(selector)
        count = els.count()
        print(f"{name} ({selector}): {count} found")
    except Exception as e:
        print(f"{name}: Error - {e}")

# Let's try to dump the HTML of the composer area
print("\n--- Saving page HTML for analysis ---")
html = poster.page.content()
with open('logs/debug/group-page.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("Saved HTML to logs/debug/group-page.html")

# Now try clicking where the composer should be
print("\n--- Manual interaction test ---")
print("Look at the browser window.")
print("The script will now try to click on the 'Write something' area.")

# Try finding by looking for specific aria-label or placeholder
try:
    # Facebook often uses aria-label
    composer = poster.page.locator('[aria-label*="Write something"], [aria-label*="Create a post"], [placeholder*="Write"]')
    if composer.count() > 0:
        print(f"Found {composer.count()} potential composer elements")
        composer.first.click()
        print("Clicked!")
        time.sleep(3)
except Exception as e:
    print(f"Composer click failed: {e}")

# Try another approach - click in the area where composer usually is
try:
    # Sometimes clicking on any "Write something" text works
    write_text = poster.page.get_by_text("Write something", exact=False)
    if write_text.count() > 0:
        print(f"Found 'Write something' text ({write_text.count()} matches)")
        write_text.first.click()
        print("Clicked on 'Write something' text!")
        time.sleep(3)
except Exception as e:
    print(f"Text click failed: {e}")

input("\nPress Enter to close browser...")
poster.close_browser()
