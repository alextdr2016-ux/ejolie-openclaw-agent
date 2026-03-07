#!/usr/bin/env python3
"""
Test Trendyol API Connection (v2 - URL corectat)
==================================================
Base URL corect: https://api.trendyol.com/sapigw/suppliers/{sellerId}/

Rulează: python3 test_trendyol_api.py
"""

import os
import sys
import json
import base64
import requests
from dotenv import load_dotenv

# --- Pas 1: Încarcă variabilele din .env ---
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
env_path = os.path.join(parent_dir, '.env')
if not os.path.exists(env_path):
    env_path = os.path.join(script_dir, '.env')

load_dotenv(env_path)
print(f"✅ Loaded .env from: {env_path}")

# --- Pas 2: Citește credențialele ---
SELLER_ID = os.getenv('TRENDYOL_SELLER_ID')
API_KEY = os.getenv('TRENDYOL_API_KEY')
API_SECRET = os.getenv('TRENDYOL_API_SECRET')

missing = []
if not SELLER_ID: missing.append('TRENDYOL_SELLER_ID')
if not API_KEY: missing.append('TRENDYOL_API_KEY')
if not API_SECRET: missing.append('TRENDYOL_API_SECRET')

if missing:
    print(f"❌ Lipsesc variabile din .env: {', '.join(missing)}")
    sys.exit(1)

print(f"✅ Seller ID: {SELLER_ID}")
print(f"✅ API Key: {API_KEY[:6]}...")
print(f"✅ API Secret: {API_SECRET[:6]}...")

# --- Pas 3: Pregătește autentificarea ---
auth_string = f"{API_KEY}:{API_SECRET}"
auth_base64 = base64.b64encode(auth_string.encode()).decode()

headers = {
    "Authorization": f"Basic {auth_base64}",
    "Content-Type": "application/json",
    "User-Agent": f"{SELLER_ID} - SelfIntegration"
}

# --- Pas 4: Test GET — Citește produsele ---
BASE_URL = "https://api.trendyol.com/sapigw"

print("\n" + "="*60)
print("TEST 1: GET Products (prima pagină, 10 produse)")
print("="*60)

url = f"{BASE_URL}/suppliers/{SELLER_ID}/products?page=0&size=10"
print(f"📡 GET {url}")

try:
    response = requests.get(url, headers=headers, timeout=30)
    print(f"📊 Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        
        total = data.get('totalElements', 'N/A')
        page = data.get('page', 'N/A')
        size = data.get('size', 'N/A')
        print(f"✅ Total produse pe Trendyol: {total}")
        print(f"📄 Pagina: {page}, Size: {size}")
        
        products = data.get('content', [])
        if products:
            print(f"\n📦 Primele {min(len(products), 5)} produse:")
            print("-" * 80)
            for i, p in enumerate(products[:5]):
                barcode = p.get('barcode', 'N/A')
                title = p.get('title', 'N/A')[:50]
                quantity = p.get('quantity', 'N/A')
                sale_price = p.get('salePrice', 'N/A')
                list_price = p.get('listPrice', 'N/A')
                approved = p.get('approved', 'N/A')
                on_sale = p.get('onSale', 'N/A')
                print(f"  {i+1}. Barcode: {barcode}")
                print(f"     Title: {title}")
                print(f"     Stoc: {quantity} | Preț: {sale_price} | List: {list_price}")
                print(f"     Aprobat: {approved} | La vânzare: {on_sale}")
                print()
        else:
            print("⚠️ Nu s-au returnat produse (lista goală)")
            
    elif response.status_code == 401:
        print("❌ EROARE 401 — Credențiale invalide!")
        print(f"   Response: {response.text[:500]}")
    elif response.status_code == 403:
        print("❌ EROARE 403 — Acces interzis!")
        print(f"   Response: {response.text[:500]}")
    else:
        print(f"❌ EROARE {response.status_code}")
        print(f"   Response: {response.text[:500]}")
        
except requests.exceptions.Timeout:
    print("❌ TIMEOUT — Trendyol API nu a răspuns în 30 secunde")
except requests.exceptions.ConnectionError as e:
    print(f"❌ CONNECTION ERROR: {e}")
except Exception as e:
    print(f"❌ EROARE NEAȘTEPTATĂ: {e}")

# --- Pas 5: DRY RUN stock update ---
print("\n" + "="*60)
print("TEST 2: Stock & Price Update (DRY RUN)")
print("="*60)

update_url = f"{BASE_URL}/suppliers/{SELLER_ID}/products/price-and-inventory"
print(f"📡 URL PUT: {update_url}")

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
print(f"📦 Exemplu payload:")
print(json.dumps(example_payload, indent=2))
print(f"\n⚠️ DRY RUN — nu s-a trimis nimic.")

# --- Rezultat ---
print("\n" + "="*60)
print("REZULTAT FINAL")
print("="*60)
if response.status_code == 200:
    print("✅ Conexiunea la Trendyol API FUNCȚIONEAZĂ!")
    print("   Putem trece la scriptul de sync complet.")
else:
    print(f"❌ Status {response.status_code} — trebuie investigat.")
