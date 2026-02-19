#!/usr/bin/env python3
"""Update local stock cache + product feed from API - run via cron every 4 hours
v3 - Pagination + saves both stock_cache.json and product_feed.json
"""
import os, json, urllib.request, time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(SCRIPT_DIR, "stock_cache.json")
FEED_FILE = os.path.join(SCRIPT_DIR, "product_feed.json")

env_path = os.path.join(SCRIPT_DIR, "..", ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                k, v = line.strip().split('=', 1)
                os.environ[k] = v

API_KEY = os.environ.get("EJOLIE_API_KEY", "")
API_URL = os.environ.get("EJOLIE_API_URL", "https://ejolie.ro/api/")
PAGE_SIZE = 50


def update_cache():
    print(f"📦 Updating stock cache + product feed (limit={PAGE_SIZE})...")

    all_products = {}
    feed_list = []
    pagina = 1
    total_fetched = 0

    while True:
        url = f"{API_URL}?produse&limit={PAGE_SIZE}&pagina={pagina}&apikey={API_KEY}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            raw = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
            data = json.loads(raw)

            if not data or not isinstance(data, dict):
                print(f"  📄 Pagina {pagina}: gol — terminat")
                break

            count = 0
            for pid, prod in data.items():
                if not isinstance(prod, dict):
                    continue

                # --- Stock cache ---
                optiuni = prod.get("optiuni", {})
                sizes = {}
                if isinstance(optiuni, dict):
                    for oid, opt in optiuni.items():
                        if not isinstance(opt, dict):
                            continue
                        sizes[opt.get("nume_optiune", "?")] = {
                            "stoc": opt.get("stoc", "?"),
                            "stoc_fizic": int(opt.get("stoc_fizic", 0) or 0),
                            "in_stock": "In stoc" in str(opt.get("stoc", "")),
                            "pret": opt.get("pret", "0"),
                            "pret_discount": opt.get("pret_discount", "0"),
                        }

                brand_name = ""
                brand_obj = prod.get("brand", {})
                if isinstance(brand_obj, dict):
                    brand_name = brand_obj.get("nume", "")
                elif brand_obj:
                    brand_name = str(brand_obj)

                all_products[pid] = {
                    "id": pid,
                    "nume": prod.get("nume", ""),
                    "cod": prod.get("cod_produs", ""),
                    "brand": brand_name,
                    "pret": prod.get("pret_discount") or prod.get("pret", "0"),
                    "stoc_general": prod.get("stoc", "?"),
                    "sizes": sizes,
                }

                # --- Product feed ---
                desc = prod.get("descriere", "")
                categorii = prod.get("categorii", [])
                cat_name = categorii[0]["nume"] if categorii and isinstance(categorii[0], dict) else ""

                feed_list.append({
                    "id": pid,
                    "title": prod.get("nume", ""),
                    "price": f"{prod.get('pret', '0')} RON",
                    "sale_price": f"{prod.get('pret_discount', '0')} RON",
                    "image": prod.get("imagine", ""),
                    "images": prod.get("imagini", []),
                    "link": prod.get("link", ""),
                    "brand": brand_name,
                    "category": cat_name,
                    "available": "in stock" if prod.get("stoc") == "In stoc" else "out of stock",
                    "description": desc[:200] if desc else "",
                })
                count += 1

            total_fetched += count
            print(f"  📡 Pagina {pagina}: {count} produse (total: {total_fetched})")

            if count < PAGE_SIZE:
                break

            pagina += 1
            time.sleep(1)

        except Exception as e:
            print(f"  ⚠️ Pagina {pagina} error: {e}")
            if pagina > 1:
                break
            time.sleep(5)
            pagina += 1

    # Save stock cache
    cache = {
        "updated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_products": len(all_products),
        "products": all_products,
    }
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, ensure_ascii=False, indent=1)
    print(f"✅ Stock cache: {len(all_products)} products → {CACHE_FILE}")

    # Save product feed
    with open(FEED_FILE, "w") as f:
        json.dump(feed_list, f, ensure_ascii=False, indent=1)
    print(f"✅ Product feed: {len(feed_list)} products → {FEED_FILE}")

    print(f"🕐 Updated: {cache['updated']}")


if __name__ == "__main__":
    update_cache()
