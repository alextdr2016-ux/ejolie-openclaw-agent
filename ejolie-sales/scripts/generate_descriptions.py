#!/usr/bin/env python3
"""
generate_descriptions.py - Generează descrieri produse din poze cu Gemini Vision
v4 - Added --id, --limit, --no-table argparse support
"""

import os
import sys
import json
import re
import time
import base64
import requests
import argparse
from datetime import datetime

# --- Config ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(SCRIPT_DIR, '..', '.env')

SIZE_TABLE_4COL = '<p><img src="https://ejolie.ro/continut/upload/Tabel%20M%20General%20Trendya.png" width="512" height="764"></p>'
SIZE_TABLE_3COL = '<p><img src="https://ejolie-assets.s3.eu-north-1.amazonaws.com/images/Tabel-Marimi-3col.png" width="512" height="764"></p>'


def load_env(path):
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, val = line.split('=', 1)
                    os.environ[key.strip()] = val.strip()


load_env(ENV_PATH)

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
API_KEY = os.environ.get('EJOLIE_API_KEY', '')
API_URL = os.environ.get('EJOLIE_API_URL', 'https://ejolie.ro/api/')

if not GEMINI_API_KEY:
    print("❌ GEMINI_API_KEY nu e setat in .env!")
    sys.exit(1)

GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

INPUT_FILE = os.path.join(SCRIPT_DIR, 'products_no_description.json')
OUTPUT_FILE = os.path.join(SCRIPT_DIR, 'generated_descriptions.json')
LOG_FILE = os.path.join(SCRIPT_DIR, 'description_generation_log.json')
EXCEL_FILE = os.path.join(SCRIPT_DIR, 'review_descriptions.xlsx')

PROMPT = """Ești copywriter expert pentru magazinul online ejolie.ro (rochii elegante din România).
Analizează imaginea rochiei "{product_name}" și scrie o descriere de produs în limba română.

EXEMPLU COMPLET (acesta este formatul exact pe care trebuie să-l urmezi):

---
Rochia Elysia este definiția eleganței supreme — o creație cu aer regal, concepută pentru femeia care își poartă feminitatea ca pe o armură de grație și putere. Croiala tip sirenă conturează silueta cu precizie, iar capa amplă din voal translucid se așază fluid peste umeri, creând o mișcare spectaculoasă la fiecare pas.

Decupajul subtil de la bust și talia structurată prin pliuri fine adaugă profunzime designului, accentuând armonios linia corpului. Realizată dintr-un material elastic, ușor satinat, rochia oferă confort și eleganță deopotrivă — o alegere ideală pentru evenimente de seară, gale sau momente în care vrei să fii memorabilă.

Detalii produs:
- Croială sirenă cu efect modelator
- Capa lungă din voal fin, fluid și elegant
- Decupaj discret în zona bustului
- Talie pliată cu efect optic subțire
- Material: stofa ușor elastică cu inserții din voal

Sugestie de styling: Completeaz-o cu cercei statement și o poșetă tip clutch metalică. O rochie ce transformă fiecare apariție într-un moment de neuitat.
---

ACUM scrie o descriere SIMILARĂ ca lungime și structură pentru rochia din imagine. OBLIGATORIU:
- Paragraf 1: 2-3 propoziții despre cum arată rochia, senzația pe care o transmite, ocazia potrivită
- Paragraf 2: 1-2 propoziții despre material, confort, versatilitate
- "Detalii produs:" cu 4-5 bullet points (croială, material, detalii vizuale, lungime, elemente speciale)
- "Sugestie de styling:" cu o propoziție de recomandare accesorii
- TOTAL: minimum 100 cuvinte, maximum 150 cuvinte
- Ton elegant, aspirațional, feminin
- Menționează culoarea și materialul vizibil în imagine
- Descrie croiala vizibilă (sirenă, A-line, mulată, evazată, dreaptă, etc.)
- NU inventa detalii pe care nu le vezi
- NU pune prețuri sau mărimi
- Scrie DOAR descrierea, fără alte comentarii"""


