"""
Simple stable Facebook login - avoids crashes by using Firefox
"""
from playwright.sync_api import sync_playwright
import json
import os
import time

def login():
    print("=" * 50)
    print("FACEBOOK LOGIN")
    print("=" * 50)
    print("\nA browser will open - please login to Facebook")
    print("-" * 50)
    
    with sync_playwright() as p:
        # Use Firefox instead of Chromium - more stable with Facebook
        browser = p.firefox.launch(headless=False)
        
        context = browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0'
        )
        page = context.new_page()
        
        print("Opening Facebook...")
        page.goto("https://www.facebook.com", timeout=60000)
        print("\n>>> LOGIN TO FACEBOOK NOW <<<\n")
        
        # Check for login every 3 seconds for 5 minutes
        for i in range(100):
            time.sleep(3)
            try:
                cookies = context.cookies()
                names = {c['name'] for c in cookies}
                
                if 'c_user' in names and 'xs' in names:
                    print("\n" + "=" * 50)
                    print("*** LOGIN SUCCESSFUL! ***")
                    print("=" * 50)
                    
                    # Save cookies
                    os.makedirs('sessions', exist_ok=True)
                    with open('sessions/facebook-cookies.json', 'w') as f:
                        json.dump(cookies, f, indent=2)
                    
                    user_id = next(c['value'] for c in cookies if c['name'] == 'c_user')
                    print(f"\nUser ID: {user_id}")
                    print("Cookies saved to: sessions/facebook-cookies.json")
                    
                    browser.close()
                    return True
            except Exception as e:
                pass
            
            print(f"Waiting for login... ({i+1})")
        
        print("\nTimeout - login not detected")
        browser.close()
        return False

if __name__ == "__main__":
    # First install Firefox for Playwright
    print("Installing Firefox browser for Playwright...")
    os.system("python -m playwright install firefox")
    print("\n")
    
    if login():
        print("\n" + "=" * 50)
        print("SUCCESS!")
        print("=" * 50)
        print("\nNow:")
        print("1. Restart your Flask server: python app.py")
        print("2. Go to http://127.0.0.1:5000")
        print("3. Dashboard should show Facebook as Connected!")
    else:
        print("\nLogin failed - please try again")
    
    input("\nPress Enter to close...")
