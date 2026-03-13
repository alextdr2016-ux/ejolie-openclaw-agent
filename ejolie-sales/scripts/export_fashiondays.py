#!/usr/bin/env python3
"""
export_fashiondays.py v2 - Export produse Ejolie+Artista pentru Fashion Days Marketplace
Ia datele direct din Extended API (stoc per marime, specificatii, imagini)
Genereaza fisier Excel in formatul template-ului Fashion Days

Rulare: python3 export_fashiondays.py [--brand ejolie,artista] [--limit 10] [--dry-run]
"""

import json
import os
import sys
import argparse
import time
import requests
from openpyxl import Workbook

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BARCODE_PATH = os.path.join(SCRIPT_DIR, 'barcode_ejolie_map.json')
OUTPUT_PATH = os.path.join(SCRIPT_DIR, 'fashiondays_export.xlsx')

ENV_PATH = os.path.join(SCRIPT_DIR, '..', '.env')
API_KEY = None
if os.path.exists(ENV_PATH):
    with open(ENV_PATH) as f:
        for line in f:
            if line.startswith('EJOLIE_API_KEY='):
                API_KEY = line.strip().split(
                    '=', 1)[1].strip().strip('"').strip("'")
if not API_KEY:
    API_KEY = os.environ.get(
        'EJOLIE_API_KEY', 'N9komxWU3aclwDHyrXfLjJdBA6ZRTs')

API_BASE = 'https://ejolie.ro/api/'
HEADERS = {'User-Agent': 'Mozilla/5.0'}
PAGE_SIZE = 50

COLOR_MAP = {
    'Alb': 'Alb', 'Albastru': 'Albastru', 'Albastru deschis': 'Albastru deschis',
    'Albastru inchis': 'Albastru inchis', 'Albastru petrol': 'Albastru',
    'Animal print': 'Multicolor', 'Aramiu': 'Auriu', 'Argintiu': 'Argintiu',
    'Auriu': 'Auriu', 'Bej': 'Bej', 'Bleumarin': 'Bleumarin', 'Bordo': 'Visiniu',
    'Caramel': 'Maro', 'Ciocolatiu': 'Maro', 'Corai': 'Corai', 'Crem': 'Bej',
    'Galben': 'Galben', 'Gri': 'Gri', 'Kaki': 'Kaki', 'Lavanda': 'Mov',
    'Lila': 'Lila', 'Maro': 'Maro', 'Mov': 'Mov', 'Multicolor': 'Multicolor',
    'Negru': 'Negru', 'Nude': 'Nude', 'Olive': 'Verde', 'Piersica': 'Roz',
    'Portocaliu': 'Portocaliu', 'Pudra': 'Roz', 'Rosu': 'Rosu', 'Roz': 'Roz',
    'Roz prafuit': 'Roz', 'Somon': 'Roz', 'Turcoaz': 'Turcoaz', 'Verde': 'Verde',
    'Verde inchis': 'Verde inchis', 'Verde lime': 'Verde', 'Verde mint': 'Verde',
    'Vernil': 'Verde', 'Visiniu': 'Visiniu', 'floral': 'Multicolor', 'Fucsia': 'Roz',
}

BASE_COLOR_MAP = {
    'Alb': 'Alb', 'Albastru': 'Albastru', 'Albastru deschis': 'Albastru',
    'Albastru inchis': 'Albastru', 'Albastru petrol': 'Albastru',
    'Animal print': 'Multicolor', 'Aramiu': 'Auriu', 'Argintiu': 'Argintiu',
    'Auriu': 'Auriu', 'Bej': 'Bej', 'Bleumarin': 'Albastru', 'Bordo': 'Rosu',
    'Caramel': 'Maro', 'Ciocolatiu': 'Maro', 'Corai': 'Roz', 'Crem': 'Bej',
    'Galben': 'Galben', 'Gri': 'Gri', 'Kaki': 'Verde', 'Lavanda': 'Mov',
    'Lila': 'Mov', 'Maro': 'Maro', 'Mov': 'Mov', 'Multicolor': 'Multicolor',
    'Negru': 'Negru', 'Nude': 'Bej', 'Olive': 'Verde', 'Piersica': 'Roz',
    'Portocaliu': 'Portocaliu', 'Pudra': 'Roz', 'Rosu': 'Rosu', 'Roz': 'Roz',
    'Roz prafuit': 'Roz', 'Somon': 'Roz', 'Turcoaz': 'Albastru', 'Verde': 'Verde',
    'Verde inchis': 'Verde', 'Verde lime': 'Verde', 'Verde mint': 'Verde',
    'Vernil': 'Verde', 'Visiniu': 'Rosu', 'floral': 'Multicolor', 'Fucsia': 'Roz',
}

