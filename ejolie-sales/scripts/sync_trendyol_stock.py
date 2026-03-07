#!/usr/bin/env python3
"""
sync_trendyol_stock.py v3 - Sincronizare stoc Trendyol cu ejolie.ro

Generează fișier Excel în formatul Trendyol "Actualizează stocul și prețul":
  Cod de bare | Stoc | Preț de vânzare Trendyol

Upload: partner.trendyol.com → Produse → Acțiuni colective → Încărcați șablonul
        Selectează: "Actualizează stocul și prețul"

Utilizare:
    python3 sync_trendyol_stock.py --input Products_export.xlsx
    python3 sync_trendyol_stock.py --input Products_export.xlsx --telegram
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime

import requests
from dotenv import load_dotenv
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment

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
        if not data or not isinstance(data, dict):
            return {}, f'(inexistent ID {ejolie_id})'
        product = data.get(str(ejolie_id), {})
        if not product:
            return {}, f'(gol ID {ejolie_id})'
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
        print("  ⚠ TELEGRAM_BOT_TOKEN nu e setat")
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
        description='Sync stoc Trendyol cu ejolie.ro')
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
        print(f"✗ Mapping {args.map} nu există!")
        sys.exit(1)

    output_path = args.output or os.path.join(
        SCRIPT_DIR, f"stoc_trendyol_{datetime.now().strftime('%Y-%m-%d_%H%M')}.xlsx"
    )

    print(f"═══ Sync Stoc Trendyol v3 ═══")
    print(f"  Input:    {args.input}")
    print(f"  Output:   {output_path}")
    print(f"  Telegram: {'Da' if args.telegram else 'Nu'}")
    print()

    # === STEP 1: Load barcode mapping ===
    with open(args.map, 'r') as f:
        barcode_map = json.load(f)
    print(
        f"  ✓ Mapping: {len(barcode_map)} barcodes → {len(set(barcode_map.values()))} produse")

    # === STEP 2: Read Trendyol export ===
    wb_in = load_workbook(args.input)
    ws_in = wb_in['Produse']

    headers = {}
    for col in range(1, ws_in.max_column + 1):
        val = ws_in.cell(row=1, column=col).value
        if val:
            headers[val] = col

    barcode_col = headers['Cod de bare']
    size_col = headers['Mărime']
    name_col = headers['Numele produsului']
    price_col = headers['Preț de vânzare Trendyol']
    stoc_old_col = headers['Stoc']

    # Grupăm pe ejolie_id
    ejolie_groups = {}  # ejolie_id → [(barcode, size, name, price, old_stock)]
    no_barcode = []
    for row in range(2, ws_in.max_row + 1):
        barcode_raw = ws_in.cell(row=row, column=barcode_col).value
        barcode = str(int(barcode_raw)) if barcode_raw else ''
        size = str(ws_in.cell(row=row, column=size_col).value or '').strip()
        name = str(ws_in.cell(row=row, column=name_col).value or '')
        price = ws_in.cell(row=row, column=price_col).value or 0
        old_stock = ws_in.cell(row=row, column=stoc_old_col).value or 0

        ejolie_id = barcode_map.get(barcode)
        if ejolie_id:
            if ejolie_id not in ejolie_groups:
                ejolie_groups[ejolie_id] = []
            ejolie_groups[ejolie_id].append(
                (barcode, size, name, float(price), int(old_stock)))
        else:
            no_barcode.append((barcode, name, size))

    total_rows = ws_in.max_row - 1
    wb_in.close()
    print(f"  ✓ {total_rows} rânduri → {len(ejolie_groups)} produse unice")

    # === STEP 3: Fetch stoc din API și construiește output ===
    output_rows = []  # [(barcode, new_stock, price)]
    stats = {'total': total_rows, 'matched': 0, 'stock_changed': 0,
             'stock_zero': 0, 'stock_same': 0, 'api_empty': 0}

    print(f"\n  Fetch stoc din API ({len(ejolie_groups)} produse)...\n")

    for i, (ejolie_id, items) in enumerate(ejolie_groups.items()):
        sizes, product_name = fetch_stock_by_id(ejolie_id)

        if sizes is None:
            # API error - keep old stock
            print(f"    ✗ API error ID {ejolie_id}: {product_name}")
            for barcode, size, name, price, old_stock in items:
                output_rows.append((barcode, old_stock, price))
            time.sleep(0.5)
            continue

        for barcode, size, name, price, old_stock in items:
            new_stock = sizes.get(size, 0)
            stats['matched'] += 1
            output_rows.append((barcode, new_stock, price))

            if new_stock == 0:
                stats['stock_zero'] += 1
                if old_stock != 0:
                    stats['stock_changed'] += 1
                    print(
                        f"    ⚠ STOC 0: {name} (mărime {size}) | era: {old_stock} → 0")
            elif new_stock != old_stock:
                stats['stock_changed'] += 1
                print(
                    f"    ✎ {name} (mărime {size}) | {old_stock} → {new_stock}")
            else:
                stats['stock_same'] += 1

        if not sizes:
            stats['api_empty'] += 1

        if (i + 1) % 20 == 0:
            print(f"    ... {i+1}/{len(ejolie_groups)} produse procesate")
        time.sleep(0.3)

    # No-barcode items → stoc 0
    for barcode, name, size in no_barcode:
        output_rows.append((barcode, 0, 0))
        print(f"    ? NO BARCODE: {barcode} | {name} size {size}")

    # === STEP 4: Generate Trendyol stock update Excel ===
    print(f"\n  Generez Excel Trendyol format ({len(output_rows)} rânduri)...")

    wb_out = Workbook()
    ws_out = wb_out.active
    ws_out.title = "Stoc"

    # Header - exact cum cere Trendyol
    ws_out['A1'] = 'Cod de bare'
    ws_out['B1'] = 'Stoc'
    ws_out['C1'] = 'Preț de vânzare Trendyol'

    header_font = Font(name='Arial', bold=True, size=11)
    for col in ['A', 'B', 'C']:
        ws_out[f'{col}1'].font = header_font

    ws_out.column_dimensions['A'].width = 20
    ws_out.column_dimensions['B'].width = 10
    ws_out.column_dimensions['C'].width = 25

    # Data rows
    zero_fill = PatternFill('solid', fgColor='FFC7CE')
    changed_fill = PatternFill('solid', fgColor='C6EFCE')

    for idx, (barcode, stock, price) in enumerate(output_rows, start=2):
        ws_out.cell(row=idx, column=1, value=int(barcode) if barcode else '')
        ws_out.cell(row=idx, column=2, value=stock)
        ws_out.cell(row=idx, column=3, value=price)

        if stock == 0:
            ws_out.cell(row=idx, column=2).fill = zero_fill

    ws_out.freeze_panes = 'A2'
    wb_out.save(output_path)

    # === STEP 5: Report ===
    print(f"""
