#!/usr/bin/env python3
"""
Blog Auto-Generator pentru ejolie.ro
=====================================
Generează articole SEO cu linkuri interne spre produse.
Folosește GPT-4o-mini pentru conținut și API Extended pentru produse.

Utilizare:
  python3 blog_generator.py --keyword "rochii cununie civila 2026"
  python3 blog_generator.py --keyword "rochii cununie civila 2026" --publish
  python3 blog_generator.py --keyword "rochii cununie civila 2026" --dry-run
  python3 blog_generator.py --list-keywords
  python3 blog_generator.py --batch 5

Cerințe:
  pip install openai requests openpyxl
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime

# ============================================================
# CONFIGURARE
# ============================================================

# Citește din .env sau setează direct


def load_env(path=None):
    """Încarcă variabilele din .env"""
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
    print("⚠️ No .env found, using environment variables")


load_env()

EJOLIE_API_KEY = os.environ.get("EJOLIE_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
EXTENDED_SESSION = os.environ.get(
    "EXTENDED_SESSION", "")  # Cookie session pentru admin

EJOLIE_API_URL = "https://ejolie.ro/api/"
EJOLIE_SITE_URL = "https://www.ejolie.ro"
BLOG_POST_URL = f"{EJOLIE_SITE_URL}/manager/blog/adauga_articol/0"

GPT_MODEL = "gpt-4o-mini"
MAX_ARTICLE_WORDS = 2000
MIN_PRODUCTS_IN_ARTICLE = 3
MAX_PRODUCTS_IN_ARTICLE = 8

# ============================================================
# KEYWORDS DATABASE
# ============================================================

KEYWORDS_DB = [
    # Nuntă & Cununie
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
    {"keyword": "rochii elegante nunta biserica",
        "category": "nunta", "priority": 3},
    {"keyword": "ce culori se poarta la nunta 2026",
        "category": "nunta", "priority": 2},

    # Ghiduri Stil
    {"keyword": "rochii elegante femei 40 ani", "category": "stil", "priority": 1},
    {"keyword": "rochii elegante femei 50 ani", "category": "stil", "priority": 1},
    {"keyword": "rochii pentru femei plinute elegante",
        "category": "stil", "priority": 1},
    {"keyword": "cum alegi rochia perfecta pentru silueta ta",
        "category": "stil", "priority": 2},
    {"keyword": "rochii de seara lungi elegante",
        "category": "stil", "priority": 2},
    {"keyword": "rochii de ocazie midi", "category": "stil", "priority": 3},
    {"keyword": "ce rochie port la botez 2026", "category": "stil", "priority": 1},

    # Tendinte
    {"keyword": "tendinte rochii elegante 2026",
        "category": "tendinte", "priority": 1},
    {"keyword": "rochii de seara primavara 2026",
        "category": "tendinte", "priority": 2},
    {"keyword": "culori la moda rochii 2026",
        "category": "tendinte", "priority": 2},
    {"keyword": "rochii de ocazie vara 2026",
        "category": "tendinte", "priority": 2},
    {"keyword": "rochii revelion 2026 2027",
        "category": "tendinte", "priority": 3},

    # Categorii SEO
    {"keyword": "rochii lungi de ocazie online romania",
        "category": "categorie", "priority": 2},
    {"keyword": "rochii elegante de seara preturi bune",
        "category": "categorie", "priority": 2},
    {"keyword": "rochii de ocazie ieftine romania",
        "category": "categorie", "priority": 3},
    {"keyword": "rochii elegante din voal satin",
        "category": "categorie", "priority": 3},
    {"keyword": "rochii din satin pentru evenimente",
        "category": "categorie", "priority": 3},

    # Intrebari
    {"keyword": "ce rochie sa port la un eveniment elegant",
        "category": "intrebari", "priority": 2},
    {"keyword": "cum aleg lungimea rochiei pentru nunta",
        "category": "intrebari", "priority": 3},
    {"keyword": "ce material e cel mai bun pentru rochii de seara",
        "category": "intrebari", "priority": 3},
    {"keyword": "se poate purta negru la nunta",
        "category": "intrebari", "priority": 2},
    {"keyword": "cum ma imbrac la cununie civila",
        "category": "intrebari", "priority": 1},
]


# ============================================================
# FUNCȚII API EJOLIE
# ============================================================

def fetch_products(search_terms=None, category=None, limit=30):
    """Ia produse din API ejolie.ro"""
    url = f"{EJOLIE_API_URL}?produse&apikey={EJOLIE_API_KEY}"
    if category:
        url += f"&categorie={category}"

    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0"})
        data = json.loads(urllib.request.urlopen(
            req, timeout=30).read().decode("utf-8"))
    except Exception as e:
        print(f"⚠️ API Error: {e}")
        return []

    products = []
    for pid, prod in data.items():
        if not isinstance(prod, dict):
            continue

        name = prod.get("nume", "")
        slug = prod.get("link_public", "")
        price = prod.get("pret", "0")
        images = prod.get("imagini", {})
        first_img = ""
        if isinstance(images, dict):
            for img_id, img_data in images.items():
                if isinstance(img_data, dict):
                    first_img = img_data.get("imagine", "")
                    break

        # Stoc
        options = prod.get("optiuni", {})
        total_stock = 0
        sizes = []
        if isinstance(options, dict):
            for oid, opt in options.items():
                if isinstance(opt, dict):
                    stoc = int(opt.get("stoc_fizic", 0))
                    total_stock += stoc
                    if stoc > 0:
                        sizes.append(opt.get("nume", ""))

        # Brand
        brand_data = prod.get("brand", {})
        brand = brand_data.get("nume", "Ejolie") if isinstance(
            brand_data, dict) else "Ejolie"

        products.append({
            "id": pid,
            "name": name,
            "slug": slug,
            "price": price,
            "image": first_img,
            "stock": total_stock,
            "sizes": sizes,
            "brand": brand,
            "url": f"{EJOLIE_SITE_URL}/{slug}" if slug else "",
        })

    # Filtrare cu stoc
    in_stock = [p for p in products if p["stock"] > 0]

    # Filtrare pe search terms
    if search_terms and in_stock:
        terms = [t.lower() for t in search_terms]
        scored = []
        for p in in_stock:
            name_lower = p["name"].lower()
            score = sum(1 for t in terms if t in name_lower)
            scored.append((score, p))
        scored.sort(key=lambda x: -x[0])
        # Ia produse cu cel puțin 1 match, sau top produse
        matched = [p for s, p in scored if s > 0]
        if len(matched) >= MIN_PRODUCTS_IN_ARTICLE:
            return matched[:limit]

    return in_stock[:limit]


def get_relevant_products(keyword, limit=MAX_PRODUCTS_IN_ARTICLE):
    """Selectează produse relevante pentru keyword"""
    # Extrage termeni de căutare din keyword
    stop_words = {"de", "la", "in", "din", "pentru", "ce", "cum", "sa", "port",
                  "alegi", "aleg", "se", "pot", "poate", "mai", "cel", "cea",
                  "un", "o", "e", "si", "sau", "2026", "2025", "ani"}

    terms = [w for w in keyword.lower().split(
    ) if w not in stop_words and len(w) > 2]

    print(f"🔍 Caut produse pentru: {terms}")
    products = fetch_products(search_terms=terms)

    if len(products) < MIN_PRODUCTS_IN_ARTICLE:
        print(
            f"⚠️ Doar {len(products)} produse cu stoc. Iau toate produsele...")
        products = fetch_products()

    # Scorare pe relevanță
    scored = []
    for p in products:
        name = p["name"].lower()
        score = 0
        for t in terms:
            if t in name:
                score += 2
        # Bonus pentru preț > 500 (produse premium)
        try:
            if float(p["price"]) > 500:
                score += 1
        except:
            pass
        scored.append((score, p))

    scored.sort(key=lambda x: -x[0])
    result = [p for _, p in scored[:limit]]

    print(f"✅ {len(result)} produse selectate")
    for p in result:
        print(f"   • {p['name'][:50]} - {p['price']} lei")

    return result


# ============================================================
# GENERARE CONȚINUT CU GPT
# ============================================================

def generate_article(keyword, products):
    """Generează articol HTML cu GPT"""

    # Pregătește lista de produse pentru prompt
    products_text = ""
    for i, p in enumerate(products, 1):
        products_text += f"""
