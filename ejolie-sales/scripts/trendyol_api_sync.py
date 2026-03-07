#!/usr/bin/env python3
"""
Trendyol Stock Sync v1.1
=========================
Sincronizează stocul între ejolie.ro (Extended CMS) și Trendyol International.

Flux:
1. Încarcă barcode_ejolie_map.json (barcode → ejolie_id)
2. GET toate produsele de pe Trendyol API (storeFrontCode=RO)
3. Mapează barcode → ejolie_id via barcode_ejolie_map.json
4. Extrage size din atributele Trendyol (attributeName=Size)
5. Fetch stoc din Extended API per id_produs (grupat, 1 call per produs)
6. Compară stocul Trendyol vs ejolie.ro
7. PUT update stoc pe Trendyol API (doar produsele cu diferențe)
8. Verifică batch status
9. Raport Telegram

Rulează: python3 trendyol_api_sync.py [--dry-run] [--verbose]
Cron: 0 */6 * * * cd ~/ejolie-openclaw-agent/ejolie-sales/scripts && python3 trendyol_api_sync.py >> /tmp/trendyol_sync.log 2>&1
"""

import os
import sys
import json
import time
import base64
import argparse
import requests
from datetime import datetime
from dotenv import load_dotenv

# ============================================================
# CONFIGURARE
# ============================================================

script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
env_path = os.path.join(parent_dir, '.env')
if not os.path.exists(env_path):
    env_path = os.path.join(script_dir, '.env')
load_dotenv(env_path)

# Credențiale
SELLER_ID = os.getenv('TRENDYOL_SELLER_ID', '1235983')
API_KEY = os.getenv('TRENDYOL_API_KEY')
API_SECRET = os.getenv('TRENDYOL_API_SECRET')
EJOLIE_API_KEY = os.getenv('EJOLIE_API_KEY')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Fișiere
BARCODE_MAP_FILE = os.path.join(script_dir, 'barcode_ejolie_map.json')

# URL-uri API
TRENDYOL_BASE = "https://apigw.trendyol.com/integration"
TRENDYOL_PRODUCTS_URL = f"{TRENDYOL_BASE}/product/sellers/{SELLER_ID}/products"
TRENDYOL_STOCK_URL = f"{TRENDYOL_BASE}/inventory/sellers/{SELLER_ID}/products/price-and-inventory"
TRENDYOL_BATCH_URL = f"{TRENDYOL_BASE}/product/sellers/{SELLER_ID}/products/batch-requests"
EJOLIE_API_URL = "https://ejolie.ro/api/"
STOREFRONT_CODE = "RO"

# Setări
TRENDYOL_PAGE_SIZE = 50
EJOLIE_API_DELAY = 0.3
TRENDYOL_BATCH_SIZE = 1000
BATCH_CHECK_DELAY = 5
BATCH_CHECK_RETRIES = 12

# ============================================================
# ARGPARSE
# ============================================================

parser = argparse.ArgumentParser(description='Trendyol Stock Sync v1.1')
parser.add_argument('--dry-run', action='store_true',
                    help='Nu trimite update-uri, doar afișează')
parser.add_argument('--verbose', '-v', action='store_true',
                    help='Detalii suplimentare')
args = parser.parse_args()

DRY_RUN = args.dry_run
VERBOSE = args.verbose

# ============================================================
# FUNCȚII HELPER
# ============================================================


def log(msg):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {msg}")


def vlog(msg):
    if VERBOSE:
        log(msg)


def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log("⚠️ Telegram nu e configurat")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    if len(message) > 4000:
        message = message[:3997] + "..."
    try:
        requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }, timeout=10)
    except Exception as e:
        log(f"⚠️ Telegram error: {e}")


def get_trendyol_headers():
    auth_string = f"{API_KEY}:{API_SECRET}"
    auth_base64 = base64.b64encode(auth_string.encode()).decode()
    return {
        "Authorization": f"Basic {auth_base64}",
        "Content-Type": "application/json",
        "User-Agent": f"{SELLER_ID} - SelfIntegration"
    }


def get_ejolie_headers():
    return {"User-Agent": "Mozilla/5.0"}


# ============================================================
# PAS 1: ÎNCARCĂ BARCODE MAP
# ============================================================

