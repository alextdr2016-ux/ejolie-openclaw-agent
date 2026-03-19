#!/usr/bin/env python3
"""
skroutz_feed.py - Generează XML Feed pentru Skroutz din Extended API
Deployed: EC2 107.23.69.199
Cron: every 6 hours
Output: /var/www/html/skroutz_feed.xml → https://ejolie.ro/skroutz_feed.xml
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
# CONFIG — citit din .env
# ================================
SCRIPT_DIR = Path(__file__).parent
ENV_FILE = SCRIPT_DIR / "../.env"

# Citim .env manual (fără python-dotenv)
env_vars = {}
if ENV_FILE.exists():
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                env_vars[key.strip()] = val.strip()

API_KEY = env_vars.get('EJOLIE_API_KEY', 'C4V9RJKpPOEcXyWDhF7tQYqrNAxeg8')
BASE_URL = "https://ejolie.ro/api/"
HEADERS = {
    'User-Agent': 'Extended API',
    'X-Api-Key': API_KEY
}

# Unde salvăm feed-ul
OUTPUT_PATH = "/var/www/html/skroutz_feed.xml"
CACHE_FILE = SCRIPT_DIR / "../scripts/stock_cache.json"

# ================================
# PASUL 1: Citim produsele
# ================================


def get_products():
    """
    Citim din stock_cache.json (deja actualizat la 4h de cron-ul existent)
    MULT mai rapid decât să facem API calls noi
    """
    print(f"📦 Citesc produse din cache: {CACHE_FILE}")

    if not CACHE_FILE.exists():
        print("⚠️ Cache nu există, fac API call direct...")
        return get_products_from_api()

    with open(CACHE_FILE) as f:
        cache = json.load(f)

    products = list(cache.values()) if isinstance(cache, dict) else cache
    print(f"✅ {len(products)} produse din cache")
    return products


def get_products_from_api():
    """Fallback: preia direct din API dacă nu există cache"""
    products = []
    page = 1

    while True:
        url = f"{BASE_URL}?produse&limit=50&pagina={page}&apikey={API_KEY}"
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
            data = response.json()
            if not data:
                break
            if isinstance(data, list):
                products.extend(data)
            elif isinstance(data, dict):
                products.extend(data.values())
            page += 1
        except Exception as e:
            print(f"❌ Eroare API pagina {page}: {e}")
            break

    return products

# ================================
# PASUL 2: Generăm XML Skroutz
# ================================


def generate_skroutz_feed(products):
    """
    Generează XML în formatul exact cerut de Skroutz
    Documentație: developer.skroutz.gr/feedspec/
    """

    # Root element — Skroutz cere <store> nu <products>
    store = ET.Element("store")

    # Data generării — OBLIGATORIE la Skroutz
    ET.SubElement(store, "created_at").text = datetime.now().strftime(
        "%Y-%m-%d %H:%M")

    products_elem = ET.SubElement(store, "products")

    count = 0
    skipped = 0

    for product in products:
        # Extragem datele de bază
        prod_id = str(product.get('id', ''))
        name = product.get('name', product.get('title', ''))
        price = product.get('price', product.get('pret', 0))
        stock = product.get('stock', product.get('stoc', 0))
        image = product.get('image', product.get('imagine', ''))
        slug = product.get('slug', '')
        category = product.get('category', product.get('categorie', ''))
        brand = product.get('brand', 'OEM')
        description = product.get('description', product.get('descriere', ''))

        # Specificații (culoare, material, etc.)
        specs = product.get('specs', {})
        if isinstance(specs, list):
            # Convertim lista în dict
            specs = {s.get('nume', ''): s.get('valoare', []) for s in specs}

        color = specs.get('Culoare', [''])[0] if specs.get('Culoare') else ''
        material = specs.get('Material', [''])[
            0] if specs.get('Material') else ''
        sizes_list = product.get('sizes', product.get('marimi', []))

        # Validare minimă
        if not prod_id or not name or not price:
            skipped += 1
            continue

        # Construim URL produs
        if slug:
            product_url = f"https://ejolie.ro/product/{slug}-{prod_id}"
        else:
            product_url = f"https://ejolie.ro/product/{prod_id}"

        # Disponibilitate
        try:
            stock_int = int(float(str(stock))) if stock else 0
        except:
            stock_int = 0

        availability = "Disponibil" if stock_int > 0 else "Indisponibil"

        # Formatăm categoria pentru Skroutz (cu >)
        if not category:
            category = "Îmbrăcăminte > Rochii"
        elif '>' not in category:
            category = f"Îmbrăcăminte > {category}"

        # ---- Creăm elementul produs ----
        prod_elem = ET.SubElement(products_elem, "product")

        ET.SubElement(prod_elem, "uid").text = prod_id
        ET.SubElement(prod_elem, "name").text = name[:255]  # max 255 chars
        ET.SubElement(prod_elem, "link").text = product_url

        if image:
            ET.SubElement(prod_elem, "image").text = image

        ET.SubElement(prod_elem, "price_with_vat").text = str(price)
        ET.SubElement(prod_elem, "category").text = category
        ET.SubElement(prod_elem, "manufacturer").text = brand or 'OEM'
        ET.SubElement(prod_elem, "availability").text = availability
        ET.SubElement(prod_elem, "quantity").text = str(stock_int)

        if description:
            ET.SubElement(prod_elem, "description").text = description[:5000]

        # Câmpuri specifice fashion
        if color:
            ET.SubElement(prod_elem, "color").text = color

        if sizes_list:
            if isinstance(sizes_list, list):
                sizes_str = ','.join(str(s) for s in sizes_list if s)
            else:
                sizes_str = str(sizes_list)
            if sizes_str:
                ET.SubElement(prod_elem, "size").text = sizes_str

        if material:
            ET.SubElement(prod_elem, "material").text = material

        count += 1

    print(f"✅ {count} produse adăugate în feed")
    print(f"⚠️  {skipped} produse sărite (date lipsă)")

    return store

# ================================
# PASUL 3: Salvăm XML-ul
# ================================


def save_feed(store_elem, output_path):
    """Salvează și formatează XML-ul frumos"""

    # Creăm directorul dacă nu există
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Convertim în string și formatăm
    xml_string = ET.tostring(store_elem, encoding='unicode')

    # Pretty print cu minidom
    try:
        pretty = minidom.parseString(
            xml_string.encode('utf-8')
        ).toprettyxml(indent="  ", encoding='UTF-8')

        with open(output_path, 'wb') as f:
            f.write(pretty)
    except Exception as e:
        # Fallback fără pretty print
        print(f"⚠️ Pretty print failed ({e}), salvez raw...")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write(xml_string)

    size_kb = Path(output_path).stat().st_size // 1024
    print(f"💾 Feed salvat: {output_path} ({size_kb} KB)")


# ================================
# MAIN
# ================================
if __name__ == "__main__":
    print(
        f"\n🚀 Skroutz Feed Generator - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    # Preim produsele
    products = get_products()

    if not products:
        print("❌ Nu s-au găsit produse. Ieșire.")
        sys.exit(1)

    # Generăm feed-ul
    print("\n🔄 Generez XML feed Skroutz...")
    store = generate_skroutz_feed(products)

    # Salvăm
    print(f"\n💾 Salvez feed-ul...")
    save_feed(store, OUTPUT_PATH)

    print(f"\n✅ GATA!")
    print(f"🌐 Feed disponibil la: https://ejolie.ro/skroutz_feed.xml")
    print(f"🔍 Validează la: https://validator.skroutz.gr")
