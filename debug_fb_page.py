"""Debug script to analyze Facebook group page structure"""
import json
import time
from playwright.sync_api import sync_playwright

# Load cookies
with open('sessions/facebook-cookies.json', 'r') as f:
    cookies = json.load(f)

# Load groups
with open('groups.json', 'r', encoding='utf-8') as f:
    groups = json.load(f)

group_id = groups[0]['username'] if groups else '992342774597629'
print(f"Testing group ID: {group_id}")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        viewport={'width': 1280, 'height': 720}
    )
    page = context.new_page()
    
    # Add stealth
    page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    """)
    
    # Sanitize and add cookies
    for cookie in cookies:
        c = dict(cookie)
        same_site = c.get('sameSite', 'Lax')
        if same_site not in ('Strict', 'Lax', 'None'):
            c['sameSite'] = 'Lax'
        if 'domain' not in c or not c['domain']:
            c['domain'] = '.facebook.com'
        allowed = {'name', 'value', 'domain', 'path', 'expires', 'httpOnly', 'secure', 'sameSite'}
        c = {k: v for k, v in c.items() if k in allowed}
        try:
            context.add_cookies([c])
        except:
            pass
    
    print("Cookies loaded, navigating to Facebook...")
    
    # Warm up
    page.goto('https://www.facebook.com/', timeout=60000)
    page.wait_for_load_state('networkidle', timeout=30000)
    time.sleep(3)
    
    print(f"Current URL: {page.url}")
    
    # Go to group
    print(f"\nNavigating to group...")
    page.goto(f'https://www.facebook.com/groups/{group_id}', timeout=60000)
    page.wait_for_load_state('networkidle', timeout=30000)
    time.sleep(5)
    
    print(f"Group URL: {page.url}")
    
    # Save HTML for analysis
    html = page.content()
    with open('logs/debug_group_page.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("Saved HTML to logs/debug_group_page.html")
    
    # Screenshot
    page.screenshot(path='logs/debug_group_page.png')
    print("Saved screenshot to logs/debug_group_page.png")
    
    # Try to find composer elements
    print("\n=== SEARCHING FOR COMPOSER ELEMENTS ===")
    
    selectors_to_try = [
        ('div[role="button"]:has-text("Write")', 'Write button'),
        ('div[role="textbox"]', 'Textbox role'),
        ('div[contenteditable="true"]', 'Contenteditable'),
        ('div[data-contents="true"]', 'Data contents'),
        ('span:has-text("Write")', 'Span with Write'),
        ('div[aria-label*="Create"]', 'Create aria-label'),
        ('div[aria-label*="post"]', 'Post aria-label'),
        ('form', 'Any form'),
    ]
    
    for selector, name in selectors_to_try:
        try:
            elements = page.query_selector_all(selector)
            if elements:
                print(f"✓ Found {len(elements)} elements: {name}")
                for i, el in enumerate(elements[:3]):  # Show first 3
                    try:
                        text = el.text_content()[:50] if el.text_content() else "(no text)"
                        visible = el.is_visible()
                        print(f"    [{i}] visible={visible}, text={text}")
                    except:
                        print(f"    [{i}] (error getting info)")
            else:
                print(f"✗ Not found: {name}")
        except Exception as e:
            print(f"✗ Error with {name}: {e}")
    
    print("\n=== LOOKING FOR ANY CLICKABLE AREAS ===")
    buttons = page.query_selector_all('div[role="button"]')
    print(f"Found {len(buttons)} div[role='button'] elements")
    for i, btn in enumerate(buttons[:10]):
        try:
            text = btn.text_content()
            if text and len(text.strip()) < 50:
                print(f"  Button {i}: '{text.strip()}'")
        except:
            pass
    
    input("\nPress ENTER to close browser...")
    browser.close()
