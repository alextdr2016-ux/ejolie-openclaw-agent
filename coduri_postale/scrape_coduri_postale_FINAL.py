#!/usr/bin/env python3
"""
Script: scrape_coduri_postale_FINAL.py  v2
Extrage TOATE codurile postale din judetul Dolj de pe codul-postal.ro

Fix v2: Accept-Encoding fara brotli (cauza eroare decompresie pe server)
"""

import requests
import json
import time
import re
import os
import csv
from datetime import datetime

BASE_URL = "https://www.codul-postal.ro"
DELAY = 0.3

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ro-RO,ro;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",  # NO brotli - causes decode errors
}

ZM_CRAIOVA = {
    "Craiova", "Filiaşi", "Filiași", "Segarcea",
    "Almăj", "Beharca", "Bogea", "Cotofenii din Față", "Cotofenii din Faţă", "Moşneni", "Moșneni", "Şitoaia", "Șitoaia",
    "Brădeşti", "Brădești", "Brădeştii Bătrâni", "Brădeștii Bătrâni", "Meteu", "Piscani", "Răcarii de Jos", "Tatomireşti", "Tatomirești",
    "Breasta", "Cotu", "Crovna", "Făget", "Obedin", "Roşieni", "Roșieni", "Valea Lungului",
    "Bucovăţ", "Bucovăț", "Cârligei", "Italieni", "Leamna de Jos", "Leamna de Sus", "Palilula", "Sărbătoarea",
    "Calopăr", "Bâzdâna", "Belcinu", "Panaghia", "Sălcuţa", "Sălcuța",
    "Cârcea", "Coşoveni", "Coșoveni",
    "Gherceşti", "Ghercești", "Gârleşti", "Gârlești", "Luncşoru", "Luncșoru", "Ungureni", "Ungurenii Mici",
    "Işalniţa", "Ișalnița", "Izvoare",
    "Malu Mare", "Ghindeni", "Preajba",
    "Mischii", "Călineşti", "Călinești", "Gogoşeşti", "Gogoșești", "Mlecăneşti", "Mlecănești", "Motoci", "Urecheşti", "Urechești",
    "Murgaşi", "Murgași", "Gaia", "Picăturile", "Rupturile", "Veleşti", "Velești",
    "Pieleşti", "Pielești", "Câmpeni", "Lânga",
    "Predeşti", "Predești", "Bucicani", "Cârstovani", "Frasin", "Milovan", "Pleşoi", "Pleșoi", "Predeştii Mici", "Predeștii Mici",
    "Şimnicu de Sus", "Șimnicu de Sus", "Albeşti", "Albești", "Cornetu", "Deleni", "Dudoviceşti", "Dudovicești",
    "Floreşti", "Florești", "Izvor", "Jieni", "Leşile", "Leșile", "Mileşti", "Milești", "Româneşti", "Românești",
    "Teasc", "Secui",
    "Terpeziţa", "Terpezița", "Căciulatu", "Căruia", "Floran", "Lazu",
    "Ţuglui", "Țuglui", "Jiul", "Unirea",
    "Vârvoru de Jos", "Bujor", "Ciutura", "Criva", "Dobromira", "Drăgoaia", "Gabru", "Vârvor",
    "Vela", "Bucovicior", "Cetăţuia", "Cetățuia", "Desnăţui", "Desnățui", "Gubaucea", "Segleţ", "Segleț", "Suharu", "Ştiubei", "Știubei",
    "Făcăi", "Mofleni", "Popoveni", "Şimnicu de Jos", "Șimnicu de Jos",
    "Almăjel", "Bâlta", "Branişte", "Braniște", "Fratoştița", "Fratostița", "Răcarii de Sus", "Uscăci",
}


def get_localities(session):
    resp = session.get(f"{BASE_URL}/judet/dolj", timeout=15)
    resp.raise_for_status()

    pattern = r'href="(/judet/dolj/([^"]+))"[^>]*>'
    matches = re.findall(pattern, resp.text)

    localities = []
    seen = set()
    for path, slug in matches:
        slug = slug.strip('/')
        if slug and slug not in seen and '/' not in slug:
            seen.add(slug)
            # Get the display name from nearby text
            name_pattern = rf'href="{re.escape(path)}"[^>]*>\s*(?:<[^>]+>)*\s*([^<]+)'
            name_match = re.search(name_pattern, resp.text)
            name = name_match.group(1).strip(
            ) if name_match else slug.replace('-', ' ').title()
            localities.append({'name': name, 'slug': slug,
                              'url': f"{BASE_URL}{path}"})

    return localities


