"""Debug what's on the Facebook group page"""
from main import FacebookGroupSpam
import time
import os

print("Starting browser (visible)...")
poster = FacebookGroupSpam(post_content='Test', headless=False)
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
print(f"Page title: {poster.page.title()}")

# Save screenshot
os.makedirs('logs/debug', exist_ok=True)
poster.page.screenshot(path='logs/debug/group-page.png', full_page=True)
print("Saved screenshot to logs/debug/group-page.png")

# Try to find elements
print("\n--- Looking for post box elements ---")

# Check various selectors
selectors_to_try = [
    ('Write something button', 'button:has-text("Write something")'),
    ('Write something div', 'div[role="button"]:has-text("Write something")'),
    ('Create post', 'div:has-text("Create a post")'),
    ('Whats on your mind', 'div:has-text("What\'s on your mind")'),
    ('Any textbox', 'div[role="textbox"]'),
    ('Contenteditable', 'div[contenteditable="true"]'),
    ('Composer area', 'div[data-pagelet="GroupInlineComposer"]'),
    ('Post composer', 'div[aria-label*="post"]'),
    ('Write post', 'span:has-text("Write")'),
]

for name, selector in selectors_to_try:
    try:
        els = poster.page.locator(selector)
        count = els.count()
        print(f"{name}: {count} found")
        if count > 0:
            # Try to get text
            try:
                text = els.first.text_content()[:100] if els.first.text_content() else "N/A"
                print(f"  -> First element text: {text}")
            except:
                pass
    except Exception as e:
        print(f"{name}: Error - {e}")

print("\n--- Looking for all clickable elements with post-related text ---")
try:
    # Get all text on page
    body_text = poster.page.locator('body').text_content()
    if 'Write' in body_text:
        print("'Write' found on page")
    if 'post' in body_text.lower():
        print("'post' found on page")
    if 'something' in body_text.lower():
        print("'something' found on page")
except Exception as e:
    print(f"Error getting page text: {e}")

input("\nPress Enter to close browser...")
poster.close_browser()
