"""
Utility functions for ejolie.ro Extended API integration.
Handles API calls, date parsing, and report formatting.
"""

import os
import sys
import json
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timedelta
from collections import Counter

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────

API_KEY = os.environ.get("EJOLIE_API_KEY", "")
DOMAIN = os.environ.get("EJOLIE_DOMAIN", "ejolie.ro")
BASE_URL = f"https://{DOMAIN}/api/"

# Status IDs
STATUS_INCASATA = "14"
STATUS_RETURNATA = "9"

# Romanian month names → month number
MONTHS_RO = {
    "ianuarie": 1, "februarie": 2, "martie": 3, "aprilie": 4,
    "mai": 5, "iunie": 6, "iulie": 7, "august": 8,
    "septembrie": 9, "octombrie": 10, "noiembrie": 11, "decembrie": 12,
}

# Report type → status filter
REPORT_STATUS = {
    "vanzari": None,
    "incasate": STATUS_INCASATA,
    "returnate": STATUS_RETURNATA,
}

# Report type → emoji and label
REPORT_LABELS = {
    "vanzari": ("📊", "VÂNZĂRI"),
    "incasate": ("💰", "ÎNCASATE"),
    "returnate": ("🔄", "RETURNATE"),
}


# ──────────────────────────────────────────────
# Date Parsing
# ──────────────────────────────────────────────

