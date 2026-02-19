#!/usr/bin/env python3
"""Update local stock cache from API - run via cron every 2-4 hours
v2 - Uses pagination instead of batch id_produse (which times out)
"""
import os, json, urllib.request, time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FEED_FILE = os.path.join(SCRIPT_DIR, "product_feed.json")
CACHE_FILE = os.path.join(SCRIPT_DIR, "stock_cache.json")

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
    print(f"📦 Updating stock cache via pagination (limit={PAGE_SIZE})...")

    all_products = {}
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

                all_products[pid] = {
                    "id": pid,
                    "nume": prod.get("nume", ""),
                    "cod": prod.get("cod_produs", ""),
                    "brand": prod.get("brand", {}).get("nume", "?") if isinstance(prod.get("brand"), dict) else str(prod.get("brand", "?")),
                    "pret": prod.get("pret_discount") or prod.get("pret", "0"),
                    "stoc_general": prod.get("stoc", "?"),
                    "sizes": sizes,
                }
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

    # Also update product_feed.json
    feed = []
    for pid, prod in all_products.items():
        feed.append({
            "id": pid,
            "title": prod["nume"],
            "price": prod.get("pret", "0"),
            "sale_price": prod.get("pret", "0"),
            "image": "",  # Not available in list endpoint
            "link": "",
            "brand": prod.get("brand", ""),
            "category": "",
            "available": "in stock" if prod.get("stoc_general") == "In stoc" else "out of stock",
            "description": "",
        })

    cache = {
        "updated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_products": len(all_products),
        "products": all_products,
    }

    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, ensure_ascii=False, indent=1)

    print(f"✅ Cache saved: {len(all_products)} products → {CACHE_FILE}")
    print(f"🕐 Updated: {cache['updated']}")


if __name__ == "__main__":
    update_cache()
