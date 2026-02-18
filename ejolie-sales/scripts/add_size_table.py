#!/usr/bin/env python3
"""
add_size_table.py - Adaugă tabel de mărimi la descrierea produselor ejolie.ro
Alege tabelul în funcție de croială (specificația "Croi" din Extended):
  - Mulat/Fitted → 4 coloane (bust, talie, sold, lungime)
  - Lejer/A-line/Evazat/Other → 3 coloane (bust, talie, lungime)
  - Dacă produsul NU are croi setat → default 3 coloane
  - Dacă produsul DEJA are tabel → SKIP

v1 - Initial version
"""

import os
import sys
import json
import re
import time
import requests
import argparse
from datetime import datetime

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

EXTENDED_EMAIL = os.environ.get('EXTENDED_EMAIL', '')
EXTENDED_PASSWORD = os.environ.get('EXTENDED_PASSWORD', '')
API_KEY = os.environ.get('EJOLIE_API_KEY', '')
API_URL = os.environ.get('EJOLIE_API_URL', 'https://ejolie.ro/api/')

if not EXTENDED_EMAIL or not EXTENDED_PASSWORD:
    print("❌ EXTENDED_EMAIL sau EXTENDED_PASSWORD nu sunt setate in .env!")
    sys.exit(1)

ADMIN_BASE = 'https://www.ejolie.ro/manager'
HEADERS = {'User-Agent': 'Mozilla/5.0'}

# Size table images
SIZE_TABLE_4COL = '<p><img src="https://ejolie.ro/continut/upload/Tabel%20M%20General%20Trendya.png" width="512" height="764"></p>'
SIZE_TABLE_3COL = '<p><img src="https://ejolie-assets.s3.eu-north-1.amazonaws.com/images/Tabel-Marimi-3col.png" width="512" height="764"></p>'

# Croi values that use 4-column (fitted) table
CROI_4COL = ['mulat', 'fitted', 'bodycon', 'sirena', 'sirenă', 'creion']

LOG_FILE = os.path.join(SCRIPT_DIR, 'size_table_log.json')


def admin_login(session):
    session.post(f'{ADMIN_BASE}/login/autentificare', data={
        'utilizator': EXTENDED_EMAIL,
        'parola': EXTENDED_PASSWORD
    })
    r2 = session.get(f'{ADMIN_BASE}/produse/detalii/12350', timeout=30)
    return 'camp_nume' in r2.text


def parse_form_fields(html):
    form_data = []
    for m in re.finditer(r'<input[^>]*>', html):
        tag = m.group(0)
        name_m = re.search(r'name=["\']([^"\']+)["\']', tag)
        val_m = re.search(r'value=["\']([^"\']*)["\']', tag)
        type_m = re.search(r'type=["\']([^"\']+)["\']', tag)
        if name_m:
            inp_type = type_m.group(1) if type_m else 'text'
            if inp_type == 'checkbox':
                if 'checked' in tag:
                    form_data.append(
                        (name_m.group(1), val_m.group(1) if val_m else 'on'))
            elif inp_type == 'radio':
                if 'checked' in tag:
                    form_data.append(
                        (name_m.group(1), val_m.group(1) if val_m else ''))
            elif inp_type != 'file':
                form_data.append(
                    (name_m.group(1), val_m.group(1) if val_m else ''))
    for m in re.finditer(r'<textarea[^>]*name=["\']([^"\']+)["\'][^>]*>(.*?)</textarea>', html, re.DOTALL):
        form_data.append((m.group(1), m.group(2)))
    for m in re.finditer(r'<select[^>]*name=["\']([^"\']+)["\'][^>]*>(.*?)</select>', html, re.DOTALL):
        sel = re.search(
            r'<option[^>]*selected[^>]*value=["\']([^"\']*)["\']', m.group(2))
        if not sel:
            sel = re.search(
                r'<option[^>]*value=["\']([^"\']*)["\'][^>]*selected', m.group(2))
        if sel:
            form_data.append((m.group(1), sel.group(1)))
    return form_data


def get_current_description(session, product_id):
    url = f'{ADMIN_BASE}/produse/detalii/{product_id}'
    r = session.get(url, timeout=30)
    if r.status_code != 200:
        return None, None

    # Extract camp_descriere
    # First try traditional form fields
    desc_match = re.search(
        r'name=["\']camp_descriere["\'][^>]*value=["\']([^"\']*)["\']', r.text)
    if not desc_match:
        desc_match = re.search(
            r'name=["\']camp_descriere["\'][^>]*>(.*?)</textarea>', r.text, re.DOTALL)
    
    # If not found, try elRTE editor div format
    if not desc_match:
        desc_match = re.search(
            r'<div[^>]*id=["\']camp_descriere["\'][^>]*>(.*?)</div>', r.text, re.DOTALL)

    current_desc = desc_match.group(1) if desc_match else ''
    return current_desc, parse_form_fields(r.text)


def get_product_croi(product_id):
    try:
        url = f"{API_URL}?id_produs={product_id}&apikey={API_KEY}"
        r = requests.get(url, headers=HEADERS, timeout=30)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and data:
                data = data[0]
            if isinstance(data, dict):
                specs = data.get('specificatii', {})
                if isinstance(specs, dict):
                    croi = specs.get('Croi', '')
                    return croi.lower().strip() if croi else ''
                elif isinstance(specs, list):
                    for spec in specs:
                        if isinstance(spec, dict) and spec.get('nume', '').lower() == 'croi':
                            return spec.get('valoare', '').lower().strip()
    except Exception as e:
        print(f"    ⚠️ API error getting croi: {e}")
    return ''


