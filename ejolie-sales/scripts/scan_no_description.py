#!/usr/bin/env python3
"""
scan_no_description.py - Scanează produse ejolie.ro fără descriere
v2 - Fix: API returnează tot pe fiecare call, deci fetch o singura data + dedup
"""

import os
import sys
import json
import re
import time
import requests
from datetime import datetime

# --- Config ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(SCRIPT_DIR, '..', '.env')


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

# --- Step 1: Fetch toate produsele (un singur call) ---


def fetch_all_products():
    """Fetch toate produsele cu detalii complete - un singur call"""
    url = f"{BASE_URL}?produse&apikey={API_KEY}"
    print(f"  📥 Fetching all products...")
    try:
        r = requests.get(url, headers=HEADERS, timeout=300)
        data = r.json()
        if not data:
            return []

        # Deduplicam pe id_produs
        products = []
        seen = set()
        for pid, prod in data.items():
            prod_id = prod.get('id_produs', pid)
            if prod_id not in seen:
                seen.add(prod_id)
                products.append(prod)

        print(f"  ✅ {len(products)} produse unice primite")
        return products
    except Exception as e:
        print(f"  ❌ Eroare: {e}")
        return []

# --- Step 2: Analizeaza descrieri ---


def analyze_descriptions(products):
    """Clasifică produsele: cu/fără descriere, stoc"""
    results = {
        'no_description': [],
        'has_description': [],
        'out_of_stock': 0,
        'short_description': []
    }

    for prod in products:
        stoc = prod.get('stoc', 'Lipsa Stoc')

        if stoc != 'In stoc':
            results['out_of_stock'] += 1
            continue

        descriere = prod.get('descriere', '') or ''
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

# --- Step 3: Export ---


def export_results(results, output_dir):
    no_desc = results['no_description'] + results['short_description']
    json_path = os.path.join(output_dir, 'products_no_description.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(no_desc, f, ensure_ascii=False, indent=2)
    print(f"\n📄 JSON salvat: {json_path} ({len(no_desc)} produse)")

    try:
        import pandas as pd
        excel_path = os.path.join(output_dir, 'scan_descriptions.xlsx')

        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            total_in_stock = len(results['no_description']) + len(
                results['has_description']) + len(results['short_description'])
            summary = pd.DataFrame([
                {'Metric': 'Total produse in API',
                    'Valoare': total_in_stock + results['out_of_stock']},
                {'Metric': 'Cu stoc > 0', 'Valoare': total_in_stock},
                {'Metric': '❌ FĂRĂ descriere', 'Valoare': len(
                    results['no_description'])},
                {'Metric': '⚠️ Descriere scurtă (<50 chars)', 'Valoare': len(
                    results['short_description'])},
                {'Metric': '✅ Cu descriere', 'Valoare': len(
                    results['has_description'])},
                {'Metric': 'Fără stoc (skip)',
                 'Valoare': results['out_of_stock']},
            ])
            summary.to_excel(writer, sheet_name='Sumar', index=False)

            if results['no_description']:
                df_no = pd.DataFrame(results['no_description'])
                df_no = df_no[['id', 'name', 'code', 'brand',
                               'price', 'price_discount', 'link', 'image']]
                df_no.to_excel(
                    writer, sheet_name='Fara Descriere', index=False)

            if results['short_description']:
                df_short = pd.DataFrame(results['short_description'])
                df_short = df_short[['id', 'name', 'code', 'brand', 'price',
                                     'description_length', 'has_size_table_only', 'link']]
                df_short.to_excel(
                    writer, sheet_name='Descriere Scurta', index=False)

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
    print("🔍 SCAN DESCRIERI PRODUSE - ejolie.ro (v2)")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    print("\n📋 Step 1: Fetch toate produsele...")
    products = fetch_all_products()

    if not products:
        print("❌ Nu am gasit produse!")
        return

    print(f"\n🔎 Step 2: Analiza descrieri...")
    results = analyze_descriptions(products)

    print("\n" + "=" * 60)
    print("📊 REZULTATE:")
    print(f"  ❌ FĂRĂ descriere:         {len(results['no_description'])}")
    print(f"  ⚠️  Descriere scurtă (<50): {len(results['short_description'])}")
    print(f"  ✅ Cu descriere:            {len(results['has_description'])}")
    print(f"  ⏭️  Fără stoc (skip):       {results['out_of_stock']}")
    print("=" * 60)

    print("\n💾 Step 3: Export rezultate...")
    export_results(results, SCRIPT_DIR)

    if results['no_description']:
        print(f"\n📋 Primele 10 produse FĂRĂ descriere:")
        for p in results['no_description'][:10]:
            print(f"  [{p['id']}] {p['name']} ({p['brand']}) - {p['link']}")

    if results['short_description']:
        print(f"\n📋 Primele 5 produse cu descriere SCURTĂ:")
        for p in results['short_description'][:5]:
            print(f"  [{p['id']}] {p['name']} - {p['description_length']} chars")

    print("\n✅ Scan complet!")


if __name__ == '__main__':
    main()
