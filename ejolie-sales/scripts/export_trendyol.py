#!/usr/bin/env python3
"""
export_trendyol.py v2 - Export ejolie.ro products to Trendyol import template
Supports both brand-based and ID range export. Uses Gemini for attribute extraction.

Utilizare:
    python3 export_trendyol.py --brand ejolie                    # toate produsele unui brand
    python3 export_trendyol.py --start 12356 --end 12415         # range de ID-uri
    python3 export_trendyol.py --ids 12356,12360,12370           # ID-uri specifice
    python3 export_trendyol.py --brand ejolie --limit 5          # primele 5 produse
    python3 export_trendyol.py --start 12356 --end 12415 --telegram
"""

import os
import json
import re
import argparse
import time
import sys
from datetime import datetime

import requests
from dotenv import load_dotenv

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(SCRIPT_DIR, '..', '.env')
if not os.path.exists(ENV_PATH):
    ENV_PATH = os.path.join(SCRIPT_DIR, '.env')
load_dotenv(ENV_PATH)

API_KEY = os.getenv('EJOLIE_API_KEY', '')
API_BASE = os.getenv('EJOLIE_API_URL', 'https://ejolie.ro/api/')
GEMINI_KEY = os.getenv('GEMINI_API_KEY', '')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '44151343')
HEADERS = {'User-Agent': 'Mozilla/5.0'}

# ═══════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════

TRENDYOL_COLORS = {
    "negru": "Negru", "neagra": "Negru", "negra": "Negru", "black": "Negru",
    "alb": "Alb", "alba": "Alb", "ivory": "Alb",
    "rosu": "Roșu", "rosie": "Roșu",
    "verde": "Verde", "lime": "Verde", "mint": "Verde", "vernil": "Verde",
    "albastru": "Albastru", "albastra": "Albastru", "bleu": "Albastru",
    "galben": "Galben", "galbena": "Galben",
    "roz": "Roz", "fucsia": "Roz", "somon": "Roz",
    "bordo": "Burgundia", "burgundy": "Burgundia", "visiniu": "Burgundia",
    "mov": "Multicolor", "lila": "Multicolor", "lavanda": "Multicolor",
    "gri": "Gri",
    "bej": "Bej", "nude": "Bej", "crem": "Crem",
    "turcoaz": "Turcoaz", "portocaliu": "Portocaliu", "portocalie": "Portocaliu",
    "coral": "Portocaliu", "caramiziu": "Portocaliu",
    "argintiu": "Argintiu", "auriu": "Auriu", "aurie": "Auriu",
    "maro": "Maro", "kaki": "Kaki", "ciocolatiu": "Maro",
    "multicolor": "Multicolor", "imprimeu": "Multicolor", "floral": "Multicolor",
    "bleumarin": "Bleumarin",
}

ALLOWED_SILUETA = ["A-line", "Asimetric", "Bodycon", "Drept",
                   "Sirenă", "Prințesă", "Shift", "Slip", "Oversize", "Peplum", "Wrap"]
ALLOWED_MANECA = ["Bretele spaghetti", "Fără mâneci",
                  "Lung", "Mâneca trei sferturi", "Scurt"]
ALLOWED_GULER = ["Fără bretele", "Gât rotund", "Gât în V",
                 "Guler bărcuță", "Guler cu rever", "Cache-coeur", "Gât înalt", "Un umăr"]
ALLOWED_OCAZIE = ["Absolvire / Bal de absolvire", "Bal", "Casual",
                  "Cocktail", "Elegant", "Elegant / Noapte", "Petrecere", "Seara / zilnic"]
ALLOWED_MATERIAL = ["Amestec poliester", "Catifea", "Crepe", "Cu paiete",
                    "Dantelă", "Fabric lucios", "Satin", "Tul", "Voal", "Altele"]


# ═══════════════════════════════════════════
#  EAN-13 BARCODE
# ═══════════════════════════════════════════

_ean_counter = 0


def generate_ean13():
    global _ean_counter
    _ean_counter += 1
    base = "200" + str(_ean_counter).zfill(9)
    base = base[:12]
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(base))
    check = (10 - (total % 10)) % 10
    return base + str(check)


# ═══════════════════════════════════════════
#  COLOR EXTRACTION
# ═══════════════════════════════════════════