def has_size_table(description_html):
    if not description_html:
        return False
    lower = description_html.lower()
    return ('tabel' in lower and 'marimi' in lower) or \
           ('tabel-marimi' in lower) or \
           ('tabel%20m' in lower) or \
           ('tabel m general' in lower)


def determine_table(croi_value):
    if not croi_value:
        return '3col', 'fără croi setat → default 3 coloane'
    for fitted in CROI_4COL:
        if fitted in croi_value:
            return '4col', f'croi "{croi_value}" → 4 coloane (fitted)'
    return '3col', f'croi "{croi_value}" → 3 coloane (lejer/evazat)'


def add_table_to_product(session, product_id, table_html):
    url = f'{ADMIN_BASE}/produse/detalii/{product_id}'

    current_desc, form_data = get_current_description(session, product_id)

    if form_data is None:
        return False, 'GET failed'
    if len(form_data) < 10:
        return False, f'Too few fields: {len(form_data)}'

    if current_desc:
        new_desc = current_desc + '\n' + table_html
    else:
        new_desc = table_html

    form_data.append(('camp_descriere', new_desc))

    r2 = session.post(url, data=form_data, timeout=30)
    if r2.status_code in [200, 302]:
        return True, 'OK'
    return False, f'POST failed: {r2.status_code}'


def get_products_list():
    feed_path = os.path.join(SCRIPT_DIR, 'product_feed.json')
    if os.path.exists(feed_path):
        with open(feed_path) as f:
            return json.load(f)
    print("❌ product_feed.json nu există!")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description='Add size tables to product descriptions')
    parser.add_argument(
        '--id', type=str, help='Add table to specific product ID')
    parser.add_argument('--limit', type=int, default=0,
                        help='Limit number of products')
    parser.add_argument('--brand', type=str, default='ejolie',
                        help='Filter by brand (default: ejolie)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be done without uploading')
    args = parser.parse_args()

    print("=" * 60)
    print("📐 ADAUGĂ TABEL MĂRIMI - ejolie.ro v1")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    if args.id:
        print(f"🎯 Mod: produs specific ID={args.id}")
    elif args.limit:
        print(f"🎯 Mod: limitat la {args.limit} produse")
    if args.dry_run:
        print("🔍 DRY RUN - nu se uploadează nimic")
    print("=" * 60)

    session = requests.Session()
    session.headers.update(HEADERS)

    if not args.dry_run:
        print("\n🔐 Login admin...", end=' ')
        if admin_login(session):
            print("✅ OK")
        else:
            print("❌ FAILED!")
            sys.exit(1)

    # Get products
    if args.id:
        products = [{'id': args.id, 'name': f'Product {args.id}', 'brand': ''}]
    else:
        all_products = get_products_list()
        brand_lower = args.brand.lower()
        products = [p for p in all_products if p.get(
            'brand', '').lower() == brand_lower]
        print(f"\n📋 {len(products)} produse {args.brand}")

    if args.limit and args.limit < len(products):
        products = products[:args.limit]

    # Load log
    log = {}
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE) as f:
            log = json.load(f)

    added = 0
    skipped_has_table = 0
    skipped_no_desc = 0
    errors = []

    for i, prod in enumerate(products):
        pid = str(prod['id'])
        name = prod.get('name', f'ID {pid}')

        print(f"\n  [{i+1}/{len(products)}] {name} (ID:{pid})")

        # 1. Check if already has table
        if not args.dry_run:
            current_desc, _ = get_current_description(session, pid)
            if current_desc and has_size_table(current_desc):
                print(f"    ⏭️ SKIP - deja are tabel mărimi")
                skipped_has_table += 1
                continue
            if not current_desc or len(current_desc.strip()) < 20:
                print(f"    ⏭️ SKIP - fără descriere (adaugă descriere mai întâi)")
                skipped_no_desc += 1
                continue

        # 2. Get croi from API
        croi = get_product_croi(pid)
        table_type, reason = determine_table(croi)
        table_html = SIZE_TABLE_4COL if table_type == '4col' else SIZE_TABLE_3COL

        print(f"    📐 {reason}")

        if args.dry_run:
            print(f"    🔍 DRY RUN: ar adăuga tabel {table_type}")
            added += 1
            continue

        # 3. Add table
        ok, msg = add_table_to_product(session, pid, table_html)
        if ok:
            added += 1
            log[pid] = {
                'name': name,
                'table_type': table_type,
                'croi': croi,
                'added_at': datetime.now().isoformat()
            }
            print(f"    ✅ Tabel {table_type} adăugat!")
        else:
            errors.append({'id': pid, 'name': name, 'error': msg})
            print(f"    ❌ {msg}")

        time.sleep(2)

        if added % 50 == 0 and added > 0:
            print("    🔐 Re-login...", end=' ')
            if admin_login(session):
                print("OK")

    # Save log
    if not args.dry_run:
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(log, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"📊 REZULTATE:")
    print(f"  ✅ Adăugate:       {added}")
    print(f"  ⏭️ Au deja tabel:  {skipped_has_table}")
    print(f"  ⏭️ Fără descriere: {skipped_no_desc}")
    print(f"  ❌ Erori:          {len(errors)}")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    main()