def load_barcode_map():
    """Încarcă barcode_ejolie_map.json."""
    log("📂 Pas 1: Încarcă barcode_ejolie_map.json...")

    if not os.path.exists(BARCODE_MAP_FILE):
        log(f"❌ Fișierul nu există: {BARCODE_MAP_FILE}")
        return None

    with open(BARCODE_MAP_FILE, 'r') as f:
        barcode_map = json.load(f)

    unique_ids = set(barcode_map.values())
    log(f"  ✅ Încărcat: {len(barcode_map)} barcodes → {len(unique_ids)} produse ejolie")

    return barcode_map


# ============================================================
# PAS 2: FETCH TOATE PRODUSELE DE PE TRENDYOL
# ============================================================

def fetch_trendyol_products():
    """Fetch toate produsele de pe Trendyol API cu paginare."""
    log("📡 Pas 2: Fetch produse de pe Trendyol API...")

    headers = get_trendyol_headers()
    all_products = []
    page = 0
    total_pages = 1

    while page < total_pages:
        url = f"{TRENDYOL_PRODUCTS_URL}?storeFrontCode={STOREFRONT_CODE}&page={page}&size={TRENDYOL_PAGE_SIZE}"
        vlog(f"  GET page {page}")

        try:
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code != 200:
                log(f"❌ Trendyol API error: {response.status_code}")
                return None

            data = response.json()
            total_pages = data.get('totalPages', 0)
            products = data.get('content', [])

            if page == 0:
                log(
                    f"  📊 Total produse pe Trendyol: {data.get('totalElements', 0)} ({total_pages} pagini)")

            all_products.extend(products)
            page += 1
            if page < total_pages:
                time.sleep(0.2)

        except Exception as e:
            log(f"❌ Eroare fetch Trendyol pagina {page}: {e}")
            return None

    log(f"  ✅ Fetch complet: {len(all_products)} produse")
    return all_products


# ============================================================
# PAS 3: MAPARE BARCODE → EJOLIE_ID + EXTRAGE SIZE
# ============================================================

def map_products(trendyol_products, barcode_map):
    """
    Mapează fiecare produs Trendyol la ejolie_id via barcode_map.
    Extrage size-ul din atributele Trendyol.
    """
    log("🔍 Pas 3: Mapare barcode → ejolie_id...")

    product_map = {}
    ejolie_ids = set()
    unmapped = 0

    for p in trendyol_products:
        barcode = p.get('barcode', '')

        if not barcode:
            continue

        # Caută ejolie_id în barcode_map
        ejolie_id = barcode_map.get(barcode)

        if not ejolie_id:
            unmapped += 1
            vlog(
                f"  ⚠️ Barcode {barcode} nu e în map ({p.get('title', '')[:30]})")
            continue

        # Extrage size din atributele Trendyol
        size = ""
        attributes = p.get('attributes', [])
        for attr in attributes:
            if attr.get('attributeName') == 'Size':
                size = str(attr.get('attributeValue', '')).strip()
                break

        product_map[barcode] = {
            'ejolie_id': ejolie_id,
            'size': size,
            'trendyol_qty': p.get('quantity', 0),
            'salePrice': p.get('salePrice', 0),
            'listPrice': p.get('listPrice', 0),
            'title': p.get('title', '')[:40],
            'onSale': p.get('onSale', False)
        }

        ejolie_ids.add(ejolie_id)

    log(f"  ✅ Mapate: {len(product_map)} barcodes → {len(ejolie_ids)} produse ejolie")
    if unmapped:
        log(f"  ⚠️ {unmapped} barcodes fără mapping (produse noi pe Trendyol?)")

    return product_map, ejolie_ids


# ============================================================
# PAS 4: FETCH STOC DIN EXTENDED API
# ============================================================

