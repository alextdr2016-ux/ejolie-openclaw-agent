#!/usr/bin/env python3
"""
IndexNow URL Submitter for ejolie.ro
====================================
Fetches products from Extended API and submits their URLs to IndexNow.

First run: submits ALL active product URLs
Subsequent runs: submits only NEW products (added since last run)

Usage:
    python3 indexnow_ejolie.py           # Normal run (only new products)
    python3 indexnow_ejolie.py --all     # Force submit ALL products
    python3 indexnow_ejolie.py --dry-run # Show what would be submitted without actually submitting
    python3 indexnow_ejolie.py --all --dry-run  # Show all products without submitting

Cron (every 6 hours):
    0 */6 * * * cd /home/ubuntu/scripts && python3 indexnow_ejolie.py >> /home/ubuntu/scripts/logs/indexnow.log 2>&1
"""

import requests
import json
import os
import sys
import time
import logging
from datetime import datetime
from dotenv import load_dotenv

# ============================================================
# LOAD .env (same as other scripts on EC2)
# ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(SCRIPT_DIR, '.env'))

# ============================================================
# CONFIGURARE
# ============================================================

# Extended API
EXTENDED_API_URL = "https://ejolie.ro/api/"
EXTENDED_API_KEY = os.getenv(
    "EJOLIE_API_KEY", "N9komxWU3aclwDHyrXfLjJdBA6ZRTs")

# IndexNow
INDEXNOW_API_URL = "https://api.indexnow.org/indexnow"
INDEXNOW_KEY = os.getenv("INDEXNOW_KEY", "27c64659075d4e448d749ba41c5910c7")
INDEXNOW_KEY_LOCATION = f"https://ejolie.ro/{INDEXNOW_KEY}.txt"
SITE_HOST = "ejolie.ro"

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN", "8491552732:AAEGioyWChtayyitIjs0_FsidxQScsf3tXU")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "44151343")

# Paths
LOGS_DIR = os.path.join(SCRIPT_DIR, "logs")
os.makedirs(LOGS_DIR, exist_ok=True)
STATE_FILE = os.path.join(SCRIPT_DIR, "indexnow_state.json")
LOG_FILE = os.path.join(LOGS_DIR, "indexnow.log")

# Limits
BATCH_SIZE = 10000          # IndexNow max per request
PRODUCTS_PER_PAGE = 500     # Extended API pagination

# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ============================================================
# HELPER FUNCTIONS
# ============================================================


def load_state():
    """Incarca starea ultimei rulari."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Nu am putut citi state file: {e}")
    return {}


def save_state(state):
    """Salveaza starea curenta."""
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        logger.info(f"State salvat in {STATE_FILE}")
    except IOError as e:
        logger.error(f"Nu am putut salva state file: {e}")


def send_telegram(message):
    """Trimite notificare pe Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code != 200:
            logger.warning(f"Telegram send failed: {resp.status_code}")
    except Exception as e:
        logger.warning(f"Telegram error: {e}")


# ============================================================
# EXTENDED API - FETCH PRODUSE
# ============================================================

def fetch_all_products():
    """Ia TOATE produsele active din Extended API cu paginare."""
    all_products = []
    page = 1

    logger.info("Incep fetch produse din Extended API...")

    while True:
        params = {
            "produse": "",
            "apikey": EXTENDED_API_KEY,
            "limit": PRODUCTS_PER_PAGE,
            "pagina": page,
            "sort": 11  # Cele mai noi
        }

        try:
            response = requests.get(
                EXTENDED_API_URL, params=params, timeout=60)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Eroare la fetch pagina {page}: {e}")
            break
        except json.JSONDecodeError as e:
            logger.error(f"Eroare JSON la pagina {page}: {e}")
            break

        # Verifica eroare API
        if isinstance(data, dict) and data.get("eroare"):
            logger.error(
                f"Eroare Extended API: {data.get('mesaj', 'necunoscuta')}")
            break

        # Extrage produsele (API returneaza dict cu id ca key)
        if isinstance(data, dict):
            products_on_page = []
            for prod_id, prod_data in data.items():
                if isinstance(prod_data, dict) and prod_data.get("id_produs"):
                    products_on_page.append(prod_data)
        elif isinstance(data, list):
            products_on_page = data
        else:
            logger.warning(f"Format neasteptat la pagina {page}")
            break

        if not products_on_page:
            logger.info(f"Pagina {page} goala - terminat.")
            break

        all_products.extend(products_on_page)
        logger.info(
            f"Pagina {page}: {len(products_on_page)} produse (total: {len(all_products)})")

        if len(products_on_page) < PRODUCTS_PER_PAGE:
            break

        page += 1
        time.sleep(0.5)

    logger.info(f"Total produse fetchuite: {len(all_products)}")
    return all_products


def extract_urls(products):
    """Extrage URL-urile produselor din campul 'link' sau construieste din id."""
    urls = []
    skipped = 0

    for prod in products:
        link = None
        prod_id = ""

        if isinstance(prod, dict):
            link = prod.get("link", "")
            prod_id = prod.get("id_produs", "")

        # Daca link-ul e gol, construieste din id
        if not link and prod_id:
            link = f"https://ejolie.ro/product/{prod_id}"

        if link:
            if not link.startswith("http"):
                link = f"https://ejolie.ro{link}"
            urls.append(link)
        else:
            skipped += 1

    if skipped > 0:
        logger.warning(f"Produse fara URL: {skipped}")

    # Deduplicate
    seen = set()
    unique_urls = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)

    logger.info(f"URL-uri unice extrase: {len(unique_urls)}")
    return unique_urls


