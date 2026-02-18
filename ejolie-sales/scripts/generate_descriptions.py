#!/usr/bin/env python3
"""
generate_descriptions.py - Generează descrieri produse din poze cu Gemini Vision
v3 - Fix: disable Gemini thinking (cauza output scurt) + tabel mărimi la final
"""

import os
import sys
import json
import re
import time
import base64
import requests
from datetime import datetime

# --- Config ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(SCRIPT_DIR, '..', '.env')

# Imaginea tabelului de mărimi - se adaugă la finalul fiecărei descrieri
SIZE_TABLE_IMG = '<p><img src="https://www.ejolie.ro/continut/upload/Tabel M General Trendya.png" style="width:512px;height:764px"></p>'


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
EXCEL_FILE = os.path.join(SCRIPT_DIR, 'review_descriptions.xlsx')

# --- Prompt template with EXAMPLE ---
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

# --- Helper: Download image as base64 ---


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

# --- Helper: Call Gemini Vision ---


def generate_with_gemini(product_name, image_b64, mime_type, retry=0):
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
            "maxOutputTokens": 2000,
            "topP": 0.9,
            "thinkingConfig": {
                "thinkingBudget": 0
            }
        }
    }

    try:
        r = requests.post(GEMINI_URL, json=payload, timeout=90)
        if r.status_code == 200:
            data = r.json()
            if 'candidates' not in data or not data['candidates']:
                print(f"⚠️ No candidates")
                return None
            candidate = data['candidates'][0]
            if candidate.get('finishReason') == 'SAFETY':
                print(f"⚠️ Safety block")
                return None
            # Gemini poate returna mai multe parts (thinking + text)
            # Luam doar text parts, ignoram thinking
            text_parts = []
            for part in candidate['content']['parts']:
                if 'text' in part:
                    text_parts.append(part['text'])
            if text_parts:
                return '\n'.join(text_parts).strip()
            return None
        elif r.status_code == 429:
            if retry < 3:
                wait = 10 * (retry + 1)
                print(f"⏳ Rate limit - aștept {wait}s...")
                time.sleep(wait)
                return generate_with_gemini(product_name, image_b64, mime_type, retry + 1)
            print(f"❌ Rate limit persistent")
            return None
        else:
            print(f"❌ API {r.status_code}: {r.text[:200]}")
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

# --- Helper: Convert text to HTML + append size table ---


def text_to_html(raw_text):
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

        # Skip dashes/separators
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

    # Adaugă tabelul de mărimi la final
    html_parts.append(SIZE_TABLE_IMG)

    return '\n'.join(html_parts)

# --- Helper: Export Excel for review ---


def export_review_excel(results, errors):
    try:
        import pandas as pd

        with pd.ExcelWriter(EXCEL_FILE, engine='openpyxl') as writer:
            if results:
                rows = []
                for r in results:
                    clean_text = re.sub(
                        r'<[^>]+>', '', r['description_html']).strip()
                    clean_text = re.sub(r'\n+', ' | ', clean_text)
                    rows.append({
                        'ID': r['id'],
                        'Nume Produs': r['name'],
                        'Brand': r['brand'],
                        'Cuvinte': r['word_count'],
                        'Descriere Text': clean_text,
                        'Link Produs': r['link'],
                        'Imagine': r['image'],
                        'Status': '✅ OK' if 80 <= r['word_count'] <= 180 else '⚠️ Verifică'
                    })
                df = pd.DataFrame(rows)
                df.to_excel(
                    writer, sheet_name='Descrieri Generate', index=False)

                ws = writer.sheets['Descrieri Generate']
                ws.column_dimensions['A'].width = 8
                ws.column_dimensions['B'].width = 35
                ws.column_dimensions['C'].width = 10
                ws.column_dimensions['D'].width = 8
                ws.column_dimensions['E'].width = 80
                ws.column_dimensions['F'].width = 45
                ws.column_dimensions['G'].width = 60
                ws.column_dimensions['H'].width = 18

            if errors:
                df_err = pd.DataFrame(errors)
                df_err.to_excel(writer, sheet_name='Erori', index=False)

            summary = pd.DataFrame([
                {'Metric': 'Total generate', 'Valoare': len(results)},
                {'Metric': 'Erori', 'Valoare': len(errors)},
                {'Metric': 'Media cuvinte',
                    'Valoare': f"{sum(r['word_count'] for r in results) / len(results):.0f}" if results else 0},
                {'Metric': 'Min cuvinte', 'Valoare': min(
                    r['word_count'] for r in results) if results else 0},
                {'Metric': 'Max cuvinte', 'Valoare': max(
                    r['word_count'] for r in results) if results else 0},
                {'Metric': 'Data generare',
                    'Valoare': datetime.now().strftime('%Y-%m-%d %H:%M')},
            ])
            summary.to_excel(writer, sheet_name='Sumar', index=False)

        print(f"📊 Excel review: {EXCEL_FILE}")
    except ImportError:
        print("⚠️ pandas/openpyxl nu e instalat")