def extract_color(name):
    words = name.lower().split()
    for word in words:
        if word in TRENDYOL_COLORS:
            return TRENDYOL_COLORS[word]
    name_lower = name.lower()
    for key, val in TRENDYOL_COLORS.items():
        if key in name_lower:
            return val
    return "Multicolor"


# ═══════════════════════════════════════════
#  GEMINI ATTRIBUTE EXTRACTION
# ═══════════════════════════════════════════

def call_gemini(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}"
    data = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 500}
    }
    try:
        resp = requests.post(url, json=data, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        return result['candidates'][0]['content']['parts'][0]['text'].strip()
    except Exception as e:
        print(f"⚠ Gemini error: {e}")
        return ""


def extract_attributes(name, description):
    clean_desc = re.sub(r'<[^>]+>', '', str(description))[:500]
    prompt = f"""Analizează acest produs vestimentar și extrage atributele.

Nume: {name}
Descriere: {clean_desc}

Alege EXACT din valorile permise:
SILUETA: {', '.join(ALLOWED_SILUETA)}
LUNGIME_MANECA: {', '.join(ALLOWED_MANECA)}
GULER: {', '.join(ALLOWED_GULER)}
OCAZIE: {', '.join(ALLOWED_OCAZIE)}
MATERIAL: {', '.join(ALLOWED_MATERIAL)}
TIP_MATERIAL: Knit, Laced, Țesut, Nespecificat
MODEL: Simplu, Cu model floral, Dantelă, Satin, Plain
CAPTUSIT: Căptușit sau Fără căptușeală
INCHIDERE: Cu fermoar, Fără închidere, Buton

Răspunde EXACT în formatul:
SILUETA: valoare
LUNGIME_MANECA: valoare
GULER: valoare
OCAZIE: valoare
MATERIAL: valoare
TIP_MATERIAL: valoare
MODEL: valoare
CAPTUSIT: valoare
INCHIDERE: valoare"""

    response = call_gemini(prompt)
    attrs = {}
    for line in response.split("\n"):
        if ":" in line:
            key, val = line.split(":", 1)
            attrs[key.strip().upper()] = val.strip()
    return attrs


# ═══════════════════════════════════════════
#  API FETCH
# ═══════════════════════════════════════════

def fetch_products_by_brand(brand="ejolie"):
    """Fetch toate produsele unui brand cu paginare."""
    all_products = {}
    page = 1
    print(f"  Fetch produse brand '{brand}'...")
    while True:
        url = f"{API_BASE}?produse&brand={brand}&apikey={API_KEY}&pagina={page}&limit=50"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=60)
            data = resp.json()
        except Exception as e:
            print(f"  ✗ Eroare pagina {page}: {e}")
            break

        if not data or not isinstance(data, dict):
            break
        all_products.update(data)
        count = len(data)
        print(
            f"    Pagina {page}: {count} produse (total: {len(all_products)})")
        if count < 50:
            break
        page += 1
        time.sleep(0.3)
    return all_products


def fetch_products_by_ids(product_ids):
    """Fetch produse individuale pe id_produs."""
    all_products = {}
    print(f"  Fetch {len(product_ids)} produse pe ID...")
    for i, pid in enumerate(product_ids):
        url = f"{API_BASE}?id_produs={pid}&apikey={API_KEY}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            data = resp.json()
            if isinstance(data, dict) and str(pid) in data:
                product = data[str(pid)]
                # Skip dacă nu are opțiuni (produs inactiv)
                if product.get('optiuni'):
                    all_products[str(pid)] = product
                else:
                    print(f"    ⚠ ID {pid}: fără opțiuni (inactiv?)")
            else:
                print(f"    ✗ ID {pid}: nu există")
        except Exception as e:
            print(f"    ✗ ID {pid}: {e}")

        if (i + 1) % 10 == 0:
            print(f"    ... {i+1}/{len(product_ids)}")
        time.sleep(0.3)
    return all_products


# ═══════════════════════════════════════════
#  EXCEL EXPORT
# ═══════════════════════════════════════════

