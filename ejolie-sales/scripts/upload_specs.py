#!/usr/bin/env python3
"""
upload_specs.py — Uploadează specificații generate pe admin Extended ejolie.ro.

Citește generated_specs.json (output generate_specs.py).
Login admin Extended → GET pagina produs → parsează form existent →
adaugă specs noi fără a suprascrie cele existente → POST.

Usage:
    python3 upload_specs.py --id 12352          # Upload 1 produs
    python3 upload_specs.py --limit 5           # Primele 5 produse
    python3 upload_specs.py                     # Toate produsele din generated_specs.json
    python3 upload_specs.py --dry-run           # Arată ce ar uploada, fără POST
"""

import json
import os
import sys
import re
import time
import argparse
import requests
from pathlib import Path
from dotenv import load_dotenv

# ── Paths ──────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
ENV_PATH = SCRIPT_DIR / '..' / '.env'
GENERATED_PATH = SCRIPT_DIR / 'generated_specs.json'

# ── Load .env ──────────────────────────────────────────────────────
load_dotenv(ENV_PATH)
EXTENDED_EMAIL = os.getenv('EXTENDED_EMAIL')
EXTENDED_PASSWORD = os.getenv('EXTENDED_PASSWORD')

if not EXTENDED_EMAIL or not EXTENDED_PASSWORD:
    print("❌ EXTENDED_EMAIL sau EXTENDED_PASSWORD nu sunt setate în .env")
    sys.exit(1)

# ── Admin URLs ─────────────────────────────────────────────────────
ADMIN_BASE = 'https://www.ejolie.ro/manager'
LOGIN_URL = f'{ADMIN_BASE}/login/autentificare'

# ── Mapping spec name → camp_optiune field ─────────────────────────
SPEC_FIELD_MAP = {
    "Culoare": "camp_optiune_10",
    "Material": "camp_optiune_11",
    "Lungime": "camp_optiune_12",
    "Croi": "camp_optiune_13",
    "Stil": "camp_optiune_14",
    "Model": "camp_optiune_15"
}

# ── Headers ────────────────────────────────────────────────────────
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}


def admin_login(session):
    """
    Login pe admin Extended.
    Returns: True dacă login OK, False dacă eșuat.
    """
    try:
        # POST login
        r = session.post(LOGIN_URL, data={
            'utilizator': EXTENDED_EMAIL,
            'parola': EXTENDED_PASSWORD
        }, headers=HEADERS, timeout=30)

        # Verificăm login — accesăm o pagină admin
        r2 = session.get(f'{ADMIN_BASE}/produse/detalii/12350', headers=HEADERS, timeout=30)

        if 'camp_nume' in r2.text or 'sectiune=specificatii' in r2.text:
            return True
        else:
            return False

    except Exception as e:
        print(f"  ❌ Eroare login: {e}")
        return False


def get_existing_specs(session, product_id):
    """
    GET pagina specificații produs din admin.
    Parsează <select multiple> cu <option selected>.
    Returns: dict {camp_optiune_XX: [lista de value_ids selectate]}
    """
    url = f'{ADMIN_BASE}/produse/detalii/{product_id}?sectiune=specificatii'

    try:
        r = session.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        html = r.text

        existing = {}
        for spec_name, field_name in SPEC_FIELD_MAP.items():
            # Form-ul folosește <select multiple> cu <option selected>
            pattern_select = rf'name="{re.escape(field_name)}\[\]".*?</select>'
            select_match = re.search(pattern_select, html, re.DOTALL)
            matches = []
            if select_match:
                select_html = select_match.group(0)
                # Găsim option-urile cu selected, excludem value="0" (Fara optiune definita)
                matches = re.findall(r'<option\s+value="(\d+)"\s+selected', select_html)
                matches = [m for m in matches if m != '0']

            existing[field_name] = [int(m) for m in matches]

        return existing

    except Exception as e:
        print(f"  ❌ Eroare GET specs {product_id}: {e}")
        return None


def upload_product_specs(session, product_id, specs_to_add, existing_specs):
    """
    POST specificații pe admin Extended.
    Combină specs existente cu cele noi (nu suprascrie).
    Returns: True dacă OK, False dacă eroare.
    """
    url = f'{ADMIN_BASE}/produse/detalii/{product_id}?sectiune=specificatii'

    # Construim form data — combinăm existing + new
    form_data = []

    # OBLIGATORIU — fără acest câmp hidden, form-ul nu se salvează
    form_data.append(('trimite', 'value'))

    for spec_name, field_name in SPEC_FIELD_MAP.items():
        # Valorile existente
        current_ids = existing_specs.get(field_name, [])

        # Valorile noi de adăugat
        new_ids = []
        if spec_name in specs_to_add:
            values = specs_to_add[spec_name]
            for v in values:
                vid = v.get('value_id')
                if vid and vid not in current_ids:
                    new_ids.append(vid)

        # Combinăm: existing + new
        all_ids = current_ids + new_ids

        if all_ids:
            for vid in all_ids:
                form_data.append((f'{field_name}[]', str(vid)))
        else:
            # Trimitem un câmp gol ca să nu dea eroare form-ul
            form_data.append((f'{field_name}[]', ''))

    try:
        r = session.post(url, data=form_data, headers=HEADERS, timeout=30)
        r.raise_for_status()

        # Verificăm dacă s-a salvat (pagina redirecționează sau conține confirm)
        if r.status_code in [200, 302]:
            return True
        else:
            print(f"  ❌ POST status: {r.status_code}")
            return False

    except Exception as e:
        print(f"  ❌ Eroare POST specs {product_id}: {e}")
        return False


