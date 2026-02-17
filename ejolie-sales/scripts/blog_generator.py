#!/usr/bin/env python3
"""
Blog Auto-Generator pentru ejolie.ro
=====================================
Generează articole SEO cu linkuri interne spre produse.
Folosește GPT-4o-mini pentru conținut și cache local pentru produse.

Utilizare:
  python3 blog_generator.py --keyword "rochii cununie civila 2026"
  python3 blog_generator.py --list-keywords

Cerințe:
  pip install openai
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime

# ============================================================
# CONFIGURARE
# ============================================================


def load_env(path=None):
    paths_to_try = [
        path,
        os.path.expanduser("~/ejolie-openclaw-agent/ejolie-sales/.env"),
        os.path.expanduser("~/.env"),
        ".env"
    ]
    for p in paths_to_try:
        if p and os.path.exists(p):
            with open(p) as f:
                for line in f:
                    line = line.strip()
                    if '=' in line and not line.startswith('#'):
                        k, v = line.split('=', 1)
                        os.environ.setdefault(k.strip(), v.strip())
            print(f"📂 Loaded env: {p}")
            return


load_env()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
EJOLIE_SITE_URL = "https://www.ejolie.ro"

GPT_MODEL = "gpt-4o-mini"
MIN_PRODUCTS_IN_ARTICLE = 3
MAX_PRODUCTS_IN_ARTICLE = 8

PRODUCTS_CACHE_PATH = os.path.expanduser("~/blog_products.json")
IMAGES_LOG_PATH = os.path.expanduser("~/blog_articles/images_log.json")

# ============================================================
# KEYWORDS DATABASE
# ============================================================

KEYWORDS_DB = [
    {"keyword": "rochii pentru invitate la nunta 2026",
        "category": "nunta", "priority": 1},
    {"keyword": "rochii cununie civila 2026", "category": "nunta", "priority": 1},
    {"keyword": "rochii nasa nunta 2026", "category": "nunta", "priority": 1},
    {"keyword": "rochii soacra nunta elegante",
        "category": "nunta", "priority": 2},
    {"keyword": "rochii domnisoare de onoare 2026",
        "category": "nunta", "priority": 2},
    {"keyword": "ce rochie port la nunta vara 2026",
        "category": "nunta", "priority": 2},
    {"keyword": "ce culori se poarta la nunta 2026",
        "category": "nunta", "priority": 2},
    {"keyword": "rochii elegante femei 40 ani", "category": "stil", "priority": 1},
    {"keyword": "rochii elegante femei 50 ani", "category": "stil", "priority": 1},
    {"keyword": "rochii pentru femei plinute elegante",
        "category": "stil", "priority": 1},
    {"keyword": "cum alegi rochia perfecta pentru silueta ta",
        "category": "stil", "priority": 2},
    {"keyword": "rochii de seara lungi elegante",
        "category": "stil", "priority": 2},
    {"keyword": "ce rochie port la botez 2026", "category": "stil", "priority": 1},
    {"keyword": "tendinte rochii elegante 2026",
        "category": "tendinte", "priority": 1},
    {"keyword": "rochii de seara primavara 2026",
        "category": "tendinte", "priority": 2},
    {"keyword": "culori la moda rochii 2026",
        "category": "tendinte", "priority": 2},
    {"keyword": "rochii de ocazie vara 2026",
        "category": "tendinte", "priority": 2},
    {"keyword": "rochii lungi de ocazie online romania",
        "category": "categorie", "priority": 2},
    {"keyword": "rochii elegante de seara preturi bune",
        "category": "categorie", "priority": 2},
    {"keyword": "se poate purta negru la nunta",
        "category": "intrebari", "priority": 2},
    {"keyword": "cum ma imbrac la cununie civila",
        "category": "intrebari", "priority": 1},
]

# ============================================================
# PRODUCT CACHE + UNIQUENESS
# ============================================================


def load_products_cache():
    if os.path.exists(PRODUCTS_CACHE_PATH):
        with open(PRODUCTS_CACHE_PATH, "r", encoding="utf-8") as f:
            products = json.load(f)
        print(f"  📦 Cache: {len(products)} produse")
        return products
    print("  ⚠️ Cache not found!")
    return []


def load_used_products():
    if not os.path.exists(IMAGES_LOG_PATH):
        return set()
    try:
        with open(IMAGES_LOG_PATH, "r") as f:
            log = json.load(f)
        used = set()
        for slug, data in log.items():
            for url in data.get("product_urls", []):
                used.add(url)
            for img in data.get("product_images", []):
                used.add(img)
        return used
    except Exception:
        return set()


def get_relevant_products(keyword, limit=MAX_PRODUCTS_IN_ARTICLE):
    stop_words = {"de", "la", "in", "din", "pentru", "ce", "cum", "sa", "port",
                  "alegi", "aleg", "se", "pot", "poate", "mai", "cel", "cea",
                  "un", "o", "e", "si", "sau", "2026", "2025", "ani"}

    terms = [w for w in keyword.lower().split(
    ) if w not in stop_words and len(w) > 2]
    print(f"🔍 Caut produse pentru: {terms}")

    all_prods = load_products_cache()
    if not all_prods:
        return []

    scored_cache = []
    for p in all_prods:
        name = p.get("name", "").lower()
        cat = p.get("category", "").lower()
        specs = " ".join([
            p.get("culoare", ""), p.get("material", ""),
            p.get("stil", ""), p.get("croi", ""), p.get("lungime", "")
        ]).lower()
        score = 0
        for t in terms:
            if t in name:
                score += 3
            if t in cat:
                score += 2
            if t in specs:
                score += 1
        if score > 0:
            scored_cache.append((score, p))

    scored_cache.sort(key=lambda x: -x[0])
    products = [p for _, p in scored_cache]

    # Exclude products used in previous articles
    used = load_used_products()
    if used:
        fresh = [p for p in products if p.get(
            "url", "") not in used and p.get("image", "") not in used]
        if len(fresh) >= MIN_PRODUCTS_IN_ARTICLE:
            products = fresh
            print(f"  🆕 Filtru unicitate: {len(products)} produse nefolosite")
        else:
            print(
                f"  ⚠️ Doar {len(fresh)} nefolosite, folosesc toate {len(products)}")

    # For events, exclude black dresses
    event_keywords = ["nunta", "cununie", "botez",
                      "nasa", "soacra", "invitate", "domnisoare"]
    is_event = any(ek in keyword.lower() for ek in event_keywords)
    if is_event and len(products) > MIN_PRODUCTS_IN_ARTICLE:
        non_black = [
            p for p in products if "Negru" not in p.get("culoare", "")]
        if len(non_black) >= MIN_PRODUCTS_IN_ARTICLE:
            products = non_black
            print(
                f"  🎨 Filtru eveniment: exclus rochii negre, {len(products)} rămase")

    # Fallback
    if len(products) < MIN_PRODUCTS_IN_ARTICLE:
        cat_terms = ["ocazie", "seara", "elegante", "lungi"]
        for p in all_prods:
            cat = p.get("category", "").lower()
            if any(ct in cat for ct in cat_terms) and p not in products:
                products.append(p)
                if len(products) >= limit:
                    break

    products = products[:limit]
    print(f"✅ {len(products)} produse selectate")
    for p in products:
        has_img = "📷" if p.get("image") else "  "
        print(f"   {has_img} {p['name'][:50]}")

    return products

# ============================================================
# GENERARE CONȚINUT CU GPT
# ============================================================


def generate_article(keyword, products):
    products_with_images = ""
    for i, p in enumerate(products, 1):
        img_url = p.get("image", "")
        img_line = f"- Imagine: {img_url}" if img_url else "- Imagine: (nu are)"
        specs = []
        if p.get('culoare') and p['culoare'] != '❌ LIPSA':
            specs.append(f"Culoare: {p['culoare']}")
        if p.get('material') and p['material'] != '❌ LIPSA':
            specs.append(f"Material: {p['material']}")
        if p.get('stil') and p['stil'] != '❌ LIPSA':
            specs.append(f"Stil: {p['stil']}")
        specs_str = ", ".join(specs) if specs else "Rochie elegantă"

        products_with_images += f"""
