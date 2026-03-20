#!/usr/bin/env python3
"""
export_shopify_ejolie.py
Combină stock_cache.json (mărimi/prețuri) + product_feed.json (imagini/descrieri)
→ CSV Shopify

Utilizare:
  python3 export_shopify_ejolie.py
  python3 export_shopify_ejolie.py --dry-run
"""

import csv
import json
import re
import os
import argparse

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
    for s, r in [('ă', 'a'), ('â', 'a'), ('î', 'i'), ('ș', 's'), ('ş', 's'), ('ț', 't'), ('ţ', 't'), ('é', 'e')]:
        text = text.replace(s, r)
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text.strip())
    return re.sub(r'-+', '-', text)[:80]


def extract_color(name):
    COLORS = ['alb', 'alba', 'negru', 'neagra', 'rosu', 'rosie', 'roz', 'fucsia',
              'albastru', 'albastra', 'verde', 'mov', 'lila', 'galben', 'bej', 'crem',
              'nude', 'pudra', 'auriu', 'aurie', 'argintiu', 'bordo', 'visiniu',
              'turcoaz', 'gri', 'maro', 'portocaliu', 'coral', 'corai', 'somon',
              'multicolor', 'kaki', 'bleumarin', 'ivory', 'grena', 'caramel']
    for w in reversed(name.lower().split()):
        if re.sub(r'[^a-z]', '', w) in COLORS:
            return w.capitalize()
    return ''


def clean_price(val):
    """'1189.00 RON' sau '1189.00' → 1189.0"""
    if not val:
        return 0.0
    try:
        return float(str(val).replace(' RON', '').replace(',', '.').strip())
    except:
        return 0.0


def clean_html(text):
    """Elimină tag-uri HTML din descriere."""
    if not text:
        return ''
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def get_price(product):
    """Preia prețul din primul size disponibil din stock_cache."""
    for size_data in product.get('sizes', {}).values():
        p = clean_price(size_data.get('pret', 0))
        pd = clean_price(size_data.get('pret_discount', 0))
        if p > 0:
            if pd > 0 and pd < p:
                return pd, p
            return p, 0.0
    return 0.0, 0.0


def build_row(product, feed, marime, is_first, img_url, img_pos):
    row = {col: '' for col in SHOPIFY_COLUMNS}

    prod_id = str(product.get('id', ''))
    title = product.get('nume', '')
    brand = product.get('brand', 'Ejolie').strip()
    cod = product.get('cod', f'FBR-E{prod_id}')
    price, compare = get_price(product)
    sku = f"{cod}-{marime.replace(' ', '')}"

    # Descriere din product_feed (curățată de HTML)
    description = clean_html(
        feed.get('description', feed.get('descriere', '')))

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
        row['Description'] = description
        row['Vendor'] = brand
        row['Product category'] = 'Apparel & Accessories > Clothing > Dresses'
        row['Type'] = 'Rochie'
        row['Tags'] = f"{brand}, rochie, ocazie"
        row['Published on online store'] = 'TRUE'
        row['Status'] = 'Active'
        row['SEO title'] = f"{title} | Ejolie"[:70]
        row['SEO description'] = f"Cumpara {title} online la ejolie.ro. Livrare rapida in Romania."[
            :160]
        row['Color (product.metafields.shopify.color-pattern)'] = extract_color(title)
        row['Google Shopping / Manufacturer part number (MPN)'] = cod

    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true',
                        help='Test 5 produse')
    parser.add_argument('--output', default=OUTPUT_FILE)
    args = parser.parse_args()

    print("=" * 50)
    print("Shopify Export - ejolie.ro")
    print(f"Mode: {'DRY-RUN' if args.dry_run else 'PRODUCTIE'}")
    print("=" * 50)

    # 1. Încarcă stock_cache.json
    print("\n Citesc stock_cache.json...")
    with open('scripts/stock_cache.json', encoding='utf-8') as f:
        cache_data = json.load(f)
    stock_products = cache_data.get('products', {})
    print(f"   {len(stock_products)} produse în cache")

    # 2. Încarcă product_feed.json
    print(" Citesc product_feed.json...")
    with open('scripts/product_feed.json', encoding='utf-8') as f:
        feed_list = json.load(f)

    # Construiește dict feed: id → product
    feed_by_id = {}
    for item in feed_list:
        pid = str(item.get('id', ''))
        if pid:
            feed_by_id[pid] = item
    print(f"   {len(feed_by_id)} produse în feed")

    # 3. Filtrează după brand
    brands_lower = [b.lower() for b in BRANDS_EXPORT]
    products = [p for p in stock_products.values()
                if isinstance(p, dict) and p.get('brand', '').lower() in brands_lower]
    print(f"   Filtrate ({'/'.join(BRANDS_EXPORT)}): {len(products)} produse")

    if args.dry_run:
        products = products[:5]
        print(f"   [DRY-RUN] Procesez 5 produse")

    # 4. Export CSV
    total_p = total_r = no_img = 0

    with open(args.output, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=SHOPIFY_COLUMNS)
        writer.writeheader()

        for product in products:
            prod_id = str(product.get('id', ''))
            title = product.get('nume', '')
            sizes = product.get('sizes', {})

            if not title or not sizes:
                continue

            # Date din product_feed
            feed = feed_by_id.get(prod_id, {})

            # Imaginile din product_feed
            all_imgs = []
            main_img = feed.get('image', '')
            if main_img:
                all_imgs.append(main_img)

            extra = feed.get('images', [])
            if isinstance(extra, list):
                for img in extra:
                    if isinstance(img, str) and img and img not in all_imgs:
                        all_imgs.append(img)

            if not all_imgs:
                no_img += 1

            # Sortează mărimi
            def sz_key(s):
                try:
                    return int(s)
                except:
                    return 999
            sorted_sizes = sorted(sizes.keys(), key=sz_key)

            for idx, marime in enumerate(sorted_sizes):
                is_first = (idx == 0)
                img_url = all_imgs[idx] if idx < len(all_imgs) else ''
                img_pos = idx + 1 if img_url else ''

                row = build_row(product, feed, marime,
                                is_first, img_url, img_pos)
                writer.writerow(row)
                total_r += 1

            total_p += 1
            if total_p % 50 == 0:
                print(f"   ... {total_p} produse")

    print(f"\n GATA!")
    print(
        f"   Produse: {total_p} | Randuri: {total_r} | Fara imagine: {no_img}")
    print(f"   Fisier:  {args.output}")

    # Sumar branduri
    from collections import Counter
    brand_counts = Counter(p.get('brand', '?') for p in products)
    print(f"\n Pe branduri:")
    for b, c in brand_counts.items():
        print(f"   {b}: {c} produse")


if __name__ == "__main__":
    main()
