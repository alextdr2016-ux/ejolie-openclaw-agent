#!/usr/bin/env python3
"""
export_fashiondays.py - Export produse Ejolie pentru Fashion Days Marketplace
Generează fișier Excel în formatul template-ului Fashion Days (eMAG)

Folosește:
- product_feed.json (cache produse Extended)
- barcode_ejolie_map.json (mapping barcode → product ID)

Rulare: python3 export_fashiondays.py [--brand ejolie] [--limit 10] [--dry-run]
"""

import json
import os
import sys
import argparse
import re
from copy import copy
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FEED_PATH = os.path.join(SCRIPT_DIR, 'product_feed.json')
BARCODE_PATH = os.path.join(SCRIPT_DIR, 'barcode_ejolie_map.json')
TEMPLATE_PATH = os.path.join(SCRIPT_DIR, 'fashiondays_template.xlsx')
OUTPUT_PATH = os.path.join(SCRIPT_DIR, 'fashiondays_export.xlsx')

# ============================================================
# MAPPING: Extended specificații → Fashion Days caracteristici
# ============================================================

# Culoare Extended → Culoare Fashion Days [5401]
COLOR_MAP = {
    'Alb': 'Alb', 'Albastru': 'Albastru', 'Albastru deschis': 'Albastru deschis',
    'Albastru inchis': 'Albastru inchis', 'Albastru petrol': 'Albastru', 'Animal print': 'Multicolor',
    'Aramiu': 'Auriu', 'Argintiu': 'Argintiu', 'Auriu': 'Auriu', 'Bej': 'Bej',
    'Bleumarin': 'Bleumarin', 'Bordo': 'Visiniu', 'Caramel': 'Maro', 'Ciocolatiu': 'Maro',
    'Corai': 'Corai', 'Crem': 'Bej', 'Galben': 'Galben', 'Gri': 'Gri', 'Kaki': 'Kaki',
    'Lavanda': 'Mov', 'Lila': 'Lila', 'Maro': 'Maro', 'Mov': 'Mov', 'Multicolor': 'Multicolor',
    'Negru': 'Negru', 'Nude': 'Nude', 'Olive': 'Verde', 'Piersica': 'Roz',
    'Portocaliu': 'Portocaliu', 'Pudra': 'Roz', 'Rosu': 'Rosu', 'Roz': 'Roz',
    'Roz prafuit': 'Roz', 'Somon': 'Roz', 'Turcoaz': 'Turcoaz', 'Verde': 'Verde',
    'Verde inchis': 'Verde inchis', 'Verde lime': 'Verde', 'Verde mint': 'Verde',
    'Vernil': 'Verde', 'Visiniu': 'Visiniu', 'floral': 'Multicolor', 'Fucsia': 'Roz',
}

# Culoare Extended → Culoare de baza Fashion Days [8956]
BASE_COLOR_MAP = {
    'Alb': 'Alb', 'Albastru': 'Albastru', 'Albastru deschis': 'Albastru',
    'Albastru inchis': 'Albastru', 'Albastru petrol': 'Albastru', 'Animal print': 'Multicolor',
    'Aramiu': 'Auriu', 'Argintiu': 'Argintiu', 'Auriu': 'Auriu', 'Bej': 'Bej',
    'Bleumarin': 'Albastru', 'Bordo': 'Rosu', 'Caramel': 'Maro', 'Ciocolatiu': 'Maro',
    'Corai': 'Roz', 'Crem': 'Bej', 'Galben': 'Galben', 'Gri': 'Gri', 'Kaki': 'Verde',
    'Lavanda': 'Mov', 'Lila': 'Mov', 'Maro': 'Maro', 'Mov': 'Mov', 'Multicolor': 'Multicolor',
    'Negru': 'Negru', 'Nude': 'Bej', 'Olive': 'Verde', 'Piersica': 'Roz',
    'Portocaliu': 'Portocaliu', 'Pudra': 'Roz', 'Rosu': 'Rosu', 'Roz': 'Roz',
    'Roz prafuit': 'Roz', 'Somon': 'Roz', 'Turcoaz': 'Albastru', 'Verde': 'Verde',
    'Verde inchis': 'Verde', 'Verde lime': 'Verde', 'Verde mint': 'Verde',
    'Vernil': 'Verde', 'Visiniu': 'Rosu', 'floral': 'Multicolor', 'Fucsia': 'Roz',
}

