#!/usr/bin/env python3
"""
Blog Image Generator for ejolie.ro
===================================
Generates images with DALL-E 3 and uploads to Extended CMS via elfinder.

Usage:
  from blog_images import generate_blog_images
  images = generate_blog_images(keyword, session, num_images=3)

Requires:
  pip install openai requests Pillow
"""

import os
import io
import re
import json
import time
import base64
import requests
from datetime import datetime

# ── Config ──
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
ELFINDER_URL = "https://www.ejolie.ro/manager/application/views/platforma/module/elfinder/php/connector.php"
ELFINDER_PARAMS = "?url=https://www.ejolie.ro/continut/upload"
BLOG_FOLDER_HASH = "l1_QmxvZw"  # elfinder hash for /continut/upload/Blog/
IMAGE_BASE_URL = "https://www.ejolie.ro/continut/upload/Blog"
IMAGES_LOG = os.path.expanduser("~/blog_articles/images_log.json")


def load_images_log():
    """Track all generated images to avoid reuse"""
    if os.path.exists(IMAGES_LOG):
        with open(IMAGES_LOG, "r") as f:
            return json.load(f)
    return {}


def save_images_log(log):
    os.makedirs(os.path.dirname(IMAGES_LOG), exist_ok=True)
    with open(IMAGES_LOG, "w") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def get_used_product_images():
    """Get set of product image URLs already used in previous articles"""
    log = load_images_log()
    used = set()
    for article_slug, data in log.items():
        for img_url in data.get("product_images", []):
            used.add(img_url)
    return used


# DALL-E prompt templates for fashion blog
COVER_PROMPT_TEMPLATE = """Professional fashion photography style image for a Romanian fashion blog article about "{keyword}". 
Show an elegant woman wearing a beautiful {style} dress in {color} tones, in a {setting} setting. 
The image should feel luxurious, aspirational, and modern. 
Style: editorial fashion photography, soft natural lighting, shallow depth of field.
DO NOT include any text, watermarks, logos, or words in the image."""

INLINE_PROMPTS = [
    """Elegant fashion flat lay: a beautiful {style} dress with accessories (shoes, clutch bag, jewelry) arranged on a neutral background. 
Style: minimalist product photography, soft shadows, pastel tones. 
NO text, watermarks, or logos.""",

    """Fashion mood board style image showing {color} color palette with fabric swatches, flowers, and elegant accessories. 
Style: lifestyle photography, soft focus, romantic aesthetic. 
NO text, watermarks, or logos.""",

    """Beautiful woman from behind walking in a {setting}, wearing an elegant {style} dress. 
Style: candid editorial photography, golden hour lighting, dreamy atmosphere. 
NO text, watermarks, or logos.""",
]

# Keyword to visual mapping
KEYWORD_VISUALS = {
    "nunta": {"style": "flowing evening", "color": "champagne and gold", "setting": "garden wedding venue"},
    "cununie": {"style": "sophisticated midi", "color": "ivory and blush pink", "setting": "elegant city hall"},
    "botez": {"style": "classy knee-length", "color": "pastel blue and cream", "setting": "sunlit church courtyard"},
    "nasa": {"style": "regal floor-length", "color": "emerald and silver", "setting": "luxurious ballroom"},
    "soacra": {"style": "refined A-line", "color": "burgundy and navy", "setting": "elegant restaurant"},
    "seara": {"style": "glamorous evening", "color": "deep red and black", "setting": "upscale gala venue"},
    "ocazie": {"style": "stunning cocktail", "color": "jewel tones", "setting": "sophisticated event space"},
    "elegante": {"style": "timeless elegant", "color": "neutral and gold", "setting": "modern luxury interior"},
    "office": {"style": "professional sheath", "color": "navy and white", "setting": "modern office lobby"},
    "revelion": {"style": "sparkling party", "color": "midnight blue and silver sequins", "setting": "New Year's Eve celebration"},
    "plinute": {"style": "flattering wrap", "color": "rich jewel tones", "setting": "beautiful terrace"},
    "silueta": {"style": "body-flattering", "color": "classic monochrome", "setting": "minimalist studio"},
    "dantela": {"style": "lace-detailed", "color": "soft blush and white", "setting": "romantic garden"},
    "voal": {"style": "flowing chiffon", "color": "soft pastels", "setting": "seaside venue"},
    "satin": {"style": "sleek satin", "color": "rich champagne", "setting": "art deco interior"},
    "sirena": {"style": "mermaid silhouette", "color": "classic black and gold", "setting": "grand staircase"},
}