Produs {i}:
- Nume: {p['name']}
- URL: {p['url']}
{img_line}
- Specificații: {specs_str}
"""

    system_prompt = """Ești un expert SEO și copywriter pentru un magazin online de rochii elegante din România (ejolie.ro).
Scrii în limba română, cu diacritice corecte (ă, â, î, ș, ț).
Stilul tău este: cald, profesional, informativ, orientat spre vânzare subtilă.
Publicul țintă: femei 25-55 ani din România care caută rochii elegante.
"""

    user_prompt = f"""Generează un articol de blog SEO-optimizat pentru keyword-ul: "{keyword}"

CERINȚE ARTICOL:
1. Titlu H1 captivant care conține keyword-ul (max 60 caractere ideal)
2. Conținut 1500-2000 cuvinte
3. Structurat cu H2 și H3 subtitluri (5-7 secțiuni)
4. Include sfaturi practice, informații utile
5. Ton conversațional dar profesional
6. Include CTA (call to action) natural spre produse

CERINȚE SEO:
1. Keyword-ul principal apare în: titlu, primul paragraf, 2-3 subtitluri, ultimul paragraf
2. Folosește variații ale keyword-ului natural în text
3. Meta title: max 60 caractere, include keyword
4. Meta description: max 155 caractere, include keyword, CTA
5. URL slug: max 5-6 cuvinte, cu cratimă
6. Minimum 8 keywords relevante în meta_keywords