# Material Extended → Material Fashion Days [6372]
MATERIAL_MAP = {
    'Acryl': 'Acril', 'Barbie': 'Sintetic', 'Brocart': 'Sintetic', 'Bumbac': 'Bumbac',
    'Catifea': 'Catifea', 'Casmir': 'Lana', 'Crep': 'Sintetic', 'Dantela': 'Dantela',
    'Jerseu': 'Tricot', 'Lana': 'Lana', 'Lycra': 'Elastan', 'Licra': 'Elastan',
    'Matase': 'Matase', 'Neopren': 'Sintetic', 'Organza': 'Sintetic', 'Paiete': 'Sintetic',
    'Piele ecologica': 'Piele ecologica', 'Poliester': 'Poliester', 'Satin': 'Satin',
    'Sifon': 'Sintetic', 'Stofa': 'Lana', 'Tafta': 'Sintetic', 'Tricot': 'Tricot',
    'Tul': 'Tul', 'Tweed': 'Lana', 'Velur': 'Catifea', 'Voal': 'Sintetic',
}

# Lungime Extended → Lungime Fashion Days [6142]
LUNGIME_MAP = {
    'Lungi': 'Lunga', 'Medii': 'Midi', 'Scurte': 'Scurta',
}

# Croi Extended → Croiala Fashion Days [9097]
CROIALA_MAP = {
    'In clini': 'Evazat', 'Lejer': 'Lejer', 'Mulat': 'Bodycon', 'Peplum': 'Cambrata',
    'Petrecuta': 'Petrecuta', 'Plisat': 'Plisata', 'Pliuri': 'Plisata',
    'Volane': 'Evazat', 'in A': 'Evazat',
}

# Stil Extended → Stil Fashion Days [6140]
STIL_MAP = {
    'Asimetrica': 'Elegant', 'Birou': 'Casual', 'Casual': 'Casual',
    'Casual-Elegant': 'Casual', 'Casual-Office': 'Casual',
    'Cu crapatura': 'Elegant', 'De ocazie': 'De ocazie',
    'De seara': 'Elegant', 'Eleganta': 'Elegant', 'Sport': 'Casual',
}

# Mărimi Extended → Fashion Days format
SIZE_MAP = {
    'S': 'S INTL', 'M': 'M INTL', 'L': 'L INTL', 'XL': 'XL INTL',
    'XXL': '2XL INTL', '2XL': '2XL INTL', 'XXXL': '3XL INTL', '3XL': '3XL INTL',
    'XS': 'XS INTL', '4XL': '4XL INTL', '5XL': '5XL INTL',
    'S/M': 'S INTL', 'M/L': 'M INTL', 'L/XL': 'L INTL',
    'ONE SIZE': 'One Size INTL', 'UNIC': 'One Size INTL',
    '34': '34 EU', '36': '36 EU', '38': '38 EU', '40': '40 EU',
    '42': '42 EU', '44': '44 EU', '46': '46 EU', '48': '48 EU',
}