MATERIAL_MAP = {
    'Acryl': 'Acril', 'Barbie': 'Sintetic', 'Brocart': 'Sintetic', 'Bumbac': 'Bumbac',
    'Catifea': 'Catifea', 'Casmir': 'Lana', 'Crep': 'Sintetic', 'Dantela': 'Dantela',
    'Jerseu': 'Tricot', 'Lana': 'Lana', 'Lycra': 'Elastan', 'Licra': 'Elastan',
    'Matase': 'Matase', 'Neopren': 'Sintetic', 'Organza': 'Sintetic', 'Paiete': 'Sintetic',
    'Piele ecologica': 'Piele ecologica', 'Poliester': 'Poliester', 'Satin': 'Satin',
    'Sifon': 'Sintetic', 'Stofa': 'Lana', 'Tafta': 'Sintetic', 'Tricot': 'Tricot',
    'Tul': 'Tul', 'Tweed': 'Lana', 'Velur': 'Catifea', 'Voal': 'Sintetic',
}

LUNGIME_MAP = {'Lungi': 'Lunga', 'Medii': 'Midi', 'Scurte': 'Scurta'}

CROIALA_MAP = {
    'In clini': 'Evazat', 'Lejer': 'Lejer', 'Mulat': 'Bodycon', 'Peplum': 'Cambrata',
    'Petrecuta': 'Petrecuta', 'Plisat': 'Plisata', 'Pliuri': 'Plisata',
    'Volane': 'Evazat', 'in A': 'Evazat',
}

STIL_MAP = {
    'Asimetrica': 'Elegant', 'Birou': 'Casual', 'Casual': 'Casual',
    'Casual-Elegant': 'Casual', 'Casual-Office': 'Casual',
    'Cu crapatura': 'Elegant', 'De ocazie': 'De ocazie',
    'De seara': 'Elegant', 'Eleganta': 'Elegant', 'Sport': 'Casual',
    'Lunga sirena': 'Elegant',
}

SIZE_MAP = {
    'S': 'S INTL', 'M': 'M INTL', 'L': 'L INTL', 'XL': 'XL INTL',
    'XXL': '2XL INTL', '2XL': '2XL INTL', 'XXXL': '3XL INTL', '3XL': '3XL INTL',
    'XS': 'XS INTL', '4XL': '4XL INTL', '5XL': '5XL INTL',
    'S/M': 'S INTL', 'M/L': 'M INTL', 'L/XL': 'L INTL',
    'ONE SIZE': 'One Size INTL', 'UNIC': 'One Size INTL',
    '34': '34 EU', '36': '36 EU', '38': '38 EU', '40': '40 EU',
    '42': '42 EU', '44': '44 EU', '46': '46 EU', '48': '48 EU',
    '50': '50 EU', '52': '52 EU',
}


def fetch_all_products():
    all_products = {}
    page = 1
    while True:
        url = f'{API_BASE}?produse&apikey={API_KEY}&pagina={page}&limit={PAGE_SIZE}'
        try:
            r = requests.get(url, headers=HEADERS, timeout=60)
            data = r.json()
        except Exception as e:
            print(f'  Error page {page}: {e}')
            break
        if not data or (isinstance(data, dict) and data.get('eroare')):
            break
        if isinstance(data, dict):
            count = 0
            for pid, pdata in data.items():
                if isinstance(pdata, dict) and 'id_produs' in pdata:
                    all_products[pid] = pdata
                    count += 1
            print(f'  Page {page}: {count} products')
            if count < PAGE_SIZE:
                break
        else:
            break
        page += 1
        time.sleep(0.3)
    return all_products