CERINȚE LINKURI INTERNE:
Include aceste produse cu linkuri și imagini în articol:
{products_with_images}

CERINȚE DESIGN - FOARTE IMPORTANT:
Folosește EXACT acest format HTML cu CSS inline pentru un design profesional de revistă de modă:

Pentru fiecare H2 secțiune:
<h2 style="font-family:Georgia,serif;font-size:1.6em;color:#2c2c2c;border-bottom:2px solid #c8a165;padding-bottom:8px;margin-top:35px;">Titlu Secțiune</h2>

Pentru paragrafe:
<p style="font-family:Georgia,serif;font-size:1.05em;line-height:1.8;color:#444;margin:15px 0;">Text paragraf</p>

Pentru PRIMUL paragraf al articolului, adaugă drop cap:
<p style="font-family:Georgia,serif;font-size:1.05em;line-height:1.8;color:#444;margin:15px 0;"><span style="float:left;font-size:3.5em;line-height:0.8;padding-right:8px;color:#c8a165;font-family:Georgia,serif;">P</span>rimul paragraf...</p>

Pentru H3:
<h3 style="font-family:Georgia,serif;font-size:1.2em;color:#555;margin-top:20px;">Subtitlu</h3>

Pentru produse - CARD cu imagine lângă text (imagine stânga, text dreapta):
<div style="display:flex;align-items:center;gap:20px;background:#faf8f5;border-radius:10px;padding:15px;margin:20px 0;border:1px solid #e8e0d4;">
  <a href="URL_PRODUS" title="NUME_PRODUS" style="flex-shrink:0;">
    <img src="URL_IMAGINE" alt="NUME_PRODUS" style="width:140px;height:180px;object-fit:cover;border-radius:8px;" />
  </a>
  <div>
    <p style="font-family:Georgia,serif;font-size:1em;color:#444;margin:0 0 8px 0;">Text recomandare natural despre produs.</p>
    <a href="URL_PRODUS" title="NUME_PRODUS" style="display:inline-block;background:#c8a165;color:#fff;padding:8px 20px;border-radius:20px;text-decoration:none;font-size:0.9em;font-family:Arial,sans-serif;">Vezi produsul &#8594;</a>
  </div>
</div>

Dacă produsul NU are imagine, folosește card fără imagine:
<div style="background:#faf8f5;border-radius:10px;padding:15px;margin:20px 0;border:1px solid #e8e0d4;">
  <p style="font-family:Georgia,serif;font-size:1em;color:#444;margin:0 0 8px 0;">Text recomandare.</p>
  <a href="URL_PRODUS" title="NUME_PRODUS" style="display:inline-block;background:#c8a165;color:#fff;padding:8px 20px;border-radius:20px;text-decoration:none;font-size:0.9em;">Vezi produsul &#8594;</a>
