#!/usr/bin/env python3
"""
Test Trendyol API Connection
=============================
Verifică dacă credențialele funcționează și citește produsele de pe Trendyol.

Rulează: python3 test_trendyol_api.py
Locație pe server: ~/ejolie-openclaw-agent/ejolie-sales/scripts/
"""

import os
import sys
import json
import base64
import requests
from dotenv import load_dotenv

# --- Pas 1: Încarcă variabilele din .env ---
# Caută .env în directorul părinte (ejolie-sales/)
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
env_path = os.path.join(parent_dir, '.env')

# Dacă nu e în parent, caută în același director
if not os.path.exists(env_path):
    env_path = os.path.join(script_dir, '.env')

load_dotenv(env_path)
print(f"✅ Loaded .env from: {env_path}")

# --- Pas 2: Citește credențialele ---
SELLER_ID = os.getenv('TRENDYOL_SELLER_ID')
API_KEY = os.getenv('TRENDYOL_API_KEY')
API_SECRET = os.getenv('TRENDYOL_API_SECRET')

# Verifică că avem totul
missing = []
if not SELLER_ID:
    missing.append('TRENDYOL_SELLER_ID')
if not API_KEY:
    missing.append('TRENDYOL_API_KEY')
if not API_SECRET:
    missing.append('TRENDYOL_API_SECRET')

if missing:
    print(f"❌ Lipsesc variabile din .env: {', '.join(missing)}")
    sys.exit(1)

print(f"✅ Seller ID: {SELLER_ID}")
print(f"✅ API Key: {API_KEY[:6]}...")
print(f"✅ API Secret: {API_SECRET[:6]}...")

# --- Pas 3: Pregătește autentificarea ---
# Trendyol folosește Basic Auth: base64(API_KEY:API_SECRET)
auth_string = f"{API_KEY}:{API_SECRET}"
auth_base64 = base64.b64encode(auth_string.encode()).decode()

headers = {
    "Authorization": f"Basic {auth_base64}",
    "Content-Type": "application/json",
    # Trendyol recomandă acest format
    "User-Agent": f"{SELLER_ID} - SelfIntegration"
}

# --- Pas 4: Test GET — Citește produsele ---
BASE_URL = "https://apigw.trendyol.com/integration"

print("\n" + "="*60)
print("TEST 1: GET Products (prima pagină, 10 produse)")
print("="*60)

url = f"{BASE_URL}/inventory/sellers/{SELLER_ID}/products?page=0&size=10"
print(f"📡 GET {url}")

try:
    response = requests.get(url, headers=headers, timeout=30)
    print(f"📊 Status Code: {response.status_code}")

    if response.status_code == 200:
        data = response.json()

        # Afișează info generale
        total = data.get('totalElements', 'N/A')
        page = data.get('page', 'N/A')
        size = data.get('size', 'N/A')
        print(f"✅ Total produse pe Trendyol: {total}")
        print(f"📄 Pagina: {page}, Size: {size}")

        # Afișează primele produse
        products = data.get('content', [])
        if products:
            print(f"\n📦 Primele {len(products)} produse:")
            print("-" * 80)
            for i, p in enumerate(products[:5]):
                barcode = p.get('barcode', 'N/A')
                title = p.get('title', 'N/A')[:50]
                quantity = p.get('quantity', 'N/A')
                sale_price = p.get('salePrice', 'N/A')
                list_price = p.get('listPrice', 'N/A')
                approved = p.get('approved', 'N/A')
                print(f"  {i+1}. Barcode: {barcode}")
                print(f"     Title: {title}")
                print(
                    f"     Stoc: {quantity} | Preț vânzare: {sale_price} | List price: {list_price}")
                print(f"     Aprobat: {approved}")
                print()
        else:
            print("⚠️ Nu s-au returnat produse (lista goală)")

    elif response.status_code == 401:
        print("❌ EROARE 401 — Credențiale invalide!")
        print("   Verifică API Key și API Secret în .env")
        print(f"   Response: {response.text[:500]}")
    elif response.status_code == 403:
        print("❌ EROARE 403 — Acces interzis!")
        print("   Seller ID-ul poate fi greșit sau contul nu are permisiuni API")
        print(f"   Response: {response.text[:500]}")
    else:
        print(f"❌ EROARE {response.status_code}")
        print(f"   Response: {response.text[:500]}")

except requests.exceptions.Timeout:
    print("❌ TIMEOUT — Trendyol API nu a răspuns în 30 secunde")
except requests.exceptions.ConnectionError as e:
    print(f"❌ CONNECTION ERROR — Nu se poate conecta la Trendyol API: {e}")
except Exception as e:
    print(f"❌ EROARE NEAȘTEPTATĂ: {e}")

# --- Pas 5: Test Stock & Price Update (DRY RUN — doar afișează payload) ---
print("\n" + "="*60)
print("TEST 2: Stock & Price Update (DRY RUN — NU trimite nimic)")
print("="*60)

# Construim un exemplu de payload
example_payload = {
    "items": [
        {
            "barcode": "2000000000015",
            "quantity": 5,
            "salePrice": 489.00,
            "listPrice": 489.00
        }
    ]
}

update_url = f"{BASE_URL}/inventory/sellers/{SELLER_ID}/products/price-and-inventory"
print(f"📡 URL care va fi folosit: PUT {update_url}")
print(f"📦 Exemplu payload:")
print(json.dumps(example_payload, indent=2))
print(f"\n⚠️ Acesta e doar un DRY RUN — nu s-a trimis nimic.")
print(f"   Când confirmă Alex, vom face un test real pe un singur produs.")

print("\n" + "="*60)
print("REZULTAT FINAL")
print("="*60)
if response.status_code == 200:
    print("✅ Conexiunea la Trendyol API FUNCȚIONEAZĂ!")
    print("   Putem trece la scriptul de sync complet.")
else:
    print("❌ Conexiunea NU funcționează. Trebuie investigat.")