Produs {i}:
- Nume: {p['name']}
- Preț: {p['price']} lei
- URL: {p['url']}
- Imagine: {EJOLIE_SITE_URL}/continut/upload/{p['image']}
- Mărimi disponibile: {', '.join(p['sizes'][:5])}
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

CERINȚE LINKURI INTERNE:
Include EXACT aceste produse cu linkuri în articol, natural integrate în text:
{products_text}

Format link produs: <a href="URL_PRODUS" title="NUME_PRODUS">text ancoră natural</a>
Inserează 1-2 produse per secțiune, cu text de recomandare natural.
Opțional: include imagini produse cu format: <img src="URL_IMAGINE" alt="DESCRIERE" style="max-width:300px;margin:10px;" />

CERINȚE TEHNICE:
- Output STRICT în format JSON cu aceste câmpuri:
{{
    "title": "Titlu articol H1",
    "meta_title": "Meta title SEO (max 60 char)",
    "meta_description": "Meta description (max 155 char)",
    "meta_keywords": "keyword1, keyword2, keyword3",
    "slug": "url-slug-seo",
    "short_description": "Descriere scurtă 150-200 caractere pentru preview",
    "content_html": "<h2>...</h2><p>...</p>... conținut HTML complet"
}}

IMPORTANT:
- content_html trebuie să fie HTML valid cu <h2>, <h3>, <p>, <ul>, <li>, <a>, <strong>, <em>
- NU include tag-ul <h1> în content_html (titlul vine separat)
- NU include <html>, <head>, <body>
- Include linkuri spre produse OBLIGATORIU
- Scrie EXCLUSIV în română cu diacritice
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
            max_tokens=4000,
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)

        tokens_used = response.usage.total_tokens
        cost = tokens_used * 0.00000015  # gpt-4o-mini pricing approx
        print(f"✅ Articol generat! Tokens: {tokens_used}, Cost: ~${cost:.4f}")

        return result

    except Exception as e:
        print(f"❌ GPT Error: {e}")
        return None


