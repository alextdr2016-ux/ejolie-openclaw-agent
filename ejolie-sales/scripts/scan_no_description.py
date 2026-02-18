#!/usr/bin/env python3
"""
scan_no_description.py - Scanează produse ejolie.ro fără descriere
Fetch toate produsele cu stoc > 0, verifică câmpul 'descriere'
Exportă rezultat în JSON + Excel
"""

import os
import sys
import json
import time
import requests
from datetime import datetime

# --- Config ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(SCRIPT_DIR, '..', '.env')

# Load .env manual (fara python-dotenv)


def load_env(path):
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, val = line.split('=', 1)
                    os.environ[key.strip()] = val.strip()


load_env(ENV_PATH)

API_KEY = os.environ.get('EJOLIE_API_KEY', '')
BASE_URL = 'https://ejolie.ro/api/'
HEADERS = {'User-Agent': 'Mozilla/5.0'}

if not API_KEY:
    print("❌ EJOLIE_API_KEY nu e setat in .env!")
    sys.exit(1)

# --- Step 1: Fetch toate ID-urile produselor ---


def fetch_all_product_ids():
    """Fetch lista completa de ID-uri produse (paginat)"""
    all_ids = []
    page = 1
    while True:
        url = f"{BASE_URL}?produse&apikey={API_KEY}&pagina={page}&limit=200"
        print(f"  📥 Pagina {page}...", end=' ')
        try:
            r = requests.get(url, headers=HEADERS, timeout=180)
            data = r.json()
            if not data:
                print("gol - terminat")
                break
            ids = list(data.keys())
            all_ids.extend(ids)
            print(f"{len(ids)} produse")
            if len(ids) < 200:
                break
            page += 1
            time.sleep(0.5)
        except Exception as e:
            print(f"❌ Eroare: {e}")
            break
    return all_ids

# --- Step 2: Fetch detalii in batch ---


def fetch_product_details(ids, batch_size=20):
    """Fetch detalii produse in batch-uri de 20"""
    all_products = []
    total = len(ids)
    for i in range(0, total, batch_size):
        batch = ids[i:i+batch_size]
        batch_str = ','.join(batch)
        url = f"{BASE_URL}?produse&id_produse={batch_str}&apikey={API_KEY}"
        print(
            f"  📦 Batch {i//batch_size + 1}/{(total-1)//batch_size + 1} ({len(batch)} produse)...", end=' ')
        try:
            r = requests.get(url, headers=HEADERS, timeout=180)
            data = r.json()
            if data:
                for pid, prod in data.items():
                    all_products.append(prod)
                print(f"✅ {len(data)} primite")
            else:
                print("⚠️ gol")
            time.sleep(0.3)
        except Exception as e:
            print(f"❌ {e}")
            time.sleep(1)
    return all_products

# --- Step 3: Analizeaza descrieri ---


def analyze_descriptions(products):
    """Clasifică produsele: cu/fără descriere, stoc"""
    results = {
        'no_description': [],    # stoc > 0, fara descriere
        'has_description': [],   # stoc > 0, cu descriere
        'out_of_stock': 0,       # fara stoc (skip)
        'short_description': []  # stoc > 0, descriere < 50 chars (suspicioase)
    }

    for prod in products:
        stoc = prod.get('stoc', 'Lipsa Stoc')

        # Skip produse fara stoc
        if stoc != 'In stoc':
            results['out_of_stock'] += 1
            continue

        descriere = prod.get('descriere', '') or ''
        # Elimina HTML tags pentru a verifica textul real
        import re
        text_only = re.sub(r'<[^>]+>', '', descriere).strip()

        product_info = {
            'id': prod.get('id_produs', ''),
            'name': prod.get('nume', ''),
            'code': prod.get('cod_produs', ''),
            'price': prod.get('pret', ''),
            'price_discount': prod.get('pret_discount', ''),
            'image': prod.get('imagine', ''),
            'images': prod.get('imagini', []),
            'link': prod.get('link', ''),
            'brand': prod.get('brand', {}).get('nume', ''),
            'description_length': len(text_only),
            'description_html_length': len(descriere),
            'has_size_table_only': 'Tabel M' in descriere and len(text_only) < 20,
        }

        if len(text_only) == 0:
            results['no_description'].append(product_info)
        elif len(text_only) < 50:
            results['short_description'].append(product_info)
        else:
            results['has_description'].append(product_info)

    return results

# --- Step 4: Export ---