# ============================================================
# INDEXNOW - SUBMIT
# ============================================================

def submit_to_indexnow(urls, dry_run=False):
    """Trimite URL-urile la IndexNow API in batch-uri."""
    if not urls:
        logger.info("Niciun URL de trimis.")
        return 0, 0

    total_success = 0
    total_errors = 0

    for i in range(0, len(urls), BATCH_SIZE):
        batch = urls[i:i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1

        logger.info(f"Batch {batch_num}: {len(batch)} URL-uri")

        if dry_run:
            logger.info(f"[DRY RUN] Ar trimite {len(batch)} URL-uri")
            for url in batch[:5]:
                logger.info(f"  -> {url}")
            if len(batch) > 5:
                logger.info(f"  ... si inca {len(batch) - 5} URL-uri")
            total_success += len(batch)
            continue

        payload = {
            "host": SITE_HOST,
            "key": INDEXNOW_KEY,
            "keyLocation": INDEXNOW_KEY_LOCATION,
            "urlList": batch
        }

        try:
            resp = requests.post(
                INDEXNOW_API_URL,
                json=payload,
                headers={"Content-Type": "application/json; charset=utf-8"},
                timeout=30
            )

            if resp.status_code in (200, 202):
                logger.info(f"Batch {batch_num}: OK ({len(batch)} URL-uri)")
                total_success += len(batch)
            else:
                logger.error(
                    f"Batch {batch_num}: EROARE {resp.status_code} - {resp.text}")
                total_errors += len(batch)

        except requests.exceptions.RequestException as e:
            logger.error(f"Batch {batch_num}: EROARE {e}")
            total_errors += len(batch)

        if i + BATCH_SIZE < len(urls):
            time.sleep(1)

    return total_success, total_errors


# ============================================================
# MAIN
# ============================================================

def main():
    start_time = time.time()

    force_all = "--all" in sys.argv
    dry_run = "--dry-run" in sys.argv

    logger.info("=" * 60)
    logger.info("IndexNow Ejolie.ro - Start")
    logger.info(
        f"Mod: {'TOATE produsele' if force_all else 'Doar produse noi'}")
    if dry_run:
        logger.info("DRY RUN - nu se trimite nimic")
    logger.info("=" * 60)

    # Incarca starea anterioara
    state = load_state()
    last_run = state.get("last_run")
    last_product_ids = set(state.get("product_ids", []))
    is_first_run = not last_run

    if is_first_run:
        logger.info("Prima rulare - se trimit TOATE produsele.")
        force_all = True
    else:
        logger.info(f"Ultima rulare: {last_run}")
        logger.info(f"Produse cunoscute: {len(last_product_ids)}")

    # Fetch produse
    products = fetch_all_products()

    if not products:
        logger.error("Nu am gasit produse. Opresc.")
        send_telegram(
            "IndexNow ejolie.ro\nNu am gasit produse in Extended API!")
        return

    # ID-uri curente
    current_product_ids = set()
    for prod in products:
        if isinstance(prod, dict) and prod.get("id_produs"):
            current_product_ids.add(str(prod["id_produs"]))

    # Determina URL-urile de trimis
    if force_all:
        urls_to_submit = extract_urls(products)
        logger.info(f"Se trimit TOATE: {len(urls_to_submit)} URL-uri")
    else:
        new_ids = current_product_ids - last_product_ids
        removed_ids = last_product_ids - current_product_ids

        logger.info(f"Produse noi: {len(new_ids)}")
        logger.info(f"Produse eliminate: {len(removed_ids)}")

        if not new_ids:
            logger.info("Nicio schimbare. Nu trimit nimic.")
            state["last_run"] = datetime.now().isoformat()
            save_state(state)
            return

        new_products = [
            p for p in products
            if isinstance(p, dict) and str(p.get("id_produs", "")) in new_ids
        ]
        urls_to_submit = extract_urls(new_products)
        logger.info(f"URL-uri noi de trimis: {len(urls_to_submit)}")

    # Submit la IndexNow
    success, errors = submit_to_indexnow(urls_to_submit, dry_run=dry_run)

    # Salveaza starea
    if not dry_run:
        state["last_run"] = datetime.now().isoformat()
        state["product_ids"] = list(current_product_ids)
        state["last_submitted_count"] = success
        state["total_products"] = len(current_product_ids)
        save_state(state)

    # Rezumat
    elapsed = round(time.time() - start_time, 1)
    logger.info(f"\n{'=' * 60}")
    logger.info(f"Total produse: {len(current_product_ids)}")
    logger.info(
        f"URL-uri trimise: {success} | Erori: {errors} | Durata: {elapsed}s")
    logger.info(f"{'=' * 60}")

    # Telegram
    mode = "DRY RUN" if dry_run else ("TOATE" if force_all else "NOI")
    send_telegram(
        f"<b>IndexNow ejolie.ro</b> [{mode}]\n\n"
        f"Produse in API: {len(current_product_ids)}\n"
        f"URL-uri trimise: {success}\n"
        f"Erori: {errors}\n"
        f"Durata: {elapsed}s"
    )


if __name__ == "__main__":
    main()
