#!/usr/bin/env python3
"""
Ejolie.ro Sales Report Generator
Generates sales, collected, and returned order reports via Extended API.

Usage:
    python3 ejolie-sales/scripts/sales_report.py --type vanzari --period "azi"
    python3 ejolie-sales/scripts/sales_report.py --type incasate --period "luna asta"
    python3 ejolie-sales/scripts/sales_report.py --type returnate --period "ianuarie"
    python3 ejolie-sales/scripts/sales_report.py --type vanzari --period "de la 01-01-2026 pana la 31-01-2026"

Environment variables:
    EJOLIE_API_KEY  - Extended API key (required)
    EJOLIE_DOMAIN   - Domain name (default: ejolie.ro)
"""

from utils import (
    parse_period,
    fetch_orders,
    calculate_report,
    format_report,
    REPORT_STATUS,
)
import argparse
import sys
import os

# Add scripts directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    parser = argparse.ArgumentParser(
        description="Ejolie.ro Sales Report Generator")
    parser.add_argument(
        "--type",
        choices=["vanzari", "incasate", "returnate"],
        required=True,
        help="Report type: vanzari (all), incasate (paid), returnate (returned)",
    )
    parser.add_argument(
        "--period",
        required=True,
        help='Period: "azi", "ieri", "luna asta", "luna trecuta", "ianuarie"..."decembrie", '
             'or "de la DD-MM-YYYY pana la DD-MM-YYYY"',
    )
    args = parser.parse_args()

    # 1. Parse period
    data_start, data_end, period_label = parse_period(args.period)

    # 2. Get status filter
    idstatus = REPORT_STATUS.get(args.type)

    # 3. Fetch orders from API
    orders = fetch_orders(data_start, data_end, idstatus)

    # 4. Calculate metrics
    metrics = calculate_report(orders)

    # 5. Format and print report
    report = format_report(args.type, period_label, metrics)
    print(report)


if __name__ == "__main__":
    main()
