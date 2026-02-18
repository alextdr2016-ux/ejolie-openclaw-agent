#!/usr/bin/env python3
import os
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

# Search for camp_descriere in different ways
print("\n=== Searching for 'camp_descriere' field ===\n")

# Method 1: Look for textarea
textarea_match = re.search(r'<textarea[^>]*name="camp_descriere"[^>]*>(.*?)</textarea>', r.text, re.DOTALL)
if textarea_match:
    print(f"✅ Found as textarea: {len(textarea_match.group(1))} chars")
    print(f"Content: {textarea_match.group(1)[:200]}...")
else:
    print("❌ Not found as textarea")

# Method 2: Look for input with value
input_match = re.search(r'<input[^>]*name="camp_descriere"[^>]*value="([^"]*)"', r.text)
if input_match:
    print(f"✅ Found as input: {len(input_match.group(1))} chars")
    print(f"Content: {input_match.group(1)[:200]}...")
else:
    print("❌ Not found as input")

# Method 3: Look for hidden field or div
hidden_match = re.search(r'name="camp_descriere"[^>]*value="([^"]*)"', r.text)
if hidden_match:
    print(f"✅ Found with value attribute: {len(hidden_match.group(1))} chars")
    print(f"Content: {hidden_match.group(1)[:200]}...")
else:
    print("❌ Not found with value attribute")

# Method 4: Look for JavaScript initialization
js_match = re.search(r'camp_descriere["\']?\s*[:=]\s*["\']([^"\']*)', r.text)
if js_match:
    print(f"✅ Found in JavaScript: {len(js_match.group(1))} chars")
    print(f"Content: {js_match.group(1)[:200]}...")
else:
    print("❌ Not found in JavaScript")

# Let's save a snippet around where camp_descriere should be
snippet_match = re.search(r'.{500}camp_descriere.{500}', r.text, re.DOTALL)
if snippet_match:
    print(f"\n=== Context around 'camp_descriere' ===\n")
    print(snippet_match.group(0))

print("\n=== All form fields (first 30) ===\n")
all_inputs = re.findall(r'<(?:input|textarea|select)[^>]*name="([^"]*)"', r.text)
for i, name in enumerate(all_inputs[:30]):
    print(f"{i+1}. {name}")