def verify_upload(session, product_id, specs_to_add):
    """
    Verifică după upload dacă specs-urile au fost salvate corect.
    Returns: (ok_count, total_count)
    """
    existing = get_existing_specs(session, product_id)
    if not existing:
        return 0, len(specs_to_add)

    ok = 0
    total = 0
    for spec_name, values in specs_to_add.items():
        field_name = SPEC_FIELD_MAP.get(spec_name)
        if not field_name:
            continue
        for v in values:
            total += 1
            vid = v.get('value_id')
            if vid in existing.get(field_name, []):
                ok += 1

    return ok, total


def load_generated_specs():
    """Citește generated_specs.json."""
    if not GENERATED_PATH.exists():
        print(f"❌ {GENERATED_PATH} nu există. Rulează generate_specs.py mai întâi.")
        sys.exit(1)

    with open(GENERATED_PATH, 'r', encoding='utf-8') as f:
        products = json.load(f)

    print(f"📦 Încărcat {len(products)} produse cu specs generate")
    return products


def main():
    parser = argparse.ArgumentParser(description='Upload specificații generate pe admin Extended')
    parser.add_argument('--id', type=int, help='Upload doar produs specific')
    parser.add_argument('--limit', type=int, default=0, help='Limită produse (0 = toate)')
    parser.add_argument('--dry-run', action='store_true', help='Arată ce ar uploada, fără POST')
    parser.add_argument('--no-verify', action='store_true', help='Nu verifica după upload')
    args = parser.parse_args()

    # ── Încarcă produse generate ───────────────────────────────────
    products = load_generated_specs()

    # ── Filtru --id ────────────────────────────────────────────────
    if args.id:
        products = [p for p in products if str(p.get('id')) == str(args.id)]
        if not products:
            print(f"❌ Produs {args.id} nu a fost găsit în generated_specs.json")
            sys.exit(1)
        print(f"🎯 Upload produs specific: {args.id}")

    # ── Filtru --limit ─────────────────────────────────────────────
    if args.limit > 0:
        products = products[:args.limit]
        print(f"📏 Limitat la {args.limit} produse")

    total = len(products)
    print(f"\n📤 Upload specs pentru {total} produse...\n")

    # ── Dry-run mode ───────────────────────────────────────────────
    if args.dry_run:
        for i, product in enumerate(products, 1):
            pid = product.get('id')
            name = product.get('name', '')
            specs = product.get('specs_to_add', {})
            print(f"[{i}/{total}] {pid} - {name}")
            for spec_name, values in specs.items():
                field = SPEC_FIELD_MAP.get(spec_name, '?')
                vals_str = ", ".join([f"{v['value']} (ID:{v['value_id']})" for v in values])
                print(f"  → {spec_name} ({field}[]): {vals_str}")
            print()
        print("🔍 Dry-run: nimic uploadat")
        return

    # ── Login admin ────────────────────────────────────────────────
    session = requests.Session()
    print("🔐 Login admin Extended...", end='', flush=True)

    if not admin_login(session):
        print(" ❌ Login eșuat!")
        sys.exit(1)
    print(" ✅ OK")

    # ── Upload loop ────────────────────────────────────────────────
    success = 0
    errors = 0
    relogin_counter = 0

    for i, product in enumerate(products, 1):
        pid = product.get('id')
        name = product.get('name', '')
        specs_to_add = product.get('specs_to_add', {})

        if not specs_to_add:
            print(f"[{i}/{total}] {pid} - {name} → ⏭️  Nimic de adăugat")
            continue

        print(f"[{i}/{total}] {pid} - {name}")

        # Re-login la fiecare 50 requests
        relogin_counter += 1
        if relogin_counter >= 50:
            print("  🔄 Re-login admin...", end='', flush=True)
            session = requests.Session()
            if admin_login(session):
                print(" ✅")
            else:
                print(" ❌ Re-login eșuat, oprire!")
                break
            relogin_counter = 0

        # 1. GET existing specs
        print(f"  📥 GET specs existente...", end='', flush=True)
        existing = get_existing_specs(session, pid)
        if existing is None:
            print(" ❌")
            errors += 1
            continue
        print(" OK")

        # Arată ce adăugăm
        for spec_name, values in specs_to_add.items():
            field = SPEC_FIELD_MAP.get(spec_name, '?')
            existing_ids = existing.get(field, [])
            vals_str = ", ".join([f"{v['value']} (ID:{v['value_id']})" for v in values])
            status = "🆕" if not existing_ids else "➕"
            print(f"  {status} {spec_name}: {vals_str}")

        # 2. POST specs
        print(f"  📤 POST specs...", end='', flush=True)
        if upload_product_specs(session, pid, specs_to_add, existing):
            print(" ✅")
        else:
            print(" ❌")
            errors += 1
            continue

        # 3. Verify (opțional)
        if not args.no_verify:
            print(f"  🔍 Verificare...", end='', flush=True)
            ok, total_specs = verify_upload(session, pid, specs_to_add)
            if ok == total_specs:
                print(f" ✅ {ok}/{total_specs} specs confirmate")
                success += 1
            else:
                print(f" ⚠️  Doar {ok}/{total_specs} specs confirmate")
                success += 1  # Parțial ok
        else:
            success += 1

        # Pauză între produse (1s)
        if i < total:
            time.sleep(1)

    # ── Statistici finale ──────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"📊 STATISTICI UPLOAD")
    print(f"{'='*60}")
    print(f"  Total produse:    {total}")
    print(f"  ✅ Succes:         {success}")
    print(f"  ❌ Erori:          {errors}")
    print(f"  ⏭️  Skip (empty):  {total - success - errors}")
    print(f"{'='*60}")
    print(f"\n✅ Upload complet!")


if __name__ == '__main__':
    main()