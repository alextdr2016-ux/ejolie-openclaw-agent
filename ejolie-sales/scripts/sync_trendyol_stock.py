#!/usr/bin/env python3
"""
sync_trendyol_stock.py v2 - Sincronizare stoc Trendyol cu ejolie.ro
Folosește barcode mapping (din fișierul de upload) pentru match 100%.

Fluxul:
  1. Citește barcode_ejolie_map.json (barcode → id_produs ejolie)
  2. Grupează Trendyol rows pe id_produs (1 API call per produs, nu per rând)
  3. Fetch stoc din API pe id_produs
  4. Match pe mărime → actualizează coloana Stoc
  5. Trimite Excel pe Telegram

Utilizare:
    python3 sync_trendyol_stock.py --input Products_07.03.2026.xlsx
    python3 sync_trendyol_stock.py --input Products_07.03.2026.xlsx --telegram
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime

import requests
from dotenv import load_dotenv
from openpyxl import load_workbook
from openpyxl.styles import PatternFill

# === CONFIG ===
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(SCRIPT_DIR, '..', '.env')
if not os.path.exists(ENV_PATH):
    ENV_PATH = os.path.join(SCRIPT_DIR, '.env')
load_dotenv(ENV_PATH)

API_KEY = os.getenv('EJOLIE_API_KEY')
API_BASE = 'https://ejolie.ro/api/'
HEADERS = {'User-Agent': 'Mozilla/5.0'}
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '44151343')
MAP_FILE = os.path.join(SCRIPT_DIR, 'barcode_ejolie_map.json')


# ═══════════════════════════════════════════
#  API
# ═══════════════════════════════════════════

def fetch_stock_by_id(ejolie_id):
    """Fetch stoc per mărime prin id_produs."""
    url = f"{API_BASE}?id_produs={ejolie_id}&apikey={API_KEY}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        product = data.get(str(ejolie_id), {})
        optiuni = product.get('optiuni', {})
        sizes = {}
        for opt in optiuni.values():
            marime = str(opt.get('nume_optiune', '')).strip()
            stoc = int(opt.get('stoc_fizic', 0))
            sizes[marime] = stoc
        return sizes, product.get('nume', '')
    except Exception as e:
        return None, str(e)


# ═══════════════════════════════════════════
#  TELEGRAM
# ═══════════════════════════════════════════

def send_telegram_file(filepath, caption=''):
    if not TELEGRAM_BOT_TOKEN:
        print("  ⚠ TELEGRAM_BOT_TOKEN nu e setat în .env")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
    try:
        with open(filepath, 'rb') as f:
            resp = requests.post(url,
                                 data={'chat_id': TELEGRAM_CHAT_ID,
                                       'caption': caption, 'parse_mode': 'HTML'},
                                 files={'document': f}, timeout=60)
        return resp.status_code == 200
    except Exception as e:
        print(f"  ✗ Telegram eroare: {e}")
        return False


# ═══════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description='Sincronizare stoc Trendyol cu ejolie.ro')
    parser.add_argument('--input', type=str, required=True,
                        help='Fișier Excel Trendyol export')
    parser.add_argument('--output', type=str,
                        default=None, help='Fișier output')
    parser.add_argument('--telegram', action='store_true',
                        help='Trimite pe Telegram')
    parser.add_argument('--map', type=str, default=MAP_FILE,
                        help='Barcode mapping JSON')
    args = parser.parse_args()

    if not API_KEY:
        print("✗ EJOLIE_API_KEY nu e setat!")
        sys.exit(1)
    if not os.path.exists(args.input):
        print(f"✗ Fișierul {args.input} nu există!")
        sys.exit(1)
    if not os.path.exists(args.map):
        print(
            f"✗ Mapping {args.map} nu există! Rulează mai întâi generate_barcode_map.py")
        sys.exit(1)

    output_path = args.output or os.path.join(
        SCRIPT_DIR, f"stoc_trendyol_{datetime.now().strftime('%Y-%m-%d_%H%M')}.xlsx"
    )

    print(f"═══ Sync Stoc Trendyol v2 (barcode) ═══")
    print(f"  Input:    {args.input}")
    print(f"  Mapping:  {args.map}")
    print(f"  Output:   {output_path}")
    print(f"  Telegram: {'Da' if args.telegram else 'Nu'}")
    print()

    # === STEP 1: Load barcode mapping ===
    with open(args.map, 'r') as f:
        barcode_map = json.load(f)
    print(
        f"  ✓ Mapping: {len(barcode_map)} barcodes → {len(set(barcode_map.values()))} produse")

    # === STEP 2: Read Trendyol Excel & group by ejolie_id ===
    wb = load_workbook(args.input)
    ws = wb['Produse']

    headers = {}
    for col in range(1, ws.max_column + 1):
        val = ws.cell(row=1, column=col).value
        if val:
            headers[val] = col

    barcode_col = headers['Cod de bare']
    size_col = headers['Mărime']
    stoc_col = headers['Stoc']
    name_col = headers['Numele produsului']
    cod_col = headers['Codul modelului']

    # Grupăm rândurile per ejolie_id
    ejolie_groups = {}  # ejolie_id → [(row_num, size, old_stock, name)]
    no_barcode_match = []
    for row in range(2, ws.max_row + 1):
        barcode = str(int(ws.cell(row=row, column=barcode_col).value)) if ws.cell(
            row=row, column=barcode_col).value else ''
        size = str(ws.cell(row=row, column=size_col).value or '').strip()
        old_stock = ws.cell(row=row, column=stoc_col).value
        name = str(ws.cell(row=row, column=name_col).value or '')
        cod = str(ws.cell(row=row, column=cod_col).value or '')

        ejolie_id = barcode_map.get(barcode)
        if ejolie_id:
            if ejolie_id not in ejolie_groups:
                ejolie_groups[ejolie_id] = []
            ejolie_groups[ejolie_id].append((row, size, old_stock, name, cod))
        else:
            no_barcode_match.append((row, barcode, name, size))

    total_rows = ws.max_row - 1
    print(f"  ✓ {total_rows} rânduri → {len(ejolie_groups)} produse unice ejolie")
    if no_barcode_match:
        print(f"  ⚠ {len(no_barcode_match)} rânduri fără barcode match")

    # === STEP 3: Fetch stoc per produs și actualizare ===
    changed_fill = PatternFill('solid', fgColor='C6EFCE')
    zero_fill = PatternFill('solid', fgColor='FFC7CE')
    error_fill = PatternFill('solid', fgColor='FFEB9C')

    stats = {'total': total_rows, 'matched': 0, 'stock_changed': 0,
             'stock_zero': 0, 'stock_same': 0, 'api_error': 0, 'no_barcode': len(no_barcode_match)}

    print(f"\n  Fetch stoc din API ({len(ejolie_groups)} produse)...\n")

    for i, (ejolie_id, rows_data) in enumerate(ejolie_groups.items()):
        # Fetch o singură dată per produs
        sizes, product_name = fetch_stock_by_id(ejolie_id)

        if sizes is None:
            print(f"    ✗ API error ID {ejolie_id}: {product_name}")
            stats['api_error'] += len(rows_data)
            for row_num, size, old_stock, name, cod in rows_data:
                ws.cell(row=row_num, column=stoc_col).fill = error_fill
            time.sleep(0.5)
            continue

        # Actualizăm fiecare rând (mărime) al produsului
        for row_num, size, old_stock, name, cod in rows_data:
            stoc = sizes.get(size, 0)
            old_val = int(old_stock) if old_stock else 0
            stats['matched'] += 1

            ws.cell(row=row_num, column=stoc_col, value=stoc)

            if stoc == 0:
                ws.cell(row=row_num, column=stoc_col).fill = zero_fill
                stats['stock_zero'] += 1
                if old_val != 0:
                    stats['stock_changed'] += 1
                    print(
                        f"    ⚠ STOC 0: {name} (mărime {size}) | era: {old_val} → 0")
            elif stoc != old_val:
                ws.cell(row=row_num, column=stoc_col).fill = changed_fill
                stats['stock_changed'] += 1
                print(f"    ✎ {name} (mărime {size}) | {old_val} → {stoc}")
            else:
                stats['stock_same'] += 1

        # Progress
        if (i + 1) % 20 == 0:
            print(f"    ... {i+1}/{len(ejolie_groups)} produse procesate")

        time.sleep(0.3)

    # Mark no-barcode rows
    for row_num, barcode, name, size in no_barcode_match:
        ws.cell(row=row_num, column=stoc_col).fill = error_fill
        print(f"    ? NO BARCODE: {barcode} | {name} size {size}")

    # === STEP 4: Save ===
    wb.save(output_path)

    # === STEP 5: Report ===
    print(f"""