def load_product_feed():
    with open(FEED_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_barcode_map():
    with open(BARCODE_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def build_product_barcode_map(barcode_map):
    """Build: product_id -> {size_index: barcode}"""
    product_barcodes = {}
    for barcode, pid in barcode_map.items():
        pid = str(pid)
        if pid not in product_barcodes:
            product_barcodes[pid] = []
        product_barcodes[pid].append(barcode)
    return product_barcodes


def get_spec_value(product, spec_name):
    """Get specification value from product feed"""
    specs = product.get('specs', {})
    if isinstance(specs, dict):
        val = specs.get(spec_name, '')
        if isinstance(val, list):
            return val[0] if val else ''
        return val or ''
    return ''


def map_value(value, mapping, default=''):
    """Map Extended value to Fashion Days value"""
    if not value:
        return default
    # Try exact match first
    if value in mapping:
        return mapping[value]
    # Try case-insensitive
    for k, v in mapping.items():
        if k.lower() == value.lower():
            return v
    return default or value


def extract_color_from_name(name):
    """Extract color from product name (fallback)"""
    colors = ['negru', 'neagra', 'alb', 'alba', 'rosu', 'rosie', 'verde', 'albastru',
              'albastra', 'roz', 'mov', 'galben', 'gri', 'maro', 'bej', 'crem',
              'bordo', 'fucsia', 'turcoaz', 'corai', 'nude', 'auriu', 'argintiu',
              'bleumarin', 'lila', 'lavanda', 'kaki', 'portocaliu', 'somon', 'visiniu']
    name_lower = name.lower()
    for color in colors:
        if color in name_lower:
            return color.capitalize()
    return ''


def get_product_images(product):
    """Get image URLs from product"""
    images = product.get('imagini', []) or product.get('images', [])
    main_image = product.get('image', '')

    if isinstance(images, list) and images:
        all_imgs = images
    elif main_image:
        all_imgs = [main_image]
    else:
        all_imgs = []

    # Ensure URLs are absolute
    result = []
    for img in all_imgs:
        if isinstance(img, dict):
            img = img.get('url', img.get('src', ''))
        if img and not img.startswith('http'):
            img = 'https://ejolie.ro' + img
        if img:
            result.append(img)

    return result


def get_sizes_with_stock(product):
    """Get sizes with stock > 0"""
    sizes = []
    optiuni = product.get('optiuni', []) or product.get('options', [])

    if isinstance(optiuni, list):
        for opt in optiuni:
            if isinstance(opt, dict):
                size_name = opt.get('optiune', opt.get('name', ''))
                stock = opt.get('stoc_fizic', opt.get('stock', 0))
                try:
                    stock = int(stock)
                except (ValueError, TypeError):
                    stock = 0
                if stock > 0 and size_name:
                    sizes.append({'name': size_name, 'stock': stock})

    # If no options found, check if product has direct stock
    if not sizes:
        stock = product.get('stoc_fizic', 0)
        try:
            stock = int(stock)
        except (ValueError, TypeError):
            stock = 0
        if stock > 0:
            sizes.append({'name': 'One Size', 'stock': stock})

    return sizes


def calculate_price_without_vat(price_with_vat, vat_rate=19):
    """Calculate price without VAT"""
    try:
        price = float(price_with_vat)
        return round(price / (1 + vat_rate / 100), 2)
    except (ValueError, TypeError):
        return 0


def generate_rows(products, barcode_map, brand_filter='ejolie,artista', limit=None):
    """Generate Fashion Days template rows"""
    product_barcodes = build_product_barcode_map(barcode_map)
    rows = []
    products_processed = 0
    products_skipped_no_barcode = 0
    products_skipped_no_stock = 0

    # Support multiple brands separated by comma
    allowed_brands = [b.strip().lower()
                      for b in brand_filter.split(',')] if brand_filter else []

    for product in products:
        # Filter by brand
        prod_brand = (product.get('brand', '') or '').strip().lower()
        if allowed_brands and prod_brand not in allowed_brands:
            continue

        pid = str(product.get('id', ''))
        name = product.get('name', product.get('title', ''))

        if not pid or not name:
            continue

        # Get sizes with stock
        sizes = get_sizes_with_stock(product)
        if not sizes:
            products_skipped_no_stock += 1
            continue

        # Get barcodes for this product
        barcodes = product_barcodes.get(pid, [])
        if not barcodes:
            products_skipped_no_barcode += 1
            continue

        # Get product data
        code = product.get('cod', product.get('code', f'FBR-{pid}'))
        description = product.get('description', product.get('descriere', ''))
        url = product.get('url', product.get('link', ''))
        images = get_product_images(product)

        # Price (Extended prices include VAT, Fashion Days wants WITHOUT VAT)
        price_with_vat = product.get('price_discount', product.get('pret_discount', 0)) or \
            product.get('price', product.get('pret', 0))
        price_no_vat = calculate_price_without_vat(price_with_vat)

        if price_no_vat <= 0:
            continue

        # Min/max price (±20% of sale price)
        min_price = round(price_no_vat * 0.5, 2)
        max_price = round(price_no_vat * 2.0, 2)

        # Specifications
        culoare = get_spec_value(
            product, 'culoare') or extract_color_from_name(name)
        material = get_spec_value(product, 'material')
        lungime = get_spec_value(product, 'lungime')
        croi = get_spec_value(product, 'croi')
        stil = get_spec_value(product, 'stil')

        # Map to Fashion Days values
        fd_culoare = map_value(culoare, COLOR_MAP, 'Negru')
        fd_base_color = map_value(culoare, BASE_COLOR_MAP, 'Negru')
        fd_material = map_value(material, MATERIAL_MAP, 'Poliester')
        fd_lungime = map_value(lungime, LUNGIME_MAP, '')
        fd_croiala = map_value(croi, CROIALA_MAP, '')
        fd_stil = map_value(stil, STIL_MAP, 'Elegant')

        # Generate one row per size
        for size_idx, size_info in enumerate(sizes):
            size_name = size_info['name']
            stock = size_info['stock']

            # Get EAN for this size
            ean = barcodes[size_idx] if size_idx < len(
                barcodes) else barcodes[-1]

            # Map size to Fashion Days format
            fd_size = SIZE_MAP.get(size_name.upper(), size_name + ' INTL')

            row = {
                'part_number': code,
                'vendor_ext_id': int(pid),
                'ean': ean,
                'sale_price': price_no_vat,
                'original_sale_price': '',
                'vat_rate': 19,
                'status': 1,
                'offer_currency': 'RON',
                'stock': stock,
                'handling_time': 1,
                'lead_time': 14,
                'warranty': 0,
                'offer_properties': '',
                'min_sale_price': min_price,
                'max_sale_price': max_price,
                'name': name[:255],
                'brand': product.get('brand', 'Ejolie'),
                'description': description,
                'url': url,
                'source_language': 'ro_RO',
                'main_image_url': images[0] if images else '',
                'other_image_url1': images[1] if len(images) > 1 else '',
                'other_image_url2': images[2] if len(images) > 2 else '',
                'other_image_url3': images[3] if len(images) > 3 else '',
                'other_image_url4': images[4] if len(images) > 4 else '',
                'other_image_url5': images[5] if len(images) > 5 else '',
                'family_id': int(pid),
                'family_name': name[:100],
                'family_type': 'Marime',
                'size_original': fd_size,
                'size_converted': fd_size,
                'culoare': fd_culoare,
                'material': fd_material,
                'colectie': '2026',
                'stil': fd_stil,
                'lungime': fd_lungime,
                'lungime_maneca': '',
                'imprimeu': 'Uni',
                'detalii': '',
                'sistem_inchidere': '',
                'culoare_baza': fd_base_color,
                'captuseala': '',
                'decolteu': '',
                'buzunare': '',
                'exterior': '',
                'barete': '',
                'material_garnituri': '',
                'talie': '',
                'pentru': 'Femei',
                'croiala': fd_croiala,
                'linie_brand': 'Ejolie',
                'marime_convertita': fd_size,
                'fit': '',
                'safety_info': '',
                'manufacturer_name': 'SMARTEX FASHION S.R.L.',
                'manufacturer_address': 'Aninoasa, str. Valea Mare nr. 1, jud. Dambovita, Romania',
                'manufacturer_email': 'contact@ejolie.ro',
                'responsible_name': '',
                'responsible_address': '',
                'responsible_email': '',
            }
            rows.append(row)

        products_processed += 1
        if limit and products_processed >= limit:
            break

    print(f"\nResults:")
    print(f"  Products processed: {products_processed}")
    print(f"  Rows generated: {len(rows)} (one per size)")
    print(f"  Skipped (no barcode): {products_skipped_no_barcode}")
    print(f"  Skipped (no stock): {products_skipped_no_stock}")

    return rows


def write_to_template(rows, template_path, output_path):
    """Write rows to Fashion Days template Excel file"""
    wb = load_workbook(template_path)
    ws = wb['Template']

    # Data starts at row 6 (rows 1-5 are headers)
    start_row = 6

    # Column mapping (0-indexed in our dict, 1-indexed in Excel)
    col_map = {
        'part_number': 1, 'vendor_ext_id': 2, 'ean': 3,
        'sale_price': 4, 'original_sale_price': 5, 'vat_rate': 6,
        'status': 7, 'offer_currency': 8, 'stock': 9,
        'handling_time': 10, 'lead_time': 11, 'warranty': 12,
        'offer_properties': 13, 'min_sale_price': 14, 'max_sale_price': 15,
        'name': 16, 'brand': 17, 'description': 18, 'url': 19,
        'source_language': 20, 'main_image_url': 21,
        'other_image_url1': 22, 'other_image_url2': 23,
        'other_image_url3': 24, 'other_image_url4': 25, 'other_image_url5': 26,
        'family_id': 27, 'family_name': 28, 'family_type': 29,
        'size_original': 30, 'size_converted': 31,
        'culoare': 32, 'material': 33, 'colectie': 34,
        'stil': 35, 'lungime': 36, 'lungime_maneca': 37,
        'imprimeu': 38, 'detalii': 39, 'sistem_inchidere': 40,
        'culoare_baza': 41, 'captuseala': 42, 'decolteu': 43,
        'buzunare': 44, 'exterior': 45, 'barete': 46,
        'material_garnituri': 47, 'talie': 48, 'pentru': 49,
        'croiala': 50, 'linie_brand': 51, 'marime_convertita': 52, 'fit': 53,
        'safety_info': 54, 'manufacturer_name': 55,
        'manufacturer_address': 56, 'manufacturer_email': 57,
        'responsible_name': 58, 'responsible_address': 59,
        'responsible_email': 60,
    }

    for row_idx, row_data in enumerate(rows):
        excel_row = start_row + row_idx
        for key, col in col_map.items():
            value = row_data.get(key, '')
            ws.cell(row=excel_row, column=col, value=value)

    wb.save(output_path)
    print(f"\nSaved: {output_path}")
    print(f"  Rows written: {len(rows)}")
    print(f"  Sheet: Template (starting row {start_row})")


def write_simple_xlsx(rows, output_path):
    """Write rows to a simple Excel file (no template needed)"""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = 'Template'

    # Headers (matching Fashion Days template exactly)
    headers_row1 = [
        'Identificare produs', '', '', 'Oferta - Pret', '', '', '', 'Moneda',
        'Oferta - Stoc & disponibilitate', '', '', '', 'Detalii oferta',
        'Oferta - Verificare pret', '', 'Descriere produs', '', '', '', '',
        'Imagini', '', '', '', '', '', 'Variation (product families)', '', '',
        'Caracteristici - Rochii'
    ]

    headers_technical = [
        'part_number', 'vendor_ext_id', 'ean', 'sale_price', 'original_sale_price',
        'vat_rate', 'status', 'offer_currency', 'stock', 'handling_time', 'lead_time',
        'warranty', 'offer_properties', 'min_sale_price', 'max_sale_price',
        'name', 'brand', 'description', 'url', 'source_language',
        'main_image_url', 'other_image_url1', 'other_image_url2',
        'other_image_url3', 'other_image_url4', 'other_image_url5',
        'family_id', 'family_name', 'family_type',
        'Marime [original]: [6506]', 'Marime [converted]: [6506]',
        'Culoare: [5401]', 'Material: [6372]', 'Colectie: [5429]',
        'Stil: [6140]', 'Lungime: [6142]', 'Lungime maneca: [6146]',
        'Imprimeu: [6155]', 'Detalii: [6469]', 'Sistem inchidere: [6765]',
        'Culoare de baza: [8956]', 'Captuseala: [9011]', 'Decolteu: [9012]',
        'Buzunare: [9015]', 'Exterior: [9018]', 'Barete: [9023]',
        'Material garnituri: [9025]', 'Talie: [9028]', 'Pentru: [9084]',
        'Croiala: [9097]', 'Linie Brand: [9370]',
        'Marime convertita: [10770]', 'Fit: [10965]',
        'safety_information', 'manufacturer_name', 'manufacturer_address',
        'manufacturer_email', 'responsible_name', 'responsible_address',
        'responsible_email',
    ]

    # Write header rows
    ws.append(headers_technical)

    # Column order for data
    col_keys = [
        'part_number', 'vendor_ext_id', 'ean', 'sale_price', 'original_sale_price',
        'vat_rate', 'status', 'offer_currency', 'stock', 'handling_time', 'lead_time',
        'warranty', 'offer_properties', 'min_sale_price', 'max_sale_price',
        'name', 'brand', 'description', 'url', 'source_language',
        'main_image_url', 'other_image_url1', 'other_image_url2',
        'other_image_url3', 'other_image_url4', 'other_image_url5',
        'family_id', 'family_name', 'family_type',
        'size_original', 'size_converted',
        'culoare', 'material', 'colectie', 'stil', 'lungime', 'lungime_maneca',
        'imprimeu', 'detalii', 'sistem_inchidere', 'culoare_baza',
        'captuseala', 'decolteu', 'buzunare', 'exterior', 'barete',
        'material_garnituri', 'talie', 'pentru', 'croiala', 'linie_brand',
        'marime_convertita', 'fit',
        'safety_info', 'manufacturer_name', 'manufacturer_address',
        'manufacturer_email', 'responsible_name', 'responsible_address',
        'responsible_email',
    ]

    for row_data in rows:
        row_values = [row_data.get(key, '') for key in col_keys]
        ws.append(row_values)

    wb.save(output_path)
    print(f"\nSaved: {output_path}")
    print(f"  Rows written: {len(rows)} + 1 header")


def main():
    parser = argparse.ArgumentParser(
        description='Export produse Ejolie pentru Fashion Days')
    parser.add_argument('--brand', default='ejolie,artista',
                        help='Brand filter, comma-separated (default: ejolie,artista)')
    parser.add_argument('--limit', type=int, default=None,
                        help='Limit number of products')
    parser.add_argument('--dry-run', action='store_true',
                        help='Only show stats, do not write file')
    parser.add_argument('--output', default=OUTPUT_PATH,
                        help='Output file path')
    args = parser.parse_args()

    print("=" * 60)
    print("Fashion Days Export - Produse Ejolie")
    print("=" * 60)

    # Load data
    print(f"\nLoading product feed from: {FEED_PATH}")
    products = load_product_feed()
    print(f"  Loaded {len(products)} products")

    print(f"\nLoading barcode map from: {BARCODE_PATH}")
    barcode_map = load_barcode_map()
    print(f"  Loaded {len(barcode_map)} barcodes")

    # Generate rows
    rows = generate_rows(products, barcode_map,
                         brand_filter=args.brand, limit=args.limit)

    if args.dry_run:
        print("\n[DRY RUN] No file written.")
        if rows:
            print("\nSample row (first):")
            for k, v in list(rows[0].items())[:15]:
                print(f"  {k}: {v}")
        return

    # Write output
    write_simple_xlsx(rows, args.output)
    print("\nDone!")


if __name__ == '__main__':
    main()