def download_image_base64(url):
    try:
        r = requests.get(url, timeout=30, headers={
                         'User-Agent': 'Mozilla/5.0'})
        if r.status_code == 200:
            content_type = r.headers.get('Content-Type', 'image/webp')
            if 'webp' in content_type or url.endswith('.webp'):
                mime = 'image/webp'
            elif 'jpeg' in content_type or 'jpg' in content_type:
                mime = 'image/jpeg'
            elif 'png' in content_type:
                mime = 'image/png'
            else:
                mime = 'image/webp'
            b64 = base64.b64encode(r.content).decode('utf-8')
            return b64, mime
        else:
            print(f"    ⚠️ HTTP {r.status_code}")
            return None, None
    except Exception as e:
        print(f"    ❌ Download err: {e}")
        return None, None


def generate_with_gemini(product_name, image_b64, mime_type, retry=0):
    prompt_text = PROMPT.format(product_name=product_name)
    payload = {
        "contents": [{"parts": [
            {"text": prompt_text},
            {"inline_data": {"mime_type": mime_type, "data": image_b64}}
        ]}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 2000,
            "topP": 0.9,
            "thinkingConfig": {"thinkingBudget": 0}
        }
    }
    try:
        r = requests.post(GEMINI_URL, json=payload, timeout=90)
        if r.status_code == 200:
            data = r.json()
            if 'candidates' not in data or not data['candidates']:
                return None
            candidate = data['candidates'][0]
            if candidate.get('finishReason') == 'SAFETY':
                return None
            text_parts = [part['text']
                          for part in candidate['content']['parts'] if 'text' in part]
            return '\n'.join(text_parts).strip() if text_parts else None
        elif r.status_code == 429 and retry < 3:
            wait = 10 * (retry + 1)
            print(f"⏳ Rate limit - aștept {wait}s...")
            time.sleep(wait)
            return generate_with_gemini(product_name, image_b64, mime_type, retry + 1)
        else:
            print(f"❌ API {r.status_code}: {r.text[:200]}")
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def text_to_html(raw_text, add_table=None):
    """Convert text to HTML. add_table: None (no table), '3col', '4col'"""
    lines = raw_text.strip().split('\n')
    html_parts = []
    in_list = False

    for line in lines:
        line = line.strip()
        if not line:
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            continue
        if line.startswith('---'):
            continue
        if line.lower().startswith('detalii produs'):
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            html_parts.append(f'<p><strong>{line}</strong></p>')
            continue
        if line.lower().startswith('sugestie de styling'):
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            if ':' in line:
                label, content = line.split(':', 1)
                html_parts.append(
                    f'<p><strong>{label.strip()}:</strong> {content.strip()}</p>')
            else:
                html_parts.append(f'<p><strong>{line}</strong></p>')
            continue
        if line.startswith(('* ', '- ', '• ', '– ')):
            if not in_list:
                html_parts.append('<ul>')
                in_list = True
            bullet_text = line.lstrip('*-•– ').strip()
            html_parts.append(f'<li>{bullet_text}</li>')
            continue
        if in_list:
            html_parts.append('</ul>')
            in_list = False
        html_parts.append(f'<p>{line}</p>')

    if in_list:
        html_parts.append('</ul>')

    # Add size table if requested
    if add_table == '4col':
        html_parts.append(SIZE_TABLE_4COL)
    elif add_table == '3col':
        html_parts.append(SIZE_TABLE_3COL)

    return '\n'.join(html_parts)


