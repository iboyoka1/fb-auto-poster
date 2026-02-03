"""Test posting with visible browser to debug selectors"""
import json
import os
import time
from main import FacebookGroupSpam

# Load groups
with open('groups.json', 'r', encoding='utf-8') as f:
    groups = json.load(f)

# Use first group only
test_group = [groups[0]] if groups else []

if not test_group:
    print("No groups found!")
    exit(1)

print(f"Testing with group: {test_group[0]['name']}")

# Create poster with VISIBLE browser (headless=False)
poster = FacebookGroupSpam(
    post_content="Test post from visible browser - " + str(int(time.time())),
    headless=False,  # VISIBLE!
    media_files=None
)

try:
    print("Starting browser (VISIBLE MODE)...")
    poster.start_browser()
    
    print("Loading cookies...")
    poster.load_cookie()
    
    print("Posting to group...")
    results = poster.post_to_groups(test_group)
    
    print("\n=== RESULTS ===")
    for r in results:
        status = "✓ SUCCESS" if r['success'] else f"✗ FAILED: {r['error']}"
        print(f"  {r['name']}: {status}")
        
finally:
    input("\nPress ENTER to close browser...")
    poster.close_browser()
