#!/usr/bin/env python3
"""
export_shopify_ejolie.py
Exportă produsele Ejolie + Artista din Extended API în format Shopify CSV.

Utilizare:
  python3 export_shopify_ejolie.py
  python3 export_shopify_ejolie.py --cache stock_cache.json   (dacă ai cache local)
  python3 export_shopify_ejolie.py --dry-run                  (test, primele 5 produse)

Fișier output: ejolie_shopify_import.csv
"""

import requests
import csv
import json
import time
import re
import os
import argparse
from pathlib import Path

# ─────────────────────────────────────────────
# CONFIGURARE
# ─────────────────────────────────────────────

# Înlocuiește cu cheia ta reală sau citește din .env
API_KEY = os.environ.get("EJOLIE_API_KEY", "C4V9RJKpPOEcXyWDhF7tQYqrNAxeg8")
API_BASE = "https://ejolie.ro/api/"
HEADERS = {"User-Agent": "Extended API"}

BRANDS_EXPORT = ["ejolie", "artista"]   # brandurile dorite

OUTPUT_FILE = "ejolie_shopify_import.csv"

# Shopify CSV - coloanele exacte din template
SHOPIFY_COLUMNS = [
    "Title", "URL handle", "Description", "Vendor", "Product category", "Type",
    "Tags", "Published on online store", "Status",
    "SKU", "Barcode",
    "Option1 name", "Option1 value", "Option1 Linked To",
    "Option2 name", "Option2 value", "Option2 Linked To",
    "Option3 name", "Option3 value", "Option3 Linked To",
    "Price", "Compare-at price", "Cost per item",
    "Charge tax", "Tax code",
    "Unit price total measure", "Unit price total measure unit",
    "Unit price base measure", "Unit price base measure unit",
    "Inventory tracker", "Inventory quantity", "Continue selling when out of stock",
    "Weight value (grams)", "Weight unit for display",
    "Requires shipping", "Fulfillment service",
    "Product image URL", "Image position", "Image alt text",
    "Variant image URL",
    "Gift card",
    "SEO title", "SEO description",
    "Color (product.metafields.shopify.color-pattern)",
    "Google Shopping / Google product category",
    "Google Shopping / Gender",
    "Google Shopping / Age group",
    "Google Shopping / Manufacturer part number (MPN)",
    "Google Shopping / Ad group name",
    "Google Shopping / Ads labels",
    "Google Shopping / Condition",
    "Google Shopping / Custom product",
    "Google Shopping / Custom label 0",
    "Google Shopping / Custom label 1",
    "Google Shopping / Custom label 2",
    "Google Shopping / Custom label 3",
    "Google Shopping / Custom label 4",
]


# ─────────────────────────────────────────────
# FUNCTII AJUTATOARE
# ─────────────────────────────────────────────

def slugify(text):
    """Transformă textul în URL handle Shopify: 'Rochie Claire Mov' → 'rochie-claire-mov'"""
    text = text.lower()
    text = re.sub(r'[ăâ]', 'a', text)
    text = re.sub(r'[îï]', 'i', text)
    text = re.sub(r'[șş]', 's', text)
    text = re.sub(r'[țţ]', 't', text)
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text.strip())
    text = re.sub(r'-+', '-', text)
    return text


def fetch_products_from_api(brand, dry_run=False):
    """Preia produsele unui brand din Extended API, paginate."""
    products = []
    page = 1
    limit = 50

    print(f"\n📦 Preiau produse brand={brand} din Extended API...")

    while True:
        url = f"{API_BASE}?produse&brand={brand}&limit={limit}&pagina={page}&apikey={API_KEY}"
        try:
            r = requests.get(url, headers=HEADERS, timeout=60)
            if r.status_code != 200 or not r.text.strip():
                print(
                    f"   ⚠️  Pagina {page} goală sau eroare {r.status_code}. Opresc.")
                break

            data = r.json()
            if not data or not isinstance(data, list):
                print(f"   ✅ Pagina {page}: fără produse. Gata.")
                break

            products.extend(data)
            print(
                f"   Pagina {page}: {len(data)} produse (total: {len(products)})")

            if len(data) < limit:
                break
            page += 1
            time.sleep(0.3)  # politicos cu API-ul

            if dry_run and len(products) >= 5:
                print("   [DRY-RUN] Opresc la 5 produse.")
                products = products[:5]
                break

        except Exception as e:
            print(f"   ❌ Eroare la pagina {page}: {e}")
            break

    return products


def fetch_products_from_cache(cache_file, brands):
    """Alternativă: citește din stock_cache.json local."""
    print(f"\n📂 Citesc din cache: {cache_file}")
    with open(cache_file, 'r', encoding='utf-8') as f:
        cache = json.load(f)

    # cache poate fi listă sau dict
    if isinstance(cache, dict):
        all_products = list(cache.values())
    else:
        all_products = cache

    filtered = [p for p in all_products if p.get(
        'brand', '').lower() in brands]
    print(f"   {len(filtered)} produse găsite pentru brandurile: {brands}")
    return filtered