def parse_period(period_text: str) -> tuple[str, str, str]:
    """
    Parse Romanian period text into (data_start, data_end, label).
    Dates returned in DD-MM-YYYY format for the Extended API.
    """
    text = period_text.strip().lower()
    today = datetime.now()

    if text in ("azi", "astazi", "today"):
        d = today
        return (
            d.strftime("%d-%m-%Y"),
            d.strftime("%d-%m-%Y"),
            f"Azi ({d.strftime('%d-%m-%Y')})",
        )

    if text in ("ieri", "yesterday"):
        d = today - timedelta(days=1)
        return (
            d.strftime("%d-%m-%Y"),
            d.strftime("%d-%m-%Y"),
            f"Ieri ({d.strftime('%d-%m-%Y')})",
        )

    if text in ("luna asta", "luna aceasta", "this month"):
        start = today.replace(day=1)
        return (
            start.strftime("%d-%m-%Y"),
            today.strftime("%d-%m-%Y"),
            f"Luna aceasta ({start.strftime('%d-%m-%Y')} - {today.strftime('%d-%m-%Y')})",
        )

    if text in ("luna trecuta", "luna anterioara", "last month"):
        first_this_month = today.replace(day=1)
        last_prev = first_this_month - timedelta(days=1)
        start_prev = last_prev.replace(day=1)
        return (
            start_prev.strftime("%d-%m-%Y"),
            last_prev.strftime("%d-%m-%Y"),
            f"Luna trecută ({start_prev.strftime('%d-%m-%Y')} - {last_prev.strftime('%d-%m-%Y')})",
        )

    # Specific month name: "ianuarie", "februarie" etc.
    if text in MONTHS_RO:
        month_num = MONTHS_RO[text]
        year = today.year
        if month_num > today.month:
            year -= 1
        start = datetime(year, month_num, 1)
        if month_num == 12:
            end = datetime(year, 12, 31)
        else:
            end = datetime(year, month_num + 1, 1) - timedelta(days=1)
        return (
            start.strftime("%d-%m-%Y"),
            end.strftime("%d-%m-%Y"),
            f"{text.capitalize()} {year} ({start.strftime('%d-%m-%Y')} - {end.strftime('%d-%m-%Y')})",
        )

    # Explicit range: "de la DD-MM-YYYY pana la DD-MM-YYYY"
    if "de la" in text and "pana" in text:
        try:
            parts = text.replace("până", "pana")
            start_str = parts.split("de la")[1].split("pana")[0].strip()
            end_str = parts.split("pana la")[1].strip(
            ) if "pana la" in parts else parts.split("pana")[1].strip()
            start_dt = datetime.strptime(start_str, "%d-%m-%Y")
            end_dt = datetime.strptime(end_str, "%d-%m-%Y")
            return (
                start_str,
                end_str,
                f"{start_dt.strftime('%d-%m-%Y')} - {end_dt.strftime('%d-%m-%Y')}",
            )
        except (ValueError, IndexError):
            pass

    # Fallback: try to parse as a single date
    for fmt in ("%d-%m-%Y", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            d = datetime.strptime(text, fmt)
            return (
                d.strftime("%d-%m-%Y"),
                d.strftime("%d-%m-%Y"),
                d.strftime("%d-%m-%Y"),
            )
        except ValueError:
            continue

    # Default: today
    print(
        f"⚠️ Nu am putut interpreta perioada '{period_text}'. Folosesc data de azi.")
    d = today
    return (
        d.strftime("%d-%m-%Y"),
        d.strftime("%d-%m-%Y"),
        f"Azi ({d.strftime('%d-%m-%Y')})",
    )


# ──────────────────────────────────────────────
# API Calls
# ──────────────────────────────────────────────

def api_get(endpoint: str, params: dict = None) -> dict:
    """Make a GET request to the Extended API."""
    if not API_KEY:
        print("❌ Eroare: EJOLIE_API_KEY nu este setat în variabilele de mediu.")
        sys.exit(1)

    if params is None:
        params = {}
    params["apikey"] = API_KEY

    query = "&".join(
        f"{k}={urllib.parse.quote(str(v))}" if v else k
        for k, v in params.items()
    )
    url = f"{BASE_URL}?{endpoint}&{query}"

    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Extended API"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data, dict) and data.get("eroare") == 1:
                print(
                    f"❌ Eroare API: {data.get('mesaj', 'Eroare necunoscută')}")
                sys.exit(1)
            return data
    except urllib.error.URLError as e:
        print(f"❌ Eroare conexiune: {e}")
        sys.exit(1)
    except json.JSONDecodeError:
        print("❌ Eroare: Răspuns invalid de la API.")
        sys.exit(1)


def fetch_orders(data_start: str, data_end: str, idstatus: str = None) -> dict:
    """Fetch orders from Extended API for a given period and optional status."""
    params = {
        "comenzi": "",
        "data_start": data_start,
        "data_end": data_end,
        "limit": "2000",
    }
    if idstatus:
        params["idstatus"] = idstatus

    return api_get("comenzi", params)


# ──────────────────────────────────────────────
# Report Calculations
# ──────────────────────────────────────────────

def calculate_report(orders: dict) -> dict:
    """Calculate report metrics from orders data."""
    if not orders or (isinstance(orders, dict) and orders.get("eroare")):
        return {
            "total_comenzi": 0,
            "valoare_totala": 0.0,
            "transport_total": 0.0,
            "valoare_neta": 0.0,
            "medie_comanda": 0.0,
            "top_produse": [],
            "metode_plata": Counter(),
        }

    total_comenzi = 0
    valoare_totala = 0.0
    transport_total = 0.0
    product_counter = Counter()
    metode_plata = Counter()

    for order_id, order in orders.items():
        if not isinstance(order, dict):
            continue

        total_comenzi += 1

        try:
            total = float(str(order.get("total_comanda", 0)).replace(",", "."))
            valoare_totala += total
        except (ValueError, TypeError):
            pass

        try:
            shipping = float(
                str(order.get("pret_livrare", 0)).replace(",", "."))
            transport_total += shipping
        except (ValueError, TypeError):
            pass

        metoda = order.get("metoda_plata", "Necunoscut")
        metode_plata[metoda] += 1

        produse = order.get("produse", {})
        if isinstance(produse, dict):
            for prod_id, prod in produse.items():
                if isinstance(prod, dict):
                    nume = prod.get("nume", "Produs necunoscut")
                    try:
                        cantitate = int(
                            float(str(prod.get("cantitate", 1)).replace(",", ".")))
                    except (ValueError, TypeError):
                        cantitate = 1
                    if "discount" not in nume.lower():
                        product_counter[nume] += cantitate

    valoare_neta = valoare_totala - transport_total
    medie_comanda = valoare_totala / total_comenzi if total_comenzi > 0 else 0.0
    top_produse = product_counter.most_common(5)

    return {
        "total_comenzi": total_comenzi,
        "valoare_totala": valoare_totala,
        "transport_total": transport_total,
        "valoare_neta": valoare_neta,
        "medie_comanda": medie_comanda,
        "top_produse": top_produse,
        "metode_plata": metode_plata,
    }


# ──────────────────────────────────────────────
# Report Formatting
# ──────────────────────────────────────────────

def format_number(n: float) -> str:
    """Format number Romanian style: 1.000,50"""
    return f"{n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_report(report_type: str, period_label: str, metrics: dict) -> str:
    """Format report for WhatsApp output."""
    emoji, label = REPORT_LABELS.get(report_type, ("📊", "VÂNZĂRI"))

    lines = [
        f"{emoji} RAPORT {label} - {period_label}",
        "━" * 35,
        f"📦 Total comenzi: {metrics['total_comenzi']}",
        f"💰 Valoare totală: {format_number(metrics['valoare_totala'])} RON",
        f"🚚 Transport total: {format_number(metrics['transport_total'])} RON",
        f"💵 Valoare netă: {format_number(metrics['valoare_neta'])} RON",
        f"📈 Medie per comandă: {format_number(metrics['medie_comanda'])} RON",
    ]

    if metrics["metode_plata"]:
        lines.append("━" * 35)
        lines.append("💳 Metode plată:")
        for metoda, count in metrics["metode_plata"].most_common():
            lines.append(f"  • {metoda}: {count} comenzi")

    if metrics["top_produse"]:
        lines.append("━" * 35)
        lines.append("🏆 Top produse:")
        for i, (name, qty) in enumerate(metrics["top_produse"], 1):
            short_name = name[:40] + "..." if len(name) > 40 else name
            lines.append(f"  {i}. {short_name} - {qty} buc")

    lines.append("━" * 35)
    return "\n".join(lines)
