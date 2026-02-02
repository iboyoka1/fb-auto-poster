"""Try posting using direct URL approach"""
from main import FacebookGroupSpam
import time

print("Starting browser (visible)...")
poster = FacebookGroupSpam(post_content='Test post from automation 🚀', headless=False)
poster.start_browser()

print("Loading cookies...")
poster.load_cookie()

# Instead of navigating to group and finding composer, 
# try going directly to the compose URL
group_id = "992342774597629"

# Method 1: Direct compose URL (if Facebook supports it)
# compose_url = f"https://www.facebook.com/groups/{group_id}/?should_open_composer=true"
# Method 2: Use mobile site which has simpler HTML
# mobile_url = f"https://m.facebook.com/groups/{group_id}"

print("\n=== Method: Standard group page with Tab navigation ===")
group_url = f"https://www.facebook.com/groups/{group_id}"
poster.page.goto(group_url, timeout=30000)
poster.page.wait_for_load_state('networkidle', timeout=15000)
time.sleep(5)

print("Page loaded. Trying to find and click composer...")

# Try clicking using coordinates - the composer is usually near the top
# First take screenshot to see layout
poster.page.screenshot(path='logs/debug/before-click.png')

# Try pressing Tab multiple times to reach the composer
print("Pressing Tab to navigate...")
for i in range(5):
    poster.page.keyboard.press('Tab')
    time.sleep(0.3)

# Press Enter to activate
poster.page.keyboard.press('Enter')
time.sleep(2)
poster.page.screenshot(path='logs/debug/after-tab-enter.png')

# Check if dialog opened by looking for textbox
textbox = poster.page.locator('div[contenteditable="true"][role="textbox"]')
if textbox.count() > 0:
    print("SUCCESS! Textbox found after Tab+Enter")
    textbox.first.click()
    poster.page.keyboard.type("Test message!", delay=50)
else:
    print("No textbox found after Tab+Enter")
    
    # Try different approach: look for the actual composer element
    print("\nTrying direct click on visible text...")
    
    # Get all role=button elements and check their text
    buttons = poster.page.locator('div[role="button"]')
    for i in range(buttons.count()):
        try:
            text = buttons.nth(i).text_content()
            if text and ('write' in text.lower() or 'something' in text.lower() or 'post' in text.lower()):
                print(f"Found button {i}: {text[:50]}...")
                buttons.nth(i).click()
                time.sleep(2)
                break
        except:
            pass

poster.page.screenshot(path='logs/debug/final-state.png')
print("\nScreenshots saved to logs/debug/")

input("\nBrowser is open. Try clicking manually on 'Write something' and watch what happens.\nPress Enter when done...")
poster.close_browser()