def export_results(results, output_dir):
    """Exporta rezultate in JSON + Excel"""

    # JSON - lista produse fara descriere (pentru scriptul de generare)
    no_desc = results['no_description'] + results['short_description']
    json_path = os.path.join(output_dir, 'products_no_description.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(no_desc, f, ensure_ascii=False, indent=2)
    print(f"\n📄 JSON salvat: {json_path} ({len(no_desc)} produse)")

    # Excel
    try:
        import pandas as pd
        excel_path = os.path.join(output_dir, 'scan_descriptions.xlsx')

        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            # Sheet 1: Sumar
            summary = pd.DataFrame([{
                'Metric': 'Total produse scanate',
                'Valoare': len(results['no_description']) + len(results['has_description']) + len(results['short_description']) + results['out_of_stock']
            }, {
                'Metric': 'Cu stoc > 0',
                'Valoare': len(results['no_description']) + len(results['has_description']) + len(results['short_description'])
            }, {
                'Metric': '❌ FĂRĂ descriere',
                'Valoare': len(results['no_description'])
            }, {
                'Metric': '⚠️ Descriere scurtă (<50 chars)',
                'Valoare': len(results['short_description'])
            }, {
                'Metric': '✅ Cu descriere',
                'Valoare': len(results['has_description'])
            }, {
                'Metric': 'Fără stoc (skip)',
                'Valoare': results['out_of_stock']
            }])
            summary.to_excel(writer, sheet_name='Sumar', index=False)

            # Sheet 2: Produse FĂRĂ descriere
            if results['no_description']:
                df_no = pd.DataFrame(results['no_description'])
                df_no = df_no[['id', 'name', 'code', 'brand',
                               'price', 'price_discount', 'link', 'image']]
                df_no.to_excel(
                    writer, sheet_name='Fara Descriere', index=False)

            # Sheet 3: Descriere scurtă
            if results['short_description']:
                df_short = pd.DataFrame(results['short_description'])
                df_short = df_short[['id', 'name', 'code', 'brand', 'price',
                                     'description_length', 'has_size_table_only', 'link']]
                df_short.to_excel(
                    writer, sheet_name='Descriere Scurta', index=False)

            # Sheet 4: Cu descriere (referinta)
            if results['has_description']:
                df_has = pd.DataFrame(results['has_description'])
                df_has = df_has[['id', 'name', 'code',
                                 'brand', 'description_length', 'link']]
                df_has.to_excel(writer, sheet_name='Cu Descriere', index=False)

        print(f"📊 Excel salvat: {excel_path}")
    except ImportError:
        print("⚠️ pandas/openpyxl nu e instalat - doar JSON exportat")

# --- Main ---


def main():
    print("=" * 60)
    print("🔍 SCAN DESCRIERI PRODUSE - ejolie.ro")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # Step 1: Fetch all IDs
    print("\n📋 Step 1: Fetch lista produse...")
    all_ids = fetch_all_product_ids()
    print(f"  Total: {len(all_ids)} produse gasite")

    if not all_ids:
        print("❌ Nu am gasit produse!")
        return

    # Step 2: Fetch details
    print(f"\n📦 Step 2: Fetch detalii ({len(all_ids)} produse)...")
    products = fetch_product_details(all_ids)
    print(f"  Detalii primite: {len(products)} produse")

    # Step 3: Analyze
    print("\n🔎 Step 3: Analiza descrieri...")
    results = analyze_descriptions(products)

    # Print summary
    print("\n" + "=" * 60)
    print("📊 REZULTATE:")
    print(f"  ❌ FĂRĂ descriere:         {len(results['no_description'])}")
    print(f"  ⚠️  Descriere scurtă (<50): {len(results['short_description'])}")
    print(f"  ✅ Cu descriere:            {len(results['has_description'])}")
    print(f"  ⏭️  Fără stoc (skip):       {results['out_of_stock']}")
    print("=" * 60)

    # Step 4: Export
    print("\n💾 Step 4: Export rezultate...")
    output_dir = SCRIPT_DIR
    export_results(results, output_dir)

    # Print first 10 fara descriere
    if results['no_description']:
        print(f"\n📋 Primele 10 produse FĂRĂ descriere:")
        for p in results['no_description'][:10]:
            print(f"  [{p['id']}] {p['name']} ({p['brand']}) - {p['link']}")

    print("\n✅ Scan complet!")


if __name__ == '__main__':
    main()
