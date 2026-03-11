#!/usr/bin/env python3
"""
auto_finalize_orders.py — Finalizare automată comenzi ejolie.ro

Comenzile cu status INCASATA (ID 14) care au 15+ zile de la livrare
sunt trecute automat în status Comanda Finalizata (ID 36).

Se procesează doar comenzile cu ID >= 112979 (din 05.03.2026).

Endpoint-uri Extended API folosite:
  - GET  ?comenzi&idstatus=14  → listare comenzi incasate
  - POST actiune=update_status_comanda → schimbare status

Cron recomandat: o dată pe zi la 08:00
  0 8 * * * cd ~/ejolie-openclaw-agent/ejolie-sales && /home/ubuntu/ejolie-openclaw-agent/venv/bin/python3 scripts/auto_finalize_orders.py >> /var/log/auto_finalize.log 2>&1

Autor: Alex Tudor / Claude
Data: 11.03.2026
"""

import requests
import json
import os
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path

# ============================================================
# CONFIGURARE
# ============================================================

# ID-ul minim de comandă de procesat (comenzile mai vechi nu se ating)
MIN_ORDER_ID = 112979  # Comanda #112979 a fost plasată pe 05.03.2026

# Numărul de zile de la livrare după care se finalizează comanda
DAYS_TO_FINALIZE = 15

# Status IDs Extended
STATUS_INCASATA = 14     # Sursa: comenzi livrate
STATUS_FINALIZATA = 36   # Destinația: după 15 zile

# API Extended
API_BASE_URL = "https://ejolie.ro/api/"
API_HEADERS = {"User-Agent": "Mozilla/5.0"}

# Telegram notificări
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "44151343")

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# ============================================================
# FUNCȚII UTILITARE
# ============================================================


