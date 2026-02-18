#!/usr/bin/env python3
"""
Blog Auto-Publisher for ejolie.ro
Runs via cron: generates article + DALL-E images + posts to Extended as draft
Sends Telegram notification when done.

Cron: 0 8 * * 1,4  (Luni și Joi la 08:00)
"""
import os
import sys
import json
import requests
from datetime import datetime

# ── Paths ──
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BLOG_GEN = os.path.join(SCRIPT_DIR, "blog_generator.py")
ARTICLES_DIR = os.path.expanduser("~/blog_articles")
PUBLISHED_LOG = os.path.join(ARTICLES_DIR, "published.json")

# ── Load env ──
env_paths = [
    os.path.join(SCRIPT_DIR, ".env"),
    os.path.expanduser("~/ejolie-openclaw-agent/ejolie-sales/.env"),
    os.path.expanduser("~/.env"),
]
for p in env_paths:
    if os.path.exists(p):
        with open(p) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
        break

EXTENDED_EMAIL = os.environ.get("EXTENDED_EMAIL", "")
EXTENDED_PASSWORD = os.environ.get("EXTENDED_PASSWORD", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# ── Keywords pool ──
KEYWORDS = [
    "rochii pentru invitate la nunta 2026",
    "rochii cununie civila 2026",
    "rochii elegante femei 40+",
    "rochii nasa nunta 2026",
    "rochii nasa botez 2026",
    "rochii soacra nunta",
    "rochii invitate nunta",
    "rochii domnisoare de onoare",
    "rochii de ocazie lungi",
    "rochii de seara elegante",
    "ce rochie port la nunta ghid complet",
    "ce culori se poarta la nunti in 2026",
    "cum aleg rochia de cununie civila",
    "rochii pentru femei plinute la nunta",
    "rochii elegante marimi mari",
    "ce rochie port la botez",
    "cum ma imbrac la nunta vara 2026",
    "cum ma imbrac la nunta iarna",
    "rochii de seara vs rochii de ocazie diferente",
    "cum aleg rochia in functie de silueta",
    "rochii lungi din voal pentru nunta",
    "rochii din dantela pentru ocazii speciale",
    "rochii elegante din satin 2026",
    "rochii tip sirena pentru nunta",
    "ce accesorii port cu rochia de ocazie",
    "rochii pentru petrecere de logodna",
    "cat dau la nunta sau botez in 2026",
    "tendinte rochii elegante primavara vara 2026",
    "rochii office elegante pentru birou",
    "rochii pentru revelion 2026",
]


def load_published():
    if os.path.exists(PUBLISHED_LOG):
        with open(PUBLISHED_LOG, "r") as f:
            return json.load(f)
    return []


def save_published(published):
    os.makedirs(ARTICLES_DIR, exist_ok=True)
    with open(PUBLISHED_LOG, "w") as f:
        json.dump(published, f, ensure_ascii=False, indent=2)


def get_next_keyword():
    published = load_published()
    published_kws = [p["keyword"] for p in published]
    available = [kw for kw in KEYWORDS if kw not in published_kws]
    if not available:
        print("⚠️ Toate keyword-urile au fost publicate!")
        return None
    return available[0]


def login_extended():
    s = requests.Session()
    s.get("https://www.ejolie.ro/manager/login", timeout=30)
    r = s.post(
        "https://www.ejolie.ro/manager/login/autentificare",
        data={"utilizator": EXTENDED_EMAIL, "parola": EXTENDED_PASSWORD},
        allow_redirects=False,
        timeout=30,
    )
    if r.status_code == 302 and "dashboard" in r.headers.get("Location", ""):
        print("✅ Login OK")
        return s
    print(f"❌ Login FAILED: {r.status_code}")
    return None


def post_article(session, article_data, cover_bytes=None):
    """POST article to Extended blog with optional cover image"""
    data = {
        "trimite": "value",
        "camp_nume": article_data["title"],
        "camp_data": datetime.now().strftime("%d-%m-%Y"),
        "camp_descriere": article_data.get("short_description", article_data.get("meta_description", "")),
        "camp_continut": article_data["content_html"],
        "camp_categorie": "1",
        "camp_linkpublic": article_data["slug"],
        "camp_title": article_data["meta_title"],
        "camp_keywords": article_data["meta_keywords"],
        "camp_description": article_data["meta_description"],
        "id_autosave": "",
    }

    files = None
    if cover_bytes:
        files = {
            "imagine": (f"{article_data['slug']}-coperta.webp", cover_bytes, "image/webp"),
        }

    r = session.post(
        "https://www.ejolie.ro/manager/blog/adauga_articol/0",
        data=data,
        files=files,
        timeout=60,
    )
    return r.status_code == 200


def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram not configured")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID,
                  "text": message, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception as e:
        print(f"⚠️ Telegram error: {e}")


def main():
    print(f"\n{'='*50}")
    print(
        f"📝 BLOG AUTO-PUBLISHER - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}")

    # 1. Pick keyword
    keyword = get_next_keyword()
    if not keyword:
        send_telegram("⚠️ Blog: Toate keyword-urile au fost publicate!")
        return

    print(f"\n📌 Keyword: {keyword}")

    # 2. Generate article
    print("\n1️⃣ Generez articol...")
    import subprocess
    result = subprocess.run(
        [sys.executable, BLOG_GEN, "--keyword", keyword],
        capture_output=True, text=True, timeout=120,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"❌ Generator error:\n{result.stderr}")
        send_telegram(
            f"❌ Blog generator FAILED: {keyword}\n{result.stderr[:200]}")
        return

    # 3. Load generated article
    slug = ""
    for line in result.stdout.split("\n"):
        if "Slug:" in line:
            slug = line.split("Slug:")[-1].strip()

    json_path = os.path.join(ARTICLES_DIR, f"{slug}.json")
    if not os.path.exists(json_path):
        print(f"❌ JSON not found: {json_path}")
        send_telegram(f"❌ Blog: JSON not found for {keyword}")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        article = json.load(f)

    print(f"  ✅ Articol: {article['title']}")
    print(f"  📝 Content: {len(article['content_html'])} chars")

    # 4. Login
    print("\n2️⃣ Login Extended...")
    session = login_extended()
    if not session:
        send_telegram("❌ Blog: Login Extended FAILED")
        return

    # 5. Generate images with DALL-E
    cover_bytes = None
    print("\n3️⃣ Generez imagini DALL-E...")
    try:
        from blog_images import generate_blog_images, inject_images_into_html, inject_product_images

        images = generate_blog_images(keyword, session, num_inline=2)

        # Inject inline DALL-E images into HTML
        if images["inline_images"]:
            article["content_html"] = inject_images_into_html(
                article["content_html"], images["inline_images"]
            )
            print(
                f"  ✅ {len(images['inline_images'])} imagini inline injectate")

        # Inject real product images next to product links
        try:
            import json as _json
            cache_path = os.path.expanduser("~/blog_products.json")
            if os.path.exists(cache_path):
                with open(cache_path, "r") as _f:
                    all_products = _json.load(_f)
                # article["content_html"] = inject_product_images(
                #     article["content_html"], all_products, article_slug=slug
                # )
                # print(f"  ✅ Poze produse reale injectate")
        except Exception as e:
            print(f"  ⚠️ Product images error: {e}")

        # Cover image bytes for form upload
        cover_bytes = images.get("cover_bytes")
        if cover_bytes:
            print(f"  ✅ Copertă portret: {len(cover_bytes)//1024}KB")

    except ImportError:
        print("  ⚠️ blog_images.py not found, skipping images")
    except Exception as e:
        print(f"  ⚠️ Image generation error: {e}")
        print("  📝 Continuă fără imagini...")

    # 6. Post article
    print("\n4️⃣ Postez pe Extended...")
    success = post_article(session, article, cover_bytes=cover_bytes)
    if success:
        print(f"  ✅ Articol postat!")

        # 7. Log published
        published = load_published()
        published.append({
            "keyword": keyword,
            "title": article["title"],
            "slug": slug,
            "date": datetime.now().isoformat(),
            "url": f"https://www.ejolie.ro/blog/{slug}",
            "has_images": cover_bytes is not None,
        })
        save_published(published)

        # 8. Update JSON with images
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(article, f, ensure_ascii=False, indent=2)

        # 9. Notify
        img_status = "cu imagini DALL-E" if cover_bytes else "fara imagini"
        msg = (
            f"✅ <b>Articol blog nou</b>\n\n"
            f"📌 <b>{article['title']}</b>\n"
            f"🔑 Keyword: {keyword}\n"
            f"📎 Slug: {slug}\n"
            f"📊 {len(article['content_html'])} caractere\n"
            f"🎨 {img_status}\n\n"
            f"👉 Verifică în admin:\n"
            f"https://www.ejolie.ro/manager/blog"
        )
        send_telegram(msg)
        print(f"\n✅ DONE! Verifică în admin și activează.")
    else:
        print(f"  ❌ POST failed!")
        send_telegram(f"❌ Blog: POST failed for {keyword}")


if __name__ == "__main__":
    main()