def fetch_ejolie_stock(ejolie_ids):
    """
    Fetch stoc din Extended API per id_produs.

    STRUCTURA Extended API (important!):
    - Returnează un DICT, nu o listă: {ejolie_id: {product_data}}
    - Dacă produsul nu există: returnează [] (listă goală)
    - Stocul per mărime: data[ejolie_id]["optiuni"][opt_id]["stoc_fizic"]
    - Numele mărimii: data[ejolie_id]["optiuni"][opt_id]["nume_optiune"]
    """
    log(f"📡 Pas 4: Fetch stoc din ejolie.ro ({len(ejolie_ids)} produse)...")

    headers = get_ejolie_headers()
    ejolie_stock = {}
    errors = 0
    empty = 0

    sorted_ids = sorted(ejolie_ids, key=lambda x: int(x) if x.isdigit() else 0)

    for i, ejolie_id in enumerate(sorted_ids):
        url = f"{EJOLIE_API_URL}?id_produs={ejolie_id}&apikey={EJOLIE_API_KEY}"

        try:
            response = requests.get(url, headers=headers, timeout=15)

            if response.status_code != 200:
                vlog(
                    f"  ❌ Eroare {response.status_code} pentru produs {ejolie_id}")
                errors += 1
                ejolie_stock[ejolie_id] = {}
                time.sleep(EJOLIE_API_DELAY)
                continue

            data = response.json()

            # Produs dezactivat/șters → returnează [] (listă goală)
            if not data or (isinstance(data, list) and len(data) == 0):
                vlog(f"  ⚠️ Produs {ejolie_id}: dezactivat → stoc 0")
                empty += 1
                ejolie_stock[ejolie_id] = {}
                time.sleep(EJOLIE_API_DELAY)
                continue

            # Extended API returnează dict: {ejolie_id: {product_data}}
            # Accesăm produsul prin cheia ejolie_id
            if isinstance(data, dict):
                product = data.get(str(ejolie_id), {})
            else:
                # Fallback dacă e listă
                product = data[0] if data else {}

            if not product:
                vlog(f"  ⚠️ Produs {ejolie_id}: structură goală → stoc 0")
                empty += 1
                ejolie_stock[ejolie_id] = {}
                time.sleep(EJOLIE_API_DELAY)
                continue

            # Extrage stoc per opțiune (mărime)
            # Câmpul corect este "nume_optiune" (nu "optiune_valoare")
            optiuni = product.get('optiuni', {})
            size_stock = {}

            for opt_id, opt_data in optiuni.items():
                if isinstance(opt_data, dict):
                    size_value = str(opt_data.get('nume_optiune', '')).strip()
                    stoc = int(opt_data.get('stoc_fizic', 0))
                    if size_value:
                        size_stock[size_value] = stoc

            ejolie_stock[ejolie_id] = size_stock

            if VERBOSE and (i + 1) % 50 == 0:
                log(f"  📊 Progres: {i + 1}/{len(ejolie_ids)}")

        except Exception as e:
            vlog(f"  ❌ Exception produs {ejolie_id}: {e}")
            errors += 1
            ejolie_stock[ejolie_id] = {}

        time.sleep(EJOLIE_API_DELAY)

    log(f"  ✅ Fetch complet: {len(ejolie_stock)} produse")
    if errors:
        log(f"  ⚠️ {errors} erori API")
    if empty:
        log(f"  ⚠️ {empty} produse dezactivate")

    return ejolie_stock


# ============================================================
# PAS 5: COMPARĂ ȘI CONSTRUIEȘTE PAYLOAD
# ============================================================

def build_update_payload(product_map, ejolie_stock):
    """Compară stocul Trendyol vs ejolie.ro și construiește payload."""
    log("🔄 Pas 5: Compară stoc...")

    items_to_update = []
    stats = {
        'total': len(product_map),
        'changed': 0,
        'unchanged': 0,
        'set_to_zero': 0,
        'increased': 0,
        'decreased': 0,
        'no_size_match': 0
    }
    changes_detail = []

    for barcode, info in product_map.items():
        ejolie_id = info['ejolie_id']
        size = info['size']
        trendyol_qty = info['trendyol_qty']

        # Caută stocul în ejolie
        size_stock = ejolie_stock.get(ejolie_id, {})

        if not size_stock:
            # Produs dezactivat → stoc 0
            ejolie_qty = 0
        else:
            # Caută mărimea exactă
            ejolie_qty = size_stock.get(size, -1)

            if ejolie_qty == -1:
                # Încearcă case-insensitive match
                matched = False
                for s_key, s_val in size_stock.items():
                    if s_key.strip().lower() == size.strip().lower():
                        ejolie_qty = s_val
                        matched = True
                        break

                if not matched:
                    # Nu s-a găsit mărimea
                    ejolie_qty = 0
                    stats['no_size_match'] += 1
                    vlog(
                        f"  ⚠️ Size mismatch: ejolie {ejolie_id} size '{size}' not in {list(size_stock.keys())}")

        # Compară
        if ejolie_qty != trendyol_qty:
            items_to_update.append({
                "barcode": barcode,
                "quantity": ejolie_qty,
                "salePrice": info['salePrice'],
                "listPrice": info['listPrice']
            })

            stats['changed'] += 1
            if ejolie_qty == 0:
                stats['set_to_zero'] += 1
            elif ejolie_qty > trendyol_qty:
                stats['increased'] += 1
            else:
                stats['decreased'] += 1

            changes_detail.append(
                f"  {info['title']} [{barcode}] s:{size}: {trendyol_qty}→{ejolie_qty}"
            )
        else:
            stats['unchanged'] += 1

    log(f"  📊 Total: {stats['total']}")
    log(f"     Modificate: {stats['changed']} (↑{stats['increased']} ↓{stats['decreased']} ⓪{stats['set_to_zero']})")
    log(f"     Nemodificate: {stats['unchanged']}")
    if stats['no_size_match']:
        log(f"     ⚠️ Size mismatch: {stats['no_size_match']}")

    if VERBOSE and changes_detail:
        log("  📋 Detalii modificări (max 20):")
        for detail in changes_detail[:20]:
            log(detail)
        if len(changes_detail) > 20:
            log(f"  ... +{len(changes_detail) - 20}")

    return items_to_update, stats, changes_detail


