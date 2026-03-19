#!/usr/bin/env python3
"""
skroutz_feed.py - Generează XML Feed pentru Skroutz din stock_cache.json
EC2: 107.23.69.199
Cron: every 6 hours
Output: /home/ubuntu/public_feeds/skroutz_feed.xml
"""

import os
import sys
import json
import requests
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
from pathlib import Path

# ================================
# CONFIG
# ================================
SCRIPT_DIR = Path(__file__).parent
CACHE_FILE = SCRIPT_DIR / "stock_cache.json"
OUTPUT_PATH = "/home/ubuntu/public_feeds/skroutz_feed.xml"

API_KEY = 'C4V9RJKpPOEcXyWDhF7tQYqrNAxeg8'
BASE_URL = "https://ejolie.ro/api/"
HEADERS = {'User-Agent': 'Extended API', 'X-Api-Key': API_KEY}

# ================================
# PASUL 1: Citim produsele din cache
# ================================


def get_products():
    print(f"📦 Citesc din: {CACHE_FILE}")

    if not CACHE_FILE.exists():
        print("⚠️ Cache inexistent, apelam API...")
        return get_products_from_api()

    with open(CACHE_FILE) as f:
        cache = json.load(f)

    # Structura: {"updated":..., "total_products":..., "products": {"12415": {...}}}
    if "products" in cache:
        products = list(cache["products"].values())
    elif isinstance(cache, dict):
        products = [v for v in cache.values() if isinstance(v, dict)]
    else:
        products = cache

    print(f"✅ {len(products)} produse găsite")
    return products


def get_products_from_api():
    products = []
    page = 1
    while True:
        url = f"{BASE_URL}?produse&limit=50&pagina={page}&apikey={API_KEY}"
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            data = r.json()
            if not data:
                break
            products.extend(data.values() if isinstance(data, dict) else data)
            page += 1
        except Exception as e:
            print(f"❌ API eroare pagina {page}: {e}")
            break
    return products

# ================================
# PASUL 2: Generăm XML Skroutz
# ================================


def generate_skroutz_feed(products):
    store = ET.Element("store")
    ET.SubElement(store, "created_at").text = datetime.now().strftime(
        "%Y-%m-%d %H:%M")
    products_elem = ET.SubElement(store, "products")

    count = 0
    skipped = 0

    for product in products:
        # Filtru — doar produse Ejolie
        if product.get('brand', '').lower() != 'ejolie':
            continue

        # --- Extragere date din structura cache ---
        prod_id = str(product.get('id', ''))
        name = product.get('nume', product.get('name', ''))
        brand = product.get('brand', 'OEM') or 'OEM'
        desc = product.get('descriere', product.get('description', ''))
        slug = product.get('slug', '')
        category = product.get('categorie', product.get('category', ''))
        image = product.get('imagine', product.get('image', ''))

        # --- Preț și stoc din sizes ---
        sizes_dict = product.get('sizes', {})
        price = 0.0
        stock_total = 0
        sizes_available = []

        for size_name, size_data in sizes_dict.items():
            if not isinstance(size_data, dict):
                continue
            if size_data.get('in_stock', False):
                stock_total += int(size_data.get('stoc_fizic', 0) or 0)
                sizes_available.append(str(size_name))
                if price == 0:
                    pd = float(size_data.get('pret_discount', 0) or 0)
                    pp = float(size_data.get('pret', 0) or 0)
                    price = pd if pd > 0 else pp

        # --- Specificații ---
        specs = product.get('specs', {})
        if isinstance(specs, list):
            specs = {s.get('nume', ''): s.get('valoare', [])
                     for s in specs if isinstance(s, dict)}

        color = specs.get('Culoare', [''])[0] if specs.get('Culoare') else ''
        material = specs.get('Material', [''])[
            0] if specs.get('Material') else ''

        # --- Validare ---
        if not prod_id or not name or price == 0:
            skipped += 1
            continue

        # --- URL produs ---
        if slug:
            url = f"https://ejolie.ro/product/{slug}-{prod_id}"
        else:
            url = f"https://ejolie.ro/product/{prod_id}"

        # --- Disponibilitate ---
        availability = "Disponibil" if stock_total > 0 else "Indisponibil"

        # --- Categorie format Skroutz ---
        if not category:
            category = "Îmbrăcăminte > Rochii"
        elif '>' not in category:
            category = f"Îmbrăcăminte > {category}"

        # --- Construim elementul XML ---
        p = ET.SubElement(products_elem, "product")
        ET.SubElement(p, "uid").text = prod_id
        ET.SubElement(p, "name").text = name[:255]
        ET.SubElement(p, "link").text = url
        ET.SubElement(p, "price_with_vat").text = f"{price:.2f}"
        ET.SubElement(p, "category").text = category
        ET.SubElement(p, "manufacturer").text = brand
        ET.SubElement(p, "availability").text = availability
        ET.SubElement(p, "quantity").text = str(stock_total)

        if image:
            ET.SubElement(p, "image").text = image
        if desc:
            ET.SubElement(p, "description").text = desc[:5000]
        if color:
            ET.SubElement(p, "color").text = color
        if sizes_available:
            ET.SubElement(p, "size").text = ','.join(sizes_available)
        if material:
            ET.SubElement(p, "material").text = material

        count += 1

    print(f"✅ {count} produse în feed | ⚠️ {skipped} sărite")
    return store

# ================================
# PASUL 3: Salvăm XML
# ================================


def save_feed(store_elem, output_path):
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    xml_bytes = ET.tostring(store_elem, encoding='unicode')

    try:
        pretty = minidom.parseString(
            xml_bytes.encode('utf-8')
        ).toprettyxml(indent="  ", encoding='UTF-8')
        with open(output_path, 'wb') as f:
            f.write(pretty)
    except Exception as e:
        print(f"⚠️ Pretty print failed: {e}, salvez raw...")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write(xml_bytes)

    size_kb = Path(output_path).stat().st_size // 1024
    print(f"💾 Salvat: {output_path} ({size_kb} KB)")


# ================================
# MAIN
# ================================
if __name__ == "__main__":
    print(
        f"\n🚀 Skroutz Feed Generator — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    products = get_products()

    if not products:
        print("❌ Zero produse. Ieșire.")
        sys.exit(1)

    print("\n🔄 Generez XML...")
    store = generate_skroutz_feed(products)

    print("\n💾 Salvez...")
    save_feed(store, OUTPUT_PATH)

    print(f"\n✅ GATA!")
    print(f"🌐 https://ejolie.ro/skroutz_feed.xml")
    print(f"🔍 Validează: https://validator.skroutz.gr")
