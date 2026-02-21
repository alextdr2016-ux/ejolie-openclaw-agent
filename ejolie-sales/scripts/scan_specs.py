#!/usr/bin/env python3
"""
scan_specs.py — Scanează produse ejolie.ro cu specificații lipsă sau incomplete.

Citește product_feed.json (cache local, actualizat la 4h).
Pentru fiecare produs, face API call ?id_produs=ID → verifică câmpul specificatii.
Salvează products_missing_specs.json cu lista produselor incomplete.

Usage:
    python3 scan_specs.py --id 12345               # Un singur produs
    python3 scan_specs.py --from-id 12365 --to-id 12415  # Range de ID-uri
    python3 scan_specs.py --limit 5                 # Primele 5 produse
    python3 scan_specs.py                           # Toate produsele
    python3 scan_specs.py --stats                   # Doar statistici, fără salvare
"""

import json
import os
import sys
import time
import argparse
import requests
from pathlib import Path
from dotenv import load_dotenv

# ── Paths ──────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
ENV_PATH = SCRIPT_DIR / '..' / '.env'          # .env e un nivel mai sus
FEED_PATH = SCRIPT_DIR / 'product_feed.json'
OUTPUT_PATH = SCRIPT_DIR / 'products_missing_specs.json'

# ── Load .env ──────────────────────────────────────────────────────
load_dotenv(ENV_PATH)
API_KEY = os.getenv('EJOLIE_API_KEY')
API_URL = os.getenv('EJOLIE_API_URL', 'https://ejolie.ro/api/')

if not API_KEY:
    print("❌ EJOLIE_API_KEY nu e setat în .env")
    sys.exit(1)

# ── Cele 6 specificații pe care le verificăm ───────────────────────
SPEC_NAMES = ['Culoare', 'Material', 'Lungime', 'Croi', 'Stil', 'Model']

# Valoarea care înseamnă "necompletat" în Extended
EMPTY_VALUE = 'Fara optiune definita'

# ── Headers API ────────────────────────────────────────────────────
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}


def load_product_feed():
    """Citește product_feed.json (cache local)."""
    if not FEED_PATH.exists():
        print(f"❌ {FEED_PATH} nu există. Rulează stock_cache_update.py mai întâi.")
        sys.exit(1)

    with open(FEED_PATH, 'r', encoding='utf-8') as f:
        products = json.load(f)

    print(f"📦 Încărcat {len(products)} produse din product_feed.json")
    return products