def load_barcode_map():
    with open(BARCODE_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def build_product_barcode_map(barcode_map):
    product_barcodes = {}
    for barcode, pid in barcode_map.items():
        pid = str(pid)
        if pid not in product_barcodes:
            product_barcodes[pid] = []
        product_barcodes[pid].append(barcode)
    return product_barcodes


def get_spec(product, spec_name):
    specs = product.get('specificatii', [])
    if isinstance(specs, list):
        for s in specs:
            if isinstance(s, dict) and s.get('nume', '').lower() == spec_name.lower():
                vals = s.get('valoare', [])
                if isinstance(vals, list) and vals:
                    return vals[0]
    return ''


def map_val(value, mapping, default=''):
    if not value:
        return default
    if value in mapping:
        return mapping[value]
    for k, v in mapping.items():
        if k.lower() == value.lower():
            return v
    return default or value


def extract_color_from_name(name):
    colors_map = {
        'negru': 'Negru', 'neagra': 'Negru', 'alb': 'Alb', 'alba': 'Alb',
        'rosu': 'Rosu', 'rosie': 'Rosu', 'verde': 'Verde', 'albastru': 'Albastru',
        'albastra': 'Albastru', 'roz': 'Roz', 'mov': 'Mov', 'galben': 'Galben',
        'gri': 'Gri', 'maro': 'Maro', 'bej': 'Bej', 'crem': 'Crem',
        'bordo': 'Bordo', 'fucsia': 'Fucsia', 'turcoaz': 'Turcoaz', 'corai': 'Corai',
        'nude': 'Nude', 'auriu': 'Auriu', 'argintiu': 'Argintiu', 'bleumarin': 'Bleumarin',
        'lila': 'Lila', 'lavanda': 'Lavanda', 'kaki': 'Kaki', 'portocaliu': 'Portocaliu',
        'somon': 'Somon', 'visiniu': 'Visiniu', 'multicolor': 'Multicolor',
    }
    name_lower = name.lower()
    for pattern, color in colors_map.items():
        if pattern in name_lower:
            return color
    return ''


def generate_rows(products, barcode_map, allowed_brands, limit=None):
    product_barcodes = build_product_barcode_map(barcode_map)
    rows = []
    stats = {'processed': 0, 'no_barcode': 0, 'no_stock': 0, 'no_brand': 0}

    for pid, product in products.items():
        brand_data = product.get('brand', {})
        brand_name = brand_data.get('nume', '') if isinstance(
            brand_data, dict) else str(brand_data)

        if allowed_brands and brand_name.lower() not in allowed_brands:
            stats['no_brand'] += 1
            continue

        pid = str(product.get('id_produs', pid))
        name = product.get('nume', '')
        if not name:
            continue

        optiuni = product.get('optiuni', {})
        sizes_with_stock = []
        if isinstance(optiuni, dict):
            for opt_id, opt_data in optiuni.items():
                if isinstance(opt_data, dict):
                    size_name = opt_data.get('nume_optiune', '')
                    try:
                        stock = int(opt_data.get('stoc_fizic', 0))
                    except (ValueError, TypeError):
                        stock = 0
                    if stock > 0 and size_name:
                        sizes_with_stock.append(
                            {'name': size_name, 'stock': stock})

        if not sizes_with_stock:
            stats['no_stock'] += 1
            continue

        barcodes = product_barcodes.get(pid, [])
        if not barcodes:
            stats['no_barcode'] += 1
            continue

        code = product.get('cod_produs', f'FBR-{pid}')
        description = product.get('descriere', '')
        url = product.get('link', '')
        cota_tva = product.get('cota_tva', 19)

        images = product.get('imagini', [])
        if not images:
            main_img = product.get('imagine', '')
            images = [main_img] if main_img else []

        price_str = product.get('pret_discount', '0') or '0'
        try:
            price_with_vat = float(str(price_str).replace(' RON', '').strip())
        except ValueError:
            price_with_vat = 0
        if price_with_vat <= 0:
            price_str = product.get('pret', '0') or '0'
            try:
                price_with_vat = float(
                    str(price_str).replace(' RON', '').strip())
            except ValueError:
                price_with_vat = 0
        if price_with_vat <= 0:
            continue

        price_no_vat = round(price_with_vat / (1 + cota_tva / 100), 2)
        min_price = round(price_no_vat * 0.5, 2)
        max_price = round(price_no_vat * 2.0, 2)

        culoare = get_spec(product, 'Culoare') or extract_color_from_name(name)
        material = get_spec(product, 'Material')
        lungime = get_spec(product, 'Lungime')
        croi = get_spec(product, 'Croi')
        stil = get_spec(product, 'Stil')

        fd_culoare = map_val(culoare, COLOR_MAP, 'Negru')
        fd_base_color = map_val(culoare, BASE_COLOR_MAP, 'Negru')
        fd_material = map_val(material, MATERIAL_MAP, 'Poliester')
        fd_lungime = map_val(lungime, LUNGIME_MAP, '')
        fd_croiala = map_val(croi, CROIALA_MAP, '')
        fd_stil = map_val(stil, STIL_MAP, 'Elegant')

        for size_idx, size_info in enumerate(sizes_with_stock):
            ean = barcodes[size_idx] if size_idx < len(
                barcodes) else barcodes[-1]
            fd_size = SIZE_MAP.get(
                size_info['name'].upper().strip(), size_info['name'] + ' EU')

            rows.append([
                code, int(pid), ean, price_no_vat, '', cota_tva, 1, 'RON',
                size_info['stock'], 1, 14, 0, '', min_price, max_price,
                name[:255], brand_name, description, url, 'ro_RO',
                images[0] if images else '',
                images[1] if len(images) > 1 else '',
                images[2] if len(images) > 2 else '',
                images[3] if len(images) > 3 else '',
                images[4] if len(images) > 4 else '',
                images[5] if len(images) > 5 else '',
                int(pid), name[:100], 'Marime',
                fd_size, fd_size,
                fd_culoare, fd_material, '2026', fd_stil, fd_lungime,
                '', 'Uni', '', '', fd_base_color, '', '', '', '', '', '', '',
                'Femei', fd_croiala, brand_name, fd_size, '',
                '', 'SMARTEX FASHION S.R.L.',
                'Aninoasa, str. Valea Mare nr. 1, jud. Dambovita, Romania',
                'contact@ejolie.ro', '', '', '',
            ])

        stats['processed'] += 1
        if limit and stats['processed'] >= limit:
            break

    print(f"\nResults:")
    print(f"  Products processed: {stats['processed']}")
    print(f"  Rows generated: {len(rows)} (one per size)")
    print(f"  Skipped (wrong brand): {stats['no_brand']}")
    print(f"  Skipped (no stock): {stats['no_stock']}")
    print(f"  Skipped (no barcode): {stats['no_barcode']}")
    return rows


def write_xlsx(rows, output_path):
    wb = Workbook()
    ws = wb.active
    ws.title = 'Template'

    groups = ['Identificare produs', '', '', 'Oferta - Pret', '', '', '', 'Moneda', 'Oferta - Stoc & disponibilitate', '', '', '', 'Detalii oferta', 'Oferta - Verificare pret', '', 'Descriere produs', '', '', '', '',
              'Imagini', '', '', '', '', '', 'Variation (product families)', '', '', 'Caracteristici - Rochii', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '']
    ws.append(groups)

    oblig = ['', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', 'Obligatoriu',
             '', 'Recomandat', '', 'Optional', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '']
    ws.append(oblig)

    tech = ['part_number', 'vendor_ext_id', 'ean', 'sale_price', 'original_sale_price', 'vat_rate', 'status', 'offer_currency', 'stock', 'handling_time', 'lead_time', 'warranty', 'offer_properties', 'min_sale_price', 'max_sale_price', 'name', 'brand', 'description', 'url', 'source_language', 'main_image_url', 'other_image_url1', 'other_image_url2', 'other_image_url3', 'other_image_url4', 'other_image_url5', 'family_id', 'family_name', 'family_type', 'Marime [original]: [6506]', 'Marime [converted]: [6506]', 'Culoare: [5401]', 'Material: [6372]', 'Colectie: [5429]',
            'Stil: [6140]', 'Lungime: [6142]', 'Lungime maneca: [6146]', 'Imprimeu: [6155]', 'Detalii: [6469]', 'Sistem inchidere: [6765]', 'Culoare de baza: [8956]', 'Captuseala: [9011]', 'Decolteu: [9012]', 'Buzunare: [9015]', 'Exterior: [9018]', 'Barete: [9023]', 'Material garnituri: [9025]', 'Talie: [9028]', 'Pentru: [9084]', 'Croiala: [9097]', 'Linie Brand: [9370]', 'Marime convertita: [10770]', 'Fit: [10965]', 'safety_information', 'manufacturer_name', 'manufacturer_address', 'manufacturer_email', 'responsible_name', 'responsible_address', 'responsible_email']
    ws.append(tech)

    oblig2 = ['Obligatoriu', 'Obligatoriu', 'Optional/Obligatoriu', 'Obligatoriu', 'Optional', 'Obligatoriu', 'Obligatoriu', 'Obligatoriu', 'Obligatoriu', 'Optional', 'Optional', 'Optional/Obligatoriu', 'Optional', 'Optional/Obligatoriu', 'Optional/Obligatoriu', 'Obligatoriu', 'Obligatoriu', 'Obligatoriu', 'Optional',
              'Obligatoriu (restrictiv)', 'Obligatoriu', 'Optional', 'Optional', 'Optional', 'Optional', 'Optional', 'Optional', 'Optional', 'Optional', 'Obligatoriu (restrictiv)', 'Obligatoriu (restrictiv)', 'Recomandat (restrictiv)', 'Recomandat (restrictiv)', 'Recomandat', 'Recomandat (restrictiv)', 'Recomandat (restrictiv)', 'Recomandat (restrictiv)', 'Recomandat (restrictiv)', 'Recomandat', 'Recomandat (restrictiv)', 'Recomandat (restrictiv)', 'Recomandat', 'Recomandat (restrictiv)', 'Recomandat', 'Recomandat', 'Recomandat', 'Recomandat', 'Recomandat', 'Recomandat (restrictiv)', 'Recomandat (restrictiv)', 'Recomandat', 'Recomandat (restrictiv)', 'Recomandat (restrictiv)', 'Legal', 'Legal', 'Legal', 'Legal', 'Legal', 'Legal', 'Legal']
    ws.append(oblig2)

    human = ['Cod produs', 'ID produs', 'EAN produs', 'Pret vanzare', 'PRP', 'TVA', 'Status', 'Moneda', 'Stoc', 'In cate zile predai comanda curierului', 'In cate zile poti reaproviziona', 'Garantie', 'Proprietatile ofertei', 'Pret minim', 'Pret maxim', 'Nume', 'Brand', 'Descriere', 'URL site propriu', 'Limba sursa', 'URL imagine principala', 'URL imagine secundara 1', 'URL imagine secundara 2', 'URL imagine secundara 3', 'URL imagine secundara 4', 'URL imagine secundara 5', 'ID familie', 'Nume familie', 'Tip Familie',
             'Marime [original]', 'Marime [converted]', 'Culoare', 'Material', 'Colectie', 'Stil', 'Lungime', 'Lungime maneca', 'Imprimeu', 'Detalii', 'Sistem inchidere', 'Culoare de baza', 'Captuseala', 'Decolteu', 'Buzunare', 'Exterior', 'Barete', 'Material garnituri', 'Talie', 'Pentru', 'Croiala', 'Linie Brand', 'Marime convertita', 'Fit', 'Avertizari de siguranta', 'Nume producator', 'Adresa producator', 'Adresa email producator', 'Nume persoana responsabila UE', 'Adresa persoana responsabila UE', 'Adresa email persoana responsabila UE']
    ws.append(human)

    for row in rows:
        ws.append(row)

    wb.save(output_path)
    print(f"\nSaved: {output_path}")
    print(f"  Header rows: 5, Data rows: {len(rows)}")


def main():
    parser = argparse.ArgumentParser(
        description='Export produse pentru Fashion Days')
    parser.add_argument('--brand', default='ejolie,artista',
                        help='Brand filter, comma-separated')
    parser.add_argument('--limit', type=int, default=None,
                        help='Limit number of products')
    parser.add_argument('--dry-run', action='store_true',
                        help='Only show stats')
    parser.add_argument('--output', default=OUTPUT_PATH,
                        help='Output file path')
    args = parser.parse_args()

    print("=" * 60)
    print("Fashion Days Export v2 - Produse Ejolie + Artista")
    print("=" * 60)

    allowed_brands = [b.strip().lower() for b in args.brand.split(',')]
    print(f"\nBrands: {', '.join(allowed_brands)}")

    print(f"\nFetching products from Extended API...")
    products = fetch_all_products()
    print(f"  Total: {len(products)} products")

    print(f"\nLoading barcode map from: {BARCODE_PATH}")
    barcode_map = load_barcode_map()
    print(f"  Total: {len(barcode_map)} barcodes")

    rows = generate_rows(products, barcode_map,
                         allowed_brands, limit=args.limit)

    if args.dry_run:
        print("\n[DRY RUN] No file written.")
        if rows:
            labels = ['part_number', 'vendor_ext_id', 'ean', 'sale_price', '', 'vat', 'status', 'currency',
                      'stock', 'handling', 'lead', 'warranty', '', 'min_price', 'max_price', 'name', 'brand']
            print(f"\nSample row:")
            for i, val in enumerate(rows[0][:17]):
                print(f"  {labels[i]}: {val}")
        return

    write_xlsx(rows, args.output)
    print("\nDone!")


if __name__ == '__main__':
    main()