# ============================================================
# PUBLICARE ÎN EXTENDED BLOG
# ============================================================

def publish_article(article_data, category=1, status="draft"):
    """Publică articolul în Extended Blog via POST"""

    if not EXTENDED_SESSION:
        print("⚠️ EXTENDED_SESSION cookie nu e setat. Articolul va fi salvat local.")
        return save_article_local(article_data)

    form_data = {
        "trimite": "value",
        "camp_nume": article_data["title"],
        "camp_data": datetime.now().strftime("%d-%m-%Y"),
        "camp_descriere": article_data.get("short_description", ""),
        "camp_continut": article_data["content_html"],
        "camp_categorie": str(category),
        "camp_linkpublic": article_data["slug"],
        "camp_title": article_data["meta_title"],
        "camp_keywords": article_data["meta_keywords"],
        "camp_description": article_data["meta_description"],
        "id_autosave": "",
    }

    encoded = urllib.parse.urlencode(form_data).encode("utf-8")

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/x-www-form-urlencoded",
        "Cookie": EXTENDED_SESSION,
        "Referer": f"{EJOLIE_SITE_URL}/manager/blog",
    }

    try:
        req = urllib.request.Request(
            BLOG_POST_URL, data=encoded, headers=headers, method="POST")
        resp = urllib.request.urlopen(req, timeout=30)

        if resp.status == 200:
            print(f"✅ Articol publicat ca {status}!")
            print(f"   URL: {EJOLIE_SITE_URL}/blog/{article_data['slug']}")
            return True
        else:
            print(f"❌ Error: HTTP {resp.status}")
            return save_article_local(article_data)

    except Exception as e:
        print(f"❌ POST Error: {e}")
        return save_article_local(article_data)


def save_article_local(article_data):
    """Salvează articolul local ca HTML și JSON"""
    slug = article_data.get("slug", "articol")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Salvează JSON
    json_path = os.path.expanduser(f"~/blog_articles/{slug}.json")
    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(article_data, f, ensure_ascii=False, indent=2)

    # Salvează HTML preview
    html_path = os.path.expanduser(f"~/blog_articles/{slug}.html")
    html_content = f"""<!DOCTYPE html>
<html lang="ro">
<head>
    <meta charset="UTF-8">
    <title>{article_data['meta_title']}</title>
    <meta name="description" content="{article_data['meta_description']}">
    <meta name="keywords" content="{article_data['meta_keywords']}">
    <style>
        body {{ font-family: Georgia, serif; max-width: 800px; margin: 40px auto; padding: 0 20px; color: #333; line-height: 1.7; }}
        h1 {{ color: #c8a165; border-bottom: 2px solid #c8a165; padding-bottom: 10px; }}
        h2 {{ color: #333; margin-top: 30px; }}
        h3 {{ color: #555; }}
        a {{ color: #c8a165; text-decoration: none; font-weight: bold; }}
        a:hover {{ text-decoration: underline; }}
        img {{ max-width: 100%; height: auto; border-radius: 8px; }}
        .meta {{ background: #f5f5f5; padding: 15px; border-radius: 8px; margin-bottom: 20px; font-size: 14px; }}
        .meta strong {{ color: #c8a165; }}
    </style>
</head>
<body>
    <div class="meta">
        <strong>SEO Title:</strong> {article_data['meta_title']}<br>
        <strong>Meta Description:</strong> {article_data['meta_description']}<br>
        <strong>Keywords:</strong> {article_data['meta_keywords']}<br>
        <strong>Slug:</strong> {article_data['slug']}<br>
        <strong>Short Description:</strong> {article_data.get('short_description', '')}
    </div>
    <h1>{article_data['title']}</h1>
    {article_data['content_html']}
</body>
</html>"""

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"💾 Salvat local:")
    print(f"   JSON: {json_path}")
    print(f"   HTML: {html_path}")

    return json_path