def extract_color(product_name):
    """Extrage culoarea din numele produsului (ultimul cuvânt dacă e culoare)."""
    COLORS = [
        'alb', 'alba', 'albe', 'negru', 'neagra', 'negre', 'rosu', 'rosie', 'rosii',
        'roz', 'albastru', 'albastra', 'verde', 'mov', 'lila', 'galben', 'galbena',
        'bej', 'crem', 'nude', 'auriu', 'aurie', 'argintiu', 'argintie',
        'bordo', 'fucsia', 'turcoaz', 'gri', 'maro', 'ciocolatiu', 'kaki',
        'portocaliu', 'bleumarin', 'navy', 'somon', 'pudra', 'multicolor',
        'visiniu', 'caramel', 'corai', 'ivory', 'bleu', 'grena',
        'catifea', 'paiete',  # uneori material/stil e ultimul cuvânt
    ]
    words = product_name.lower().split()
    for w in reversed(words):
        if w in COLORS:
            return w.capitalize()
    return ''


def build_tags(product):
    """Construiește taguri Shopify din specificații Extended."""
    tags = []

    specs = product.get('specificatii', [])
    if isinstance(specs, list):
        for spec in specs:
            for val in spec.get('valoare', []):
                if val:
                    tags.append(val)
    elif isinstance(specs, dict):
        for key, vals in specs.items():
            if isinstance(vals, list):
                tags.extend(vals)
            elif vals:
                tags.append(str(vals))

    # Adaugă categoria
    cat = product.get('categorie', '') or product.get('category', '')
    if cat:
        tags.append(cat)

    return ', '.join(set(tags)) if tags else 'rochie, ocazie, ejolie'


def get_price(product):
    """Returnează prețul de vânzare și prețul comparat."""
    price = product.get('pret_discount') or product.get('pret', 0)
    price_compare = product.get('pret', 0)

    try:
        price = float(str(price).replace(',', '.'))
        price_compare = float(str(price_compare).replace(',', '.'))
    except:
        price = 0.0
        price_compare = 0.0

    if price == price_compare or price == 0:
        return price_compare, ''  # fără "compare at" dacă nu e reducere
    return price, price_compare


def get_sizes(product):
    """
    Extrage mărimile cu stoc.
    Returnează lista de tuple: [(marime, cantitate), ...]
    """
    sizes = []

    # Încearcă 'marimi' (format cache)
    marimi = product.get('marimi', [])
    if isinstance(marimi, list):
        for m in marimi:
            if isinstance(m, dict):
                marime = m.get('marime', m.get('optiune', ''))
                qty = m.get('stoc_fizic', m.get('stoc', 0))
                if marime:
                    sizes.append((str(marime), int(qty) if qty else 0))
            elif isinstance(m, str):
                sizes.append((m, 0))

    # Încearcă 'optiuni' (alt format Extended)
    if not sizes:
        optiuni = product.get('optiuni', [])
        if isinstance(optiuni, list):
            for o in optiuni:
                if isinstance(o, dict):
                    marime = o.get('optiune1', o.get('marime', ''))
                    qty = o.get('stoc_fizic', o.get('cantitate', 0))
                    if marime:
                        sizes.append((str(marime), int(qty) if qty else 0))

    # Fallback: un singur rând fără mărime
    if not sizes:
        sizes = [('One Size', 1)]

    return sizes