═══ SINCRONIZARE COMPLETĂ ═══
  Total rânduri:       {stats['total']}
  Matched:             {stats['matched']} ({stats['matched']*100//max(stats['total'], 1)}%)
  No barcode match:    {stats['no_barcode']}
  API errors:          {stats['api_error']}
  Stoc modificat:      {stats['stock_changed']}
  Stoc zero (epuizat): {stats['stock_zero']}
  Stoc neschimbat:     {stats['stock_same']}
  API calls:           {len(ejolie_groups)} (1 per produs, nu per rând!)

  📁 Fișier salvat: {output_path}""")

    # === STEP 6: Telegram ===
    if args.telegram:
        print(f"\n  📤 Trimit pe Telegram...")
        caption = (
            f"📦 <b>Stoc Trendyol actualizat — {datetime.now().strftime('%d.%m.%Y %H:%M')}</b>\n\n"
            f"✅ Matched: {stats['matched']}/{stats['total']} ({stats['matched']*100//max(stats['total'], 1)}%)\n"
            f"✎ Stoc modificat: {stats['stock_changed']}\n"
            f"⚠ Stoc zero: {stats['stock_zero']}\n"
            f"🔄 API calls: {len(ejolie_groups)}"
        )
        if send_telegram_file(output_path, caption=caption):
            print("  ✓ Trimis pe Telegram!")
        else:
            print("  ✗ Eroare Telegram")


if __name__ == '__main__':
    main()