DEFAULT_VISUAL = {"style": "elegant",
                  "color": "rich jewel tones", "setting": "luxurious venue"}


def get_visuals_for_keyword(keyword):
    """Match keyword to visual style"""
    keyword_lower = keyword.lower()
    for key, visuals in KEYWORD_VISUALS.items():
        if key in keyword_lower:
            return visuals
    return DEFAULT_VISUAL


def generate_dalle_image(prompt, size="1024x1024"):
    """Generate image with DALL-E 3, return bytes"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}",
    }
    body = {
        "model": "dall-e-3",
        "prompt": prompt,
        "n": 1,
        "size": size,
        "quality": "standard",
        "response_format": "b64_json",
    }

    resp = requests.post(
        "https://api.openai.com/v1/images/generations",
        headers=headers,
        json=body,
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()

    b64_data = data["data"][0]["b64_json"]
    revised_prompt = data["data"][0].get("revised_prompt", "")
    image_bytes = base64.b64decode(b64_data)

    return image_bytes, revised_prompt


def generate_gemini_image(prompt, size="1024x1024"):
    """Generate image with Gemini Imagen, return bytes"""
    if not GEMINI_API_KEY:
        raise Exception("GEMINI_API_KEY not set")

    # Map DALL-E sizes to aspect ratios
    aspect = "1:1"
    if "1792x1024" in size:
        aspect = "16:9"
    elif "1024x1792" in size:
        aspect = "9:16"

    body = {
        "instances": [{"prompt": prompt}],
        "parameters": {
            "sampleCount": 1,
            "aspectRatio": aspect,
        }
    }
    resp = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/imagen-4.0-generate-001:predict?key={GEMINI_API_KEY}",
        headers={"Content-Type": "application/json"},
        json=body,
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    b64_data = data["predictions"][0]["bytesBase64Encoded"]
    image_bytes = base64.b64decode(b64_data)
    return image_bytes, prompt


def convert_to_webp(image_bytes, quality=85, min_width=1200):
    """Convert image to WebP format, upscale if needed"""
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes))
        # Upscale if too small
        if img.width < min_width:
            ratio = min_width / img.width
            new_h = int(img.height * ratio)
            img = img.resize((min_width, new_h), Image.LANCZOS)
        output = io.BytesIO()
        img.save(output, format="WEBP", quality=quality)
        return output.getvalue()
    except ImportError:
        print("  ⚠️ Pillow not installed, using PNG")
        return image_bytes


def upload_to_elfinder(session, image_bytes, filename):
    """Upload image to Extended elfinder Blog folder"""
    files = {
        "upload[]": (filename, io.BytesIO(image_bytes), "image/webp" if filename.endswith(".webp") else "image/png"),
    }
    data = {
        "cmd": "upload",
        "target": BLOG_FOLDER_HASH,
    }

    resp = session.post(
        ELFINDER_URL + ELFINDER_PARAMS,
        data=data,
        files=files,
        timeout=60,
    )
    resp.raise_for_status()
    result = resp.json()

    added = result.get("added", [])
    if added:
        return f"{IMAGE_BASE_URL}/{added[0]['name']}"

    raise Exception(f"Upload failed: {json.dumps(result)}")


def slugify(text):
    """Generate URL-friendly slug"""
    slug = text.lower()
    for old, new in {"ă": "a", "â": "a", "î": "i", "ș": "s", "ț": "t"}.items():
        slug = slug.replace(old, new)
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s]+', '-', slug)
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug[:50]


def generate_blog_images(keyword, session, num_inline=2):
    """
    Generate cover + inline images for a blog article.

    Args:
        keyword: Article keyword (e.g. "rochii cununie civila 2026")
        session: requests.Session with Extended admin login
        num_inline: Number of inline images (1-3)

    Returns:
        dict with:
            cover_url: URL of cover image
            inline_images: list of {url, alt, position} dicts
    """
    visuals = get_visuals_for_keyword(keyword)
    slug = slugify(keyword)
    timestamp = datetime.now().strftime("%Y%m%d")

    result = {
        "cover_url": "",
        "cover_bytes": None,
        "inline_images": [],
    }

    # Load log for uniqueness
    images_log = load_images_log()
    dalle_urls = []

    # 1. Generate cover image
    print(f"  🎨 Generez copertă Gemini Imagen (portret)...", flush=True)
    cover_prompt = COVER_PROMPT_TEMPLATE.format(keyword=keyword, **visuals)
    # Add uniqueness: include slug in prompt
    cover_prompt += f"\nUnique scene variation for: {slug}"

    try:
        try:
            img_bytes, revised = generate_gemini_image(
                cover_prompt, size="1024x1792")
        except Exception as gemini_err:
            print(f"  ⚠️ Gemini cover error: {gemini_err}")
            print(f"  🔄 Fallback DALL-E...")
            img_bytes, revised = generate_dalle_image(
                cover_prompt, size="1024x1792")
        webp_bytes = convert_to_webp(img_bytes, quality=85)

        cover_filename = f"{slug}-coperta-{timestamp}.webp"
        cover_url = upload_to_elfinder(session, webp_bytes, cover_filename)

        result["cover_url"] = cover_url
        result["cover_bytes"] = webp_bytes  # For form upload as "imagine"
        dalle_urls.append(cover_url)
        print(f"  ✅ Copertă: {cover_url} ({len(webp_bytes)//1024}KB)")
    except Exception as e:
        print(f"  ❌ Copertă DALL-E error: {e}")

    # 2. Generate inline images
    for i in range(min(num_inline, len(INLINE_PROMPTS))):
        print(f"  🎨 Generez imagine Gemini inline {i+1}...", flush=True)
        prompt = INLINE_PROMPTS[i].format(**visuals)
        # Add uniqueness
        prompt += f"\nUnique variation {i+1} for article: {slug}"

        try:
            try:
                img_bytes, revised = generate_dalle_image(
                    prompt, size="1024x1024")
            except Exception as dalle_err:
                print(f"  ⚠️ DALL-E inline error: {dalle_err}")
                print(f"  🔄 Fallback Gemini Imagen...")
                img_bytes, revised = generate_gemini_image(
                    prompt, size="1024x1024")
            webp_bytes = convert_to_webp(img_bytes, quality=80)

            inline_filename = f"{slug}-img{i+1}-{timestamp}.webp"
            inline_url = upload_to_elfinder(
                session, webp_bytes, inline_filename)

            alt_texts = [
                f"Rochii elegante pentru {keyword.split()[1] if len(keyword.split()) > 1 else 'ocazie'} - ejolie.ro",
                f"Accesorii și ținute pentru {keyword.split()[-1] if keyword.split() else 'evenimente'} - ejolie.ro",
                f"Inspirație modă {keyword.split()[0]} elegante - ejolie.ro",
            ]

            result["inline_images"].append({
                "url": inline_url,
                "alt": alt_texts[i % len(alt_texts)],
                "position": i,
            })
            dalle_urls.append(inline_url)
            print(
                f"  ✅ Inline {i+1}: {inline_url} ({len(webp_bytes)//1024}KB)")

            time.sleep(2)

        except Exception as e:
            print(f"  ❌ Inline {i+1} DALL-E error: {e}")

    # Save DALL-E images to log
    images_log[slug] = images_log.get(slug, {})
    images_log[slug]["dalle_images"] = dalle_urls
    images_log[slug]["date"] = datetime.now().isoformat()
    save_images_log(images_log)

    return result


def inject_images_into_html(content_html, inline_images):
    """Insert inline images into article HTML at appropriate positions"""
    if not inline_images:
        return content_html

    # Split content by H2 sections
    sections = re.split(r'(<h2[^>]*>)', content_html)

    if len(sections) < 3:
        for img in inline_images:
            content_html += f'\n<p style="text-align:center;"><img src="{img["url"]}" alt="{img["alt"]}" style="max-width:100%;border-radius:8px;margin:20px 0;" /></p>\n'
        return content_html

    insert_positions = [3, 5, 7]

    for img_idx, img in enumerate(inline_images):
        pos = insert_positions[img_idx % len(insert_positions)]
        if pos < len(sections):
            img_html = f'\n<p style="text-align:center;"><img src="{img["url"]}" alt="{img["alt"]}" style="max-width:100%;border-radius:8px;margin:20px 0;" /></p>\n'
            sections[pos] = sections[pos] + img_html

    return ''.join(sections)


def inject_product_images(content_html, products, article_slug=""):
    """
    Insert real product images next to their links in the article.
    Finds <a href="product_url"> and adds <img> after the paragraph.
    Skips images already used in previous articles.
    """
    if not products:
        return content_html

    # Load previously used images
    used_images = get_used_product_images()

    # Build URL→image map from products that have images
    url_to_img = {}
    for p in products:
        img = p.get("image", "")
        url = p.get("url", "")
        name = p.get("name", "")
        if img and url and img not in used_images:
            url_to_img[url] = {"img": img, "name": name}

    if not url_to_img:
        return content_html

    # Track which product images we use in this article
    used_in_this_article = []

    # Find all product links and add images after their containing paragraph
    for url, info in url_to_img.items():
        escaped_url = re.escape(url)

        pattern = r'(<(?:p|li)[^>]*>(?:(?!</(?:p|li)>).)*' + \
            escaped_url + r'(?:(?!</(?:p|li)>).)*</(?:p|li)>)'

        match = re.search(pattern, content_html, re.DOTALL)
        if match:
            product_img_html = (
                f'\n<div style="text-align:center;margin:15px 0;">'
                f'<a href="{url}" title="{info["name"]}">'
                f'<img src="{info["img"]}" alt="{info["name"]} - ejolie.ro" '
                f'style="max-width:350px;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.1);" />'
                f'</a>'
                f'<br><em style="font-size:0.9em;color:#666;">{info["name"]}</em>'
                f'</div>\n'
            )
            content_html = content_html[:match.end(
            )] + product_img_html + content_html[match.end():]
            used_in_this_article.append(info["img"])

    # Log used images for this article
    if article_slug and used_in_this_article:
        log = load_images_log()
        if article_slug not in log:
            log[article_slug] = {}
        log[article_slug]["product_images"] = used_in_this_article
        save_images_log(log)

    return content_html


# ── Main (for testing) ──
if __name__ == "__main__":
    import sys

    # Load env
    env_paths = [
        os.path.expanduser("~/ejolie-openclaw-agent/ejolie-sales/.env"),
        os.path.expanduser("~/.env"),
        ".env",
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

    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
    EXTENDED_EMAIL = os.environ.get("EXTENDED_EMAIL", "")
    EXTENDED_PASSWORD = os.environ.get("EXTENDED_PASSWORD", "")

    keyword = sys.argv[1] if len(
        sys.argv) > 1 else "rochii cununie civila 2026"

    print(f"🎨 Blog Image Generator - Test")
    print(f"📌 Keyword: {keyword}")
    print(f"{'='*50}")

    # Login
    print("🔐 Login Extended...")
    s = requests.Session()
    s.get("https://www.ejolie.ro/manager/login", timeout=30)
    r = s.post(
        "https://www.ejolie.ro/manager/login/autentificare",
        data={"utilizator": EXTENDED_EMAIL, "parola": EXTENDED_PASSWORD},
        allow_redirects=False,
        timeout=30,
    )
    if r.status_code != 302:
        print("❌ Login failed!")
        sys.exit(1)
    print("✅ Login OK")

    # Generate images
    images = generate_blog_images(keyword, s, num_inline=2)

    print(f"\n{'='*50}")
    print(f"✅ Rezultat:")
    print(f"  Copertă: {images['cover_url']}")
    for img in images['inline_images']:
        print(f"  Inline: {img['url']}")
