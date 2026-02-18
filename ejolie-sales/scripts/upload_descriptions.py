#!/usr/bin/env python3
"""
upload_descriptions.py - Uploadează descrieri generate pe ejolie.ro
v2 - Added --id, --limit argparse support
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

if not EXTENDED_EMAIL or not EXTENDED_PASSWORD:
    print("❌ EXTENDED_EMAIL sau EXTENDED_PASSWORD nu sunt setate in .env!")
    sys.exit(1)

INPUT_FILE = os.path.join(SCRIPT_DIR, 'generated_descriptions.json')
UPLOAD_LOG = os.path.join(SCRIPT_DIR, 'upload_descriptions_log.json')

ADMIN_BASE = 'https://www.ejolie.ro/manager'
HEADERS = {'User-Agent': 'Mozilla/5.0'}


def admin_login(session):
    r = session.post(f'{ADMIN_BASE}/login/autentificare', data={
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


def upload_description(session, product_id, description_html):
    url = f'{ADMIN_BASE}/produse/detalii/{product_id}'
    r = session.get(url, timeout=30)
    if r.status_code != 200:
        return False, f'GET failed: {r.status_code}'
    form_data = parse_form_fields(r.text)
    if len(form_data) < 10:
        return False, f'Too few fields parsed: {len(form_data)}'
    form_data.append(('camp_descriere', description_html))
    r2 = session.post(url, data=form_data, timeout=30)
    if r2.status_code in [200, 302]:
        r3 = session.get(url, timeout=30)
        check_text = re.sub(r'<[^>]+>', '', description_html)[:50]
        if check_text in r3.text:
            return True, 'OK'
        else:
            return True, 'POST OK but verification unclear'
    return False, f'POST failed: {r2.status_code}'


def main():
    parser = argparse.ArgumentParser(
        description='Upload generated descriptions to ejolie.ro')
    parser.add_argument(
        '--id', type=str, help='Upload only for specific product ID')
    parser.add_argument('--limit', type=int, default=0,
                        help='Limit number of products to upload')
    args = parser.parse_args()

    print("=" * 60)
    print("📤 UPLOAD DESCRIERI PRODUSE - ejolie.ro v2")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    if args.id:
        print(f"🎯 Mod: produs specific ID={args.id}")
    elif args.limit:
        print(f"🎯 Mod: limitat la {args.limit} produse")
    print("=" * 60)

    if not os.path.exists(INPUT_FILE):
        print(f"❌ {INPUT_FILE} nu există! Rulează generate_descriptions.py")
        sys.exit(1)

    with open(INPUT_FILE) as f:
        products = json.load(f)

    # Filter by ID if specified
    if args.id:
        products = [p for p in products if str(p['id']) == str(args.id)]
        if not products:
            print(
                f"❌ Produsul {args.id} nu a fost găsit în generated_descriptions.json!")
            sys.exit(1)

    # Apply limit
    if args.limit and args.limit < len(products):
        products = products[:args.limit]

    print(f"\n📋 {len(products)} descrieri de uploadat")

    # Load existing upload log (resume support) - skip for --id mode
    uploaded = {}
    if os.path.exists(UPLOAD_LOG) and not args.id:
        with open(UPLOAD_LOG) as f:
            uploaded = json.load(f)
        print(f"📂 {len(uploaded)} deja uploadate (skip)")

    # Login
    print("\n🔐 Login admin...", end=' ')
    session = requests.Session()
    session.headers.update(HEADERS)
    if admin_login(session):
        print("✅ OK")
    else:
        print("❌ FAILED!")
        sys.exit(1)

    success = 0
    errors = []
    skipped = 0

    for i, prod in enumerate(products):
        pid = prod['id']
        name = prod['name']
        html = prod['description_html']

        if pid in uploaded and not args.id:
            skipped += 1
            continue

        print(f"  [{i+1}/{len(products)}] 📤 {name}...", end=' ')
        ok, msg = upload_description(session, pid, html)

        if ok:
            success += 1
            uploaded[pid] = {
                'name': name,
                'status': msg,
                'uploaded_at': datetime.now().isoformat()
            }
            print(f"✅ {msg}")
        else:
            errors.append({'id': pid, 'name': name, 'error': msg})
            print(f"❌ {msg}")

        if (success + len(errors)) % 10 == 0 and not args.id:
            with open(UPLOAD_LOG, 'w', encoding='utf-8') as f:
                json.dump(uploaded, f, ensure_ascii=False, indent=2)

        time.sleep(2)

        if (success + len(errors)) % 50 == 0 and (success + len(errors)) > 0:
            print("    🔐 Re-login...", end=' ')
            if admin_login(session):
                print("OK")

    # Final save
    with open(UPLOAD_LOG, 'w', encoding='utf-8') as f:
        json.dump(uploaded, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"📊 REZULTATE UPLOAD:")
    print(f"  ✅ Uploadate:  {success}")
    print(f"  ⏭️ Skip:       {skipped}")
    print(f"  ❌ Erori:      {len(errors)}")
    print(f"  📄 Total:      {success + skipped}/{len(products)}")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    main()
