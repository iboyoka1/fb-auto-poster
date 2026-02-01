#!/usr/bin/env python
"""Test posting to Facebook groups"""
import sys
import json

# Add project to path
sys.path.insert(0, '.')

from main import FacebookGroupSpam

def test_posting():
    # Load groups
    with open('groups.json', 'r', encoding='utf-8') as f:
        groups = json.load(f)
    
    print(f"Found {len(groups)} groups")
    test_group = groups[0]
    print(f"Testing with group: {test_group.get('name', 'Unknown')} (ID: {test_group['username']})")
    
    # Create poster
    print("\n1. Creating FacebookGroupSpam...")
    poster = FacebookGroupSpam(post_content="Test post from automation", headless=False)  # headless=False to see what happens
    
    print("2. Starting browser...")
    poster.start_browser()
    
    print("3. Loading cookies...")
    poster.load_cookie()
    
    print("4. Posting to group...")
    results = poster.post_to_groups([test_group])
    
    print(f"\n5. Results: {json.dumps(results, indent=2, default=str)}")
    
    print("6. Closing browser...")
    poster.close_browser()
    
    print("\nDone!")

if __name__ == '__main__':
    test_posting()
