#!/usr/bin/env python3
"""
export_shopify_v2.py
Export produse din Extended API → CSV Shopify
Include taguri din: specificatii + categorii + brand
Include stoc real din optiuni → stoc_fizic

Utilizare:
  python3 export_shopify_v2.py
  python3 export_shopify_v2.py --dry-run
  python3 export_shopify_v2.py --limit 50
"""

import csv
import json
import re
import os
import time
import argparse
import requests

# ============================================================
# CONFIG
# ============================================================
API_BASE = 'https://ejolie.ro/api/'
API_KEY = 'N9komxWU3aclwDHyrXfLjJdBA6ZRTs'
HEADERS = {'User-Agent': 'Mozilla/5.0'}
PAGE_SIZE = 50
BRANDS_EXPORT = ['ejolie', 'artista']
OUTPUT_FILE = 'ejolie_shopify_v2.csv'

# Categorii pe care NU le vrem ca taguri (prea generice)
CATEGORII_EXCLUDE = ['catalog', 'noua colectie']

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


# ============================================================
# HELPERS
# ============================================================
def slugify(text):
    text = text.lower()
    for s, r in [('ă', 'a'), ('â', 'a'), ('î', 'i'), ('ș', 's'), ('ş', 's'),
                 ('ț', 't'), ('ţ', 't'), ('é', 'e')]:
        text = text.replace(s, r)
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text.strip())
    return re.sub(r'-+', '-', text)[:80]


def clean_html(text):
    if not text:
        return ''
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def clean_price(val):
    if not val:
        return 0.0
    try:
        return float(str(val).replace(' RON', '').replace(',', '.').strip())
    except:
        return 0.0


def build_tags(product):
    """
    Generează taguri din:
    1. Brand
    2. Specificatii (Culoare, Material, Lungime, Croi, Stil, Model)
    3. Categorii (filtrate)
    """
    tags = set()

    # 1. Tag brand
    brand = product.get('brand', {})
    if isinstance(brand, dict):
        brand_name = brand.get('nume', '').lower()
    else:
        brand_name = str(brand).lower()
    if brand_name:
        tags.add(brand_name)

    # Tag generic rochie
    tags.add('rochie')

    # 2. Specificatii
    specs = product.get('specificatii', [])
    for spec in specs:
        nume_spec = spec.get('nume', '').lower()
        valori = spec.get('valoare', [])

        for val in valori:
            val_clean = val.strip().lower()
            if not val_clean:
                continue

            # Lungime → rochie-lunga, rochie-scurta, etc.
            if nume_spec == 'lungime':
                tag = slugify(f"rochie-{val_clean}")
                tags.add(tag)
            # Croi → sirena, evazat, etc.
            elif nume_spec == 'croi':
                tags.add(slugify(val_clean))
            # Culoare → fucsia, negru, etc.
            elif nume_spec == 'culoare':
                tags.add(slugify(val_clean))
            # Stil → elegant, casual, etc.
            elif nume_spec == 'stil':
                tags.add(slugify(val_clean))
            # Material → poliester, etc.
            elif nume_spec == 'material':
                tags.add(slugify(val_clean))

    # 3. Categorii
    categorii = product.get('categorii', [])
    for cat in categorii:
        cat_nume = cat.get('nume', '').lower().strip()
        if cat_nume and cat_nume not in CATEGORII_EXCLUDE:
            tags.add(slugify(cat_nume))

    return ', '.join(sorted(tags))


def get_price_and_stock(optiuni, marime):
    """Extrage pret si stoc real pentru o marime specifica."""
    for opt in optiuni.values():
        if opt.get('nume_optiune', '') == marime:
            pret = clean_price(opt.get('pret', 0))
            pret_discount = clean_price(opt.get('pret_discount', 0))
            stoc_fizic = int(opt.get('stoc_fizic', 0))

            if pret_discount > 0 and pret_discount < pret:
                return pret_discount, pret, stoc_fizic
            return pret, 0.0, stoc_fizic
    return 0.0, 0.0, 0


def build_row(product, marime, is_first, img_url, img_pos, tags):
    row = {col: '' for col in SHOPIFY_COLUMNS}

    title = product.get('nume', '')
    cod = product.get('cod_produs', f"FBR-{product.get('id_produs', '')}")
    optiuni = product.get('optiuni', {})

    brand = product.get('brand', {})
    brand_name = brand.get('nume', 'Ejolie') if isinstance(
        brand, dict) else str(brand)

    price, compare, stoc_fizic = get_price_and_stock(optiuni, marime)
    sku = f"{cod}-{marime.replace(' ', '')}"

    description = clean_html(product.get('descriere', ''))

    # Culoare din specificatii
    culoare = ''
    for spec in product.get('specificatii', []):
        if spec.get('nume', '').lower() == 'culoare':
            vals = spec.get('valoare', [])
            if vals:
                culoare = vals[0]
            break

    row['URL handle'] = slugify(title)
    row['SKU'] = sku
    row['Option1 name'] = 'Size'
    row['Option1 value'] = marime
    row['Price'] = f"{price:.2f}"
    row['Compare-at price'] = f"{compare:.2f}" if compare else ''
    row['Charge tax'] = 'TRUE'
    row['Inventory tracker'] = 'shopify'
    row['Inventory quantity'] = str(stoc_fizic)  # STOC REAL!
    row['Continue selling when out of stock'] = 'FALSE'
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
        row['Vendor'] = brand_name
        row['Product category'] = 'Apparel & Accessories > Clothing > Dresses'
        row['Type'] = 'Rochie'
        row['Tags'] = tags
        row['Published on online store'] = 'TRUE'
        row['Status'] = 'Active'
        row['SEO title'] = f"{title} | {brand_name}"[:70]
        row['SEO description'] = f"Cumpara {title} online. Livrare rapida in Romania."[
            :160]
        row['Color (product.metafields.shopify.color-pattern)'] = culoare
        row['Google Shopping / Manufacturer part number (MPN)'] = cod

    return row


