#!/usr/bin/env python3
"""
Script: scrape_coduri_postale_zm_craiova.py
Descriere: Extrage codurile postale pe strazi de pe site-ul Postei Romane
           pentru toate localitatile din Zona Metropolitana Craiova.
           
Sursa: https://www.posta-romana.ro/ccp.html
Endpoint-uri API descoperite:
  - POST /cnpr-app/modules/cauta-cod-postal/ajax/cauta_orase.php?q=
    Body: judet=Dolj  →  returneaza lista localitati (HTML select options)
  - POST /cnpr-app/modules/cauta-cod-postal/ajax/cautare_pentru_cod.php?q=
    Body: judet=Dolj&localitate=Craiova&adresa=Calea Bucuresti
    →  returneaza JSON cu {formular: "HTML cu rezultate", found: N}

Strategie: Pentru fiecare localitate, cautam cu fiecare litera a-z
           pentru a acoperi toate strazile posibile.
           
Autor: Alex Tudor (generat cu Claude)
Data: Martie 2026
Rulare: python3 scrape_coduri_postale_zm_craiova.py
Output: coduri_postale_zm_craiova_complet.xlsx
"""

import requests
import json
import time
import re
import os
from datetime import datetime

# ============================================================
# CONFIGURARE
# ============================================================

# URL-uri API Posta Romana
BASE_URL = "https://www.posta-romana.ro"
URL_LOCALITATI = f"{BASE_URL}/cnpr-app/modules/cauta-cod-postal/ajax/cauta_orase.php?q="
URL_CAUTARE = f"{BASE_URL}/cnpr-app/modules/cauta-cod-postal/ajax/cautare_pentru_cod.php?q="

# Judet
JUDET = "Dolj"

# Localitati din Zona Metropolitana Craiova (cele care au coduri pe strazi = orase)
# Comunele/satele au de obicei 1 singur cod postal
LOCALITATI_CU_STRAZI = [
    "Craiova",
    "Filiași",     # oras
    "Segarcea",    # oras
    "Băilești",    # oras mare din Dolj, optional
]

# Toate localitatile din ZM Craiova (inclusiv sate - au cod unic)
LOCALITATI_ZM = [
    "Craiova", "Filiași", "Segarcea",
    # Comune
    "Almăj", "Beharca", "Bogea", "Cotofenii din Față", "Moșneni", "Șitoaia",
    "Brădești", "Brădeștii Bătrâni", "Meteu", "Piscani", "Răcarii de Jos", "Tatomirești",
    "Breasta", "Cotu", "Crovna", "Făget", "Obedin", "Roșieni", "Valea Lungului",
    "Bucovăț", "Cârligei", "Italieni", "Leamna de Jos", "Leamna de Sus", "Palilula", "Sărbătoarea",
    "Calopăr", "Bâzdâna", "Belcinu", "Panaghia", "Sălcuța",
    "Cârcea", "Coșoveni",
    "Ghercești", "Gârlești", "Luncșoru", "Ungureni", "Ungurenii Mici",
    "Işalnița", "Izvoare",
    "Malu Mare", "Ghindeni", "Preajba",
    "Mischii", "Călinești", "Gogoșești", "Mlecănești", "Motoci", "Urechești",
    "Murgași", "Gaia", "Picăturile", "Rupturile", "Velești",
    "Pielești", "Câmpeni", "Lânga",
    "Predești", "Bucicani", "Cârstovani", "Frasin", "Milovan", "Pleșoi", "Predeștii Mici",
    "Șimnicu de Sus", "Albești", "Cornetu", "Deleni", "Dudovicești", "Florești",
    "Izvor", "Jieni", "Leșile", "Milești", "Românești",
    "Teasc", "Secui",
    "Terpezița", "Căciulatu", "Căruia", "Floran", "Lazu",
    "Țuglui", "Jiul", "Unirea",
    "Vârvoru de Jos", "Bujor", "Ciutura", "Criva", "Dobromira", "Drăgoaia", "Gabru", "Vârvor",
    "Vela", "Bucovicior", "Cetățuia", "Desnățui", "Gubaucea", "Segleț", "Suharu", "Știubei",
]

# Litere pentru cautare (acoperim tot alfabetul)
LITERE_CAUTARE = list("abcdefghijklmnoprstuvzăâîșț")

# Delay intre requesturi (secunde) - respectam serverul
DELAY = 0.5

