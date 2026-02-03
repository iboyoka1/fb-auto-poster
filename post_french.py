"""Post to Facebook group with French locale support"""
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
group_name = groups[0]['name'] if groups else 'Test Group'
post_content = f"Test post {int(time.time())}"

print(f"Posting to: {group_name}")
print(f"Content: {post_content}")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=100)
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
    
    print("1. Going to Facebook...")
    page.goto('https://www.facebook.com/', timeout=60000)
    time.sleep(3)
    
    print(f"2. Going to group {group_id}...")
    page.goto(f'https://www.facebook.com/groups/{group_id}', timeout=60000)
    page.wait_for_load_state('networkidle', timeout=30000)
    time.sleep(5)
    
    # Scroll to trigger lazy load
    page.evaluate("window.scrollBy(0, 300)")
    time.sleep(2)
    page.evaluate("window.scrollTo(0, 0)")
    time.sleep(2)
    
    print("3. Looking for composer...")
    
    # Try multiple selectors for different languages
    composer_selectors = [
        # English
        'div[role="button"]:has-text("Write")',
        'span:has-text("Write something")',
        # French
        'div[role="button"]:has-text("Écrire")',
        'div[role="button"]:has-text("Exprimez")',
        'span:has-text("Exprimez-vous")',
        'span:has-text("Écrire quelque chose")',
        # Arabic
        'div[role="button"]:has-text("اكتب")',
        # Generic
        'div[role="textbox"]',
        'div[contenteditable="true"]',
        # New Facebook structure - look for composer container
        'div[class*="x1lliihq"]:has-text("Write")',
        'div[class*="x1lliihq"]:has-text("Écrire")',
        'div[class*="x1lliihq"]:has-text("Exprimez")',
    ]
    
    clicked = False
    for selector in composer_selectors:
        try:
            el = page.locator(selector).first
            if el.is_visible(timeout=2000):
                print(f"   Found: {selector}")
                el.click()
                clicked = True
                break
        except:
            pass
    
    if not clicked:
        print("   Could not find composer with standard selectors")
        print("   Trying to click by visible text...")
        
        # Try clicking any element with these texts
        texts_to_try = ["Write", "Écrire", "Exprimez", "اكتب", "post", "publication"]
        for text in texts_to_try:
            try:
                el = page.get_by_text(text, exact=False).first
                if el.is_visible(timeout=1000):
                    print(f"   Found text: {text}")
                    el.click()
                    clicked = True
                    break
            except:
                pass
    
    if clicked:
        print("4. Waiting for composer dialog...")
        time.sleep(3)
        
        print("5. Typing content...")
        page.keyboard.type(post_content, delay=50)
        time.sleep(2)
        
        print("6. Looking for Post button...")
        post_selectors = [
            'div[aria-label="Post"]',
            'div[aria-label="Publier"]',
            'div[aria-label="نشر"]',
            'span:has-text("Post")',
            'span:has-text("Publier")',
        ]
        
        posted = False
        for selector in post_selectors:
            try:
                btn = page.locator(selector).first
                if btn.is_visible(timeout=2000):
                    print(f"   Found post button: {selector}")
                    btn.click()
                    posted = True
                    break
            except:
                pass
        
        if not posted:
            print("   Trying Ctrl+Enter...")
            page.keyboard.press('Control+Enter')
            posted = True
        
        if posted:
            print("7. Waiting for post to complete...")
            time.sleep(5)
            print("\n✓ POST ATTEMPTED!")
        else:
            print("\n✗ Could not find Post button")
    else:
        print("\n✗ Could not find composer - taking screenshot...")
        page.screenshot(path='logs/no_composer_found.png')
        
        # Print all visible buttons for debugging
        print("\nVisible buttons on page:")
        buttons = page.query_selector_all('div[role="button"]')
        for btn in buttons[:15]:
            try:
                text = btn.text_content()
                if text and btn.is_visible() and len(text.strip()) < 100:
                    print(f"  - {text.strip()[:60]}")
            except:
                pass
    
    input("\nPress ENTER to close browser...")
    browser.close()
