#!/usr/bin/env python3
"""Export ejolie.ro products to Trendyol import template with GPT attribute extraction"""

import os, json, re, argparse, urllib.request, time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Load env
env_path = os.path.join(SCRIPT_DIR, "..", ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                k, v = line.strip().split('=', 1)
                os.environ[k] = v

OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")
API_KEY = os.environ.get("EJOLIE_API_KEY", "")
API_URL = os.environ.get("EJOLIE_API_URL", "https://ejolie.ro/api/")

TRENDYOL_COLORS = {
    "negru": "Negru", "neagra": "Negru", "negra": "Negru", "black": "Negru",
    "alb": "Alb", "alba": "Alb", "ivory": "Alb",
    "rosu": "Roșu", "rosie": "Roșu",
    "verde": "Verde",
    "albastru": "Albastru", "albastra": "Albastru",
    "galben": "Galben", "galbena": "Galben",
    "roz": "Roz", "fucsia": "Roz",
    "bordo": "Burgundia", "burgundy": "Burgundia", "visiniu": "Burgundia",
    "mov": "Multicolor", "lila": "Multicolor",
    "gri": "Gri",
    "bej": "Bej", "nude": "Bej", "crem": "Crem",
    "turcoaz": "Turcoaz", "portocaliu": "Portocaliu", "coral": "Portocaliu",
    "argintiu": "Argintiu", "auriu": "Auriu", "aurie": "Auriu",
    "maro": "Maro", "kaki": "Kaki",
    "multicolor": "Multicolor", "imprimeu": "Multicolor",
    "bleumarin": "Bleumarin",
    "somon": "Roz", "lavanda": "Multicolor", "mint": "Verde",
}

ALLOWED_SILUETA = ["A-line", "Asimetric", "Bodycon", "Drept", "Sirenă", "Prințesă", "Shift", "Slip", "Oversize", "Peplum", "Wrap"]
ALLOWED_MANECA = ["Bretele spaghetti", "Fără mâneci", "Lung", "Mâneca trei sferturi", "Scurt"]
ALLOWED_GULER = ["Fără bretele", "Gât rotund", "Gât în V", "Guler bărcuță", "Guler cu rever", "Cache-coeur", "Gât înalt", "Un umăr"]
ALLOWED_OCAZIE = ["Absolvire / Bal de absolvire", "Bal", "Casual", "Cocktail", "Elegant", "Elegant / Noapte", "Petrecere", "Seara / zilnic"]
ALLOWED_MATERIAL = ["Amestec poliester", "Catifea", "Crepe", "Cu paiete", "Dantelă", "Fabric lucios", "Satin", "Tul", "Voal", "Altele"]
ALLOWED_TIP_MATERIAL = ["Knit", "Laced", "Țesut", "Nespecificat"]


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


def call_gpt(prompt, model="gpt-4o-mini"):
    url = "https://api.openai.com/v1/chat/completions"
    data = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 500,
    }).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={
        "Authorization": f"Bearer {OPENAI_KEY}",
        "Content-Type": "application/json",
    })
    resp = urllib.request.urlopen(req, timeout=30)
    result = json.loads(resp.read().decode("utf-8"))
    return result["choices"][0]["message"]["content"].strip()


def extract_attributes_gpt(name, description):
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
TIP_MATERIAL: {', '.join(ALLOWED_TIP_MATERIAL)}
MODEL: Simplu, Cu model floral, Dantelă, Satin, Plain
CAPTUSIT: Căptușit sau Fără căptușeală
INCHIDERE: Cu fermoar, Fără închidere, Buton

