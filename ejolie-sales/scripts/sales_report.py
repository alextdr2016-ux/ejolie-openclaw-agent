#!/usr/bin/env python3
"""Ejolie.ro Sales Report Generator"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("⏳ Se generează raportul... (poate dura până la 60s)", flush=True)

from utils import (
    parse_period,
    fetch_orders,
    calculate_report,
    format_report,
    calculate_product_report,
    format_product_report,
    calculate_profit_report,
    format_profit_report,
    filter_orders_by_brand,
    REPORT_STATUS,
)
import argparse

RESULT_FILE = "/tmp/ejolie_last_report.txt"


def main():
    parser = argparse.ArgumentParser(description="Ejolie.ro Sales Report Generator")
    parser.add_argument("--type", choices=["vanzari", "incasate", "returnate", "produse", "profit"], required=True)
    parser.add_argument("--period", required=True)
    parser.add_argument("--brand", default=None, help="Filter by brand: ejolie, trendya, artista")
    parser.add_argument("--furnizor", default=None, help="Alias for --brand")
    parser.add_argument("--check", action="store_true", help="Check last report result")
    parser.add_argument("--format", default="text", choices=["text", "xlsx"], help="Output format: text or xlsx")
    args = parser.parse_args()

    if args.check:
        if os.path.exists(RESULT_FILE):
            with open(RESULT_FILE) as f:
                print(f.read())
        else:
            print("⏳ Raportul nu este încă gata.")
        return

    brand = args.brand or args.furnizor

    data_start, data_end, period_label = parse_period(args.period)
    filter_label = f" [🏷️ {brand.capitalize()}]" if brand else ""
    print(f"📅 Perioadă: {period_label}{filter_label}", flush=True)

    print("📡 Se preiau comenzile din API...", flush=True)

    if args.type == "profit":
        # Profit uses incasate (status 14) by default
        orders = fetch_orders(data_start, data_end, "14")
        print(f"✅ {len(orders)} comenzi încasate găsite.", flush=True)
        metrics = calculate_profit_report(orders, brand_filter=brand)
        report = format_profit_report(period_label, metrics, brand_name=brand)

    elif args.type == "produse":
        orders = fetch_orders(data_start, data_end)
        print(f"✅ {len(orders)} comenzi găsite.", flush=True)
        metrics = calculate_product_report(orders, brand_filter=brand)
        report = format_product_report(period_label, metrics, brand_name=brand)

    else:
        idstatus = REPORT_STATUS.get(args.type)
        orders = fetch_orders(data_start, data_end, idstatus)
        if brand:
            orders = filter_orders_by_brand(orders, brand)
            print(f"🏷️ Filtrat după '{brand}': {len(orders)} comenzi rămase.", flush=True)
        else:
            print(f"✅ {len(orders)} comenzi găsite.", flush=True)
        metrics = calculate_report(orders, brand_filter=brand)
        report = format_report(args.type, period_label, metrics, brand_name=brand)

    with open(RESULT_FILE, "w") as f:
        f.write(report)

    print(report)


if __name__ == "__main__":
    main()
