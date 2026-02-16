#!/usr/bin/env python3
"""
EJOLIE.RO - Audit & Auto-Fill Product Specifications
=====================================================
Script care:
1. Exporta produsele din Extended API
2. Identifica produsele fara specificatii completate
3. Foloseste GPT pentru a genera specificatii lipsa
4. Genereaza fisier Excel pentru import in Extended

Specificatii tracked: Culoare, Material, Lungime, Croi, Stil, Model

Utilizare:
  python3 specs_audit_and_fill.py --audit          # Doar audit - vezi ce lipseste
  python3 specs_audit_and_fill.py --fill --limit 5  # Completeaza cu GPT (test 5 produse)
  python3 specs_audit_and_fill.py --fill             # Completeaza toate
  
Autor: Claude AI pentru Alex Tudor
Data: 16 Februarie 2026
"""

import os
import sys
import json
import time
import argparse
import requests
from pathlib import Path

# ============================================================
# CONFIGURARE
# ============================================================

# Calea catre .env (pe EC2: ~/ejolie-openclaw-agent/ejolie-sales/.env)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(SCRIPT_DIR, '..', '.env')

# Alternativa: cauta .env in mai multe locuri
ENV_PATHS = [
    ENV_PATH,
    os.path.join(SCRIPT_DIR, '.env'),
    os.path.expanduser('~/ejolie-openclaw-agent/ejolie-sales/.env'),
]

# Extended API
EXTENDED_API_URL = "https://www.ejolie.ro/api/"
EXTENDED_API_KEY = None  # Se incarca din .env

# OpenAI
OPENAI_API_KEY = None  # Se incarca din .env
GPT_MODEL = "gpt-4o-mini"  # Ieftin si rapid

# Specificatiile pe care le tracked
SPEC_NAMES = ["Culoare", "Material", "Lungime", "Croi", "Stil", "Model"]

# Valorile VALIDE pentru fiecare specificatie (exact cum sunt in Extended)
VALID_VALUES = {
    "Culoare": [
        "Alb", "Albastru", "Albastru deschis", "Albastru inchis", "Albastru petrol",
        "Animal print", "Aramiu", "Argintiu", "Auriu", "Bej", "Bleumarin",
        "Bordo", "Caramel", "Ciocolatiu", "Corai", "Crem", "Galben", "Gri",
        "Kaki", "Lavanda", "Lila", "Maro", "Mov", "Multicolor", "Negru",
        "Nude", "Olive", "Piersica", "Portocaliu", "Pudra", "Rosu", "Roz",
        "Somon", "Turcoaz", "Verde", "Verde inchis", "Verde lime", "Verde mint",
        "Vernil", "Visiniu", "floral"
    ],
    "Material": [
        "Acryl", "Barbie", "Brocart", "Bumbac", "Catifea", "Casmir", "Crep",
        "Dantela", "Jerseu", "Lana", "Lycra", "Matase", "Neopren", "Organza",
        "Paiete", "Piele ecologica", "Poliester", "Satin", "Sifon", "Stofa",
        "Tafta", "Tricot", "Tul", "Tweed", "Velur", "Voal"
    ],
    "Lungime": ["Lungi", "Medii", "Scurte"],
    "Croi": [
        "In clini", "Lejer", "Mulat", "Peplum", "Petrecuta",
        "Plisat", "Pliuri", "Volane", "in A"
    ],
    "Stil": [
        "Asimetrica", "Birou", "Casual", "Casual-Elegant", "Casual-Office",
        "Cu crapatura", "De ocazie", "De seara", "Eleganta", "Sport"
    ],
    "Model": [
        "Accesorizata la baza gatului", "Aplicatii 3D", "Bretele reglabile",
        "Broderie", "Brosa", "Buzunare", "Cambrat", "Captuseala",
        "Centura inclusa", "Cordon", "Cu buzunare", "Cu captuseala",
        "Cu cordon", "Cu fermoar", "Cu funda", "Cu gluga", "Cu nasturi",
        "Decolteu in V", "Fara maneci", "Maneci lungi", "Maneci scurte",
        "Rochie camasa", "Umeri goi", "Un umar gol"
    ]
}

