#!/usr/bin/env python3
"""
generate_nir.py - Generare automată NIR (Notă de Intrare Recepție) pentru ejolie.ro
Trage date din Extended API și generează fișier Excel formatat.

Utilizare:
    python3 generate_nir.py --start 12356 --end 12415
    python3 generate_nir.py --ids 12356,12358,12360
    python3 generate_nir.py --start 12356 --end 12415 --output nir_martie_2026.xlsx
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime

import requests
from dotenv import load_dotenv
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# === CONFIG ===
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(SCRIPT_DIR, '..', '.env')
if not os.path.exists(ENV_PATH):
    ENV_PATH = os.path.join(SCRIPT_DIR, '.env')
load_dotenv(ENV_PATH)

API_KEY = os.getenv('EJOLIE_API_KEY')
API_BASE = 'https://ejolie.ro/api/'
HEADERS = {'User-Agent': 'Mozilla/5.0'}


def fetch_product(product_id):
    """Fetch un singur produs din Extended API."""
    url = f"{API_BASE}?id_produs={product_id}&apikey={API_KEY}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if str(product_id) in data:
            return data[str(product_id)]
        return None
    except Exception as e:
        print(f"  ✗ Eroare la produsul {product_id}: {e}")
        return None


def extract_nir_data(product):
    """Extrage datele necesare pentru NIR dintr-un produs API."""
    pid = product.get('id_produs', '')
    nume_full = product.get('nume', '')

    # Scoatem prefixul "Rochie " / "Bluza " etc. pentru nume scurt
    prefixes = ['Rochie ', 'Bluza ', 'Fusta ',
                'Sacou ', 'Palton ', 'Pantaloni ', 'Pulover ']
    nume_scurt = nume_full
    for prefix in prefixes:
        if nume_full.startswith(prefix):
            # Scoatem prefixul SI culoarea (ultimul cuvânt)
            rest = nume_full[len(prefix):]
            parts = rest.rsplit(' ', 1)
            if len(parts) > 1:
                nume_scurt = parts[0]  # Doar numele modelului
            else:
                nume_scurt = rest
            break

    # Culoare din specificatii
    culoare = ''
    for spec in product.get('specificatii', []):
        if spec['nume'] == 'Culoare':
            culoare = ', '.join(spec.get('valoare', []))
            break

    # Cod produs
    cod = product.get('cod_produs', '')

    # Mărimi și bucăți din optiuni
    optiuni = product.get('optiuni', {})
    marimi = []
    total_buc = 0
    for opt in optiuni.values():
        marimi.append(opt.get('nume_optiune', ''))
        total_buc += int(opt.get('stoc_fizic', 0))

    # Sortăm mărimile numeric
    try:
        marimi_sorted = sorted(marimi, key=lambda x: int(x))
    except ValueError:
        marimi_sorted = sorted(marimi)

    if marimi_sorted:
        marimi_str = f"{marimi_sorted[0]}-{marimi_sorted[-1]}"
    else:
        marimi_str = ''

    # Preț ieșire (vânzare)
    pret_iesire = float(product.get('pret', 0))
    # Dacă are preț discount activ, folosim acel preț
    pret_discount = float(product.get('pret_discount', 0))
    if pret_discount > 0:
        pret_iesire = pret_discount

    # Preț intrare (achiziție) din furnizor
    pret_intrare = 0
    furnizori = product.get('furnizor', [])
    if furnizori:
        pret_achizitie = furnizori[0].get('pret_achizitie', '0')
        pret_intrare = float(pret_achizitie)

    # Cota TVA
    cota_tva = int(product.get('cota_tva', 19))

    return {
        'id': pid,
        'nume': nume_scurt,
        'culoare': culoare,
        'cod': cod,
        'marimi': marimi_str,
        'buc': total_buc,
        'pret_intrare': pret_intrare,
        'pret_iesire': pret_iesire,
        'cota_tva': cota_tva,
    }


def generate_nir_excel(products_data, output_path):
    """Generează fișierul Excel NIR cu formule."""
    wb = Workbook()
    ws = wb.active
    ws.title = "NIR"

    # === STILURI ===
    header_font = Font(name='Arial', bold=True, size=11, color='FFFFFF')
    header_fill = PatternFill('solid', fgColor='4472C4')
    header_align = Alignment(
        horizontal='center', vertical='center', wrap_text=True)

    data_font = Font(name='Arial', size=10)
    data_align = Alignment(horizontal='center', vertical='center')
    data_align_left = Alignment(horizontal='left', vertical='center')

    money_format = '#,##0.00'
    int_format = '#,##0'

    total_font = Font(name='Arial', bold=True, size=11)
    total_fill = PatternFill('solid', fgColor='D9E2F3')

    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )

    # === TITLU ===
    ws.merge_cells('A1:N1')
    title_cell = ws['A1']
    title_cell.value = f"NIR - Notă de Intrare Recepție — {datetime.now().strftime('%d.%m.%Y')}"
    title_cell.font = Font(name='Arial', bold=True, size=14, color='1F4E79')
    title_cell.alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[1].height = 30

    # === HEADER (rândul 3) ===
    headers = [
        'Id produs', 'Nume', 'Culoare', 'Cod', 'Mărimi',
        'Buc', 'Preț intrare', 'Preț ieșire',
        'Valoare intrare', 'Valoare ieșire',
        'TVA', 'Adaos comercial', 'Cotă TVA', 'Total intrare'
    ]
    col_widths = [12, 20, 16, 16, 12, 8, 14, 14, 16, 16, 16, 16, 10, 16]

    for col_idx, (header, width) in enumerate(zip(headers, col_widths), 1):
        cell = ws.cell(row=3, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = thin_border
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    ws.row_dimensions[3].height = 35

    # === DATE PRODUSE (de la rândul 4) ===
    start_row = 4
    for i, prod in enumerate(products_data):
        row = start_row + i

        # A: Id produs
        ws.cell(row=row, column=1, value=int(prod['id'])).font = data_font
        ws.cell(row=row, column=1).alignment = data_align

        # B: Nume
        ws.cell(row=row, column=2, value=prod['nume']).font = data_font
        ws.cell(row=row, column=2).alignment = data_align_left

        # C: Culoare
        ws.cell(row=row, column=3, value=prod['culoare']).font = data_font
        ws.cell(row=row, column=3).alignment = data_align

        # D: Cod
        ws.cell(row=row, column=4, value=prod['cod']).font = data_font
        ws.cell(row=row, column=4).alignment = data_align

        # E: Mărimi
        ws.cell(row=row, column=5, value=prod['marimi']).font = data_font
        ws.cell(row=row, column=5).alignment = data_align

        # F: Bucăți
        ws.cell(row=row, column=6, value=prod['buc']).font = data_font
        ws.cell(row=row, column=6).alignment = data_align
        ws.cell(row=row, column=6).number_format = int_format

        # G: Preț intrare
        ws.cell(row=row, column=7, value=prod['pret_intrare']).font = data_font
        ws.cell(row=row, column=7).alignment = data_align
        ws.cell(row=row, column=7).number_format = money_format

        # H: Preț ieșire
        ws.cell(row=row, column=8, value=prod['pret_iesire']).font = data_font
        ws.cell(row=row, column=8).alignment = data_align
        ws.cell(row=row, column=8).number_format = money_format

        # I: Valoare intrare = Buc × Preț intrare (FORMULĂ)
        cell_i = ws.cell(row=row, column=9)
        cell_i.value = f'=F{row}*G{row}'
        cell_i.font = data_font
        cell_i.alignment = data_align
        cell_i.number_format = money_format

        # J: Valoare ieșire = Buc × Preț ieșire (FORMULĂ)
        cell_j = ws.cell(row=row, column=10)
        cell_j.value = f'=F{row}*H{row}'
        cell_j.font = data_font
        cell_j.alignment = data_align
        cell_j.number_format = money_format

        # K: TVA = Valoare ieșire × Cotă TVA / (100 + Cotă TVA) (FORMULĂ)
        cell_k = ws.cell(row=row, column=11)
        cell_k.value = f'=J{row}*M{row}/(100+M{row})'
        cell_k.font = data_font
        cell_k.alignment = data_align
        cell_k.number_format = money_format

        # L: Adaos comercial = Valoare ieșire - Valoare intrare - TVA (FORMULĂ)
        cell_l = ws.cell(row=row, column=12)
        cell_l.value = f'=J{row}-I{row}-K{row}'
        cell_l.font = data_font
        cell_l.alignment = data_align
        cell_l.number_format = money_format

        # M: Cotă TVA (procent)
        ws.cell(row=row, column=13, value=prod['cota_tva']).font = data_font
        ws.cell(row=row, column=13).alignment = data_align

        # N: Total intrare = Valoare intrare (FORMULĂ)
        cell_n = ws.cell(row=row, column=14)
        cell_n.value = f'=I{row}'
        cell_n.font = data_font
        cell_n.alignment = data_align
        cell_n.number_format = money_format

        # Border pe toate celulele rândului
        for col in range(1, 15):
            ws.cell(row=row, column=col).border = thin_border

        # Alternating row colors
        if i % 2 == 0:
            light_fill = PatternFill('solid', fgColor='F2F7FB')
            for col in range(1, 15):
                ws.cell(row=row, column=col).fill = light_fill

    # === RÂND TOTALURI ===
    total_row = start_row + len(products_data)
    ws.cell(row=total_row, column=1, value='TOTAL').font = total_font
    ws.merge_cells(f'A{total_row}:E{total_row}')
    ws.cell(row=total_row, column=1).alignment = Alignment(
        horizontal='right', vertical='center')

    # Totaluri cu formule SUM
    sum_cols = {
        6: int_format,     # F: Buc
        9: money_format,   # I: Valoare intrare
        10: money_format,  # J: Valoare ieșire
        11: money_format,  # K: TVA
        12: money_format,  # L: Adaos comercial
        14: money_format,  # N: Total intrare
    }
    last_data_row = total_row - 1
    for col, fmt in sum_cols.items():
        col_letter = get_column_letter(col)
        cell = ws.cell(row=total_row, column=col)
        cell.value = f'=SUM({col_letter}{start_row}:{col_letter}{last_data_row})'
        cell.font = total_font
        cell.alignment = data_align
        cell.number_format = fmt

    # Stil total row
    for col in range(1, 15):
        ws.cell(row=total_row, column=col).fill = total_fill
        ws.cell(row=total_row, column=col).border = thin_border

    # === FREEZE PANES ===
    ws.freeze_panes = 'A4'

    # === PRINT SETTINGS ===
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.orientation = 'landscape'
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0

    wb.save(output_path)
    return total_row


def main():
    parser = argparse.ArgumentParser(
        description='Generare NIR din Extended API')
    parser.add_argument('--start', type=int, help='ID produs start')
    parser.add_argument('--end', type=int, help='ID produs end')
    parser.add_argument('--ids', type=str,
                        help='Lista de ID-uri separate prin virgulă')
    parser.add_argument('--output', type=str, default=None,
                        help='Nume fișier output (default: nir_YYYY-MM-DD.xlsx)')
    args = parser.parse_args()

    if not API_KEY:
        print("✗ EJOLIE_API_KEY nu este setat în .env!")
        sys.exit(1)

    # Determinăm lista de ID-uri
    if args.ids:
        product_ids = [int(x.strip()) for x in args.ids.split(',')]
    elif args.start and args.end:
        product_ids = list(range(args.start, args.end + 1))
    else:
        print("✗ Specifică --start și --end SAU --ids")
        sys.exit(1)

    # Output filename
    if args.output:
        output_path = args.output
    else:
        output_path = f"nir_{datetime.now().strftime('%Y-%m-%d')}.xlsx"

    print(f"═══ Generare NIR ═══")
    print(
        f"  Produse: {len(product_ids)} (ID {product_ids[0]} → {product_ids[-1]})")
    print(f"  Output:  {output_path}")
    print()

    # Fetch produse din API
    products_data = []
    skipped = 0
    for i, pid in enumerate(product_ids):
        print(f"  [{i+1}/{len(product_ids)}] Fetch produs {pid}...", end=' ')
        product = fetch_product(pid)

        if not product:
            print("✗ Nu există sau eroare API")
            skipped += 1
            continue

        nir_row = extract_nir_data(product)

        if nir_row['buc'] == 0:
            print(f"⚠ Stoc 0 - {nir_row['nume']} {nir_row['culoare']} (skip)")
            skipped += 1
            continue

        if nir_row['pret_intrare'] == 0:
            print(
                f"⚠ Preț achiziție 0 - {nir_row['nume']} {nir_row['culoare']}")

        print(f"✓ {nir_row['nume']} {nir_row['culoare']} | {nir_row['buc']} buc | intrare: {nir_row['pret_intrare']} | ieșire: {nir_row['pret_iesire']}")
        products_data.append(nir_row)

        # Rate limiting - nu supraîncărcăm API-ul
        if i < len(product_ids) - 1:
            time.sleep(0.3)

    print()
    if not products_data:
        print("✗ Niciun produs valid găsit!")
        sys.exit(1)

    # Generare Excel
    print(f"  Generare Excel cu {len(products_data)} produse...")
    total_row = generate_nir_excel(products_data, output_path)

    # Sumar
    total_intrare = sum(p['buc'] * p['pret_intrare'] for p in products_data)
    total_iesire = sum(p['buc'] * p['pret_iesire'] for p in products_data)
    total_buc = sum(p['buc'] for p in products_data)

    print(f"""
═══ NIR GENERAT CU SUCCES ═══
  Fișier:           {output_path}
  Produse:          {len(products_data)} (skip: {skipped})
  Total bucăți:     {total_buc}
  Valoare intrare:  {total_intrare:,.2f} RON
  Valoare ieșire:   {total_iesire:,.2f} RON
  Adaos brut:       {total_iesire - total_intrare:,.2f} RON
""")


if __name__ == '__main__':
    main()
