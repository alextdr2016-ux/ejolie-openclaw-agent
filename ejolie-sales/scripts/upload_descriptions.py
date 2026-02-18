#!/usr/bin/env python3
"""
upload_descriptions.py - Uploadează descrieri generate pe ejolie.ro
Citește generated_descriptions.json, login admin, parse form, POST camp_descriere
v1 - metoda safe: parse toate campurile + adauga/inlocuieste camp_descriere
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

EXTENDED_EMAIL = os.environ.get('EXTENDED_EMAIL', '')
EXTENDED_PASSWORD = os.environ.get('EXTENDED_PASSWORD', '')

if not EXTENDED_EMAIL or not EXTENDED_PASSWORD:
    print("❌ EXTENDED_EMAIL sau EXTENDED_PASSWORD nu sunt setate in .env!")
    sys.exit(1)

INPUT_FILE = os.path.join(SCRIPT_DIR, 'generated_descriptions.json')
UPLOAD_LOG = os.path.join(SCRIPT_DIR, 'upload_descriptions_log.json')

ADMIN_BASE = 'https://www.ejolie.ro/manager'
HEADERS = {'User-Agent': 'Mozilla/5.0'}

# --- Helper: Login ---


def admin_login(session):
    """Login in Extended admin, returneaza True/False"""
    r = session.post(f'{ADMIN_BASE}/login/autentificare', data={
        'utilizator': EXTENDED_EMAIL,
        'parola': EXTENDED_PASSWORD
    })
    # Verificam daca suntem logati - fetch dashboard
    r2 = session.get(f'{ADMIN_BASE}/')
    if 'deconectare' in r2.text.lower() or 'logout' in r2.text.lower():
        return True
    return False

# --- Helper: Parse form fields ---


def parse_form_fields(html):
    """Parseaza toate campurile din formularul de editare produs"""
    form_data = []

    # 1. Input fields (hidden, text, number)
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

    # 2. Textareas (camp_descriere_scurta, etc. - NU camp_descriere, e hidden de elRTE)
    for m in re.finditer(r'<textarea[^>]*name=["\']([^"\']+)["\'][^>]*>(.*?)</textarea>', html, re.DOTALL):
        form_data.append((m.group(1), m.group(2)))

    # 3. Selects (selected option)
    for m in re.finditer(r'<select[^>]*name=["\']([^"\']+)["\'][^>]*>(.*?)</select>', html, re.DOTALL):
        sel = re.search(
            r'<option[^>]*selected[^>]*value=["\']([^"\']*)["\']', m.group(2))
        if not sel:
            sel = re.search(
                r'<option[^>]*value=["\']([^"\']*)["\'][^>]*selected', m.group(2))
        if sel:
            form_data.append((m.group(1), sel.group(1)))

    return form_data

# --- Helper: Upload single product ---


def upload_description(session, product_id, description_html):
    """Upload descriere pentru un singur produs. Return True/False"""
    url = f'{ADMIN_BASE}/produse/detalii/{product_id}'

    # Fetch product edit page
    r = session.get(url, timeout=30)
    if r.status_code != 200:
        return False, f'GET failed: {r.status_code}'

    # Parse all form fields
    form_data = parse_form_fields(r.text)

    if len(form_data) < 10:
        return False, f'Too few fields parsed: {len(form_data)}'

    # Add camp_descriere (elRTE hides it, so we add manually)
    form_data.append(('camp_descriere', description_html))

    # POST back
    r2 = session.post(url, data=form_data, timeout=30)

    if r2.status_code in [200, 302]:
        # Verify
        r3 = session.get(url, timeout=30)
        # Check if first 50 chars of description are in page
        check_text = re.sub(r'<[^>]+>', '', description_html)[:50]
        if check_text in r3.text:
            return True, 'OK'
        else:
            return True, 'POST OK but verification unclear'

    return False, f'POST failed: {r2.status_code}'

# --- Main ---


def main():
    print("=" * 60)
    print("📤 UPLOAD DESCRIERI PRODUSE - ejolie.ro")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # Load descriptions
    if not os.path.exists(INPUT_FILE):
        print(f"❌ {INPUT_FILE} nu există! Rulează generate_descriptions.py")
        sys.exit(1)

    with open(INPUT_FILE) as f:
        products = json.load(f)

    print(f"\n📋 {len(products)} descrieri de uploadat")

    # Load existing upload log (resume support)
    uploaded = {}
    if os.path.exists(UPLOAD_LOG):
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

    # Process
    success = 0
    errors = []
    skipped = 0

    for i, prod in enumerate(products):
        pid = prod['id']
        name = prod['name']
        html = prod['description_html']

        # Skip if already uploaded
        if pid in uploaded:
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

        # Save progress every 10
        if (success + len(errors)) % 10 == 0:
            with open(UPLOAD_LOG, 'w', encoding='utf-8') as f:
                json.dump(uploaded, f, ensure_ascii=False, indent=2)
            print(f"    💾 Progres salvat ({success} uploadate)")

        # Rate limit - be gentle with admin
        time.sleep(2)

        # Re-login every 50 products (session might expire)
        if (success + len(errors)) % 50 == 0 and (success + len(errors)) > 0:
            print("    🔐 Re-login...", end=' ')
            if admin_login(session):
                print("OK")
            else:
                print("FAILED - trying to continue")

    # Final save
    with open(UPLOAD_LOG, 'w', encoding='utf-8') as f:
        json.dump(uploaded, f, ensure_ascii=False, indent=2)

    # Summary
    print("\n" + "=" * 60)
    print("📊 REZULTATE UPLOAD:")
    print(f"  ✅ Uploadate:  {success}")
    print(f"  ⏭️ Skip:       {skipped}")
    print(f"  ❌ Erori:      {len(errors)}")
    print(f"  📄 Total:      {success + skipped}/{len(products)}")
    print("=" * 60)

    # Lista completa
    print("\n" + "=" * 90)
    print("📋 LISTA COMPLETĂ PRODUSE UPLOADATE:")
    print("=" * 90)
    print(f"{'#':<4} {'ID':<7} {'Nume Produs':<50} {'Status'}")
    print("-" * 90)
    idx = 1
    for prod in products:
        pid = prod['id']
        name = prod['name'][:48]
        if pid in uploaded:
            print(f"{idx:<4} {pid:<7} {name:<50} ✅ {uploaded[pid]['status']}")
        else:
            err = next((e for e in errors if e['id'] == pid), None)
            if err:
                print(f"{idx:<4} {pid:<7} {name:<50} ❌ {err['error']}")
            else:
                print(f"{idx:<4} {pid:<7} {name:<50} ⏭️ skip")
        idx += 1
    print("-" * 90)

    if errors:
        print(f"\n⚠️ Erori:")
        for e in errors:
            print(f"  [{e['id']}] {e['name']} — {e['error']}")

    print(f"\n📄 Upload log: {UPLOAD_LOG}")
    print("✅ Upload complet!")


if __name__ == '__main__':
    main()