# ============================================================
# FUNCTII HELPER
# ============================================================


def load_env():
    """Incarca variabilele din .env"""
    global EXTENDED_API_KEY, OPENAI_API_KEY

    env_file = None
    for path in ENV_PATHS:
        if os.path.exists(path):
            env_file = path
            break

    if not env_file:
        print("❌ Nu am gasit fisierul .env!")
        print(f"   Am cautat in: {ENV_PATHS}")
        print("   Creaza un fisier .env cu:")
        print("   EXTENDED_API_KEY=cheia_ta")
        print("   OPENAI_API_KEY=cheia_ta")
        sys.exit(1)

    print(f"📁 Incarc .env din: {env_file}")
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key == 'EXTENDED_API_KEY':
                    EXTENDED_API_KEY = value
                elif key == 'OPENAI_API_KEY':
                    OPENAI_API_KEY = value

    if not EXTENDED_API_KEY:
        print("❌ EXTENDED_API_KEY nu e setat in .env!")
        sys.exit(1)

    print(f"✅ Extended API Key: ...{EXTENDED_API_KEY[-6:]}")
    if OPENAI_API_KEY:
        print(f"✅ OpenAI API Key: ...{OPENAI_API_KEY[-6:]}")


def fetch_all_products():
    """Preia TOATE produsele din Extended API"""
    print("\n📦 Preiau lista de produse din Extended API...")

    all_products = []
    page = 1

    while True:
        params = {
            'produse': '',
            'apikey': EXTENDED_API_KEY,
            'pagina': page,
            'per_pagina': 20  # Extended default
        }

        try:
            resp = requests.get(EXTENDED_API_URL, params=params, timeout=30)
            data = resp.json()
        except Exception as e:
            print(f"❌ Eroare la pagina {page}: {e}")
            break

        if not data or (isinstance(data, dict) and 'error' in data):
            break

        # Extended API returneaza lista de produse sau dict cu produse
        products = data if isinstance(data, list) else data.get('produse', [])

        if not products:
            break

        all_products.extend(products)
        print(
            f"   Pagina {page}: {len(products)} produse (total: {len(all_products)})")

        if len(products) < 20:
            break

        page += 1
        time.sleep(0.3)  # Rate limiting

    print(f"\n✅ Total produse gasite: {len(all_products)}")
    return all_products


def fetch_product_details(product_id):
    """Preia detalii complete pentru un produs (inclusiv specificatii)"""
    params = {
        'id_produs': product_id,
        'apikey': EXTENDED_API_KEY
    }

    try:
        resp = requests.get(EXTENDED_API_URL, params=params, timeout=15)
        return resp.json()
    except Exception as e:
        print(f"   ❌ Eroare la produsul {product_id}: {e}")
        return None


def analyze_specs(product_detail):
    """Analizeaza ce specificatii are/nu are un produs"""
    specs = product_detail.get('specificatii', [])

    # Construieste un dict cu specificatiile existente
    existing = {}
    if specs:
        for spec in specs:
            name = spec.get('nume', '')
            values = spec.get('valoare', [])
            if values and values[0]:  # Nu e gol
                existing[name] = values

    # Verifica ce lipseste
    missing = []
    for spec_name in SPEC_NAMES:
        if spec_name not in existing:
            missing.append(spec_name)

    return existing, missing