def fetch_product_specs(product_id):
    """
    Fetch specificații pentru un produs via API.
    API returnează {"ID": {datele_produsului}} — trebuie extras din wrapper.
    Returns: dict cu specs sau None dacă eroare.
    """
    url = f"{API_URL}?id_produs={product_id}&apikey={API_KEY}"

    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        data = r.json()

        # API returnează {"ID": {datele}} — extragem product_data
        if isinstance(data, dict) and str(product_id) in data:
            product_data = data[str(product_id)]
        elif isinstance(data, dict) and len(data) == 1:
            product_data = list(data.values())[0]
        else:
            product_data = data

        # Câmpul specificatii e un array de obiecte: [{nume, valoare[]}, ...]
        specs_raw = product_data.get('specificatii', []) if isinstance(product_data, dict) else []

        # Construim dict structurat
        specs = {}
        for spec_name in SPEC_NAMES:
            specs[spec_name] = []

        for item in specs_raw:
            name = item.get('nume', '')
            values = item.get('valoare', [])

            if name in specs:
                # Filtrăm valorile goale / "Fara optiune definita"
                clean_values = [v for v in values if v and v != EMPTY_VALUE]
                specs[name] = clean_values

        return specs

    except requests.exceptions.Timeout:
        print(f"  ⏱️  Timeout pentru produs {product_id}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"  ❌ Eroare API pentru {product_id}: {e}")
        return None
    except (json.JSONDecodeError, KeyError) as e:
        print(f"  ❌ Eroare parsare pentru {product_id}: {e}")
        return None


def scan_product(product):
    """
    Scanează un produs și returnează dict cu specs + missing.
    Returns: dict sau None dacă API fail.
    """
    pid = product.get('id')
    name = product.get('title', product.get('name', 'Unknown'))
    image = product.get('image', '')

    specs = fetch_product_specs(pid)
    if specs is None:
        return None

    # Determinăm ce specificații lipsesc
    missing = [spec for spec in SPEC_NAMES if not specs.get(spec)]

    return {
        'id': pid,
        'name': name,
        'image': image,
        'current_specs': specs,
        'missing': missing,
        'missing_count': len(missing),
        'complete': len(missing) == 0
    }


def print_product_result(result):
    """Afișează rezultatul scanării unui produs."""
    status = "✅" if result['complete'] else "⚠️"
    print(f"\n{status} [{result['id']}] {result['name']}")

    for spec in SPEC_NAMES:
        values = result['current_specs'].get(spec, [])
        if values:
            print(f"    ✓ {spec}: {', '.join(values)}")
        else:
            print(f"    ✗ {spec}: LIPSĂ")

    if result['missing']:
        print(f"  → Lipsesc {result['missing_count']}/6: {', '.join(result['missing'])}")
    else:
        print(f"  → Toate 6 specificațiile sunt complete!")


def print_stats(results):
    """Afișează statistici sumar."""
    total = len(results)
    complete = sum(1 for r in results if r['complete'])
    incomplete = total - complete

    # Detalii pe fiecare spec
    spec_stats = {}
    for spec in SPEC_NAMES:
        missing_count = sum(1 for r in results if spec in r['missing'])
        spec_stats[spec] = missing_count

    print("\n" + "=" * 60)
    print("📊 STATISTICI SCANARE SPECIFICAȚII")
    print("=" * 60)
    print(f"  Total produse scanate:    {total}")
    print(f"  ✅ Complete (6/6 specs):   {complete}")
    print(f"  ⚠️  Incomplete:            {incomplete}")
    if total > 0:
        print(f"  Procent complete:         {complete/total*100:.1f}%")

    print(f"\n  Specificații lipsă per categorie:")
    for spec, count in sorted(spec_stats.items(), key=lambda x: -x[1]):
        bar = "█" * (count // 5) + "░" * ((total - count) // 5)
        print(f"    {spec:12s}: {count:4d} lipsă  {bar}")

    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description='Scanează produse cu specificații lipsă')
    parser.add_argument('--id', type=int, help='ID produs specific')
    parser.add_argument('--from-id', type=int, dest='from_id', help='ID start range (inclusiv)')
    parser.add_argument('--to-id', type=int, dest='to_id', help='ID end range (inclusiv)')
    parser.add_argument('--limit', type=int, default=0, help='Limită produse (0 = toate)')
    parser.add_argument('--stats', action='store_true', help='Doar statistici, fără salvare JSON')
    parser.add_argument('--brand', type=str, default=None, help='Filtrare brand: ejolie, trendya, artista')
    args = parser.parse_args()

    # ── Încarcă feed-ul ────────────────────────────────────────────
    products = load_product_feed()

    # ── Filtru brand ───────────────────────────────────────────────
    if args.brand:
        products = [p for p in products if p.get('brand', '').lower() == args.brand.lower()]
        print(f"🏷️  Filtrat brand '{args.brand}': {len(products)} produse")

    # ── Filtru --id ────────────────────────────────────────────────
    if args.id:
        products = [p for p in products if str(p.get('id')) == str(args.id)]
        if not products:
            print(f"❌ Produs {args.id} nu a fost găsit în product_feed.json")
            sys.exit(1)
        print(f"🎯 Scanare produs specific: {args.id}")

    # ── Filtru --from-id / --to-id ─────────────────────────────────
    if args.from_id or args.to_id:
        from_id = args.from_id or 0
        to_id = args.to_id or 999999
        products = [p for p in products if from_id <= int(p.get('id', 0)) <= to_id]
        print(f"📏 Range: ID {from_id} → {to_id} ({len(products)} produse)")
        if not products:
            print(f"❌ Niciun produs în range-ul {from_id}-{to_id}")
            sys.exit(1)

    # ── Filtru --limit ─────────────────────────────────────────────
    if args.limit > 0:
        products = products[:args.limit]
        print(f"📏 Limitat la {args.limit} produse")

    # ── Scanare ────────────────────────────────────────────────────
    results = []
    errors = 0
    total = len(products)

    print(f"\n🔍 Scanare {total} produse...\n")

    for i, product in enumerate(products, 1):
        pid = product.get('id')
        name = product.get('title', product.get('name', ''))

        # Progress
        print(f"[{i}/{total}] Scanare {pid} - {name[:50]}...", end='', flush=True)

        result = scan_product(product)

        if result is None:
            errors += 1
            print(" ❌ EROARE")
            continue

        results.append(result)

        if result['complete']:
            print(f" ✅ 6/6")
        else:
            print(f" ⚠️  {6 - result['missing_count']}/6 ({', '.join(result['missing'][:2])}...)")

        # Pauză între requesturi (0.5s) — nu supraîncărcăm API-ul
        if i < total:
            time.sleep(0.5)

    # ── Afișare detalii per produs (dacă --id sau --limit mic) ─────
    if args.id or (args.limit and args.limit <= 5):
        for result in results:
            print_product_result(result)

    # ── Statistici ─────────────────────────────────────────────────
    if results:
        print_stats(results)

    # ── Erori ──────────────────────────────────────────────────────
    if errors > 0:
        print(f"\n⚠️  {errors} produse cu erori API (nu au fost scanate)")

    # ── Salvare JSON (doar produsele incomplete) ───────────────────
    if not args.stats and not args.id:
        incomplete = [r for r in results if not r['complete']]

        with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
            json.dump(incomplete, f, ensure_ascii=False, indent=2)

        print(f"\n💾 Salvat {len(incomplete)} produse incomplete în {OUTPUT_PATH.name}")

    elif args.id:
        # Pentru --id, salvăm doar rezultatul individual
        if results:
            single_path = SCRIPT_DIR / f'specs_scan_{args.id}.json'
            with open(single_path, 'w', encoding='utf-8') as f:
                json.dump(results[0], f, ensure_ascii=False, indent=2)
            print(f"\n💾 Salvat rezultat în {single_path.name}")

    print("\n✅ Scanare completă!")


if __name__ == '__main__':
    main()