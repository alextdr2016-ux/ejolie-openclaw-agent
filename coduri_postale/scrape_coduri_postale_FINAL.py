#!/usr/bin/env python3
"""
scrape_coduri_postale_FINAL.py v3
Sursa: codul-postal.ro | HTML static | ~2 min

Structura HTML descoperita:
  Lista localitati:
    <a href="/judet/dolj/craiova" class="loc" data-name="craiova">
      <span class="loc-name">Craiova</span>
      <span class="loc-code">1557 străzi</span>
    </a>
    
  Tabel coduri (3 coloane): <tr><td>Strada</td><td>Numere</td><td>Cod</td></tr>
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
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "ro-RO,ro;q=0.9",
}

ZM_CRAIOVA = {
    "Craiova", "Filiaşi", "Filiași", "Segarcea",
    "Almăj", "Beharca", "Bogea", "Cotofenii din Față", "Cotofenii din Faţă", "Moşneni", "Moșneni", "Şitoaia", "Șitoaia",
    "Brădeşti", "Brădești", "Brădeştii Bătrâni", "Brădeștii Bătrâni", "Meteu", "Piscani", "Răcarii de Jos", "Tatomireşti", "Tatomirești",
    "Breasta", "Cotu", "Crovna", "Făget", "Obedin", "Roşieni", "Roșieni", "Valea Lungului",
    "Bucovăţ", "Bucovăț", "Cârligei", "Cârligei", "Italieni", "Leamna de Jos", "Leamna de Sus", "Palilula", "Sărbătoarea",
    "Calopăr", "Bâzdâna", "Bâzdâna", "Belcinu", "Panaghia", "Sălcuţa", "Sălcuța",
    "Cârcea", "Cârcea", "Coşoveni", "Coșoveni",
    "Gherceşti", "Ghercești", "Gârleşti", "Gârlești", "Luncşoru", "Luncșoru", "Ungureni", "Ungurenii Mici",
    "Işalniţa", "Ișalnița", "Izvoare",
    "Malu Mare", "Ghindeni", "Preajba",
    "Mischii", "Călineşti", "Călinești", "Gogoşeşti", "Gogoșești", "Mlecăneşti", "Mlecănești", "Motoci", "Urecheşti", "Urechești",
    "Murgaşi", "Murgași", "Gaia", "Picăturile", "Rupturile", "Veleşti", "Velești",
    "Pieleşti", "Pielești", "Câmpeni", "Lânga", "Lânga",
    "Predeşti", "Predești", "Bucicani", "Cârstovani", "Cârstovani", "Frasin", "Milovan", "Pleşoi", "Pleșoi", "Predeştii Mici", "Predeștii Mici",
    "Şimnicu de Sus", "Șimnicu de Sus", "Albeşti", "Albești", "Cornetu", "Deleni", "Dudoviceşti", "Dudovicești",
    "Floreşti", "Florești", "Izvor", "Jieni", "Leşile", "Leșile", "Mileşti", "Milești", "Româneşti", "Românești",
    "Teasc", "Secui",
    "Terpeziţa", "Terpezița", "Căciulatu", "Căruia", "Floran", "Lazu",
    "Ţuglui", "Țuglui", "Jiul", "Unirea",
    "Vârvoru de Jos", "Bujor", "Ciutura", "Criva", "Dobromira", "Drăgoaia", "Gabru", "Vârvor",
    "Vela", "Bucovicior", "Cetăţuia", "Cetățuia", "Desnăţui", "Desnățui", "Gubaucea", "Segleţ", "Segleț", "Suharu", "Ştiubei", "Știubei",
    "Făcăi", "Mofleni", "Popoveni", "Şimnicu de Jos", "Șimnicu de Jos",
    "Almăjel", "Bâlta", "Bâlta", "Branişte", "Braniște", "Fratoştița", "Fratoștiţa", "Fratostița", "Răcarii de Sus", "Uscăci",
}


def get_localities(session):
    """Extrage localitati din <span class='loc-name'>Nume</span> + href slug."""
    resp = session.get(f"{BASE_URL}/judet/dolj", timeout=15)
    resp.raise_for_status()
    html = resp.text

    # Pattern: <a href="/judet/dolj/slug" class="loc" data-name="...">
    #            <span class="loc-name">Nume Localitate</span>
    pattern = r'href="/judet/dolj/([^"]+)"[^>]*>.*?<span class="loc-name">([^<]+)</span>'
    matches = re.findall(pattern, html, re.DOTALL)

    seen = set()
    localities = []
    for slug, name in matches:
        slug = slug.strip('/')
        name = name.strip()
        if slug and slug not in seen:
            seen.add(slug)
            localities.append({
                'name': name,
                'slug': slug,
                'url': f"{BASE_URL}/judet/dolj/{slug}",
            })

    return localities


def scrape_locality(session, loc):
    """Extrage coduri din tabelul HTML al localitatii."""
    try:
        resp = session.get(loc['url'], timeout=30)
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        print(f"  [ERR] {loc['name']}: {e}")
        return []

    results = []

    # Tabel 3 coloane: Strada | Numere | Cod postal
    rows = re.findall(
        r'<tr[^>]*>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*</tr>',
        html, re.DOTALL
    )

    for c1, c2, c3 in rows:
        strada = re.sub(r'<[^>]+>', '', c1).strip()
        numere = re.sub(r'<[^>]+>', '', c2).strip()
        cod = re.sub(r'<[^>]+>', '', c3).strip()

        if cod and cod.isdigit() and len(cod) == 6 and cod.startswith('20'):
            results.append({
                'cod_postal': cod,
                'judet': 'Dolj',
                'localitate': loc['name'],
                'strada': f"{strada} {numere}".strip() if numere else strada,
                'numere': numere,
                'in_zm': loc['name'] in ZM_CRAIOVA,
            })

    # Fallback: cauta cod postal pe pagina (sate mici fara tabel)
    if not results:
        codes = set(re.findall(r'\b(20[0-7]\d{3})\b', html))
        for cod in codes:
            results.append({
                'cod_postal': cod, 'judet': 'Dolj', 'localitate': loc['name'],
                'strada': '', 'numere': '', 'in_zm': loc['name'] in ZM_CRAIOVA,
            })

    return results


def export_excel(all_data, zm_data, path):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    wb = Workbook()
    hf = Font(name='Arial', bold=True, size=11, color='FFFFFF')
    hfill = PatternFill('solid', fgColor='2F5496')
    ha = Alignment(horizontal='center', vertical='center', wrap_text=True)
    tb = Border(left=Side(style='thin'), right=Side(style='thin'),
                top=Side(style='thin'), bottom=Side(style='thin'))
    zm_fill = PatternFill('solid', fgColor='E2EFDA')
    hdrs = ['Nr.', 'Cod Poștal', 'Județ',
            'Localitate', 'Strada', 'Numere/Blocuri']

    def fill_sheet(ws, title, data):
        ws.merge_cells('A1:F1')
        ws['A1'] = title
        ws['A1'].font = Font(name='Arial', bold=True, size=14, color='2F5496')
        ws['A1'].alignment = Alignment(horizontal='center')
        ws.merge_cells('A2:F2')
        ws['A2'] = f'Sursa: codul-postal.ro | {datetime.now().strftime("%d.%m.%Y %H:%M")}'
        ws['A2'].font = Font(name='Arial', size=10,
                             italic=True, color='666666')
        ws['A2'].alignment = Alignment(horizontal='center')
        for col, h in enumerate(hdrs, 1):
            c = ws.cell(row=4, column=col, value=h)
            c.font, c.fill, c.alignment, c.border = hf, hfill, ha, tb
        data.sort(key=lambda x: (x['localitate'],
                  x['strada'], x['cod_postal']))
        for i, rd in enumerate(data):
            row = i + 5
            for col, val in enumerate([i+1, rd['cod_postal'], rd['judet'], rd['localitate'], rd['strada'], rd.get('numere', '')], 1):
                c = ws.cell(row=row, column=col, value=val)
                c.font = Font(name='Arial', size=10, bold=(col == 2))
                c.alignment = Alignment(horizontal='center') if col in (
                    1, 2) else Alignment()
                c.border = tb
                if rd.get('in_zm'):
                    c.fill = zm_fill
        for col, w in {'A': 7, 'B': 12, 'C': 10, 'D': 22, 'E': 45, 'F': 35}.items():
            ws.column_dimensions[col].width = w
        ws.freeze_panes = 'A5'
        ws.auto_filter.ref = f'A4:F{4+len(data)}'

    ws1 = wb.active
    ws1.title = "ZM Craiova"
    fill_sheet(ws1, 'CODURI POȘTALE — ZONA METROPOLITANĂ CRAIOVA 2026', zm_data)
    ws2 = wb.create_sheet("Tot Dolj")
    fill_sheet(ws2, 'CODURI POȘTALE — JUDEȚUL DOLJ COMPLET 2026', all_data)

    # Sumar
    ws3 = wb.create_sheet("Sumar")
    ws3['A1'] = 'SUMAR'
    ws3['A1'].font = Font(name='Arial', bold=True, size=14, color='2F5496')
    for col, h in enumerate(['Localitate', 'Intrări', 'Coduri unice', 'ZM'], 1):
        c = ws3.cell(row=3, column=col, value=h)
        c.font, c.fill, c.border = hf, hfill, tb
    from collections import Counter
    lc = Counter(r['localitate'] for r in all_data)
    lu = {}
    for r in all_data:
        lu.setdefault(r['localitate'], set()).add(r['cod_postal'])
    for i, (loc, cnt) in enumerate(sorted(lc.items()), 4):
        ws3.cell(row=i, column=1, value=loc).border = tb
        ws3.cell(row=i, column=2, value=cnt).border = tb
        ws3.cell(row=i, column=3, value=len(lu.get(loc, set()))).border = tb
        is_zm = 'DA' if loc in ZM_CRAIOVA else ''
        ws3.cell(row=i, column=4, value=is_zm).border = tb
        if is_zm:
            for c in range(1, 5):
                ws3.cell(row=i, column=c).fill = zm_fill
    for col, w in {'A': 25, 'B': 10, 'C': 12, 'D': 8}.items():
        ws3.column_dimensions[col].width = w

    wb.save(path)


def main():
    sd = os.path.dirname(os.path.abspath(__file__))

    print("=" * 60)
    print("  CODURI POSTALE DOLJ — codul-postal.ro  v3")
    print(f"  {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print("=" * 60)

    s = requests.Session()
    s.headers.update(HEADERS)

    print("\n[1] Localitati Dolj...")
    locs = get_localities(s)
    print(f"    {len(locs)} localitati")
    if not locs:
        print("    ❌ Eroare")
        return

    # Show first 5 to verify names
    print(f"    Primele 5: {[l['name'] for l in locs[:5]]}")
    zm_count = sum(1 for l in locs if l['name'] in ZM_CRAIOVA)
    print(f"    Din ZM Craiova: {zm_count}")

    print(f"\n[2] Extragere coduri...\n")
    all_data = []

    for i, loc in enumerate(locs):
        r = scrape_locality(s, loc)
        all_data.extend(r)
        zm = " [ZM]" if loc['name'] in ZM_CRAIOVA else ""
        if r:
            print(f"  [{i+1}/{len(locs)}] {loc['name']}{zm}: {len(r)}")
        time.sleep(DELAY)

    # Dedup
    u = {}
    for r in all_data:
        u[f"{r['cod_postal']}|{r['localitate']}|{r['strada']}"] = r
    all_data = list(u.values())
    zm_data = [r for r in all_data if r.get('in_zm')]

    ct = len(set(r['cod_postal'] for r in all_data))
    cz = len(set(r['cod_postal'] for r in zm_data))
    lt = len(set(r['localitate'] for r in all_data))
    lz = len(set(r['localitate'] for r in zm_data))

    print(f"\n{'='*60}")
    print(
        f"  Tot Dolj:   {len(all_data)} intrari | {ct} coduri | {lt} localitati")
    print(
        f"  ZM Craiova: {len(zm_data)} intrari | {cz} coduri | {lz} localitati")
    print(f"{'='*60}")

    xlsx = os.path.join(sd, "coduri_postale_dolj_COMPLET_2026.xlsx")
    export_excel(all_data, zm_data, xlsx)
    print(f"\n✅ Excel: {xlsx}")

    with open(os.path.join(sd, "coduri_postale_dolj_2026.csv"), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=[
                           'cod_postal', 'judet', 'localitate', 'strada', 'numere', 'in_zm'])
        w.writeheader()
        w.writerows(sorted(all_data, key=lambda x: (
            x['localitate'], x['cod_postal'])))
    print("✅ CSV salvat")

    with open(os.path.join(sd, "coduri_postale_dolj_2026.json"), 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    print("✅ JSON salvat")
    print(f"\n🎉 GATA!")


if __name__ == "__main__":
    main()
