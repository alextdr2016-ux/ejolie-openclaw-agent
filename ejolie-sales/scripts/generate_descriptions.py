#!/usr/bin/env python3
"""
generate_descriptions.py - Generează descrieri produse din poze cu Gemini Vision
Citește products_no_description.json, trimite imaginea la Gemini, salvează descrieri HTML
v1 - 100-150 cuvinte, template Elysia (2 paragrafe + detalii + styling)
"""

import os
import sys
import json
import time
import base64
import requests
from datetime import datetime

# --- Config ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(SCRIPT_DIR, '..', '.env')


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
if not GEMINI_API_KEY:
    print("❌ GEMINI_API_KEY nu e setat in .env!")
    sys.exit(1)

GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

INPUT_FILE = os.path.join(SCRIPT_DIR, 'products_no_description.json')
OUTPUT_FILE = os.path.join(SCRIPT_DIR, 'generated_descriptions.json')
LOG_FILE = os.path.join(SCRIPT_DIR, 'description_generation_log.json')

# --- Prompt template ---
PROMPT = """Ești copywriter expert pentru un magazin online de rochii elegante din România (ejolie.ro).

Analizează imaginea acestei rochii și scrie o DESCRIERE de produs în limba română.

Numele produsului: {product_name}

STRUCTURĂ OBLIGATORIE (exact acest format):
1. Un paragraf descriptiv (2-3 propoziții) - descrie cum arată rochia, ce senzație transmite, pentru ce ocazie e potrivită
2. Al doilea paragraf (1-2 propoziții) - detalii despre material, confort, versatilitate
3. "Detalii produs:" urmat de 4-5 bullet points cu: croială, material, detalii vizuale, lungime, elemente speciale
4. "Sugestie de styling:" - o propoziție cu recomandare de accesorii/încălțăminte

REGULI:
- Total 100-150 cuvinte
- Ton elegant, aspirațional, feminin
- Menționează culoarea reală din imagine
- Descrie materialul pe baza aspectului vizual (satin, voal, dantelă, crep, etc.)
- Descrie croiala (sirenă, A-line, mulată, evazată, dreaptă, etc.)
- NU inventa detalii pe care nu le vezi în imagine
- NU pune prețuri sau mărimi
- Scrie DOAR textul, fără HTML tags, fără formatare markdown

Răspunde DOAR cu descrierea, nimic altceva."""

# --- Helper: Download image as base64 ---


def download_image_base64(url):
    """Descarcă imagine și returnează base64 + mime type"""
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
            print(f"    ⚠️ HTTP {r.status_code} pentru imagine")
            return None, None
    except Exception as e:
        print(f"    ❌ Eroare download: {e}")
        return None, None

# --- Helper: Call Gemini Vision ---


def generate_with_gemini(product_name, image_b64, mime_type):
    """Trimite imagine + prompt la Gemini Vision, returnează text"""
    prompt_text = PROMPT.format(product_name=product_name)

    payload = {
        "contents": [{
            "parts": [
                {"text": prompt_text},
                {
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": image_b64
                    }
                }
            ]
        }],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 1000
        }
    }

    try:
        r = requests.post(GEMINI_URL, json=payload, timeout=60)
        if r.status_code == 200:
            data = r.json()
            text = data['candidates'][0]['content']['parts'][0]['text']
            return text.strip()
        else:
            print(f"    ❌ Gemini API {r.status_code}: {r.text[:200]}")
            return None
    except Exception as e:
        print(f"    ❌ Gemini error: {e}")
        return None

# --- Helper: Convert text to HTML ---


def text_to_html(raw_text):
    """Convertește textul generat în HTML cu tag-uri permise de Extended"""
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

        # Detectează "Detalii produs:" sau "Sugestie de styling:"
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
            # Extrage textul dupa "Sugestie de styling:"
            if ':' in line:
                label, content = line.split(':', 1)
                html_parts.append(
                    f'<p><strong>{label.strip()}:</strong> {content.strip()}</p>')
            else:
                html_parts.append(f'<p><strong>{line}</strong></p>')
            continue

        # Bullet points (*, -, •)
        if line.startswith(('* ', '- ', '• ', '– ')):
            if not in_list:
                html_parts.append('<ul>')
                in_list = True
            bullet_text = line.lstrip('*-•– ').strip()
            html_parts.append(f'<li>{bullet_text}</li>')
            continue

        # Paragraf normal
        if in_list:
            html_parts.append('</ul>')
            in_list = False
        html_parts.append(f'<p>{line}</p>')

    if in_list:
        html_parts.append('</ul>')

    return '\n'.join(html_parts)

# --- Main ---


def main():
    print("=" * 60)
    print("🎨 GENERARE DESCRIERI PRODUSE - Gemini Vision")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # Load products
    if not os.path.exists(INPUT_FILE):
        print(
            f"❌ Fișierul {INPUT_FILE} nu există! Rulează mai întâi scan_no_description.py")
        sys.exit(1)

    with open(INPUT_FILE) as f:
        products = json.load(f)

    print(f"\n📋 {len(products)} produse de procesat")

    # Load existing results (pentru resume)
    existing = {}
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE) as f:
            existing_list = json.load(f)
            existing = {item['id']: item for item in existing_list}
        print(f"📂 {len(existing)} descrieri existente (skip)")

    # Process
    results = list(existing.values())  # păstrăm cele existente
    errors = []
    skipped = 0
    processed = 0

    for i, prod in enumerate(products):
        pid = prod['id']
        name = prod['name']
        image_url = prod.get('image', '')

        # Skip daca deja generat
        if pid in existing:
            skipped += 1
            continue

        # Skip daca nu are imagine
        if not image_url:
            print(f"  [{i+1}/{len(products)}] ⏭️ {name} — fără imagine")
            errors.append({'id': pid, 'name': name, 'error': 'no image'})
            continue

        print(f"  [{i+1}/{len(products)}] 🔄 {name}...", end=' ')

        # Download image
        img_b64, mime = download_image_base64(image_url)
        if not img_b64:
            errors.append({'id': pid, 'name': name,
                          'error': 'image download failed'})
            continue

        # Generate with Gemini
        raw_text = generate_with_gemini(name, img_b64, mime)
        if not raw_text:
            errors.append({'id': pid, 'name': name, 'error': 'gemini failed'})
            continue

        # Convert to HTML
        html = text_to_html(raw_text)

        # Count words
        import re
        word_count = len(re.sub(r'<[^>]+>', '', html).split())

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

        # Save progress every 10 products
        if processed % 10 == 0:
            with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"    💾 Progres salvat ({processed} noi)")

        # Rate limit - 1 sec between calls
        time.sleep(1)

    # Final save
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # Save errors
    if errors:
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(errors, f, ensure_ascii=False, indent=2)

    # Summary
    print("\n" + "=" * 60)
    print("📊 REZULTATE:")
    print(f"  ✅ Generate:  {processed}")
    print(f"  ⏭️ Skip:      {skipped}")
    print(f"  ❌ Erori:     {len(errors)}")
    print(f"  📄 Total:     {len(results)} descrieri in {OUTPUT_FILE}")

    if results:
        avg_words = sum(r['word_count'] for r in results) / len(results)
        print(f"  📏 Media:     {avg_words:.0f} cuvinte/descriere")

    if errors:
        print(f"\n⚠️ Erori salvate in {LOG_FILE}")
        for e in errors[:5]:
            print(f"  [{e['id']}] {e['name']} — {e['error']}")

    print("\n✅ Generare completă!")
    print(f"➡️ Următorul pas: python3 upload_descriptions.py")


if __name__ == '__main__':
    main()