</div>

Pentru lista de sfaturi, folosește iconuri:
<div style="background:#faf8f5;border-radius:10px;padding:20px;margin:20px 0;">
  <p style="margin:8px 0;font-family:Georgia,serif;color:#444;">&#10024; <strong>Sfat 1</strong> — text sfat</p>
  <p style="margin:8px 0;font-family:Georgia,serif;color:#444;">&#128087; <strong>Sfat 2</strong> — text sfat</p>
  <p style="margin:8px 0;font-family:Georgia,serif;color:#444;">&#128161; <strong>Sfat 3</strong> — text sfat</p>
</div>

Separator între secțiuni majore:
<hr style="border:none;height:1px;background:linear-gradient(to right,transparent,#c8a165,transparent);margin:30px 0;" />

CTA final:
<div style="text-align:center;background:linear-gradient(135deg,#2c2c2c,#444);border-radius:12px;padding:30px;margin:30px 0;">
  <p style="font-family:Georgia,serif;font-size:1.3em;color:#c8a165;margin:0 0 15px 0;">Descoperă colecția completă pe ejolie.ro</p>
  <a href="https://www.ejolie.ro" style="display:inline-block;background:#c8a165;color:#fff;padding:12px 35px;border-radius:25px;text-decoration:none;font-size:1.1em;font-family:Arial,sans-serif;">Explorează Rochiile &#8594;</a>
</div>

REGULI STRICTE:
- Alternează 1-2 paragrafe text cu un card produs — NU pune 3+ paragrafe consecutive fără card
- Folosește maxim 1 card produs per secțiune H2
- Adaugă separator hr între secțiuni majore
- NU include h1, html, head, body
- content_html TREBUIE să fie HTML valid cu CSS inline
- Scrie EXCLUSIV în română cu diacritice corecte

CERINȚE TEHNICE:
Output STRICT în format JSON:
{{
    "title": "Titlu articol H1",
    "meta_title": "Meta title SEO (max 60 char)",
    "meta_description": "Meta description (max 155 char)",
    "meta_keywords": "keyword1, keyword2, keyword3, ..., keyword8",
    "slug": "url-slug-seo",
    "short_description": "Descriere scurtă 150-200 caractere",
    "content_html": "HTML complet cu CSS inline"
}}
"""

    print(f"\n🤖 Generez articol cu {GPT_MODEL}...")

    try:
        import openai
        client = openai.OpenAI(api_key=OPENAI_API_KEY)

        response = client.chat.completions.create(
            model=GPT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=8000,
            response_format={"type": "json_object"}
        )

        raw_content = response.choices[0].message.content
        print(f"📝 Raw response length: {len(raw_content)}")
        result = json.loads(raw_content)

        tokens_used = response.usage.total_tokens
        cost = tokens_used * 0.00000015
        print(f"✅ Articol generat! Tokens: {tokens_used}, Cost: ~${cost:.4f}")
        return result

    except json.JSONDecodeError as e:
        print(f"❌ JSON Parse Error: {e}")
        return None
    except Exception as e:
        print(f"❌ GPT Error: {e}")
        return None

# ============================================================
# SALVARE LOCALĂ
# ============================================================


def save_article_local(article_data):
    slug = article_data.get("slug", "articol")
    json_path = os.path.expanduser(f"~/blog_articles/{slug}.json")
    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(article_data, f, ensure_ascii=False, indent=2)

    html_path = os.path.expanduser(f"~/blog_articles/{slug}.html")
    html_content = f"""<!DOCTYPE html>
