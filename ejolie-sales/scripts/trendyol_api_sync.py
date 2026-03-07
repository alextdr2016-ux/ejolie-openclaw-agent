#!/usr/bin/env python3
"""
Trendyol Stock Sync v1.0
=========================
Sincronizează stocul între ejolie.ro (Extended CMS) și Trendyol International.

Flux:
1. GET toate produsele de pe Trendyol API (storeFrontCode=RO)
2. Extrage ejolie_id din stockCode (format: {ejolie_id}-{size})
3. Fetch stoc din Extended API per id_produs (grupat, 1 call per produs)
4. Compară stocul Trendyol vs ejolie.ro
5. PUT update stoc pe Trendyol API (doar produsele cu diferențe)
6. Verifică batch status
7. Raport Telegram

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

# Încarcă .env
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

# URL-uri API
TRENDYOL_BASE = "https://apigw.trendyol.com/integration"
TRENDYOL_PRODUCTS_URL = f"{TRENDYOL_BASE}/product/sellers/{SELLER_ID}/products"
TRENDYOL_STOCK_URL = f"{TRENDYOL_BASE}/inventory/sellers/{SELLER_ID}/products/price-and-inventory"
TRENDYOL_BATCH_URL = f"{TRENDYOL_BASE}/product/sellers/{SELLER_ID}/products/batch-requests"
EJOLIE_API_URL = "https://ejolie.ro/api/"
STOREFRONT_CODE = "RO"

# Setări
TRENDYOL_PAGE_SIZE = 50        # Max produse per pagină Trendyol
EJOLIE_API_DELAY = 0.3         # Delay între calluri Extended API (secunde)
TRENDYOL_BATCH_SIZE = 1000     # Max items per PUT request
BATCH_CHECK_DELAY = 5          # Secunde între verificări batch status
BATCH_CHECK_RETRIES = 12       # Max verificări batch status (12 x 5s = 60s)


# ============================================================
# ARGPARSE
# ============================================================

parser = argparse.ArgumentParser(description='Trendyol Stock Sync')
parser.add_argument('--dry-run', action='store_true',
                    help='Nu trimite update-uri, doar afișează ce ar face')
parser.add_argument('--verbose', '-v', action='store_true',
                    help='Afișează detalii suplimentare')
args = parser.parse_args()

DRY_RUN = args.dry_run
VERBOSE = args.verbose


# ============================================================
# FUNCȚII HELPER
# ============================================================

def log(msg):
    """Print cu timestamp."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {msg}")


def vlog(msg):
    """Print doar în modul verbose."""
    if VERBOSE:
        log(msg)