def scrape_locality(session, locality):
    try:
        resp = session.get(locality['url'], timeout=20)
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        print(f"  [EROARE] {locality['name']}: {e}")
        return []

    results = []

    # Pattern 1: tabel cu 3 coloane (strada, numere, cod) - orase mari
    pattern3 = r'<tr[^>]*>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*</tr>'
    rows = re.findall(pattern3, html, re.DOTALL)

    for strada_raw, numere_raw, cod_raw in rows:
        strada = re.sub(r'<[^>]+>', '', strada_raw).strip()
        numere = re.sub(r'<[^>]+>', '', numere_raw).strip()
        cod = re.sub(r'<[^>]+>', '', cod_raw).strip()

        if not cod or not cod.isdigit() or len(cod) != 6:
            continue
        if cod.lower().startswith('cod'):
            continue

        strada_full = f"{strada} {numere}".strip() if numere else strada
        results.append({
            'cod_postal': cod,
            'judet': 'Dolj',
            'localitate': locality['name'],
            'strada': strada_full,
            'numere': numere,
            'in_zm_craiova': locality['name'] in ZM_CRAIOVA,
        })

    # Pattern 2: tabel cu 2 coloane (localitate, cod) - sate mici
    if not results:
        pattern2 = r'<tr[^>]*>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*</tr>'
        rows2 = re.findall(pattern2, html, re.DOTALL)
        for col1_raw, col2_raw in rows2:
            col1 = re.sub(r'<[^>]+>', '', col1_raw).strip()
            col2 = re.sub(r'<[^>]+>', '', col2_raw).strip()
            # Decide which is the code
            if col2.isdigit() and len(col2) == 6:
                results.append({
                    'cod_postal': col2, 'judet': 'Dolj', 'localitate': locality['name'],
                    'strada': col1 if col1 != locality['name'] else '',
                    'numere': '', 'in_zm_craiova': locality['name'] in ZM_CRAIOVA,
                })
            elif col1.isdigit() and len(col1) == 6:
                results.append({
                    'cod_postal': col1, 'judet': 'Dolj', 'localitate': locality['name'],
                    'strada': col2, 'numere': '',
                    'in_zm_craiova': locality['name'] in ZM_CRAIOVA,
                })

    # Fallback: cauta orice cod postal 20xxxx in pagina
    if not results:
        codes = re.findall(r'\b(20\d{4})\b', html)
        codes = list(set(codes))
        for cod in codes:
            results.append({
                'cod_postal': cod, 'judet': 'Dolj', 'localitate': locality['name'],
                'strada': '', 'numere': '',
                'in_zm_craiova': locality['name'] in ZM_CRAIOVA,
            })

    return results