def export_trendyol(products, output_path):
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Introdu informațiile despre pro"

    headers = [
        "Cod de bare", "Codul modelului", "Marca produsului", "ID categorie",
        "Titlu", "Descriere", "Preț inițial", "Preț de vânzare Trendyol",
        "Stoc", "Cod stoc", "Cotă TVA",
        "Imagine 1", "Imagine 2", "Imagine 3", "Imagine 4",
        "Imagine 5", "Imagine 6", "Imagine 7", "Imagine 8",
        "Termendeprelucrare", "Mărime", "Buzunar", "Siluetă",
        "Lungimea mânecii", "Potrivire", "Ocazie",
        "Detalii privind durabilitatea", "Compoziția materialului",
        "Culoare", "Guler", "Tipul de material", "Tipul de mânecă",
        "Tip de produs", "Model", "Tipul de material",
        "Origine", "Tipul de închidere", "Instrucțiuni de îngrijire",
        "Grupa de vârstă", "Detalii despre produs",
        "Numele producătorului", "Starea curelei", "Culoare",
        "Sex", "Persona", "Material", "Colecția",
        "Caracteristici suplimentare", "Căptușeală", "Lungime"
    ]

    red_fill = PatternFill(start_color="FFD9D9",
                           end_color="FFD9D9", fill_type="solid")
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = Font(bold=True, size=9)
        cell.alignment = Alignment(horizontal="center", wrap_text=True)
        if col <= 11:
            cell.fill = red_fill

    row_idx = 2
    prod_count = 0
    gpt_cache = {}

    for pid, prod in products.items():
        optiuni = prod.get("optiuni", {})
        if not isinstance(optiuni, dict):
            continue

        name = prod.get("nume", "")
        cod = prod.get("cod_produs", "")
        pret = prod.get("pret", "0")
        pret_discount = prod.get("pret_discount", "0")
        descriere = prod.get("descriere", "")
        clean_desc = re.sub(r'<[^>]+>', '', str(descriere))[:2000]
        color = extract_color(name)

        imagini = prod.get("imagini", [])
        if not isinstance(imagini, list):
            imagini = []
        imagine_main = prod.get("imagine", "")
        if imagine_main and imagine_main not in imagini:
            imagini.insert(0, imagine_main)

        if pid not in gpt_cache:
            prod_count += 1
            print(f"  🤖 [{prod_count}] {name[:45]}...", end=" ", flush=True)
            attrs = extract_attributes(name, descriere)
            gpt_cache[pid] = attrs
            print("✅")
            time.sleep(0.5)
        attrs = gpt_cache[pid]

        try:
            p = float(str(pret).replace(",", ".")) if pret else 0
            pd = float(str(pret_discount).replace(
                ",", ".")) if pret_discount else 0
            sell_price = pd if pd > 0 and pd < p else p
        except:
            p = 0
            sell_price = 0

        for oid, opt in optiuni.items():
            if not isinstance(opt, dict):
                continue
            stoc_fizic = int(opt.get("stoc_fizic", 0))
            if stoc_fizic <= 0:
                continue

            size = opt.get("nume_optiune", "")
            try:
                op = float(str(opt.get("pret", pret)).replace(",", "."))
                opd = float(
                    str(opt.get("pret_discount", "0")).replace(",", "."))
                opt_sell = opd if opd > 0 and opd < op else op
            except:
                op = p
                opt_sell = sell_price

            barcode = generate_ean13()
            brand_data = prod.get("brand", {})
            brand_name = brand_data.get("nume", "Ejolie") if isinstance(
                brand_data, dict) else str(brand_data)

            row = [
                barcode, cod or pid, brand_name, 543,
                name, clean_desc[:5000], op, opt_sell,
                stoc_fizic, f"{cod}-{size}", 21,
            ]
            for i in range(8):
                row.append(imagini[i] if i < len(imagini) else "")
            row.extend([
                3, size, "Fără buzunar",
                attrs.get("SILUETA", "A-line"),
                attrs.get("LUNGIME_MANECA", "Fără mâneci"),
                attrs.get("SILUETA", "A-line"),
                attrs.get("OCAZIE", "Elegant"),
                "Nu", "",
                color,
                attrs.get("GULER", "Gât rotund"),
                attrs.get("TIP_MATERIAL", "Țesut"),
                attrs.get("LUNGIME_MANECA", "Fără mâneci"),
                "Simplu", attrs.get("MODEL", "Simplu"),
                attrs.get("TIP_MATERIAL", "Țesut"),
                "RO", attrs.get("INCHIDERE", "Cu fermoar"),
                "", "Adult", "", brand_name, "Fără centură",
                color, "Femeie", "Feminin",
                attrs.get("MATERIAL", "Amestec poliester"),
                "Elegant / Noapte", "",
                attrs.get("CAPTUSIT", "Căptușit"), "",
            ])
            for col, val in enumerate(row, 1):
                ws.cell(row=row_idx, column=col, value=val)
            row_idx += 1

    for col in range(1, len(headers) + 1):
        import openpyxl.utils
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 18

    total = row_idx - 2
    wb.save(output_path)
    return total, prod_count