def send_telegram(message):
    """Trimite mesaj pe Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log("⚠️ Telegram nu e configurat, skip notificare")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    # Telegram are limită de 4096 caractere
    if len(message) > 4000:
        message = message[:3997] + "..."

    try:
        response = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }, timeout=10)
        if response.status_code != 200:
            log(f"⚠️ Telegram error: {response.status_code}")
    except Exception as e:
        log(f"⚠️ Telegram exception: {e}")


def get_trendyol_headers():
    """Returnează headers pentru Trendyol API."""
    auth_string = f"{API_KEY}:{API_SECRET}"
    auth_base64 = base64.b64encode(auth_string.encode()).decode()
    return {
        "Authorization": f"Basic {auth_base64}",
        "Content-Type": "application/json",
        "User-Agent": f"{SELLER_ID} - SelfIntegration"
    }


def get_ejolie_headers():
    """Returnează headers pentru Extended API."""
    return {
        "User-Agent": "Mozilla/5.0"
    }


# ============================================================
# PAS 1: FETCH TOATE PRODUSELE DE PE TRENDYOL
# ============================================================

def fetch_trendyol_products():
    """
    Fetch toate produsele de pe Trendyol API cu paginare.
    Returnează lista de produse cu barcode, stockCode, quantity, salePrice, listPrice.
    """
    log("📡 Pas 1: Fetch produse de pe Trendyol API...")

    headers = get_trendyol_headers()
    all_products = []
    page = 0
    total_pages = 1  # Se actualizează la primul request

    while page < total_pages:
        url = f"{TRENDYOL_PRODUCTS_URL}?storeFrontCode={STOREFRONT_CODE}&page={page}&size={TRENDYOL_PAGE_SIZE}"
        vlog(f"  GET page {page}: {url}")

        try:
            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code != 200:
                log(
                    f"❌ Trendyol API error: {response.status_code} - {response.text[:200]}")
                return None

            data = response.json()
            total_pages = data.get('totalPages', 0)
            total_elements = data.get('totalElements', 0)
            products = data.get('content', [])

            if page == 0:
                log(
                    f"  📊 Total produse pe Trendyol: {total_elements} ({total_pages} pagini)")

            all_products.extend(products)
            vlog(
                f"  ✅ Pagina {page}: {len(products)} produse (total: {len(all_products)})")

            page += 1

            # Mic delay între pagini
            if page < total_pages:
                time.sleep(0.2)

        except Exception as e:
            log(f"❌ Eroare fetch Trendyol pagina {page}: {e}")
            return None

    log(f"  ✅ Fetch complet: {len(all_products)} produse de pe Trendyol")
    return all_products


# ============================================================
# PAS 2: EXTRAGE EJOLIE IDs DIN STOCKCODE
# ============================================================

def extract_ejolie_ids(trendyol_products):
    """
    Extrage ejolie_id din stockCode (format: {ejolie_id}-{size}).
    Grupează barcodes per ejolie_id.

    Returnează:
    - product_map: {barcode: {ejolie_id, stockCode, trendyol_qty, salePrice, listPrice}}
    - ejolie_ids: set de ejolie_id unice
    """
    log("🔍 Pas 2: Extrage ejolie IDs din stockCode...")

    product_map = {}
    ejolie_ids = set()
    skipped = 0

    for p in trendyol_products:
        barcode = p.get('barcode')
        stock_code = p.get('stockCode', '')

        if not barcode or not stock_code:
            skipped += 1
            continue

        # stockCode format: "17649-46" → ejolie_id = "17649"
        # Unele stockCode-uri pot avea format diferit
        parts = stock_code.rsplit('-', 1)
        if len(parts) == 2:
            ejolie_id = parts[0]
            size = parts[1]
        else:
            # Fallback: folosim tot stockCode-ul ca ejolie_id
            ejolie_id = stock_code
            size = ""
            vlog(
                f"  ⚠️ stockCode fără size: {stock_code} (barcode: {barcode})")

        product_map[barcode] = {
            'ejolie_id': ejolie_id,
            'stockCode': stock_code,
            'size': size,
            'trendyol_qty': p.get('quantity', 0),
            'salePrice': p.get('salePrice', 0),
            'listPrice': p.get('listPrice', 0),
            'title': p.get('title', '')[:40],
            'onSale': p.get('onSale', False)
        }

        ejolie_ids.add(ejolie_id)

    log(f"  ✅ {len(product_map)} barcodes → {len(ejolie_ids)} produse ejolie unice")
    if skipped:
        log(f"  ⚠️ {skipped} produse skip (fără barcode/stockCode)")

    return product_map, ejolie_ids


# ============================================================
# PAS 3: FETCH STOC DIN EXTENDED API
# ============================================================

def fetch_ejolie_stock(ejolie_ids):
    """
    Fetch stoc din Extended API per id_produs.
    Folosim API-ul individual (?id_produs=ID) care returnează TOATE produsele.

    Returnează: {ejolie_id: {size: stoc_fizic, ...}}
    """
    log(f"📡 Pas 3: Fetch stoc din ejolie.ro ({len(ejolie_ids)} produse)...")

    headers = get_ejolie_headers()
    ejolie_stock = {}
    errors = 0
    empty_responses = 0

    for i, ejolie_id in enumerate(sorted(ejolie_ids)):
        url = f"{EJOLIE_API_URL}?id_produs={ejolie_id}&apikey={EJOLIE_API_KEY}"

        try:
            response = requests.get(url, headers=headers, timeout=15)

            if response.status_code != 200:
                vlog(
                    f"  ❌ Eroare {response.status_code} pentru produs {ejolie_id}")
                errors += 1
                ejolie_stock[ejolie_id] = {}
                continue

            data = response.json()

            # Verifică dacă produsul există
            if isinstance(data, list) and len(data) == 0:
                vlog(
                    f"  ⚠️ Produs {ejolie_id}: [] (dezactivat/șters) → stoc 0")
                empty_responses += 1
                ejolie_stock[ejolie_id] = {}
                continue

            # Extrage stocul per opțiune (mărime)
            # Structura: data.optiuni.{id_optiune}.stoc_fizic + data.optiuni.{id_optiune}.optiune_valoare
            product_data = data
            if isinstance(data, list):
                product_data = data[0] if data else {}

            optiuni = product_data.get('optiuni', {})
            size_stock = {}

            for opt_id, opt_data in optiuni.items():
                if isinstance(opt_data, dict):
                    size_value = str(opt_data.get(
                        'optiune_valoare', '')).strip()
                    stoc = int(opt_data.get('stoc_fizic', 0))
                    if size_value:
                        size_stock[size_value] = stoc

            ejolie_stock[ejolie_id] = size_stock

            if VERBOSE and (i + 1) % 50 == 0:
                log(f"  📊 Progres: {i + 1}/{len(ejolie_ids)} produse procesate")

        except Exception as e:
            vlog(f"  ❌ Exception pentru produs {ejolie_id}: {e}")
            errors += 1
            ejolie_stock[ejolie_id] = {}

        # Rate limiting
        time.sleep(EJOLIE_API_DELAY)

    log(f"  ✅ Fetch complet: {len(ejolie_stock)} produse")
    if errors:
        log(f"  ⚠️ {errors} erori API")
    if empty_responses:
        log(f"  ⚠️ {empty_responses} produse dezactivate/șterse")

    return ejolie_stock


# ============================================================
# PAS 4: COMPARĂ ȘI CONSTRUIEȘTE PAYLOAD
# ============================================================

def build_update_payload(product_map, ejolie_stock):
    """
    Compară stocul Trendyol vs ejolie.ro și construiește payload-ul de update.
    Returnează lista de items de actualizat și statistici.
    """
    log("🔄 Pas 4: Compară stoc și construiește payload...")

    items_to_update = []
    stats = {
        'total': len(product_map),
        'changed': 0,
        'unchanged': 0,
        'set_to_zero': 0,
        'increased': 0,
        'decreased': 0,
        'no_match': 0
    }

    changes_detail = []

    for barcode, info in product_map.items():
        ejolie_id = info['ejolie_id']
        size = info['size']
        trendyol_qty = info['trendyol_qty']

        # Caută stocul în ejolie
        size_stock = ejolie_stock.get(ejolie_id, {})

        if not size_stock:
            # Produsul nu există în ejolie sau e dezactivat → stoc 0
            ejolie_qty = 0
            if trendyol_qty != 0:
                stats['no_match'] += 1
        else:
            # Caută mărimea exactă
            ejolie_qty = size_stock.get(size, 0)

            # Dacă nu găsește direct, încearcă cu leading zeros sau fără
            if ejolie_qty == 0 and size not in size_stock:
                # Încearcă variante: "38" vs "38.0", "S" vs "s"
                for s_key, s_val in size_stock.items():
                    if s_key.strip().lower() == size.strip().lower():
                        ejolie_qty = s_val
                        break

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
                f"  {info['title']} [{barcode}]: {trendyol_qty} → {ejolie_qty}"
            )
        else:
            stats['unchanged'] += 1

    log(f"  📊 Rezultat comparare:")
    log(f"     Total: {stats['total']}")
    log(f"     Modificate: {stats['changed']} (↑{stats['increased']} ↓{stats['decreased']} ⓪{stats['set_to_zero']})")
    log(f"     Nemodificate: {stats['unchanged']}")

    if VERBOSE and changes_detail:
        log("  📋 Detalii modificări:")
        for detail in changes_detail[:20]:  # Max 20 pentru verbose
            log(detail)
        if len(changes_detail) > 20:
            log(f"  ... și încă {len(changes_detail) - 20} modificări")

    return items_to_update, stats, changes_detail


# ============================================================
# PAS 5: PUT UPDATE PE TRENDYOL API
# ============================================================

def update_trendyol_stock(items_to_update):
    """
    Trimite PUT request pe Trendyol API cu items-urile de actualizat.
    Împarte în batches dacă sunt mai mult de TRENDYOL_BATCH_SIZE items.
    Returnează lista de batchRequestIds.
    """
    if not items_to_update:
        log("✅ Pas 5: Nimic de actualizat!")
        return []

    log(f"📡 Pas 5: Update stoc pe Trendyol ({len(items_to_update)} items)...")

    if DRY_RUN:
        log("  ⚠️ DRY RUN — nu se trimite nimic!")
        log(f"  📦 Ar trimite {len(items_to_update)} items")
        return ['DRY_RUN']

    headers = get_trendyol_headers()
    batch_ids = []

    # Împarte în batches
    for i in range(0, len(items_to_update), TRENDYOL_BATCH_SIZE):
        batch = items_to_update[i:i + TRENDYOL_BATCH_SIZE]
        batch_num = (i // TRENDYOL_BATCH_SIZE) + 1

        payload = {"items": batch}

        log(f"  📦 Batch {batch_num}: {len(batch)} items")
        vlog(f"     PUT {TRENDYOL_STOCK_URL}")

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
                log(f"  ✅ Batch {batch_num} trimis: batchRequestId = {batch_id}")
            else:
                log(f"  ❌ Batch {batch_num} eroare: {response.status_code}")
                log(f"     Response: {response.text[:300]}")

        except Exception as e:
            log(f"  ❌ Batch {batch_num} exception: {e}")

        # Delay între batches
        if i + TRENDYOL_BATCH_SIZE < len(items_to_update):
            time.sleep(1)

    return batch_ids


# ============================================================
# PAS 6: VERIFICĂ BATCH STATUS
# ============================================================

def check_batch_status(batch_ids):
    """
    Verifică statusul batch-urilor trimise.
    """
    if not batch_ids or batch_ids == ['DRY_RUN']:
        return

    log("🔍 Pas 6: Verificare batch status...")

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
                        if status == 'COMPLETED' and failed_count == 0:
                            log(
                                f"  ✅ Batch {batch_id[:20]}...: {status} ({item_count} items, 0 failed)")
                        else:
                            log(
                                f"  ⚠️ Batch {batch_id[:20]}...: {status} ({item_count} items, {failed_count} failed)")

                            # Afișează detalii erori
                            items = data.get('items', [])
                            for item in items:
                                if item.get('status') == 'FAILED':
                                    reasons = item.get('failureReasons', [])
                                    barcode = item.get('requestItem', {}).get(
                                        'barcode', 'N/A')
                                    log(f"     ❌ {barcode}: {reasons}")
                        break
                    else:
                        vlog(
                            f"  ⏳ Batch {batch_id[:20]}...: {status} (attempt {attempt + 1})")
                        time.sleep(BATCH_CHECK_DELAY)
                else:
                    vlog(f"  ⚠️ Batch check error: {response.status_code}")
                    time.sleep(BATCH_CHECK_DELAY)

            except Exception as e:
                vlog(f"  ⚠️ Batch check exception: {e}")
                time.sleep(BATCH_CHECK_DELAY)
        else:
            log(f"  ⚠️ Batch {batch_id[:20]}...: timeout după {BATCH_CHECK_RETRIES} verificări")


# ============================================================
# PAS 7: RAPORT TELEGRAM
# ============================================================

def send_report(stats, changes_detail, batch_ids, duration):
    """Trimite raport pe Telegram."""
    log("📨 Pas 7: Trimite raport Telegram...")

    now = datetime.now().strftime('%d.%m.%Y %H:%M')
    dry_run_tag = " [DRY RUN]" if DRY_RUN else ""

    msg = f"🔄 <b>Trendyol Stock Sync{dry_run_tag}</b>\n"
    msg += f"📅 {now} | ⏱ {duration:.0f}s\n\n"

    msg += f"📊 <b>Statistici:</b>\n"
    msg += f"  Total produse Trendyol: {stats['total']}\n"
    msg += f"  Modificate: {stats['changed']}\n"

    if stats['changed'] > 0:
        msg += f"    ↑ Stoc crescut: {stats['increased']}\n"
        msg += f"    ↓ Stoc scăzut: {stats['decreased']}\n"
        msg += f"    ⓪ Epuizate (→0): {stats['set_to_zero']}\n"

    msg += f"  Nemodificate: {stats['unchanged']}\n"

    if stats['no_match'] > 0:
        msg += f"  ⚠️ Fără corespondent ejolie: {stats['no_match']}\n"

    # Adaugă max 10 modificări
    if changes_detail:
        msg += f"\n📋 <b>Modificări ({min(len(changes_detail), 10)}/{len(changes_detail)}):</b>\n"
        for detail in changes_detail[:10]:
            msg += f"{detail}\n"
        if len(changes_detail) > 10:
            msg += f"  ... +{len(changes_detail) - 10} altele\n"

    if batch_ids and batch_ids != ['DRY_RUN']:
        msg += f"\n🔑 Batch IDs: {len(batch_ids)}"

    send_telegram(msg)
    log("  ✅ Raport trimis pe Telegram")


# ============================================================
# MAIN
# ============================================================

def main():
    start_time = time.time()

    log("=" * 60)
    log("🚀 TRENDYOL STOCK SYNC v1.0")
    if DRY_RUN:
        log("⚠️  MOD: DRY RUN (nu se trimit update-uri)")
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
        log(f"❌ Lipsesc credențiale: {', '.join(missing)}")
        sys.exit(1)

    # Pas 1: Fetch produse Trendyol
    trendyol_products = fetch_trendyol_products()
    if trendyol_products is None:
        log("❌ Nu s-au putut fetch produsele de pe Trendyol. ABORT.")
        send_telegram(
            "❌ <b>Trendyol Stock Sync FAILED</b>\nNu s-au putut fetch produsele de pe Trendyol.")
        sys.exit(1)

    if not trendyol_products:
        log("⚠️ 0 produse pe Trendyol. Nimic de sincronizat.")
        send_telegram(
            "⚠️ <b>Trendyol Stock Sync</b>\n0 produse pe Trendyol. Nimic de sincronizat.")
        sys.exit(0)

    # Pas 2: Extrage ejolie IDs
    product_map, ejolie_ids = extract_ejolie_ids(trendyol_products)

    # Pas 3: Fetch stoc din ejolie.ro
    ejolie_stock = fetch_ejolie_stock(ejolie_ids)

    # Pas 4: Compară și construiește payload
    items_to_update, stats, changes_detail = build_update_payload(
        product_map, ejolie_stock)

    # Pas 5: Update Trendyol
    batch_ids = update_trendyol_stock(items_to_update)

    # Pas 6: Verifică status
    check_batch_status(batch_ids)

    # Pas 7: Raport
    duration = time.time() - start_time
    send_report(stats, changes_detail, batch_ids, duration)

    log("=" * 60)
    log(f"✅ SYNC COMPLET în {duration:.0f} secunde")
    log("=" * 60)


if __name__ == '__main__':
    main()