def export_to_excel(all_data, zm_data, filename):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    wb = Workbook()
    hf = Font(name='Arial', bold=True, size=11, color='FFFFFF')
    hfill = PatternFill('solid', fgColor='2F5496')
    ha = Alignment(horizontal='center', vertical='center', wrap_text=True)
    tb = Border(left=Side(style='thin'), right=Side(style='thin'),
                top=Side(style='thin'), bottom=Side(style='thin'))
    zm_fill = PatternFill('solid', fgColor='E2EFDA')
    headers = ['Nr.', 'Cod Poștal', 'Județ',
               'Localitate', 'Strada', 'Numere/Blocuri']

    def write_sheet(ws, title, data, start_row=4):
        ws.merge_cells(f'A1:F1')
        ws['A1'] = title
        ws['A1'].font = Font(name='Arial', bold=True, size=14, color='2F5496')
        ws['A1'].alignment = Alignment(horizontal='center')
        ws.merge_cells(f'A2:F2')
        ws['A2'] = f'Sursa: codul-postal.ro | {datetime.now().strftime("%d.%m.%Y %H:%M")}'
        ws['A2'].font = Font(name='Arial', size=10,
                             italic=True, color='666666')
        ws['A2'].alignment = Alignment(horizontal='center')

        hr = start_row
        for col, h in enumerate(headers, 1):
            c = ws.cell(row=hr, column=col, value=h)
            c.font, c.fill, c.alignment, c.border = hf, hfill, ha, tb

        data.sort(key=lambda x: (x['localitate'],
                  x['strada'], x['cod_postal']))
        for i, rd in enumerate(data):
            row = hr + 1 + i
            vals = [i+1, rd['cod_postal'], rd['judet'],
                    rd['localitate'], rd['strada'], rd.get('numere', '')]
            for col, val in enumerate(vals, 1):
                c = ws.cell(row=row, column=col, value=val)
                c.font = Font(name='Arial', size=10, bold=(col == 2))
                c.alignment = Alignment(horizontal='center') if col in (
                    1, 2) else Alignment()
                c.border = tb
                if rd.get('in_zm_craiova'):
                    c.fill = zm_fill

        for col, w in {'A': 7, 'B': 12, 'C': 10, 'D': 22, 'E': 45, 'F': 35}.items():
            ws.column_dimensions[col].width = w
        ws.freeze_panes = f'A{hr+1}'
        ws.auto_filter.ref = f'A{hr}:F{hr + len(data)}'

    # Sheet 1: ZM Craiova
    ws1 = wb.active
    ws1.title = "ZM Craiova"
    write_sheet(
        ws1, 'CODURI POȘTALE - ZONA METROPOLITANĂ CRAIOVA (2026)', zm_data)

    # Sheet 2: Tot Dolj
    ws2 = wb.create_sheet("Tot Dolj")
    write_sheet(ws2, 'CODURI POȘTALE - JUDEȚUL DOLJ COMPLET (2026)', all_data)

    # Sheet 3: Sumar
    ws3 = wb.create_sheet("Sumar")
    ws3['A1'] = 'SUMAR PE LOCALITĂȚI'
    ws3['A1'].font = Font(name='Arial', bold=True, size=14, color='2F5496')
    for col, h in enumerate(['Localitate', 'Nr. Intrări', 'Coduri Unice', 'ZM Craiova'], 1):
        c = ws3.cell(row=3, column=col, value=h)
        c.font, c.fill, c.border = hf, hfill, tb

    from collections import Counter
    loc_counts = Counter(r['localitate'] for r in all_data)
    loc_unique_codes = {}
    for r in all_data:
        loc_unique_codes.setdefault(
            r['localitate'], set()).add(r['cod_postal'])

    for i, (loc, cnt) in enumerate(sorted(loc_counts.items()), 4):
        ws3.cell(row=i, column=1, value=loc).border = tb
        ws3.cell(row=i, column=2, value=cnt).border = tb
        ws3.cell(row=i, column=2).alignment = Alignment(horizontal='center')
        ws3.cell(row=i, column=3, value=len(
            loc_unique_codes.get(loc, set()))).border = tb
        ws3.cell(row=i, column=3).alignment = Alignment(horizontal='center')
        is_zm = 'DA' if loc in ZM_CRAIOVA else ''
        ws3.cell(row=i, column=4, value=is_zm).border = tb
        ws3.cell(row=i, column=4).alignment = Alignment(horizontal='center')
        if is_zm:
            for col in range(1, 5):
                ws3.cell(row=i, column=col).fill = zm_fill

    tr = 4 + len(loc_counts)
    ws3.cell(row=tr, column=1, value='TOTAL').font = Font(
        name='Arial', bold=True)
    ws3.cell(row=tr, column=1).border = tb
    ws3.cell(row=tr, column=2, value=len(all_data)
             ).font = Font(name='Arial', bold=True)
    ws3.cell(row=tr, column=2).border = tb
    ws3.cell(row=tr, column=3, value=len(
        set(r['cod_postal'] for r in all_data))).font = Font(name='Arial', bold=True)
    ws3.cell(row=tr, column=3).border = tb

    for col, w in {'A': 25, 'B': 12, 'C': 14, 'D': 14}.items():
        ws3.column_dimensions[col].width = w

    wb.save(filename)


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))

    print("=" * 65)
    print("  CODURI POSTALE DOLJ COMPLET - codul-postal.ro")
    print(f"  {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print("=" * 65)

    session = requests.Session()
    session.headers.update(HEADERS)

    print("\n[1] Extrag lista localitati Dolj...")
    localities = get_localities(session)
    print(f"    ✅ {len(localities)} localitati")
    if not localities:
        print("    ❌ Eroare. Oprire.")
        return

    print(f"\n[2] Extrag coduri postale...\n")
    all_data = []
    errors = []

    for i, loc in enumerate(localities):
        results = scrape_locality(session, loc)
        all_data.extend(results)

        zm = " [ZM]" if loc['name'] in ZM_CRAIOVA else ""
        if results:
            print(
                f"  [{i+1}/{len(localities)}] {loc['name']}{zm}: {len(results)}")
        elif zm:
            print(f"  [{i+1}/{len(localities)}] {loc['name']}{zm}: 0 ⚠️")
            errors.append(loc['name'])

        time.sleep(DELAY)

    # Dedup
    unique = {}
    for r in all_data:
        unique[f"{r['cod_postal']}|{r['localitate']}|{r['strada']}"] = r
    all_data = list(unique.values())

    zm_data = [r for r in all_data if r.get('in_zm_craiova')]

    print(f"\n{'=' * 65}")
    print(
        f"  Tot Dolj:   {len(all_data)} intrari | {len(set(r['cod_postal'] for r in all_data))} coduri | {len(set(r['localitate'] for r in all_data))} localitati")
    print(
        f"  ZM Craiova: {len(zm_data)} intrari | {len(set(r['cod_postal'] for r in zm_data))} coduri | {len(set(r['localitate'] for r in zm_data))} localitati")
    if errors:
        print(f"  ⚠️  Erori la: {', '.join(errors)}")
    print(f"{'=' * 65}")

    xlsx = os.path.join(script_dir, "coduri_postale_dolj_COMPLET_2026.xlsx")
    export_to_excel(all_data, zm_data, xlsx)
    print(f"\n✅ Excel: {xlsx}")

    csv_f = os.path.join(script_dir, "coduri_postale_dolj_2026.csv")
    with open(csv_f, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=[
                           'cod_postal', 'judet', 'localitate', 'strada', 'numere', 'in_zm_craiova'])
        w.writeheader()
        w.writerows(sorted(all_data, key=lambda x: (
            x['localitate'], x['cod_postal'])))
    print(f"✅ CSV: {csv_f}")

    with open(os.path.join(script_dir, "coduri_postale_dolj_2026.json"), 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    print(f"✅ JSON salvat")

    print(f"\n🎉 GATA! Output: {script_dir}")


if __name__ == "__main__":
    main()