Răspunde EXACT:
SILUETA: valoare
LUNGIME_MANECA: valoare
GULER: valoare
OCAZIE: valoare
MATERIAL: valoare
TIP_MATERIAL: valoare
MODEL: valoare
CAPTUSIT: valoare
INCHIDERE: valoare"""
    try:
        response = call_gpt(prompt)
        attrs = {}
        for line in response.split("\n"):
            if ":" in line:
                key, val = line.split(":", 1)
                attrs[key.strip().upper()] = val.strip()
        return attrs
    except Exception as e:
        print(f"    ⚠️ GPT error: {e}")
        return {}


def fetch_products(brand="ejolie"):
    url = f"{API_URL}?produse&brand={brand}&apikey={API_KEY}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    data = json.loads(urllib.request.urlopen(req, timeout=180).read().decode("utf-8"))
    all_products = {}
    ids = [pid for pid, p in data.items() if isinstance(p, dict)]
    print(f"📦 {len(ids)} produse {brand}")
    batch_size = 20
    for i in range(0, len(ids), batch_size):
        batch = ids[i:i+batch_size]
        url2 = f"{API_URL}?produse&id_produse={','.join(batch)}&apikey={API_KEY}"
        try:
            req2 = urllib.request.Request(url2, headers={"User-Agent": "Mozilla/5.0"})
            batch_data = json.loads(urllib.request.urlopen(req2, timeout=180).read().decode("utf-8"))
            for pid, prod in batch_data.items():
                if isinstance(prod, dict):
                    all_products[pid] = prod
            print(f"  📡 {min(i+batch_size, len(ids))}/{len(ids)}...")
        except Exception as e:
            print(f"  ⚠️ {e}")
        time.sleep(0.5)
    return all_products


def export_trendyol(products, output=None):
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill

    if output is None:
        output = "/home/ubuntu/ejolie_trendyol_export.xlsx"

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

    red_fill = PatternFill(start_color="FFD9D9", end_color="FFD9D9", fill_type="solid")
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
            optiuni = {}

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
            attrs = extract_attributes_gpt(name, descriere)
            gpt_cache[pid] = attrs
            print("✅")
            time.sleep(0.8)
        attrs = gpt_cache[pid]

        try:
            p = float(str(pret).replace(",", ".")) if pret else 0
            pd = float(str(pret_discount).replace(",", ".")) if pret_discount else 0
            sell_price = pd if pd > 0 and pd < p else p
        except:
            p = 0
            sell_price = 0

        if optiuni:
            for oid, opt in optiuni.items():
                if not isinstance(opt, dict):
                    continue
                stoc_fizic = opt.get("stoc_fizic", 0)
                try:
                    stoc_fizic = int(stoc_fizic)
                except:
                    stoc_fizic = 0
                if stoc_fizic <= 0:
                    continue

                size = opt.get("nume_optiune", "")
                try:
                    op = float(str(opt.get("pret", pret)).replace(",", "."))
                    opd = float(str(opt.get("pret_discount", "0")).replace(",", "."))
                    opt_sell = opd if opd > 0 and opd < op else op
                except:
                    op = p
                    opt_sell = sell_price

                barcode = f"{cod}-{size}" if cod else f"{pid}-{size}"
                row = [
                    barcode, cod or pid, "Ejolie", 543,
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
                    "", "Adult", "", "Ejolie", "Fără centură",
                    color, "Femeie", "Feminin",
                    attrs.get("MATERIAL", "Amestec poliester"),
                    "Elegant / Noapte", "",
                    attrs.get("CAPTUSIT", "Căptușit"), "",
                ])
                for col, val in enumerate(row, 1):
                    ws.cell(row=row_idx, column=col, value=val)
                row_idx += 1

    for col in range(1, len(headers) + 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 18

    total = row_idx - 2
    wb.save(output)
    print(f"\n✅ Trendyol export: {output} ({total} rânduri, {prod_count} produse GPT)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--brand", default="ejolie")
    parser.add_argument("--output", default=None)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    print(f"🛒 Export Trendyol - brand: {args.brand}")
    products = fetch_products(brand=args.brand)
    if args.limit:
        products = dict(list(products.items())[:args.limit])
        print(f"  ⚡ Limitat la {args.limit} produse")
    export_trendyol(products, output=args.output)

if __name__ == "__main__":
    main()