# ═══════════════════════════════════════════
#  TELEGRAM
# ═══════════════════════════════════════════

def send_telegram_file(filepath, caption=''):
    if not TELEGRAM_BOT_TOKEN:
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
    try:
        with open(filepath, 'rb') as f:
            resp = requests.post(url,
                                 data={'chat_id': TELEGRAM_CHAT_ID,
                                       'caption': caption, 'parse_mode': 'HTML'},
                                 files={'document': f}, timeout=60)
        return resp.status_code == 200
    except:
        return False


# ═══════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description='Export ejolie.ro products to Trendyol template')
    parser.add_argument("--brand", default=None,
                        help="Export pe brand (ejolie, trendya, artista)")
    parser.add_argument("--start", type=int, help="ID produs start")
    parser.add_argument("--end", type=int, help="ID produs end")
    parser.add_argument("--ids", type=str,
                        help="ID-uri specifice separate prin virgulă")
    parser.add_argument("--output", default=None, help="Fișier output")
    parser.add_argument("--limit", type=int, default=None,
                        help="Limită număr produse")
    parser.add_argument("--telegram", action='store_true',
                        help="Trimite pe Telegram")
    args = parser.parse_args()

    if not API_KEY:
        print("✗ EJOLIE_API_KEY nu e setat!")
        sys.exit(1)
    if not GEMINI_KEY:
        print("✗ GEMINI_API_KEY nu e setat!")
        sys.exit(1)

    # Determină modul de fetch
    if args.ids:
        product_ids = [int(x.strip()) for x in args.ids.split(',')]
        mode = f"IDs: {len(product_ids)} produse"
    elif args.start and args.end:
        product_ids = list(range(args.start, args.end + 1))
        mode = f"Range: {args.start}-{args.end} ({len(product_ids)} IDs)"
    elif args.brand:
        product_ids = None
        mode = f"Brand: {args.brand}"
    else:
        print("✗ Specifică --brand, --start/--end, sau --ids")
        sys.exit(1)

    output_path = args.output or os.path.join(
        SCRIPT_DIR, f"trendyol_export_{datetime.now().strftime('%Y-%m-%d_%H%M')}.xlsx"
    )

    print(f"═══ Export Trendyol ═══")
    print(f"  Mod:      {mode}")
    print(f"  Output:   {output_path}")
    print(f"  Telegram: {'Da' if args.telegram else 'Nu'}")
    print()

    # Fetch produse
    if product_ids:
        products = fetch_products_by_ids(product_ids)
    else:
        products = fetch_products_by_brand(brand=args.brand)

    if args.limit:
        products = dict(list(products.items())[:args.limit])
        print(f"  ⚡ Limitat la {args.limit} produse")

    if not products:
        print("✗ Niciun produs găsit!")
        sys.exit(1)

    print(f"\n  📦 {len(products)} produse de exportat\n")

    # Export
    total_rows, prod_count = export_trendyol(products, output_path)

    print(f"""
═══ EXPORT COMPLET ═══
  Fișier:    {output_path}
  Rânduri:   {total_rows} (1 per mărime cu stoc > 0)
  Produse:   {prod_count} (atribute Gemini)

  ⬆ UPLOAD PE TRENDYOL:
    1. partner.trendyol.com → Produse → Acțiuni colective
    2. Tab "Încărcați șablonul"
    3. Tip: "Crearea de produse noi"
    4. Upload: {os.path.basename(output_path)}""")

    if args.telegram:
        print(f"\n  📤 Trimit pe Telegram...")
        caption = (
            f"📦 <b>Trendyol Export — {datetime.now().strftime('%d.%m.%Y')}</b>\n\n"
            f"✅ {total_rows} rânduri, {prod_count} produse\n"
            f"⬆ Upload: Crearea de produse noi"
        )
        if send_telegram_file(output_path, caption=caption):
            print("  ✓ Trimis pe Telegram!")
        else:
            print("  ✗ Eroare Telegram")


if __name__ == "__main__":
    main()
