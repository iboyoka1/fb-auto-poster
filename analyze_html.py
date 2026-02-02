"""Analyze the HTML to find the correct selector"""
import re

html = open('logs/debug/group-page.html', encoding='utf-8').read()

print("=== Looking for aria-label with Write ===")
matches = re.findall(r'aria-label="[^"]*[Ww]rite[^"]*"', html)
print(f"Found {len(matches)} matches:")
for m in matches[:10]:
    print(f"  {m}")

print("\n=== Looking for aria-label with post ===")
matches = re.findall(r'aria-label="[^"]*[Pp]ost[^"]*"', html)
print(f"Found {len(matches)} matches:")
for m in matches[:10]:
    print(f"  {m}")

print("\n=== Looking for aria-label with create ===")
matches = re.findall(r'aria-label="[^"]*[Cc]reate[^"]*"', html)
print(f"Found {len(matches)} matches:")
for m in matches[:10]:
    print(f"  {m}")

print("\n=== Looking for placeholder attributes ===")
matches = re.findall(r'placeholder="[^"]*"', html)
print(f"Found {len(matches)} matches:")
for m in matches[:10]:
    print(f"  {m}")

print("\n=== Looking for data-pagelet ===")
matches = re.findall(r'data-pagelet="[^"]*"', html)
print(f"Found {len(matches)} matches:")
for m in matches[:20]:
    print(f"  {m}")