# ============================================================
# PUBLICARE VIA BROWSER (CLAUDE IN CHROME)
# ============================================================

def generate_browser_js(article_data, category=1):
    """Generează JavaScript pentru publicare din consolă browser"""

    # Escape content for JS
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
    
    const resp = await fetch('/manager/blog/adauga_articol/0', {{
        method: 'POST',
        body: formData,
        credentials: 'same-origin'
    }});
    
    console.log('Status:', resp.status);
    if (resp.ok) {{
        console.log('✅ Articol creat! Slug: {slug}');
    }} else {{
        console.log('❌ Error:', resp.statusText);
    }}
}})();"""

    js_path = os.path.expanduser(f"~/blog_articles/{slug}_publish.js")
    os.makedirs(os.path.dirname(js_path), exist_ok=True)
    with open(js_path, "w", encoding="utf-8") as f:
        f.write(js)

    print(f"📋 JavaScript pentru browser salvat: {js_path}")
    return js_path


# ============================================================
# MAIN
# ============================================================

def process_keyword(keyword, publish=False, dry_run=False):
    """Pipeline complet pentru un keyword"""

    print(f"\n{'='*60}")
    print(f"📝 KEYWORD: {keyword}")
    print(f"{'='*60}")

    # 1. Ia produse relevante
    products = get_relevant_products(keyword)

    if not products:
        print("❌ Nu s-au găsit produse. Skip.")
        return None

    if dry_run:
        print("🏃 DRY RUN - nu generez articol")
        return None

    # 2. Generează articol
    article = generate_article(keyword, products)

    if not article:
        print("❌ Generarea articolului a eșuat.")
        return None

    # 3. Afișează preview
    print(f"\n📰 PREVIEW:")
    print(f"   Titlu: {article['title']}")
    print(f"   SEO Title: {article['meta_title']}")
    print(f"   Meta Desc: {article['meta_description']}")
    print(f"   Slug: {article['slug']}")
    print(f"   Conținut: {len(article['content_html'])} caractere HTML")

    # 4. Salvează local
    json_path = save_article_local(article)

    # 5. Generează JS pentru publicare prin browser
    js_path = generate_browser_js(article)

    # 6. Publică dacă cerut
    if publish:
        publish_article(article)

    return article


def main():
    parser = argparse.ArgumentParser(
        description="Blog Auto-Generator pentru ejolie.ro")
    parser.add_argument("--keyword", "-k", help="Keyword pentru articol")
    parser.add_argument("--publish", "-p", action="store_true",
                        help="Publică direct în Extended")
    parser.add_argument("--dry-run", "-d", action="store_true",
                        help="Doar arată produsele, nu genera")
    parser.add_argument("--list-keywords", "-l",
                        action="store_true", help="Arată toate keywords")
    parser.add_argument("--batch", "-b", type=int,
                        help="Generează N articole (prioritate 1 first)")
    parser.add_argument("--category", "-c", type=int, default=1,
                        help="Categorie blog (1=Blog, 2=Lifestyle)")

    args = parser.parse_args()

    # Verificări
    if not EJOLIE_API_KEY:
        print("❌ EJOLIE_API_KEY nu e setat! Adaugă în .env sau export.")
        sys.exit(1)
    if not OPENAI_API_KEY and not args.list_keywords and not args.dry_run:
        print("❌ OPENAI_API_KEY nu e setat! Adaugă în .env sau export.")
        sys.exit(1)

    if args.list_keywords:
        print("\n📋 KEYWORDS DATABASE:")
        print(f"{'Prio':>4} | {'Categorie':<12} | Keyword")
        print("-" * 70)
        for kw in sorted(KEYWORDS_DB, key=lambda x: (x["priority"], x["category"])):
            print(
                f"  {kw['priority']}  | {kw['category']:<12} | {kw['keyword']}")
        print(f"\nTotal: {len(KEYWORDS_DB)} keywords")
        return

    if args.batch:
        # Generează N articole, prioritate 1 first
        keywords = sorted(KEYWORDS_DB, key=lambda x: x["priority"])[
            :args.batch]
        print(f"\n🚀 BATCH MODE: Generez {len(keywords)} articole")
        for kw in keywords:
            process_keyword(
                kw["keyword"], publish=args.publish, dry_run=args.dry_run)
            if not args.dry_run:
                time.sleep(2)  # Pauză între articole
        return

    if args.keyword:
        process_keyword(args.keyword, publish=args.publish,
                        dry_run=args.dry_run)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