def fetch_product_by_id(product_id):
    """Fetch a single product from Extended API by ID"""
    url = f"{API_URL}?id_produs={product_id}&apikey={API_KEY}"
    try:
        req = requests.get(
            url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=60)
        if req.status_code == 200:
            data = req.json()
            if isinstance(data, dict) and data:
                # API returns dict with product data
                return {
                    'id': str(product_id),
                    'name': data.get('nume', ''),
                    'brand': data.get('brand', ''),
                    'link': data.get('link', ''),
                    'image': data.get('imagine', ''),
                }
        return None
    except Exception as e:
        print(f"❌ API error: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description='Generate product descriptions with Gemini Vision')
    parser.add_argument('--id', type=str, help='Process specific product ID')
    parser.add_argument('--limit', type=int, default=0,
                        help='Limit number of products to process')
    parser.add_argument('--no-table', action='store_true',
                        help='Do NOT append size table to description')
    args = parser.parse_args()

    print("=" * 60)
    print("🎨 GENERARE DESCRIERI PRODUSE - Gemini Vision v4")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    if args.id:
        print(f"🎯 Mod: produs specific ID={args.id}")
    elif args.limit:
        print(f"🎯 Mod: limitat la {args.limit} produse")
    if args.no_table:
        print(f"📐 Tabel mărimi: NU")
    else:
        print(f"📐 Tabel mărimi: DA (se adaugă automat)")
    print("=" * 60)

    # Determine products to process
    if args.id:
        # Fetch single product from API
        print(f"\n📡 Fetch produs {args.id} din API...")
        prod = fetch_product_by_id(args.id)
        if not prod:
            print(f"❌ Produsul {args.id} nu a fost găsit!")
            sys.exit(1)
        products = [prod]
        print(f"✅ {prod['name']}")
    else:
        if not os.path.exists(INPUT_FILE):
            print(f"❌ {INPUT_FILE} nu există! Rulează scan_no_description.py")
            sys.exit(1)
        with open(INPUT_FILE) as f:
            products = json.load(f)

    total = len(products)
    if args.limit and args.limit < total:
        products = products[:args.limit]
        total = len(products)

    print(f"\n📋 {total} produse de procesat")

    # Load existing (resume support)
    existing = {}
    if os.path.exists(OUTPUT_FILE) and not args.id:
        with open(OUTPUT_FILE) as f:
            existing_list = json.load(f)
            existing = {item['id']: item for item in existing_list}
        print(f"📂 {len(existing)} existente (skip)")

    results = list(existing.values()) if not args.id else []
    errors = []
    skipped = 0
    processed = 0

    for i, prod in enumerate(products):
        pid = prod['id']
        name = prod['name']
        image_url = prod.get('image', '')

        if pid in existing and not args.id:
            skipped += 1
            continue

        if not image_url:
            print(f"  [{i+1}/{total}] ⏭️ {name} — fără imagine")
            errors.append({'id': pid, 'name': name, 'error': 'no image'})
            continue

        print(f"  [{i+1}/{total}] 🔄 {name}...", end=' ')

        img_b64, mime = download_image_base64(image_url)
        if not img_b64:
            errors.append({'id': pid, 'name': name,
                          'error': 'image download failed'})
            continue

        raw_text = generate_with_gemini(name, img_b64, mime)
        if not raw_text:
            errors.append({'id': pid, 'name': name, 'error': 'gemini failed'})
            continue

        # Determine table type (no table if --no-table)
        table_type = None
        if not args.no_table:
            table_type = '4col'  # default, will be overridden by add_size_table.py per croi

        html = text_to_html(raw_text, add_table=table_type)
        word_count = len(re.sub(r'<[^>]+>', '', raw_text).split())

        result = {
            'id': pid,
            'name': name,
            'brand': prod.get('brand', ''),
            'link': prod.get('link', ''),
            'image': image_url,
            'description_text': raw_text,
            'description_html': html,
            'word_count': word_count
        }
        results.append(result)
        processed += 1

        print(f"✅ {word_count} cuvinte")

        if processed % 10 == 0 and not args.id:
            with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

        time.sleep(1.5)

    # Final save
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    if errors:
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(errors, f, ensure_ascii=False, indent=2)

    # Summary
    avg_words = sum(r['word_count']
                    for r in results) / len(results) if results else 0
    print(f"\n{'=' * 60}")
    print(f"📊 REZULTATE:")
    print(f"  ✅ Generate:  {processed}")
    print(f"  ⏭️ Skip:      {skipped}")
    print(f"  ❌ Erori:     {len(errors)}")
    print(f"  📄 Total:     {len(results)} descrieri")
    print(f"  📏 Media:     {avg_words:.0f} cuvinte/descriere")
    print(f"{'=' * 60}")

    if args.id and results:
        print(f"\n📝 DESCRIERE GENERATĂ:")
        print(f"{results[-1]['description_text']}")


if __name__ == '__main__':
    main()
