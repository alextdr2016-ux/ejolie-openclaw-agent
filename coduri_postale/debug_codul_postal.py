#!/usr/bin/env python3
"""Debug: ce returneaza codul-postal.ro pe EC2"""
import requests
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
}
s = requests.Session()
s.headers.update(HEADERS)

# 1. Pagina judete - Dolj
print("=== 1. PAGINA LOCALITATI DOLJ ===")
r1 = s.get("https://www.codul-postal.ro/judet/dolj", timeout=15)
print(f"Status: {r1.status_code}, Length: {len(r1.text)}")

# Caut link-uri
links = re.findall(r'href="(/judet/dolj/[^"]+)"', r1.text)
print(f"Links /judet/dolj/*: {len(links)}")
if links:
    print(f"First 5: {links[:5]}")

# Este site SSR sau SPA?
print(f"\nContains 'Craiova': {'Craiova' in r1.text}")
print(f"Contains '__NUXT': {'__NUXT' in r1.text}")
print(f"Contains 'nuxt': {'nuxt' in r1.text.lower()}")

# Chunk de HTML in jurul 'dolj'
idx = r1.text.lower().find('craiova')
if idx > -1:
    print(f"\nIn jurul 'Craiova' ({idx}):")
    print(r1.text[max(0, idx-200):idx+300])
else:
    print(f"\nCraiova NOT found in HTML! First 3000 chars:")
    print(r1.text[:3000])

# 2. Pagina Craiova direct
print("\n\n=== 2. PAGINA CRAIOVA ===")
r2 = s.get("https://www.codul-postal.ro/judet/dolj/craiova", timeout=15)
print(f"Status: {r2.status_code}, Length: {len(r2.text)}")
print(f"Contains '<table': {'<table' in r2.text}")
print(f"Contains '<tr': {'<tr' in r2.text}")

# Count rows
rows = re.findall(r'<tr[^>]*>', r2.text)
print(f"<tr> tags: {len(rows)}")

# Try 3-column pattern
pattern = r'<tr[^>]*>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*</tr>'
matches = re.findall(pattern, r2.text, re.DOTALL)
print(f"3-col rows: {len(matches)}")
if matches:
    print(f"First 3: {matches[:3]}")

# Try simpler pattern
tds = re.findall(r'<td[^>]*>(.*?)</td>', r2.text, re.DOTALL)
print(f"\nTotal <td>: {len(tds)}")
if tds:
    # Show some td content
    clean = [re.sub(r'<[^>]+>', '', t).strip() for t in tds[:15]]
    print(f"First 15 td values: {clean}")

# Check if data is in JSON/script tag (SPA)
scripts = re.findall(r'<script[^>]*>(.*?)</script>', r2.text, re.DOTALL)
for i, scr in enumerate(scripts):
    if '200' in scr and ('strada' in scr.lower() or 'cod' in scr.lower() or 'postal' in scr.lower()):
        print(f"\nScript #{i} has postal data! First 500 chars:")
        print(scr[:500])
        break

# Show chunk around first 200xxx code
idx2 = r2.text.find('200')
if idx2 > -1:
    print(f"\nAround first '200' ({idx2}):")
    print(r2.text[max(0, idx2-100):idx2+300])
