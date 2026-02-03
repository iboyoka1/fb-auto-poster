"""Test posting to a single group"""
import time
from main import FacebookGroupSpam

test_group = [{'username': '3782643445397239', 'name': 'Test Group'}]

poster = FacebookGroupSpam(
    post_content='Test post ' + str(int(time.time())),
    headless=False,
    media_files=None
)

print('Starting browser...')
poster.start_browser()
print('Loading cookies...')
poster.load_cookie()
print('Posting to group 3782643445397239...')
results = poster.post_to_groups(test_group)

for r in results:
    if r['success']:
        print(f"SUCCESS: Posted to {r['name']}")
    else:
        print(f"FAILED: {r['error']}")

input('Press ENTER to close...')
poster.close_browser()