# ============================================================
# PAS 6: PUT UPDATE PE TRENDYOL API
# ============================================================

def update_trendyol_stock(items_to_update):
    """PUT pe Trendyol API cu batching."""
    if not items_to_update:
        log("✅ Pas 6: Nimic de actualizat!")
        return []

    log(f"📡 Pas 6: Update stoc pe Trendyol ({len(items_to_update)} items)...")

    if DRY_RUN:
        log("  ⚠️ DRY RUN — nu se trimite nimic!")
        return ['DRY_RUN']

    headers = get_trendyol_headers()
    batch_ids = []

    for i in range(0, len(items_to_update), TRENDYOL_BATCH_SIZE):
        batch = items_to_update[i:i + TRENDYOL_BATCH_SIZE]
        batch_num = (i // TRENDYOL_BATCH_SIZE) + 1

        # Adaugă storeFrontCode la fiecare item (necesar pt International)
        for item in batch:
            item['storeFrontCode'] = STOREFRONT_CODE

        payload = {"items": batch}

        log(f"  📦 Batch {batch_num}: {len(batch)} items")

        try:
            response = requests.put(
                TRENDYOL_STOCK_URL,
                headers=headers,
                json=payload,
                timeout=60
            )

            if response.status_code == 200:
                data = response.json()
                batch_id = data.get('batchRequestId', 'N/A')
                batch_ids.append(batch_id)
                log(f"  ✅ Batch {batch_num}: batchRequestId = {batch_id}")
            else:
                log(
                    f"  ❌ Batch {batch_num}: {response.status_code} - {response.text[:300]}")

        except Exception as e:
            log(f"  ❌ Batch {batch_num} exception: {e}")

        if i + TRENDYOL_BATCH_SIZE < len(items_to_update):
            time.sleep(1)

    return batch_ids


# ============================================================
# PAS 7: VERIFICĂ BATCH STATUS
# ============================================================

def check_batch_status(batch_ids):
    """Verifică statusul batch-urilor."""
    if not batch_ids or batch_ids == ['DRY_RUN']:
        return

    log("🔍 Pas 7: Verificare batch status...")
    headers = get_trendyol_headers()

    for batch_id in batch_ids:
        url = f"{TRENDYOL_BATCH_URL}/{batch_id}"

        for attempt in range(BATCH_CHECK_RETRIES):
            try:
                response = requests.get(url, headers=headers, timeout=30)

                if response.status_code == 200:
                    data = response.json()
                    status = data.get('status', 'UNKNOWN')
                    item_count = data.get('itemCount', 0)
                    failed_count = data.get('failedItemCount', 0)

                    if status in ('COMPLETED', 'FAILED'):
                        if failed_count == 0:
                            log(f"  ✅ Batch: {status} ({item_count} items, 0 failed)")
                        else:
                            log(f"  ⚠️ Batch: {status} ({item_count} items, {failed_count} failed)")
                            for item in data.get('items', []):
                                if item.get('status') == 'FAILED':
                                    reasons = item.get('failureReasons', [])
                                    bc = item.get('requestItem', {}).get(
                                        'barcode', 'N/A')
                                    log(f"     ❌ {bc}: {reasons}")
                        break
                    else:
                        vlog(f"  ⏳ Status: {status} (attempt {attempt + 1})")
                        time.sleep(BATCH_CHECK_DELAY)
                else:
                    time.sleep(BATCH_CHECK_DELAY)

            except Exception as e:
                time.sleep(BATCH_CHECK_DELAY)
        else:
            log(f"  ⚠️ Batch timeout după {BATCH_CHECK_RETRIES} verificări")


# ============================================================
# PAS 8: RAPORT TELEGRAM
# ============================================================

def send_report(stats, changes_detail, batch_ids, duration):
    log("📨 Pas 8: Raport Telegram...")

    now = datetime.now().strftime('%d.%m.%Y %H:%M')
    dry_tag = " [DRY RUN]" if DRY_RUN else ""

    msg = f"🔄 <b>Trendyol Stock Sync{dry_tag}</b>\n"
    msg += f"📅 {now} | ⏱ {duration:.0f}s\n\n"
    msg += f"📊 <b>Statistici:</b>\n"
    msg += f"  Total: {stats['total']}\n"
    msg += f"  Modificate: {stats['changed']}\n"

    if stats['changed'] > 0:
        msg += f"    ↑ Crescut: {stats['increased']}\n"
        msg += f"    ↓ Scăzut: {stats['decreased']}\n"
        msg += f"    ⓪ Epuizate: {stats['set_to_zero']}\n"

    msg += f"  Nemodificate: {stats['unchanged']}\n"

    if stats.get('no_size_match', 0):
        msg += f"  ⚠️ Size mismatch: {stats['no_size_match']}\n"

    if changes_detail:
        msg += f"\n📋 <b>Modificări ({min(10, len(changes_detail))}/{len(changes_detail)}):</b>\n"
        for d in changes_detail[:10]:
            msg += f"{d}\n"
        if len(changes_detail) > 10:
            msg += f"  ... +{len(changes_detail) - 10}\n"

    send_telegram(msg)
    log("  ✅ Raport trimis")


# ============================================================
# MAIN
# ============================================================

def main():
    start_time = time.time()

    log("=" * 60)
    log("🚀 TRENDYOL STOCK SYNC v1.1")
    if DRY_RUN:
        log("⚠️  DRY RUN")
    log("=" * 60)

    # Verifică credențiale
    missing = []
    if not API_KEY:
        missing.append('TRENDYOL_API_KEY')
    if not API_SECRET:
        missing.append('TRENDYOL_API_SECRET')
    if not EJOLIE_API_KEY:
        missing.append('EJOLIE_API_KEY')
    if missing:
        log(f"❌ Lipsesc: {', '.join(missing)}")
        sys.exit(1)

    # Pas 1: Încarcă barcode map
    barcode_map = load_barcode_map()
    if barcode_map is None:
        log("❌ ABORT — nu s-a putut încărca barcode_ejolie_map.json")
        send_telegram(
            "❌ <b>Trendyol Sync FAILED</b>\nNu s-a putut încărca barcode_ejolie_map.json")
        sys.exit(1)

    # Pas 2: Fetch produse Trendyol
    trendyol_products = fetch_trendyol_products()
    if trendyol_products is None:
        log("❌ ABORT — nu s-au putut fetch produsele Trendyol")
        send_telegram(
            "❌ <b>Trendyol Sync FAILED</b>\nNu s-au putut fetch produsele Trendyol")
        sys.exit(1)

    if not trendyol_products:
        log("⚠️ 0 produse pe Trendyol")
        sys.exit(0)

    # Pas 3: Mapare
    product_map, ejolie_ids = map_products(trendyol_products, barcode_map)

    # Pas 4: Fetch stoc ejolie
    ejolie_stock = fetch_ejolie_stock(ejolie_ids)

    # Pas 5: Compară
    items_to_update, stats, changes_detail = build_update_payload(
        product_map, ejolie_stock)

    # Pas 6: Update
    batch_ids = update_trendyol_stock(items_to_update)

    # Pas 7: Verifică status
    check_batch_status(batch_ids)

    # Pas 8: Raport
    duration = time.time() - start_time
    send_report(stats, changes_detail, batch_ids, duration)

    log("=" * 60)
    log(f"✅ SYNC COMPLET în {duration:.0f}s")
    log("=" * 60)


if __name__ == '__main__':
    main()