def gpt_generate_specs(product_name, product_description, missing_specs):
    """Foloseste GPT pentru a genera specificatiile lipsa"""
    if not OPENAI_API_KEY:
        print("❌ OPENAI_API_KEY nu e setat! Nu pot folosi GPT.")
        return {}

    # Construieste prompt-ul cu valorile valide
    valid_options = ""
    for spec in missing_specs:
        if spec in VALID_VALUES:
            valid_options += f"\n{spec} - alege DOAR din: {', '.join(VALID_VALUES[spec])}"

    prompt = f"""Esti un expert in fashion e-commerce. Analizeaza acest produs si completeaza specificatiile lipsa.

PRODUS: {product_name}
DESCRIERE: {product_description[:500] if product_description else 'Fara descriere'}

SPECIFICATII DE COMPLETAT (alege EXACT din valorile date):
{valid_options}

REGULI IMPORTANTE:
- Alege DOAR valori din listele de mai sus, nu inventa altele
- Pentru Culoare: extrage din numele produsului daca e posibil
- Pentru Material: analizeaza descrierea
- Pentru Lungime: Lungi = rochii lungi/maxi, Medii = midi/pana la genunchi, Scurte = mini
- Pentru Croi: analizeaza silueta din descriere
- Pentru Stil: analizeaza contextul (seara, casual, office etc.)
- Pentru Model: analizeaza detaliile (maneci, decolteu, accesorii)
- Daca nu esti sigur, pune cea mai probabila valoare

Raspunde DOAR in format JSON, fara alte explicatii:
{{"Culoare": "valoare", "Material": "valoare", "Lungime": "valoare", "Croi": "valoare", "Stil": "valoare", "Model": "valoare"}}

Include DOAR specificatiile cerute: {', '.join(missing_specs)}"""

    try:
        import openai
        client = openai.OpenAI(api_key=OPENAI_API_KEY)

        response = client.chat.completions.create(
            model=GPT_MODEL,
            messages=[
                {"role": "system", "content": "Esti un expert in fashion care completeaza specificatii de produs. Raspunzi DOAR in JSON valid."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=200
        )

        result_text = response.choices[0].message.content.strip()
        # Curata JSON-ul
        result_text = result_text.replace(
            '```json', '').replace('```', '').strip()

        result = json.loads(result_text)

        # Valideaza ca valorile sunt din lista permisa
        validated = {}
        for spec_name, value in result.items():
            if spec_name in VALID_VALUES:
                if value in VALID_VALUES[spec_name]:
                    validated[spec_name] = value
                else:
                    # Cauta cea mai apropiata valoare
                    closest = find_closest_value(
                        value, VALID_VALUES[spec_name])
                    if closest:
                        validated[spec_name] = closest
                        print(
                            f"      ⚠️ {spec_name}: '{value}' → '{closest}' (corectat)")
                    else:
                        print(
                            f"      ❌ {spec_name}: '{value}' nu e valid, skip")

        return validated

    except json.JSONDecodeError as e:
        print(f"      ❌ GPT a returnat JSON invalid: {e}")
        return {}
    except Exception as e:
        print(f"      ❌ Eroare GPT: {e}")
        return {}


def find_closest_value(value, valid_list):
    """Gaseste cea mai apropiata valoare din lista valida"""
    value_lower = value.lower().strip()
    for valid in valid_list:
        if valid.lower() == value_lower:
            return valid
    # Cautare partiala
    for valid in valid_list:
        if value_lower in valid.lower() or valid.lower() in value_lower:
            return valid
    return None


def generate_excel(products_with_specs, output_path):
    """Genereaza fisierul Excel pentru import in Extended"""
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment

    wb = openpyxl.Workbook()

    # === Sheet 1: Fisier pentru Import Extended ===
    ws_import = wb.active
    ws_import.title = "Import Specificatii"

    # Headers conform template-ului Extended
    # Coloanele A-AH sunt obligatorii (chiar daca goale), apoi specificatiile
    headers = [
        "Nume produs",      # A
        "Descriere",         # B
        "Categorie",         # C
        "Brand",             # D
        "Optiune 1",         # E
        "Optiune 2",         # F
        "Optiune 3",         # G
        "Optiune 4",         # H
        "Optiune 5",         # I
        "Furnizor",          # J
        "Pret vanzare",      # K
        "Pret intrare",      # L
        "Adaos %",           # M
        "Discount %",        # N
        "Moneda",            # O
        "Cod produs",        # P
        "Stoc",              # Q
        "Stoc fizic",        # R
        "Greutate (KG)",     # S
    ]
    # Imagini T-AH (15 coloane)
    for i in range(1, 16):
        headers.append(f"Imagine {i}")

    # Specificatii
    for spec_name in SPEC_NAMES:
        headers.append(spec_name)

    # Scrie headers
    header_fill = PatternFill(start_color="4472C4",
                              end_color="4472C4", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)

    for col, header in enumerate(headers, 1):
        cell = ws_import.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    # Scrie datele
    row = 2
    for prod in products_with_specs:
        ws_import.cell(row=row, column=1, value=prod.get('nume', ''))
        ws_import.cell(row=row, column=4, value=prod.get('brand', ''))
        ws_import.cell(row=row, column=16, value=prod.get('cod_produs', ''))

        # Specificatii (incep de la coloana 35 = AI dupa 15 imagini)
        spec_start_col = 20 + 15  # Dupa S + 15 imagini = coloana 35
        for i, spec_name in enumerate(SPEC_NAMES):
            value = prod.get('specs_new', {}).get(spec_name, '')
            ws_import.cell(row=row, column=spec_start_col + i, value=value)

        row += 1

    # Auto-width
    for col in ws_import.columns:
        max_length = 0
        for cell in col:
            if cell.value:
                max_length = max(max_length, len(str(cell.value)))
        ws_import.column_dimensions[col[0].column_letter].width = min(
            max_length + 2, 40)

    # === Sheet 2: Raport Audit ===
    ws_audit = wb.create_sheet("Raport Audit")
    audit_headers = ["Cod Produs", "Nume Produs", "Culoare", "Material", "Lungime",
                     "Croi", "Stil", "Model", "Specs Lipsa", "Status"]

    for col, header in enumerate(audit_headers, 1):
        cell = ws_audit.cell(row=1, column=col, value=header)
        cell.fill = PatternFill(start_color="70AD47",
                                end_color="70AD47", fill_type="solid")
        cell.font = Font(color="FFFFFF", bold=True)

    row = 2
    for prod in products_with_specs:
        ws_audit.cell(row=row, column=1, value=prod.get('cod_produs', ''))
        ws_audit.cell(row=row, column=2, value=prod.get('nume', ''))

        existing = prod.get('specs_existing', {})
        new_specs = prod.get('specs_new', {})
        missing = prod.get('specs_missing', [])

        for i, spec_name in enumerate(SPEC_NAMES):
            val = existing.get(spec_name, new_specs.get(spec_name, ''))
            if isinstance(val, list):
                val = ', '.join(val)
            cell = ws_audit.cell(row=row, column=3 + i, value=val or '-')

            # Coloreaza: verde = existent, galben = completat de GPT, rosu = lipsa
            if spec_name in existing:
                cell.fill = PatternFill(
                    start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
            elif spec_name in new_specs:
                cell.fill = PatternFill(
                    start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
            else:
                cell.fill = PatternFill(
                    start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")

        ws_audit.cell(row=row, column=9, value=len(missing))
        status = "✅ Complet" if not missing else f"⚠️ Lipsesc {len(missing)}"
        ws_audit.cell(row=row, column=10, value=status)

        row += 1

    # Auto-width sheet 2
    for col in ws_audit.columns:
        max_length = 0
        for cell in col:
            if cell.value:
                max_length = max(max_length, len(str(cell.value)))
        ws_audit.column_dimensions[col[0].column_letter].width = min(
            max_length + 2, 40)

    wb.save(output_path)
    print(f"\n📊 Excel salvat: {output_path}")


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description='Ejolie.ro - Audit & Fill Product Specifications')
    parser.add_argument('--audit', action='store_true',
                        help='Doar audit - vezi ce specificatii lipsesc')
    parser.add_argument('--fill', action='store_true',
                        help='Completeaza specificatiile lipsa cu GPT')
    parser.add_argument('--limit', type=int, default=0,
                        help='Limiteaza numarul de produse (0 = toate)')
    parser.add_argument('--brand', type=str, default='ejolie',
                        help='Brand de filtrat (default: ejolie)')
    parser.add_argument('--output', type=str, default='',
                        help='Calea fisierului Excel output')
    args = parser.parse_args()

    if not args.audit and not args.fill:
        args.audit = True  # Default: audit

    print("=" * 60)
    print("🔍 EJOLIE.RO - Audit & Fill Product Specifications")
    print("=" * 60)

    # 1. Incarca .env
    load_env()

    # 2. Preia lista de produse
    products = fetch_all_products()

    if not products:
        print("❌ Nu am gasit produse!")
        sys.exit(1)

    # 3. Preia detalii + specificatii pentru fiecare produs
    print(f"\n🔎 Verific specificatiile pentru fiecare produs...")

    results = []
    total = len(products)
    if args.limit > 0:
        total = min(total, args.limit)

    products_missing = 0
    products_complete = 0

    for i, prod in enumerate(products[:total]):
        product_id = prod.get('id', prod.get('id_produs', ''))
        product_name = prod.get('nume', prod.get('nume_scurt', ''))
        product_code = prod.get('cod_produs', '')
        product_brand = prod.get('brand', '')

        if isinstance(product_brand, dict):
            product_brand = product_brand.get('nume', '')

        print(
            f"\n   [{i+1}/{total}] {product_name[:50]}... (cod: {product_code})")

        # Preia detalii complete
        details = fetch_product_details(product_id)
        if not details:
            continue

        # Analizeaza specificatii
        existing_specs, missing_specs = analyze_specs(details)

        result = {
            'id': product_id,
            'nume': product_name,
            'cod_produs': product_code,
            'brand': product_brand,
            'descriere': details.get('descriere', ''),
            'specs_existing': existing_specs,
            'specs_missing': missing_specs,
            'specs_new': {}
        }

        if missing_specs:
            products_missing += 1
            print(f"      ⚠️ Lipsesc: {', '.join(missing_specs)}")

            # Daca fill mode, completeaza cu GPT
            if args.fill:
                print(f"      🤖 Generez cu GPT...")
                new_specs = gpt_generate_specs(
                    product_name,
                    details.get('continut', details.get('descriere', '')),
                    missing_specs
                )
                result['specs_new'] = new_specs
                if new_specs:
                    print(f"      ✅ Generat: {new_specs}")
                time.sleep(0.5)  # Rate limiting OpenAI
        else:
            products_complete += 1
            print(f"      ✅ Toate specificatiile complete!")

        results.append(result)
        time.sleep(0.3)  # Rate limiting Extended API

    # 4. Raport
    print("\n" + "=" * 60)
    print("📊 RAPORT FINAL")
    print("=" * 60)
    print(f"   Total produse verificate: {len(results)}")
    print(f"   ✅ Complete (toate specs): {products_complete}")
    print(f"   ⚠️ Cu specificatii lipsa: {products_missing}")

    if products_missing > 0:
        # Statistici per specificatie
        print(f"\n   Detalii per specificatie:")
        for spec_name in SPEC_NAMES:
            missing_count = sum(
                1 for r in results if spec_name in r['specs_missing'])
            pct = (missing_count / len(results)) * 100 if results else 0
            bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
            print(
                f"   {spec_name:12s}: {missing_count:4d} lipsa ({pct:.0f}%) {bar}")

    # 5. Genereaza Excel
    if args.output:
        output_path = args.output
    else:
        output_path = os.path.expanduser(
            f'~/ejolie_specs_{"fill" if args.fill else "audit"}.xlsx')

    generate_excel(results, output_path)

    print(f"\n🎯 Gata! Fisierul Excel e la: {output_path}")
    if args.fill:
        print(f"   Importa-l in Extended: Manager → Actualizari → Import produse")
    print()


if __name__ == '__main__':
    main()
