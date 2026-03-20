#!/usr/bin/env python3
"""
export_shopify_ejolie.py - Export produse ejolie.ro → Shopify CSV
Utilizare:
  python3 export_shopify_ejolie.py --cache stock_cache.json
  python3 export_shopify_ejolie.py --cache stock_cache.json --dry-run
"""

import requests
import csv
import json
import time
import re
import os
import argparse

API_KEY = os.environ.get("EJOLIE_API_KEY", "C4V9RJKpPOEcXyWDhF7tQYqrNAxeg8")
API_BASE = "https://ejolie.ro/api/"
HEADERS = {"User-Agent": "Extended API"}
BRANDS_EXPORT = ["ejolie", "artista"]
OUTPUT_FILE = "ejolie_shopify_import.csv"

SHOPIFY_COLUMNS = [
    "Title", "URL handle", "Description", "Vendor", "Product category", "Type",
    "Tags", "Published on online store", "Status", "SKU", "Barcode",
    "Option1 name", "Option1 value", "Option1 Linked To",
    "Option2 name", "Option2 value", "Option2 Linked To",
    "Option3 name", "Option3 value", "Option3 Linked To",
    "Price", "Compare-at price", "Cost per item", "Charge tax", "Tax code",
    "Unit price total measure", "Unit price total measure unit",
    "Unit price base measure", "Unit price base measure unit",
    "Inventory tracker", "Inventory quantity", "Continue selling when out of stock",
    "Weight value (grams)", "Weight unit for display", "Requires shipping", "Fulfillment service",
    "Product image URL", "Image position", "Image alt text", "Variant image URL", "Gift card",
    "SEO title", "SEO description",
    "Color (product.metafields.shopify.color-pattern)",
    "Google Shopping / Google product category", "Google Shopping / Gender",
    "Google Shopping / Age group", "Google Shopping / Manufacturer part number (MPN)",
    "Google Shopping / Ad group name", "Google Shopping / Ads labels",
    "Google Shopping / Condition", "Google Shopping / Custom product",
    "Google Shopping / Custom label 0", "Google Shopping / Custom label 1",
    "Google Shopping / Custom label 2", "Google Shopping / Custom label 3",
    "Google Shopping / Custom label 4",
]


def slugify(text):
    text = text.lower()
    for s, r in [('ă', 'a'), ('â', 'a'), ('î', 'i'), ('ș', 's'), ('ş', 's'), ('ț', 't'), ('ţ', 't')]:
        text = text.replace(s, r)
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text.strip())
    return re.sub(r'-+', '-', text)[:80]


def extract_color(name):
    COLORS = ['alb', 'alba', 'negru', 'neagra', 'rosu', 'rosie', 'roz', 'fucsia',
              'albastru', 'albastra', 'verde', 'mov', 'lila', 'galben', 'bej', 'crem',
              'nude', 'pudra', 'auriu', 'aurie', 'argintiu', 'bordo', 'visiniu',
              'turcoaz', 'gri', 'maro', 'portocaliu', 'coral', 'corai', 'somon',
              'multicolor', 'kaki', 'bleumarin', 'navy', 'ivory']
    for w in reversed(name.lower().split()):
        if re.sub(r'[^a-z]', '', w) in COLORS:
            return w.capitalize()
    return ''


def get_price(product):
    """Preia prețul din primul size disponibil."""
    for size_data in product.get('sizes', {}).values():
        p = float(size_data.get('pret', 0) or 0)
        pd = float(size_data.get('pret_discount', 0) or 0)
        if p > 0:
            if pd > 0 and pd < p:
                return pd, p   # redus, original
            return p, 0.0
    return 0.0, 0.0


def get_image(product):
    img = product.get('imagine') or product.get(
        'image') or product.get('img') or ''
    if img and img.startswith('/'):
        img = 'https://ejolie.ro' + img
    return img


def get_extra_images(product):
    result = []
    for item in product.get('imagini', product.get('images', [])):
        url = item.get('url', item.get('src', '')) if isinstance(
            item, dict) else str(item)
        if url:
            if url.startswith('/'):
                url = 'https://ejolie.ro' + url
            result.append(url)
    return result


def build_tags(product):
    tags = set()
    for field in ['culoare', 'material', 'lungime', 'croi', 'stil', 'model']:
        v = product.get(field, '')
        if v:
            tags.add(v)
    for spec in product.get('specificatii', []):
        if isinstance(spec, dict):
            for v in spec.get('valoare', []):
                if v:
                    tags.add(v)
    cat = product.get('categorie', product.get('category', ''))
    if cat:
        tags.add(cat if isinstance(cat, str) else ', '.join(cat))
    brand = product.get('brand', '')
    if brand:
        tags.add(brand)
    return ', '.join(sorted(tags)) if tags else 'rochie, ejolie'