# ============================================================
# FETCH API
# ============================================================
def fetch_all_products(limit=None):
    """Fetch toate produsele din Extended API."""
    all_products = []
    page = 1
    total_fetched = 0

    print(f"\n Fetch produse din API...")

    while True:
        url = f"{API_BASE}?produse&apikey={API_KEY}&pagina={page}&limit={PAGE_SIZE}"
        try:
            r = requests.get(url, headers=HEADERS, timeout=60)
            data = r.json()
        except Exception as e:
            print(f"   Eroare pagina {page}: {e}")
            break

        if not data:
            break

        for prod in data.values():
            if not isinstance(prod, dict):
                continue

            # Filtru brand
            brand = prod.get('brand', {})
            brand_name = brand.get('nume', '').lower() if isinstance(
                brand, dict) else str(brand).lower()
            if brand_name not in BRANDS_EXPORT:
                continue

            all_products.append(prod)
            total_fetched += 1

            if limit and total_fetched >= limit:
                print(f"   Limita atinsa: {total_fetched} produse")
                return all_products

        print(
            f"   Pagina {page}: {len(data)} produse | Total: {total_fetched}")

        if len(data) < PAGE_SIZE:
            break

        page += 1
        time.sleep(0.3)  # Politicos cu serverul

    return all_products


# ============================================================
# MAIN
# ============================================================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true',
                        help='Test 5 produse')
    parser.add_argument('--limit', type=int, default=None,
                        help='Limita produse')
    parser.add_argument('--output', default=OUTPUT_FILE)
    args = parser.parse_args()

    print("=" * 50)
    print("Shopify Export v2 - ejolie.ro")
    print(f"Mode: {'DRY-RUN (5 produse)' if args.dry_run else 'PRODUCTIE'}")
    print("=" * 50)

    # Fetch produse
    limit = 5 if args.dry_run else args.limit
    products = fetch_all_products(limit=limit)
    print(f"\n Total produse filtrate: {len(products)}")

    # Export CSV
    total_p = total_r = no_img = no_price = 0

    with open(args.output, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=SHOPIFY_COLUMNS)
        writer.writeheader()

        for product in products:
            title = product.get('nume', '')
            optiuni = product.get('optiuni', {})
            imagini = product.get('imagini', [])
            imagine_main = product.get('imagine', '')

            if not title or not optiuni:
                continue

            # Construieste lista imagini
            all_imgs = []
            if imagine_main:
                all_imgs.append(imagine_main)
            for img in imagini:
                if isinstance(img, str) and img and img not in all_imgs:
                    all_imgs.append(img)

            if not all_imgs:
                no_img += 1

            # Generează taguri o singură dată per produs
            tags = build_tags(product)

            # Sortează mărimi numeric
            def sz_key(s):
                try:
                    return int(s)
                except:
                    return 999

            sorted_sizes = sorted(
                [opt.get('nume_optiune', '') for opt in optiuni.values()],
                key=sz_key
            )

            for idx, marime in enumerate(sorted_sizes):
                if not marime:
                    continue

                is_first = (idx == 0)
                img_url = all_imgs[idx] if idx < len(all_imgs) else ''
                img_pos = idx + 1 if img_url else ''

                row = build_row(product, marime, is_first,
                                img_url, img_pos, tags)

                # Skip dacă nu are preț
                if not row['Price'] or float(row['Price']) == 0:
                    no_price += 1
                    continue

                writer.writerow(row)
                total_r += 1

            total_p += 1
            if total_p % 50 == 0:
                print(f"   ... {total_p} produse procesate")

    print(f"\n GATA!")
    print(f"   Produse:       {total_p}")
    print(f"   Randuri CSV:   {total_r}")
    print(f"   Fara imagine:  {no_img}")
    print(f"   Fara pret:     {no_price}")
    print(f"   Fisier:        {args.output}")

    # Preview taguri pentru primele 3 produse
    if args.dry_run and products:
        print(f"\n Preview taguri (primele 3):")
        for p in products[:3]:
            print(f"   {p.get('nume', '')[:50]}")
            print(f"   Tags: {build_tags(p)}")
            print()


if __name__ == "__main__":
    main()