# Headers
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/javascript, */*",
    "Accept-Language": "ro-RO,ro;q=0.9,en;q=0.8",
    "Referer": "https://www.posta-romana.ro/ccp.html",
    "X-Requested-With": "XMLHttpRequest",
}

# ============================================================
# FUNCTII
# ============================================================


def parse_results_html(html_str):
    """
    Parseaza HTML-ul din raspunsul API si extrage datele.
    Formatul e: div-uri cu p-uri care contin cod postal, judet, localitate, strada, subunitate.
    """
    results = []
    # Pattern: fiecare rand e un div.cod-postal-line cu mai multe div-uri copii
    # Extragem textul din tagurile <p>
    lines = re.findall(
        r'<div class="col-md-12 cod-postal-line">(.*?)</div>\s*</div>\s*</div>\s*</div>\s*</div>', html_str, re.DOTALL)

    if not lines:
        # Incercam alt pattern
        lines = html_str.split('cod-postal-line')

    # Pattern mai simplu - extragem toate <p>...</p> din fiecare linie
    # Fiecare "linie" din rezultat are 5 valori: cod, judet, localitate, strada, subunitate
    p_tags = re.findall(r'<p[^>]*>(.*?)</p>', html_str)

    # Grupam cate 5 (sau 6 daca include si unitati postale)
    # Din observatii: sunt 5 coloane per rand
    chunk_size = 5
    for i in range(0, len(p_tags), chunk_size):
        chunk = p_tags[i:i+chunk_size]
        if len(chunk) >= 4:
            cod = chunk[0].strip()
            judet = chunk[1].strip() if len(chunk) > 1 else ""
            localitate = chunk[2].strip() if len(chunk) > 2 else ""
            strada = chunk[3].strip() if len(chunk) > 3 else ""
            subunitate = chunk[4].strip() if len(chunk) > 4 else ""

            # Skip header rows sau mesaje de eroare
            if cod and cod[0].isdigit() and len(cod) == 6:
                results.append({
                    "cod_postal": cod,
                    "judet": judet,
                    "localitate": localitate,
                    "strada": strada,
                    "subunitate_postala": subunitate,
                })

    return results


def cauta_coduri(judet, localitate, adresa="", session=None):
    """
    Cauta coduri postale pe Posta Romana.
    Returneaza lista de dict-uri cu rezultatele.
    """
    if session is None:
        session = requests.Session()
        session.headers.update(HEADERS)

    data = {
        "judet": judet,
        "localitate": localitate,
        "adresa": adresa,
    }

    try:
        resp = session.post(URL_CAUTARE, data=data, timeout=30)
        resp.raise_for_status()

        result = resp.json()
        found = result.get("found", 0)
        html = result.get("formular", "")

        if found > 0:
            return parse_results_html(html)
        else:
            return []

    except Exception as e:
        print(f"  [EROARE] {judet}/{localitate}/{adresa}: {e}")
        return []


def scrape_localitate_completa(judet, localitate, session):
    """
    Extrage TOATE codurile postale pentru o localitate.
    Strategie: cautam cu fiecare litera + cautare goala (pt localitati mici).
    """
    all_results = {}  # key = cod_postal+strada pentru deduplicare

    # 1. Cautare fara adresa (pt localitati mici cu cod unic)
    print(f"  Cautare generala...")
    results = cauta_coduri(judet, localitate, "", session)
    for r in results:
        key = f"{r['cod_postal']}|{r['strada']}"
        all_results[key] = r
    time.sleep(DELAY)

    # 2. Cautare cu fiecare litera (pt orase cu multe strazi)
    if localitate in LOCALITATI_CU_STRAZI:
        for litera in LITERE_CAUTARE:
            print(f"  Cautare '{litera}'...", end=" ")
            results = cauta_coduri(judet, localitate, litera, session)
            new_count = 0
            for r in results:
                key = f"{r['cod_postal']}|{r['strada']}"
                if key not in all_results:
                    all_results[key] = r
                    new_count += 1
            print(f"{len(results)} gasite, {new_count} noi")
            time.sleep(DELAY)

    return list(all_results.values())


def export_to_excel(all_data, filename):
    """
    Exporta datele in format Excel cu formatare profesionala.
    """
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    except ImportError:
        print("Instalare openpyxl...")
        os.system("pip3 install openpyxl --break-system-packages -q")
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    wb = Workbook()
    ws = wb.active
    ws.title = "Coduri Postale ZM Craiova"

    # Stiluri
    header_font = Font(name='Arial', bold=True, size=11, color='FFFFFF')
    header_fill = PatternFill('solid', fgColor='2F5496')
    header_align = Alignment(
        horizontal='center', vertical='center', wrap_text=True)
    data_font = Font(name='Arial', size=10)
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )

    # Titlu
    ws.merge_cells('A1:F1')
    ws['A1'] = f'CODURI POȘTALE PE STRĂZI - ZONA METROPOLITANĂ CRAIOVA'
    ws['A1'].font = Font(name='Arial', bold=True, size=14, color='2F5496')
    ws['A1'].alignment = Alignment(horizontal='center')

    ws.merge_cells('A2:F2')
    ws['A2'] = f'Sursa: Poșta Română (posta-romana.ro) | Generat: {datetime.now().strftime("%d.%m.%Y %H:%M")}'
    ws['A2'].font = Font(name='Arial', size=10, italic=True, color='666666')
    ws['A2'].alignment = Alignment(horizontal='center')

    # Headers
    headers = ['Nr.', 'Cod Poștal', 'Județ', 'Localitate',
               'Strada / Adresa', 'Subunitate Poștală']
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=4, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = thin_border

    # Date
    # Sortam dupa localitate, apoi dupa strada
    all_data.sort(key=lambda x: (x['localitate'], x['strada']))

    for i, row_data in enumerate(all_data):
        row = i + 5
        ws.cell(row=row, column=1, value=i+1).font = data_font
        ws.cell(row=row, column=1).alignment = Alignment(horizontal='center')
        ws.cell(row=row, column=1).border = thin_border

        ws.cell(row=row, column=2, value=row_data['cod_postal']).font = Font(
            name='Arial', size=10, bold=True)
        ws.cell(row=row, column=2).alignment = Alignment(horizontal='center')
        ws.cell(row=row, column=2).border = thin_border

        ws.cell(row=row, column=3, value=row_data['judet']).font = data_font
        ws.cell(row=row, column=3).border = thin_border

        ws.cell(row=row, column=4,
                value=row_data['localitate']).font = data_font
        ws.cell(row=row, column=4).border = thin_border

        ws.cell(row=row, column=5, value=row_data['strada']).font = data_font
        ws.cell(row=row, column=5).border = thin_border

        ws.cell(row=row, column=6,
                value=row_data['subunitate_postala']).font = data_font
        ws.cell(row=row, column=6).border = thin_border

    # Latimi coloane
    ws.column_dimensions['A'].width = 7
    ws.column_dimensions['B'].width = 12
    ws.column_dimensions['C'].width = 10
    ws.column_dimensions['D'].width = 20
    ws.column_dimensions['E'].width = 50
    ws.column_dimensions['F'].width = 30

    # Freeze panes
    ws.freeze_panes = 'A5'
    ws.auto_filter.ref = f'A4:F{4 + len(all_data)}'

    wb.save(filename)
    print(f"\n✅ Excel salvat: {filename}")
    print(f"   Total randuri: {len(all_data)}")


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 60)
    print("SCRAPER CODURI POSTALE - ZONA METROPOLITANA CRAIOVA")
    print(
        f"Sursa: Posta Romana | Data: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print("=" * 60)

    session = requests.Session()
    session.headers.update(HEADERS)

    # Pas 1: Verificam conexiunea
    print("\n[1] Verificare conexiune Posta Romana...")
    try:
        resp = session.get(f"{BASE_URL}/ccp.html", timeout=10)
        print(f"    Status: {resp.status_code} OK")
    except Exception as e:
        print(f"    EROARE: {e}")
        print("    Verificati conexiunea la internet!")
        return

    # Pas 2: Extragem coduri pentru fiecare localitate
    all_data = []

    for localitate in LOCALITATI_ZM:
        print(f"\n[*] {localitate}...")
        results = scrape_localitate_completa(JUDET, localitate, session)
        all_data.extend(results)
        print(f"    → {len(results)} coduri gasite")

    # Pas 3: Deduplicare finala
    unique = {}
    for r in all_data:
        key = f"{r['cod_postal']}|{r['strada']}"
        unique[key] = r
    all_data = list(unique.values())

    print(f"\n{'=' * 60}")
    print(f"TOTAL: {len(all_data)} coduri postale unice")
    print(f"{'=' * 60}")

    # Pas 4: Export Excel - salvam in acelasi folder cu scriptul
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_file = os.path.join(
        script_dir, "coduri_postale_zm_craiova_complet.xlsx")
    export_to_excel(all_data, output_file)

    # Pas 5: Export si CSV (backup)
    csv_file = os.path.join(
        script_dir, "coduri_postale_zm_craiova_complet.csv")
    try:
        import csv
        with open(csv_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=[
                                    'cod_postal', 'judet', 'localitate', 'strada', 'subunitate_postala'])
            writer.writeheader()
            writer.writerows(all_data)
        print(f"✅ CSV salvat: {csv_file}")
    except Exception as e:
        print(f"⚠️  Eroare CSV: {e}")

    print(f"\n🎉 Gata! Fisierele sunt in: {os.getcwd()}")


if __name__ == "__main__":
    main()
