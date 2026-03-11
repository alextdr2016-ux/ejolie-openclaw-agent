#!/usr/bin/env python3
import requests
import re

s = requests.Session()
s.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0",
    "Accept-Encoding": "gzip, deflate",
})

r = s.get("https://www.codul-postal.ro/judet/dolj", timeout=15)

# Show raw HTML around first 3 locality links
pattern = r'href="(/judet/dolj/([^"]+))"'
matches = re.findall(pattern, r.text)
print(f"Total links: {len(matches)}")

for path, slug in matches[:5]:
    # Show 300 chars around this link
    idx = r.text.find(f'href="{path}"')
    chunk = r.text[idx:idx+400]
    print(f"\n--- {slug} ---")
    print(chunk)
    print()

# Also show the Craiova page - first 3000 chars
print("\n\n=== CRAIOVA PAGE ===")
r2 = s.get("https://www.codul-postal.ro/judet/dolj/craiova", timeout=15)
print(f"Status: {r2.status_code}, Length: {len(r2.text)}")
print(r2.text[:3000])
