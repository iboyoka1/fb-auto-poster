"""Quick test to verify if Facebook session works"""
from main import FacebookGroupSpam
import time

print("Starting browser...")
poster = FacebookGroupSpam(post_content='Test', headless=True)  # HEADLESS mode like Render
poster.start_browser()

print("Loading cookies...")
poster.load_cookie()

print("Navigating to Facebook...")
poster.page.goto('https://www.facebook.com/')
poster.page.wait_for_load_state('networkidle')
time.sleep(5)

url = poster.page.url
title = poster.page.title()
print(f"Current URL: {url}")
print(f"Page title: {title}")

if 'login' in url.lower():
    print("\n❌ RESULT: Session NOT valid - redirected to login")
else:
    print("\n✅ RESULT: Session appears valid!")

input("\nPress Enter to close browser...")
poster.close_browser()
