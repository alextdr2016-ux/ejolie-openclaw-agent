#!/usr/bin/env python3
"""Update local stock cache from API - run via cron every 2-4 hours"""

import os, json, urllib.request, time, sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FEED_FILE = os.path.join(SCRIPT_DIR, "product_feed.json")
CACHE_FILE = os.path.join(SCRIPT_DIR, "stock_cache.json")

env_path = os.path.join(SCRIPT_DIR, ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                k, v = line.strip().split('=', 1)
                os.environ[k] = v

API_KEY = os.environ.get("EJOLIE_API_KEY", "")
API_URL = os.environ.get("EJOLIE_API_URL", "https://ejolie.ro/api/")


def update_cache():
    with open(FEED_FILE) as f:
        feed = json.load(f)
    
    product_ids = [p["id"] for p in feed if p.get("id")]
    total = len(product_ids)
    print(f"📦 Updating stock cache: {total} products...")
    
    all_products = {}
    batch_size = 20
    
    for i in range(0, total, batch_size):
        batch = product_ids[i:i+batch_size]
        ids_str = ",".join(batch)
        url = f"{API_URL}?produse&id_produse={ids_str}&apikey={API_KEY}"
        
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            data = json.loads(urllib.request.urlopen(req, timeout=180).read().decode("utf-8"))
            
            for pid, prod in data.items():
                optiuni = prod.get("optiuni", {})
                sizes = {}
                if isinstance(optiuni, dict):
                    for oid, opt in optiuni.items():
                        sizes[opt.get("nume_optiune", "?")] = {
                            "stoc": opt.get("stoc", "?"),
                            "in_stock": "In stoc" in str(opt.get("stoc", "")),
                            "pret": opt.get("pret", "0"),
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
            
            done = min(i + batch_size, total)
            print(f"  📡 {done}/{total}...")
        except Exception as e:
            print(f"  ⚠️ Batch error: {e}")
        
        time.sleep(0.5)
    
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
