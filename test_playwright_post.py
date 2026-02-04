"""Test Playwright posting to a single group"""
import os
import json
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import FacebookGroupSpam

def test_post():
    print("=" * 50)
    print("PLAYWRIGHT POSTING TEST")
    print("=" * 50)
    
    # Load groups
    groups_file = os.path.join(os.path.dirname(__file__), 'groups.json')
    with open(groups_file, 'r', encoding='utf-8') as f:
        groups = json.load(f)
    
    if not groups:
        print("ERROR: No groups found in groups.json")
        return
    
    print(f"Found {len(groups)} groups")
    print("\nAvailable groups:")
    for i, g in enumerate(groups[:10]):  # Show first 10
        print(f"  {i}: {g.get('name', 'Unknown')} (ID: {g.get('username', 'N/A')})")
    
    # Pick first group for test
    test_group = groups[0]
    print(f"\n>>> Testing with group: {test_group['name']}")
    
    # Create poster - use_persistent=False to avoid lock issues during testing
    test_content = "🔥 Test post from auto-poster - please ignore 🔥"
    poster = FacebookGroupSpam(post_content=test_content, headless=False, use_persistent=False)
    
    print("\nStarting browser...")
    poster.start_browser()
    
    print("Loading cookies...")
    cookie_path = os.path.join(os.path.dirname(__file__), 'sessions', 'facebook-cookies.json')
    print(f"Cookie path: {cookie_path}")
    print(f"Cookie exists: {os.path.exists(cookie_path)}")
    poster.load_cookie(cookie_path)
    
    print("\nPosting to group...")
    results = poster.post_to_groups([test_group])
    
    print("\n" + "=" * 50)
    print("RESULTS:")
    print("=" * 50)
    for r in results:
        status = "✅ SUCCESS" if r['success'] else "❌ FAILED"
        print(f"{status}: {r['name']}")
        if r.get('error'):
            print(f"   Error: {r['error']}")
    
    input("\nPress Enter to close browser...")
    poster.close_browser()
    print("Done!")

if __name__ == "__main__":
    test_post()