def build_row(product, marime, is_first, img_url, img_pos):
    row = {col: '' for col in SHOPIFY_COLUMNS}
    prod_id = product.get('id', '')
    title = product.get('nume', product.get('name', ''))
    brand = product.get('brand', 'Ejolie').strip()
    cod = product.get('cod', f'FBR-E{prod_id}')
    price, compare = get_price(product)
    sku = f"{cod}-{marime.replace(' ', '')}"

    row['URL handle'] = slugify(title)
    row['SKU'] = sku
    row['Option1 name'] = 'Size'
    row['Option1 value'] = marime
    row['Price'] = f"{price:.2f}"
    row['Compare-at price'] = f"{compare:.2f}" if compare else ''
    row['Charge tax'] = 'TRUE'
    row['Inventory tracker'] = 'shopify'
    row['Inventory quantity'] = '0'
    row['Continue selling when out of stock'] = 'TRUE'
    row['Weight value (grams)'] = '500'
    row['Weight unit for display'] = 'g'
    row['Requires shipping'] = 'TRUE'
    row['Fulfillment service'] = 'manual'
    row['Gift card'] = 'FALSE'
    row['Google Shopping / Condition'] = 'New'
    row['Google Shopping / Age group'] = 'Adult (13+ years old)'
    row['Google Shopping / Gender'] = 'Female'
    row['Google Shopping / Google product category'] = 'Apparel & Accessories > Clothing > Dresses'

    if img_url:
        row['Product image URL'] = img_url
        row['Image position'] = str(img_pos)
        row['Image alt text'] = title if is_first else f"{title} {img_pos}"

    if is_first:
        row['Title'] = title
        row['Description'] = product.get(
            'descriere', product.get('description', ''))
        row['Vendor'] = brand
        row['Product category'] = 'Apparel & Accessories > Clothing > Dresses'
        row['Type'] = 'Rochie'
        row['Tags'] = build_tags(product)
        row['Published on online store'] = 'TRUE'
        row['Status'] = 'Active'
        row['SEO title'] = f"{title} | Ejolie"[:70]
        row['SEO description'] = f"Cumpără {title} online la ejolie.ro. Livrare rapidă în România."[
            :160]
        row['Color (product.metafields.shopify.color-pattern)'] = extract_color(title)
        row['Google Shopping / Manufacturer part number (MPN)'] = cod
    return row


def load_cache(cache_file, brands):
    print(f"\n📂 Citesc cache: {cache_file}")
    with open(cache_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    products_dict = data.get('products', data)
    brands_lower = [b.lower() for b in brands]
    result = [p for p in products_dict.values()
              if isinstance(p, dict) and p.get('brand', '').lower() in brands_lower]
    print(
        f"   Total în cache: {data.get('total_products', '?')} | Filtrate: {len(result)}")
    return result


def load_api(brands, dry_run=False):
    all_products = []
    for brand in brands:
        print(f"\n📦 Preiau brand={brand} din API...")
        for page in range(1, 50):
            url = f"{API_BASE}?produse&brand={brand}&limit=50&pagina={page}&apikey={API_KEY}"
            try:
                r = requests.get(url, headers=HEADERS, timeout=60)
                data = r.json() if r.text.strip() else {}
                if isinstance(data, dict):
                    prods = [p for p in data.values() if isinstance(p, dict)]
                elif isinstance(data, list):
                    prods = data
                else:
                    break
                if not prods:
                    break
                prods_b = [p for p in prods if p.get(
                    'brand', '').lower() == brand.lower()]
                all_products.extend(prods_b)
                print(f"   Pagina {page}: {len(prods_b)} produse")
                if len(prods) < 50:
                    break
                time.sleep(0.3)
                if dry_run and len(all_products) >= 5:
                    break
            except Exception as e:
                print(f"   ❌ {e}")
                break
    return all_products[:5] if dry_run else all_products


def export_csv(products, output_file, dry_run=False):
    if dry_run:
        products = products[:5]
    total_p = total_r = skipped = 0

    with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=SHOPIFY_COLUMNS)
        writer.writeheader()

        for product in products:
            title = product.get('nume', product.get('name', ''))
            sizes = product.get('sizes', {})
            if not title or not sizes:
                skipped += 1
                continue

            # Imaginile
            main_img = get_image(product)
            extra = get_extra_images(product)
            all_imgs = ([main_img] if main_img else []) + \
                [i for i in extra if i != main_img]

            # Sortează mărimi numeric
            def sz_key(s):
                try:
                    return int(s)
                except:
                    return 999
            sorted_sizes = sorted(sizes.keys(), key=sz_key)

            for idx, marime in enumerate(sorted_sizes):
                is_first = (idx == 0)
                img_url = all_imgs[idx] if idx < len(all_imgs) else ''
                img_pos = idx + 1
                row = build_row(product, marime, is_first, img_url, img_pos)
                writer.writerow(row)
                total_r += 1

            total_p += 1
            if total_p % 50 == 0:
                print(f"   ... {total_p} produse")

    print(f"\n✅ GATA!")
    print(f"   Produse: {total_p} | Rânduri: {total_r} | Skipped: {skipped}")
    print(f"   Fișier:  {output_file}")
    return total_p, total_r


def main():
    parser = argparse.ArgumentParser(
        description='Export ejolie.ro → Shopify CSV')
    parser.add_argument('--cache', help='stock_cache.json local')
    parser.add_argument('--dry-run', action='store_true',
                        help='Test 5 produse')
    parser.add_argument('--output', default=OUTPUT_FILE)
    parser.add_argument('--brands', nargs='+', default=BRANDS_EXPORT)
    args = parser.parse_args()

    print("=" * 50)
    print("🛍️  Export Shopify - ejolie.ro")
    print(
        f"Branduri: {args.brands} | {'DRY-RUN' if args.dry_run else 'PRODUCTIE'}")
    print("=" * 50)

    products = load_cache(args.cache, args.brands) if args.cache else load_api(
        args.brands, args.dry_run)

    if not products:
        print("❌ Nu s-au găsit produse!")
        return

    export_csv(products, args.output, dry_run=args.dry_run)

    # Sumar branduri
    brand_counts = {}
    for p in products:
        b = p.get('brand', 'Unknown')
        brand_counts[b] = brand_counts.get(b, 0) + 1
    print(f"\n📊 Pe branduri:")
    for b, c in sorted(brand_counts.items()):
        print(f"   {b}: {c} produse")
    print(
        f"\n🚀 Import în Shopify: Admin → Produse → Import → selectează {args.output}")


if __name__ == "__main__":
    main()