def build_shopify_row(product, marime, is_first_row, image_index, images_list):
    """
    Construiește un dict cu toate coloanele Shopify pentru un rând.
    is_first_row=True → rândul principal cu titlu, descriere, imagini
    is_first_row=False → variantă suplimentară
    """
    row = {col: '' for col in SHOPIFY_COLUMNS}

    prod_id = product.get('id', product.get('id_produs', ''))
    title = product.get('name', product.get('nume', product.get('title', '')))
    brand = (product.get('brand', 'Ejolie')).strip()
    price, compare_price = get_price(product)
    sku = f"FBR-E{prod_id}-{marime.replace(' ', '')}"
    handle = slugify(title)
    color = extract_color(title)

    # Imagine principală pentru acest rând
    main_image = images_list[0] if images_list else ''
    current_image = images_list[image_index] if image_index < len(
        images_list) else ''

    row['URL handle'] = handle
    row['SKU'] = sku
    row['Barcode'] = ''  # Shopify generează automat
    row['Option1 name'] = 'Size'
    row['Option1 value'] = marime
    row['Price'] = f"{price:.2f}" if price else ''
    row['Compare-at price'] = f"{compare_price:.2f}" if compare_price else ''
    row['Charge tax'] = 'TRUE'
    row['Inventory tracker'] = 'shopify'
    row['Inventory quantity'] = '0'
    row['Continue selling when out of stock'] = 'TRUE'
    row['Weight value (grams)'] = '500'  # estimat pentru o rochie
    row['Weight unit for display'] = 'g'
    row['Requires shipping'] = 'TRUE'
    row['Fulfillment service'] = 'manual'
    row['Gift card'] = 'FALSE'
    row['Google Shopping / Condition'] = 'New'
    row['Google Shopping / Age group'] = 'Adult (13+ years old)'
    row['Google Shopping / Gender'] = 'Female'
    row['Google Shopping / Google product category'] = 'Apparel & Accessories > Clothing > Dresses'

    if is_first_row:
        row['Title'] = title
        row['Description'] = product.get(
            'descriere', product.get('description', ''))
        row['Vendor'] = brand
        row['Product category'] = 'Apparel & Accessories > Clothing > Dresses'
        row['Type'] = 'Rochie'
        row['Tags'] = build_tags(product)
        row['Published on online store'] = 'TRUE'
        row['Status'] = 'Active'
        row['Product image URL'] = main_image
        row['Image position'] = '1'
        row['Image alt text'] = title
        row['SEO title'] = f"{title} | Ejolie"[:70]
        row['SEO description'] = f"Cumpără {title} online. Livrare rapidă în România."[
            :160]
        row['Color (product.metafields.shopify.color-pattern)'] = color
        row['Google Shopping / Manufacturer part number (MPN)'] = f"FBR-E{prod_id}"
    else:
        # Rândul variantei: imagine suplimentară dacă există
        if current_image and current_image != main_image:
            row['Product image URL'] = current_image
            row['Image position'] = str(image_index + 1)
            row['Image alt text'] = f"{title} - imagine {image_index + 1}"

    return row


def export_to_shopify_csv(products_by_brand, output_file):
    """Scrie CSV-ul final Shopify."""
    total_rows = 0
    total_products = 0

    with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=SHOPIFY_COLUMNS)
        writer.writeheader()

        for brand, products in products_by_brand.items():
            print(f"\n✍️  Procesez brand: {brand} ({len(products)} produse)")

            for product in products:
                title = product.get('name', product.get(
                    'nume', product.get('title', '')))
                if not title:
                    continue

                # Extrage imaginile (toate imaginile produsului)
                images = []
                main_img = product.get('image', product.get('imagine', ''))
                if main_img:
                    images.append(main_img)
                # Imagini suplimentare
                extra_imgs = product.get('imagini', product.get('images', []))
                if isinstance(extra_imgs, list):
                    for img in extra_imgs:
                        if isinstance(img, dict):
                            src = img.get('url', img.get(
                                'src', img.get('link', '')))
                        else:
                            src = str(img)
                        if src and src not in images:
                            images.append(src)

                sizes = get_sizes(product)

                for idx, (marime, qty) in enumerate(sizes):
                    is_first = (idx == 0)
                    image_idx = min(idx, len(images) - 1) if images else 0
                    row = build_shopify_row(
                        product, marime, is_first, image_idx, images)
                    writer.writerow(row)
                    total_rows += 1

                total_products += 1

                if total_products % 50 == 0:
                    print(f"   ... {total_products} produse procesate")

    print(f"\n✅ Export complet!")
    print(f"   Produse: {total_products}")
    print(f"   Rânduri CSV: {total_rows}")
    print(f"   Fișier: {output_file}")
    return total_products, total_rows


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Export produse ejolie.ro → Shopify CSV')
    parser.add_argument(
        '--cache', help='Folosește stock_cache.json local în loc de API')
    parser.add_argument('--dry-run', action='store_true',
                        help='Test cu 5 produse')
    parser.add_argument('--output', default=OUTPUT_FILE,
                        help='Fișier output CSV')
    args = parser.parse_args()

    products_by_brand = {}

    if args.cache:
        # Citire din cache local
        all_products = fetch_products_from_cache(args.cache, BRANDS_EXPORT)
        for p in all_products:
            brand = p.get('brand', 'ejolie').lower()
            products_by_brand.setdefault(brand, []).append(p)
    else:
        # Preluare din API
        for brand in BRANDS_EXPORT:
            prods = fetch_products_from_api(brand, dry_run=args.dry_run)
            if prods:
                products_by_brand[brand] = prods

    if not products_by_brand:
        print("❌ Nu s-au găsit produse! Verifică API key sau conexiunea.")
        return

    total_p, total_r = export_to_shopify_csv(products_by_brand, args.output)

    print(f"\n📋 SUMAR FINAL:")
    for brand, prods in products_by_brand.items():
        print(f"   {brand.capitalize()}: {len(prods)} produse")
    print(f"   Total rânduri CSV: {total_r}")
    print(f"\n🚀 Pași următori în Shopify:")
    print(f"   1. Admin Shopify → Produse → Import")
    print(f"   2. Selectează: {args.output}")
    print(f"   3. Bifează 'Publish new products' dacă vrei activ imediat")
    print(f"   4. Verifică primele 5 produse după import!")


if __name__ == "__main__":
    main()
