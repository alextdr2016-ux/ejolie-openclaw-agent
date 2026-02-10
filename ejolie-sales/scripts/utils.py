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
# Configuration - load .env if env vars not set
# ──────────────────────────────────────────────

def _load_env_file():
    """Load variables from .env file in skill root directory."""
    env_paths = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"),
        os.path.expanduser("~/.openclaw/workspace/skills/ejolie-sales/.env"),
    ]
    for env_path in env_paths:
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        os.environ.setdefault(key.strip(), value.strip())
            break

_load_env_file()

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

    # Strip "luna " prefix: "luna ianuarie" → "ianuarie"
    if text.startswith("luna "):
        month_candidate = text[5:].strip()
        if month_candidate in MONTHS_RO:
            text = month_candidate

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

    # Normalize text for range parsing
    normalized = text.replace("până", "pana").replace("pînă", "pana")

    # Explicit range: "de la DD-MM-YYYY pana la DD-MM-YYYY"
    if "de la" in normalized and "pana" in normalized:
        try:
            start_str = normalized.split("de la")[1].split("pana")[0].strip()
            end_str = normalized.split("pana la")[1].strip() if "pana la" in normalized else normalized.split("pana")[1].strip()
            start_dt = datetime.strptime(start_str, "%d-%m-%Y")
            end_dt = datetime.strptime(end_str, "%d-%m-%Y")
            return (
                start_str,
                end_str,
                f"{start_dt.strftime('%d-%m-%Y')} - {end_dt.strftime('%d-%m-%Y')}",
            )
        except (ValueError, IndexError):
            pass

    # Range with "pana la" without "de la": "06-02-2026 pana la 08-02-2026"
    if "pana la" in normalized or "pana" in normalized:
        try:
            sep = "pana la" if "pana la" in normalized else "pana"
            parts = normalized.split(sep)
            start_str = parts[0].strip()
            end_str = parts[1].strip()
            start_dt = datetime.strptime(start_str, "%d-%m-%Y")
            end_dt = datetime.strptime(end_str, "%d-%m-%Y")
            return (
                start_str,
                end_str,
                f"{start_dt.strftime('%d-%m-%Y')} - {end_dt.strftime('%d-%m-%Y')}",
            )
        except (ValueError, IndexError):
            pass

    # Range with dash or "to": "06-02-2026 - 08-02-2026" or "06-02-2026 to 08-02-2026"
    import re as _re
    range_match = _re.match(
        r"(\d{2}[-.]\d{2}[-.]\d{4})\s*(?:-|to|la|–|—)\s*(\d{2}[-.]\d{2}[-.]\d{4})",
        normalized,
    )
    if range_match:
        try:
            s = range_match.group(1).replace(".", "-")
            e = range_match.group(2).replace(".", "-")
            start_dt = datetime.strptime(s, "%d-%m-%Y")
            end_dt = datetime.strptime(e, "%d-%m-%Y")
            return (
                s,
                e,
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
        with urllib.request.urlopen(req, timeout=180) as resp:
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


def fetch_orders(data_start: str, data_end: str, idstatus: str = None, idfurnizor: str = None) -> dict:
    """Fetch orders from Extended API for a given period, optional status and supplier."""
    params = {
        "comenzi": "",
        "data_start": data_start,
        "data_end": data_end,
        "limit": "2000",
    }
    if idstatus:
        params["idstatus"] = idstatus
    if idfurnizor:
        params["idfurnizor"] = idfurnizor

    return api_get("comenzi", params)


# ──────────────────────────────────────────────
# Brand Filtering
# ──────────────────────────────────────────────

# Brand name aliases for flexible matching
BRAND_ALIASES = {
    "ejolie": ["ejolie", "e-jolie"],
    "trendya": ["trendya"],
    "artista": ["artista"],
    "godeea": ["godeea", "go deea"],
    "benush": ["benush"],
    "fabrex": ["fabrex"],
}


# Furnizor name → API id
FURNIZORI = {
    "ejolie": "1",
    "trendya": "2",
    "artista": "3",
    "godeea": "4",
    "benush": "5",
    "fabrex": "6",
}


def filter_orders_by_brand(orders: dict, brand_name: str) -> dict:
    """Filter orders to only include products matching the given brand.
    Returns orders that have at least one product from the brand,
    with non-matching products removed."""
    if not brand_name or not orders:
        return orders

    brand_lower = brand_name.strip().lower()
    # Find matching aliases
    match_names = BRAND_ALIASES.get(brand_lower, [brand_lower])

    filtered = {}
    for order_id, order in orders.items():
        if not isinstance(order, dict):
            continue

        produse = order.get("produse", {})
        if not isinstance(produse, dict):
            continue

        # Filter products by brand
        filtered_products = {}
        brand_total = 0.0
        for prod_id, prod in produse.items():
            if not isinstance(prod, dict):
                continue
            prod_brand = prod.get("brand_nume", "").strip().lower()
            if any(alias in prod_brand for alias in match_names):
                filtered_products[prod_id] = prod
                try:
                    brand_total += float(prod.get("pret_unitar", 0)) * float(prod.get("cantitate", 1))
                except (ValueError, TypeError):
                    pass

        if filtered_products:
            # Clone order with only matching products
            order_copy = dict(order)
            order_copy["produse"] = filtered_products
            # Recalculate order total based on filtered products
            order_copy["total_comanda"] = brand_total
            order_copy["pret_livrare"] = 0  # Can't split shipping per brand
            filtered[order_id] = order_copy

    return filtered


# ──────────────────────────────────────────────
# Report Calculations
# ──────────────────────────────────────────────

def calculate_report(orders: dict, brand_filter: str = None) -> dict:
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


def format_report(report_type: str, period_label: str, metrics: dict, brand_name: str = None) -> str:
    """Format report for WhatsApp output."""
    emoji, label = REPORT_LABELS.get(report_type, ("📊", "VÂNZĂRI"))

    brand_tag = f" [🏷️ {brand_name.capitalize()}]" if brand_name else ""
    lines = [
        f"{emoji} RAPORT {label} - {period_label}{brand_tag}",
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



# ──────────────────────────────────────────────
# Product Report
# ──────────────────────────────────────────────

def calculate_product_report(orders: dict, brand_filter: str = None) -> dict:
    """Calculate product-level metrics from orders."""
    from collections import Counter, defaultdict

    if not orders:
        return {"products": Counter(), "sizes": Counter(), "models": Counter(), 
                "total_products": 0, "total_qty": 0}

    products = Counter()       # "Rochie X (Marime: 38)" → qty
    sizes = Counter()          # "38" → qty
    models = Counter()         # "Rochie X" → qty
    brand_products = Counter() # brand → qty

    total_qty = 0

    for oid, order in orders.items():
        if not isinstance(order, dict):
            continue
        for pid, prod in order.get("produse", {}).items():
            if not isinstance(prod, dict):
                continue

            # Brand filter
            if brand_filter:
                prod_brand = prod.get("brand_nume", "").strip().lower()
                if brand_filter.lower() not in prod_brand:
                    continue

            nume = prod.get("nume", "Produs necunoscut")
            try:
                qty = int(float(str(prod.get("cantitate", 1)).replace(",", ".")))
            except (ValueError, TypeError):
                qty = 1

            if "discount" in nume.lower():
                continue

            total_qty += qty
            products[nume] += qty

            # Extract size
            if "Marime:" in nume:
                size = nume.split("Marime:")[1].split(")")[0].strip()
                # Handle multiple sizes like "Marime Sacou: 46, Marime Fusta: 46"
                if "," not in size:
                    sizes[size] += qty

            # Extract base model (without size)
            if "(Marime" in nume:
                base = nume.split("(Marime")[0].strip()
            elif "(Marime Sacou" in nume:
                base = nume.split("(Marime Sacou")[0].strip()
            else:
                base = nume
            models[base] += qty

            # Brand stats
            brand = prod.get("brand_nume", "Necunoscut")
            brand_products[brand] += qty

    return {
        "products": products,
        "sizes": sizes,
        "models": models,
        "brands": brand_products,
        "total_products": len(products),
        "total_qty": total_qty,
    }


def format_product_report(period_label: str, metrics: dict, brand_name: str = None) -> str:
    """Format product report for WhatsApp."""
    brand_tag = f" [🏷️ {brand_name.capitalize()}]" if brand_name else ""

    lines = [
        f"👗 RAPORT PRODUSE - {period_label}{brand_tag}",
        "━" * 35,
        f"📦 Total produse unice: {metrics['total_products']}",
        f"🛒 Total bucăți vândute: {metrics['total_qty']}",
    ]

    # Top models (aggregated without size)
    if metrics["models"]:
        lines.append("━" * 35)
        lines.append("🏆 Top 10 modele (toate mărimile):")
        for i, (name, qty) in enumerate(metrics["models"].most_common(10), 1):
            short = name[:35] + "..." if len(name) > 35 else name
            lines.append(f"  {i}. {short} — {qty} buc")

    # Top products with size
    if metrics["products"]:
        lines.append("━" * 35)
        lines.append("📏 Top 10 produse + mărime:")
        for i, (name, qty) in enumerate(metrics["products"].most_common(10), 1):
            short = name[:40] + "..." if len(name) > 40 else name
            lines.append(f"  {i}. {short} — {qty} buc")

    # Top sizes
    if metrics["sizes"]:
        lines.append("━" * 35)
        lines.append("📐 Top mărimi vândute:")
        for size, qty in metrics["sizes"].most_common():
            lines.append(f"  • Mărime {size}: {qty} buc")

    # Brand breakdown
    if metrics["brands"] and not brand_name:
        lines.append("━" * 35)
        lines.append("🏷️ Pe branduri:")
        for brand, qty in metrics["brands"].most_common():
            lines.append(f"  • {brand}: {qty} buc")

    lines.append("━" * 35)
    return "\n".join(lines)



# ──────────────────────────────────────────────
# Profit Report
# ──────────────────────────────────────────────

COST_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cost_cache.json")


def load_cost_cache() -> dict:
    """Load cost cache from file."""
    if os.path.exists(COST_CACHE_FILE):
        with open(COST_CACHE_FILE) as f:
            return json.load(f)
    return {}


def calculate_profit_report(orders: dict, brand_filter: str = None) -> dict:
    """Calculate profit metrics using cost cache."""
    cost_map = load_cost_cache()

    if not orders:
        return {
            "total_revenue": 0, "total_cost": 0, "total_profit": 0,
            "margin": 0, "products": [], "missing_cost": 0,
            "total_comenzi": 0,
        }

    total_revenue = 0.0
    total_cost = 0.0
    missing_cost = 0
    products = []
    order_ids = set()

    for oid, order in orders.items():
        if not isinstance(order, dict):
            continue

        for pid, prod in order.get("produse", {}).items():
            if not isinstance(prod, dict):
                continue

            # Brand filter
            if brand_filter:
                prod_brand = prod.get("brand_nume", "").strip().lower()
                if brand_filter.lower() not in prod_brand:
                    continue

            opt_id = str(prod.get("id_optiune", ""))
            try:
                sell = float(str(prod.get("pret_unitar", 0)).replace(",", "."))
                qty = int(float(str(prod.get("cantitate", 1)).replace(",", ".")))
            except (ValueError, TypeError):
                continue

            if "discount" in prod.get("nume", "").lower():
                continue

            cost_data = cost_map.get(opt_id)
            cost = cost_data["pret_lista"] if cost_data else 0
            if not cost_data:
                missing_cost += 1

            profit = (sell - cost) * qty
            total_revenue += sell * qty
            total_cost += cost * qty
            order_ids.add(oid)

            products.append({
                "nume": prod.get("nume", "?"),
                "sell": sell,
                "cost": cost,
                "profit": profit,
                "qty": qty,
                "brand": prod.get("brand_nume", "?"),
            })

    total_profit = total_revenue - total_cost
    margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0

    # Sort by profit descending
    products.sort(key=lambda x: x["profit"], reverse=True)

    return {
        "total_revenue": total_revenue,
        "total_cost": total_cost,
        "total_profit": total_profit,
        "margin": margin,
        "products": products,
        "missing_cost": missing_cost,
        "total_comenzi": len(order_ids),
    }


def format_profit_report(period_label: str, metrics: dict, brand_name: str = None) -> str:
    """Format profit report for WhatsApp."""
    brand_tag = f" [🏷️ {brand_name.capitalize()}]" if brand_name else ""

    # Split products with known cost vs unknown
    with_cost = [p for p in metrics["products"] if p["cost"] > 0]
    without_cost = [p for p in metrics["products"] if p["cost"] == 0 and p["sell"] > 0]
    returns = [p for p in metrics["products"] if p["sell"] < 0]

    rev_known = sum(p["sell"] * p["qty"] for p in with_cost)
    cost_known = sum(p["cost"] * p["qty"] for p in with_cost)
    profit_known = rev_known - cost_known
    margin_known = (profit_known / rev_known * 100) if rev_known > 0 else 0
    rev_unknown = sum(p["sell"] * p["qty"] for p in without_cost)
    rev_returns = sum(p["sell"] * p["qty"] for p in returns)

    lines = [
        f"💵 RAPORT PROFIT - {period_label}{brand_tag}",
        "━" * 35,
        f"📦 Total comenzi: {metrics['total_comenzi']}",
        f"💰 Venituri totale: {format_number(metrics['total_revenue'])} RON",
    ]

    if returns:
        lines.append(f"🔄 Retururi/Discount: {format_number(rev_returns)} RON")

    lines.append("━" * 35)
    lines.append("✅ PROFIT CALCULAT (produse cu cost cunoscut):")
    lines.append(f"  💰 Venituri: {format_number(rev_known)} RON ({len(with_cost)} produse)")
    lines.append(f"  📦 Cost achiziție: {format_number(cost_known)} RON")
    lines.append(f"  💵 PROFIT: {format_number(profit_known)} RON")
    lines.append(f"  📈 Marjă: {margin_known:.1f}%")

    if without_cost:
        lines.append("")
        lines.append(f"⚠️ FĂRĂ COST ({len(without_cost)} produse, {format_number(rev_unknown)} RON venituri)")
        lines.append(f"  Profitul real e mai mare, dar nu poate fi calculat exact")

    # Top profitable (only with known cost)
    top = sorted(with_cost, key=lambda x: x["profit"], reverse=True)
    if top:
        lines.append("━" * 35)
        lines.append("🏆 Top 10 cele mai profitabile:")
        for i, p in enumerate(top[:10], 1):
            short = p["nume"][:30] + "..." if len(p["nume"]) > 30 else p["nume"]
            margin_p = ((p["sell"] - p["cost"]) / p["sell"] * 100) if p["sell"] > 0 else 0
            lines.append(f"  {i}. {short}")
            lines.append(f"     {format_number(p['sell'])} → cost {format_number(p['cost'])} = {format_number(p['profit'])} ({margin_p:.0f}%)")

    # Least profitable (only with known cost, excluding returns)
    low = sorted(with_cost, key=lambda x: (x["sell"] - x["cost"]) / x["sell"] if x["sell"] > 0 else 999)
    if len(low) > 3:
        lines.append("━" * 35)
        lines.append("⚠️ Marjă mică (sub 40%):")
        shown = 0
        for p in low:
            if p["sell"] <= 0:
                continue
            margin_p = ((p["sell"] - p["cost"]) / p["sell"] * 100)
            if margin_p < 40:
                short = p["nume"][:30] + "..." if len(p["nume"]) > 30 else p["nume"]
                lines.append(f"  • {short}")
                lines.append(f"    {format_number(p['sell'])} → cost {format_number(p['cost'])} = {format_number(p['profit'])} ({margin_p:.0f}%)")
                shown += 1
                if shown >= 5:
                    break
        if shown == 0:
            lines.append("  Toate produsele au marjă peste 40% 👍")

    lines.append("━" * 35)
    return "\n".join(lines)
