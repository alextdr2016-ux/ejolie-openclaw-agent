#!/usr/bin/env python3
import os
import sys
import requests
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(SCRIPT_DIR, '..', '.env')

# Load .env
if os.path.exists(ENV_PATH):
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                os.environ[key.strip()] = val.strip()

EXTENDED_EMAIL = os.environ.get('EXTENDED_EMAIL')
EXTENDED_PASSWORD = os.environ.get('EXTENDED_PASSWORD')
ADMIN_BASE = 'https://www.ejolie.ro/manager'
HEADERS = {'User-Agent': 'Mozilla/5.0'}

session = requests.Session()
session.headers.update(HEADERS)

print("🔐 Logging in...")
session.post(f'{ADMIN_BASE}/login/autentificare', data={
    'utilizator': EXTENDED_EMAIL,
    'parola': EXTENDED_PASSWORD
})

print("📥 Fetching product 9150...")
url = f'{ADMIN_BASE}/produse/detalii/9150'
r = session.get(url, timeout=30)

print(f"Status code: {r.status_code}")
print(f"Response length: {len(r.text)} chars")

# Check for camp_descriere
desc_match = re.search(r"name=[\"']camp_descriere[\"'][^>]*value=[\"']([^\"']*)[\"']", r.text)
if not desc_match:
    desc_match = re.search(r"name=[\"']camp_descriere[\"'][^>]*>(.*?)</textarea>", r.text, re.DOTALL)

if desc_match:
    desc = desc_match.group(1)
    print(f'\n✅ Found camp_descriere: {len(desc)} chars')
    print(f'First 300 chars:\n{desc[:300]}')
    print(f'...')
    print(f'Last 100 chars:\n{desc[-100:]}')
else:
    print('\n❌ No camp_descriere found!')
    print('\nSearching for any textareas...')
    textareas = re.findall(r"<textarea[^>]*name=[\"']([^\"']*)[\"'][^>]*>", r.text)
    print(f'Found textareas with names: {textareas}')
    
    # Try to find any description field
    desc_fields = re.findall(r'(descriere[^"\']*)', r.text, re.IGNORECASE)
    print(f'\nFields containing "descriere": {set(desc_fields[:20])}')