def load_api_key():
    """Încarcă API key din .env sau environment"""
    # Verifică env var
    api_key = os.getenv("EJOLIE_API_KEY", "")
    if api_key:
        return api_key

    # Verifică .env din directorul curent sau părinte
    for env_path in [".env", "../.env", "ejolie-sales/.env"]:
        full_path = Path(env_path)
        if full_path.exists():
            with open(full_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("#") or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    if key.strip() == "EJOLIE_API_KEY":
                        return value.strip()

    logger.error("❌ EJOLIE_API_KEY nu a fost găsit în .env sau environment")
    sys.exit(1)


def load_telegram_token():
    """Încarcă Telegram bot token din .env sau environment"""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if token:
        return token

    for env_path in [".env", "../.env", "ejolie-sales/.env"]:
        full_path = Path(env_path)
        if full_path.exists():
            with open(full_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("#") or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    if key.strip() == "TELEGRAM_BOT_TOKEN":
                        return value.strip()
    return ""


def send_telegram(message):
    """Trimite mesaj pe Telegram"""
    token = load_telegram_token()
    if not token:
        logger.warning("⚠️ TELEGRAM_BOT_TOKEN lipsește, skip notificare")
        return

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        r = requests.post(url, data=data, timeout=10)
        if r.status_code == 200:
            logger.info("✅ Notificare Telegram trimisă")
        else:
            logger.warning(f"⚠️ Telegram error: {r.status_code}")
    except Exception as e:
        logger.warning(f"⚠️ Telegram exception: {e}")


# ============================================================
# FUNCȚII API EXTENDED
# ============================================================

def get_incasate_orders(api_key):
    """
    Ia toate comenzile cu status INCASATA (14).
    Returnează dict cu {order_id: order_data}.
    """
    params = {
        "comenzi": "",
        "idstatus": STATUS_INCASATA,
        "limit": 2000,
        "apikey": api_key
    }

    logger.info(
        f"📡 Preiau comenzile cu status INCASATA (ID {STATUS_INCASATA})...")

    try:
        response = requests.get(
            API_BASE_URL,
            params=params,
            headers=API_HEADERS,
            timeout=60
        )

        if response.status_code != 200:
            logger.error(f"❌ API error: HTTP {response.status_code}")
            return {}

        data = response.json()

        # Verifică erori API
        if isinstance(data, dict) and data.get("eroare") == 1:
            logger.error(f"❌ API error: {data.get('mesaj')}")
            return {}

        logger.info(f"📦 Total comenzi INCASATE primite: {len(data)}")
        return data

    except requests.exceptions.Timeout:
        logger.error("❌ API timeout (60s)")
        return {}
    except Exception as e:
        logger.error(f"❌ API exception: {e}")
        return {}


def update_order_status(api_key, order_id, new_status_id):
    """
    Schimbă statusul unei comenzi prin API Extended.
    POST cu actiune=update_status_comanda
    Returnează True dacă a reușit, False altfel.
    """
    data = {
        "actiune": "update_status_comanda",
        "id_comanda": order_id,
        "id_status": new_status_id,
        "apikey": api_key
    }

    try:
        response = requests.post(
            API_BASE_URL,
            data=data,
            headers=API_HEADERS,
            timeout=30
        )

        if response.status_code != 200:
            logger.error(f"  ❌ #{order_id}: HTTP {response.status_code}")
            return False

        result = response.json()

        if result.get("eroare", 1) == 0:
            logger.info(f"  ✅ #{order_id}: Status schimbat → Finalizata")
            return True
        else:
            logger.error(
                f"  ❌ #{order_id}: {result.get('mesaj', 'eroare necunoscută')}")
            return False

    except Exception as e:
        logger.error(f"  ❌ #{order_id}: Exception: {e}")
        return False


# ============================================================
# LOGICA PRINCIPALĂ
# ============================================================

def get_delivery_date(order):
    """
    Extrage data livrării din AWB stadii.
    Caută stadiul care conține 'livrat' + 'succes'.
    Returnează datetime sau None.
    """
    awb_data = order.get("awb", {})
    if not awb_data or not isinstance(awb_data, dict):
        return None

    for awb_id, awb_info in awb_data.items():
        stadii = awb_info.get("stadii", {})
        if not stadii or not isinstance(stadii, dict):
            continue

        for sid, stadiu in stadii.items():
            status_text = stadiu.get("status", "").lower()
            if "livrat" in status_text and "succes" in status_text:
                # Format: "10-03-2026 / 18:01:48"
                data_str = stadiu.get("data", "")
                date_part = data_str.split(" / ")[0]  # "10-03-2026"
                try:
                    return datetime.strptime(date_part, "%d-%m-%Y")
                except ValueError:
                    logger.warning(f"  ⚠️ Format dată invalid: {data_str}")
                    return None

    return None


def process_orders(dry_run=False):
    """
    Procesează comenzile INCASATE și le finalizează pe cele cu 15+ zile.

    Args:
        dry_run: Dacă True, doar afișează ce ar face, fără să modifice.
    """
    api_key = load_api_key()
    now = datetime.now()

    logger.info("=" * 60)
    logger.info(
        f"🚀 Auto-finalizare comenzi — {now.strftime('%d.%m.%Y %H:%M')}")
    logger.info(f"   Min order ID: {MIN_ORDER_ID}")
    logger.info(f"   Zile necesare: {DAYS_TO_FINALIZE}")
    if dry_run:
        logger.info("   ⚠️ DRY RUN — nu se modifică nimic")
    logger.info("=" * 60)

    # Pas 1: Ia comenzile INCASATE
    orders = get_incasate_orders(api_key)
    if not orders:
        logger.info("📭 Nicio comandă INCASATA găsită.")
        return

    # Pas 2: Filtrare și analiză
    finalized = []      # Comenzi finalizate cu succes
    waiting = []        # Comenzi care mai așteaptă
    no_delivery = []    # Comenzi fără dată de livrare
    skipped = 0         # Comenzi cu ID < MIN_ORDER_ID

    for order_id_str, order in orders.items():
        order_id = int(order_id_str)

        # Filtru: doar comenzi >= MIN_ORDER_ID
        if order_id < MIN_ORDER_ID:
            skipped += 1
            continue

        # Extrage data livrării
        delivery_date = get_delivery_date(order)

        if delivery_date is None:
            no_delivery.append(order_id)
            logger.warning(
                f"  ⚠️ #{order_id}: Nu am găsit data livrării în AWB")
            continue

        # Calculează zilele de la livrare
        days_since = (now - delivery_date).days

        if days_since >= DAYS_TO_FINALIZE:
            # Trebuie finalizată
            if dry_run:
                logger.info(
                    f"  🔄 #{order_id}: livrat {delivery_date.strftime('%d.%m.%Y')} ({days_since} zile) → AR FI FINALIZATĂ")
                finalized.append((order_id, delivery_date, days_since))
            else:
                success = update_order_status(
                    api_key, order_id, STATUS_FINALIZATA)
                if success:
                    finalized.append((order_id, delivery_date, days_since))
                # Pauză mică între request-uri (rate limiting Extended API)
                import time
                time.sleep(0.5)
        else:
            remaining = DAYS_TO_FINALIZE - days_since
            waiting.append((order_id, delivery_date, days_since, remaining))

    # Pas 3: Raport
    logger.info("")
    logger.info("=" * 60)
    logger.info("📊 RAPORT")
    logger.info("=" * 60)
    logger.info(f"  Total comenzi INCASATE: {len(orders)}")
    logger.info(f"  Ignorate (< #{MIN_ORDER_ID}): {skipped}")
    logger.info(f"  Finalizate acum: {len(finalized)}")
    logger.info(f"  Așteaptă (sub {DAYS_TO_FINALIZE} zile): {len(waiting)}")
    logger.info(f"  Fără dată livrare: {len(no_delivery)}")

    if finalized:
        logger.info("")
        logger.info("  ✅ FINALIZATE:")
        for oid, d, days in finalized:
            logger.info(
                f"     #{oid} — livrat {d.strftime('%d.%m.%Y')} ({days} zile)")

    if waiting:
        logger.info("")
        logger.info("  ⏳ AȘTEAPTĂ:")
        for oid, d, days, remaining in sorted(waiting, key=lambda x: x[3]):
            logger.info(
                f"     #{oid} — livrat {d.strftime('%d.%m.%Y')} ({days} zile, mai sunt {remaining} zile)")

    if no_delivery:
        logger.info("")
        logger.info(f"  ⚠️ FĂRĂ DATĂ LIVRARE: {no_delivery}")

    # Pas 4: Notificare Telegram
    if not dry_run and (finalized or no_delivery):
        msg = f"<b>🔄 Auto-finalizare comenzi</b>\n"
        msg += f"📅 {now.strftime('%d.%m.%Y %H:%M')}\n\n"

        if finalized:
            msg += f"<b>✅ Finalizate: {len(finalized)}</b>\n"
            for oid, d, days in finalized:
                msg += f"  • #{oid} (livrat {d.strftime('%d.%m.%Y')}, {days}z)\n"
            msg += "\n"

        if waiting:
            msg += f"⏳ Așteaptă: {len(waiting)} comenzi\n"

        if no_delivery:
            msg += f"\n⚠️ Fără dată livrare: {', '.join(f'#{x}' for x in no_delivery)}\n"

        send_telegram(msg)

    elif not dry_run and not finalized:
        # Trimite notificare doar dacă sunt comenzi care așteaptă
        if waiting:
            # Găsim prima comandă care va fi finalizată
            next_order = min(waiting, key=lambda x: x[3])
            msg = f"<b>🔄 Auto-finalizare comenzi</b>\n"
            msg += f"📅 {now.strftime('%d.%m.%Y %H:%M')}\n\n"
            msg += f"📭 Nicio comandă de finalizat azi.\n"
            msg += f"⏳ {len(waiting)} comenzi așteaptă.\n"
            msg += f"📌 Următoarea: #{next_order[0]} pe {(next_order[1] + timedelta(days=DAYS_TO_FINALIZE)).strftime('%d.%m.%Y')}"
            send_telegram(msg)

    logger.info("")
    logger.info("✅ Proces terminat.")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    # Suportă flag --dry-run pentru testare
    dry_run = "--dry-run" in sys.argv or "-d" in sys.argv

    try:
        process_orders(dry_run=dry_run)
    except Exception as e:
        logger.error(f"💥 Eroare fatală: {e}")
        import traceback
        traceback.print_exc()

        # Trimite eroarea pe Telegram
        try:
            send_telegram(
                f"💥 <b>EROARE auto_finalize_orders.py</b>\n\n{str(e)}")
        except:
            pass

        sys.exit(1)