# --- Main ---


def main():
    print("=" * 60)
    print("🎨 GENERARE DESCRIERI PRODUSE - Gemini Vision v3")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    if not os.path.exists(INPUT_FILE):
        print(f"❌ {INPUT_FILE} nu există! Rulează scan_no_description.py")
        sys.exit(1)

    with open(INPUT_FILE) as f:
        products = json.load(f)

    print(f"\n📋 {len(products)} produse de procesat")
    print(f"📐 Tabel mărimi: DA (se adaugă automat la final)")

    # Load existing (resume support)
    existing = {}
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE) as f:
            existing_list = json.load(f)
            existing = {item['id']: item for item in existing_list}
        print(f"📂 {len(existing)} existente (skip)")

    results = list(existing.values())
    errors = []
    skipped = 0
    processed = 0

    for i, prod in enumerate(products):
        pid = prod['id']
        name = prod['name']
        image_url = prod.get('image', '')

        if pid in existing:
            skipped += 1
            continue

        if not image_url:
            print(f"  [{i+1}/{len(products)}] ⏭️ {name} — fără imagine")
            errors.append({'id': pid, 'name': name, 'error': 'no image'})
            continue

        print(f"  [{i+1}/{len(products)}] 🔄 {name}...", end=' ')

        img_b64, mime = download_image_base64(image_url)
        if not img_b64:
            errors.append({'id': pid, 'name': name,
                          'error': 'image download failed'})
            continue

        raw_text = generate_with_gemini(name, img_b64, mime)
        if not raw_text:
            errors.append({'id': pid, 'name': name, 'error': 'gemini failed'})
            continue

        html = text_to_html(raw_text)
        # Word count fara HTML si fara size table
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

        if processed % 10 == 0:
            with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"    💾 Progres salvat ({processed} noi)")

        time.sleep(1.5)

    # Final save
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    if errors:
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(errors, f, ensure_ascii=False, indent=2)

    # Excel review
    print("\n📊 Export Excel review...")
    export_review_excel(results, errors)

    # Summary
    avg_words = sum(r['word_count']
                    for r in results) / len(results) if results else 0

    print("\n" + "=" * 60)
    print("📊 REZULTATE:")
    print(f"  ✅ Generate:  {processed}")
    print(f"  ⏭️ Skip:      {skipped}")
    print(f"  ❌ Erori:     {len(errors)}")
    print(f"  📄 Total:     {len(results)} descrieri")
    print(f"  📏 Media:     {avg_words:.0f} cuvinte/descriere")
    print("=" * 60)

    # LISTA COMPLETA
    print("\n" + "=" * 90)
    print("📋 LISTA COMPLETĂ PRODUSE CU DESCRIERI GENERATE:")
    print("=" * 90)
    print(f"{'#':<4} {'ID':<7} {'Brand':<10} {'Cuv':<5} {'Nume Produs':<45} {'Status'}")
    print("-" * 90)
    for idx, r in enumerate(results, 1):
        status = "✅" if 80 <= r['word_count'] <= 180 else "⚠️"
        name_short = r['name'][:43] if len(r['name']) > 43 else r['name']
        print(
            f"{idx:<4} {r['id']:<7} {r['brand']:<10} {r['word_count']:<5} {name_short:<45} {status}")
    print("-" * 90)
    print(f"TOTAL: {len(results)} produse | Media: {avg_words:.0f} cuvinte")

    if errors:
        print(f"\n⚠️ {len(errors)} erori in {LOG_FILE}")

    print(f"\n📊 Review Excel: {EXCEL_FILE}")
    print(f"📄 JSON: {OUTPUT_FILE}")
    print(f"➡️ Next: python3 upload_descriptions.py")


if __name__ == '__main__':
    main()