<html lang="ro">
<head>
    <meta charset="UTF-8">
    <title>{article_data['meta_title']}</title>
    <style>body{{font-family:Georgia,serif;max-width:800px;margin:40px auto;padding:0 20px;color:#333;line-height:1.7;}}</style>
</head>
<body>
    <h1 style="color:#c8a165;border-bottom:2px solid #c8a165;padding-bottom:10px;">{article_data['title']}</h1>
    {article_data['content_html']}
</body>
</html>"""

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"💾 Salvat local:")
    print(f"   JSON: {json_path}")
    print(f"   HTML: {html_path}")
    return json_path


def generate_browser_js(article_data, category=1):
    content = article_data["content_html"].replace(
        "\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
    title = article_data["title"].replace("'", "\\'")
    short_desc = article_data.get("short_description", "").replace("'", "\\'")
    slug = article_data["slug"]
    meta_title = article_data["meta_title"].replace("'", "\\'")
    meta_keywords = article_data["meta_keywords"].replace("'", "\\'")
    meta_description = article_data["meta_description"].replace("'", "\\'")

    js = f"""(async () => {{
    const formData = new FormData();
    formData.append('trimite', 'value');
    formData.append('camp_nume', '{title}');
    formData.append('camp_data', '{datetime.now().strftime("%d-%m-%Y")}');
    formData.append('camp_descriere', '{short_desc}');
    formData.append('camp_continut', `{content}`);
    formData.append('camp_categorie', '{category}');
    formData.append('camp_linkpublic', '{slug}');
    formData.append('camp_title', '{meta_title}');
    formData.append('camp_keywords', '{meta_keywords}');
    formData.append('camp_description', '{meta_description}');
    formData.append('id_autosave', '');
    const resp = await fetch('/manager/blog/adauga_articol/0', {{method:'POST',body:formData,credentials:'same-origin'}});
    console.log(resp.ok ? '✅ Creat: {slug}' : '❌ Error');
}})();"""

    js_path = os.path.expanduser(f"~/blog_articles/{slug}_publish.js")
    os.makedirs(os.path.dirname(js_path), exist_ok=True)
    with open(js_path, "w", encoding="utf-8") as f:
        f.write(js)
    print(f"📋 JS salvat: {js_path}")
    return js_path

# ============================================================
# MAIN
# ============================================================


def process_keyword(keyword, publish=False, dry_run=False):
    print(f"\n{'='*60}")
    print(f"📝 KEYWORD: {keyword}")
    print(f"{'='*60}")

    products = get_relevant_products(keyword)
    if not products:
        print("❌ Nu s-au găsit produse. Skip.")
        return None

    if dry_run:
        print("🏃 DRY RUN - nu generez articol")
        return None

    article = generate_article(keyword, products)
    if not article:
        print("❌ Generarea articolului a eșuat.")
        return None

    print(f"\n📰 PREVIEW:")
    print(f"   Titlu: {article['title']}")
    print(f"   SEO Title: {article['meta_title']}")
    print(f"   Meta Desc: {article['meta_description']}")
    print(f"   Slug: {article['slug']}")
    print(f"   Conținut: {len(article['content_html'])} caractere HTML")

    save_article_local(article)
    generate_browser_js(article)
    return article


def main():
    parser = argparse.ArgumentParser(
        description="Blog Auto-Generator ejolie.ro")
    parser.add_argument("--keyword", "-k", help="Keyword pentru articol")
    parser.add_argument("--publish", "-p", action="store_true")
    parser.add_argument("--dry-run", "-d", action="store_true")
    parser.add_argument("--list-keywords", "-l", action="store_true")
    parser.add_argument("--batch", "-b", type=int)

    args = parser.parse_args()

    if not OPENAI_API_KEY and not args.list_keywords and not args.dry_run:
        print("❌ OPENAI_API_KEY nu e setat!")
        sys.exit(1)

    if args.list_keywords:
        print("\n📋 KEYWORDS DATABASE:")
        for kw in sorted(KEYWORDS_DB, key=lambda x: (x["priority"], x["category"])):
            print(
                f"  P{kw['priority']} | {kw['category']:<12} | {kw['keyword']}")
        print(f"\nTotal: {len(KEYWORDS_DB)} keywords")
        return

    if args.batch:
        keywords = sorted(KEYWORDS_DB, key=lambda x: x["priority"])[
            :args.batch]
        for kw in keywords:
            process_keyword(
                kw["keyword"], publish=args.publish, dry_run=args.dry_run)
            if not args.dry_run:
                time.sleep(2)
        return

    if args.keyword:
        process_keyword(args.keyword, publish=args.publish,
                        dry_run=args.dry_run)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