═══ SINCRONIZARE COMPLETĂ ═══
  Total rânduri:       {stats['total']}
  Matched:             {stats['matched']} ({stats['matched']*100//max(stats['total'], 1)}%)
  Stoc modificat:      {stats['stock_changed']}
  Stoc zero (epuizat): {stats['stock_zero']}
  Stoc neschimbat:     {stats['stock_same']}
  API empty (șterse):  {stats['api_empty']}
  API calls:           {len(ejolie_groups)}

  📁 Fișier salvat: {output_path}

  ⬆ UPLOAD PE TRENDYOL:
    1. partner.trendyol.com → Produse → Acțiuni colective
    2. Tab "Încărcați șablonul"
    3. Selectează "Actualizează stocul și prețul"
    4. Upload fișierul {os.path.basename(output_path)}""")

    # === STEP 6: Telegram ===
    if args.telegram:
        print(f"\n  📤 Trimit pe Telegram...")
        caption = (
            f"📦 <b>Stoc Trendyol — {datetime.now().strftime('%d.%m.%Y %H:%M')}</b>\n\n"
            f"✅ Matched: {stats['matched']}/{stats['total']}\n"
            f"✎ Modificat: {stats['stock_changed']}\n"
            f"⚠ Stoc zero: {stats['stock_zero']}\n"
            f"🔄 API calls: {len(ejolie_groups)}\n\n"
            f"⬆ Upload: Acțiuni colective → Actualizează stocul și prețul"
        )
        if send_telegram_file(output_path, caption=caption):
            print("  ✓ Trimis pe Telegram!")
        else:
            print("  ✗ Eroare Telegram")


if __name__ == '__main__':
    main()
