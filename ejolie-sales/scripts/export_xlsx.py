#!/usr/bin/env python3
"""Export ejolie sales data to Excel"""

import sys
import os
import json
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import parse_period, fetch_orders, filter_orders_by_brand

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
except ImportError:
    os.system("pip3 install openpyxl --break-system-packages -q")
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter


def safe_float(val, default=0.0):
    try:
        return float(val) if val is not None else default
    except (ValueError, TypeError):
        return default


def export_orders_xlsx(period="luna trecuta", brand=None, output=None):
    data_start, data_end, label = parse_period(period)

    if output is None:
        safe_label = label.replace(" ", "_").replace("/", "-").replace("(", "").replace(")", "")
        output = f"/home/ubuntu/raport_vanzari_{safe_label}.xlsx"

    print(f"📅 Perioadă: {label}")
    print(f"📡 Se preiau comenzile...")

    orders = fetch_orders(data_start, data_end)
    if brand:
        orders = filter_orders_by_brand(orders, brand)

    print(f"✅ {len(orders)} comenzi găsite")

    wb = openpyxl.Workbook()

    # === Sheet 1: Comenzi ===
    ws = wb.active
    ws.title = "Comenzi"

    headers = ["Nr Comandă", "Data", "Client", "Telefon", "Județ", "Status",
               "Metoda Plată", "Produse", "Valoare Produse", "Transport", "Total Comandă"]

    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )

    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")
        cell.border = thin_border

    for row_idx, order in enumerate(orders.values(), 2):
        # Products list & value
        products_list = []
        val_produse = 0.0
        produse = order.get("produse", {})
        if isinstance(produse, dict):
            for p in produse.values():
                if isinstance(p, dict):
                    name = p.get("nume", "?")
                    qty = int(float(p.get("cantitate", 1)))
                    pret = safe_float(p.get("pret_unitar", 0))
                    val_produse += pret * qty
                    products_list.append(f"{name} x{qty}")

        # Client info
        client = order.get("client", {})
        if isinstance(client, dict):
            client_name = client.get("nume", "")
            client_phone = client.get("telefon", "")
            livrare = client.get("livrare", {})
            judet = livrare.get("judet", "") if isinstance(livrare, dict) else ""
        else:
            client_name = str(client)
            client_phone = ""
            judet = ""

        total_comanda = safe_float(order.get("total_comanda", 0))
        pret_livrare = safe_float(order.get("pret_livrare", 0))

        row_data = [
            order.get("id_comanda", ""),
            order.get("data", ""),
            client_name,
            client_phone,
            judet,
            order.get("status", ""),
            order.get("metoda_plata", ""),
            "; ".join(products_list),
            val_produse,
            pret_livrare,
            total_comanda,
        ]

        for col, val in enumerate(row_data, 1):
            cell = ws.cell(row=row_idx, column=col, value=val)
            cell.border = thin_border
            if col in (9, 10, 11):
                cell.number_format = '#,##0.00'

    # Auto-width
    for col in range(1, len(headers) + 1):
        max_len = len(str(headers[col-1]))
        for row in range(2, min(len(orders) + 2, 50)):
            val = ws.cell(row=row, column=col).value
            if val:
                max_len = max(max_len, min(len(str(val)), 50))
        ws.column_dimensions[get_column_letter(col)].width = max_len + 3

    # === Sheet 2: Produse Detail ===
    ws_prod = wb.create_sheet("Produse")
    prod_headers = ["Nr Comandă", "Data", "Produs", "Brand", "Categorie", "Cantitate",
                    "Preț Unitar", "Preț Fără Discount", "Discount", "Total Produs"]

    for col, h in enumerate(prod_headers, 1):
        cell = ws_prod.cell(row=1, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")
        cell.border = thin_border

    prod_row = 2
    for order in orders.values():
        produse = order.get("produse", {})
        if not isinstance(produse, dict):
            continue
        for p in produse.values():
            if not isinstance(p, dict):
                continue
            qty = int(float(p.get("cantitate", 1)))
            pret = safe_float(p.get("pret_unitar", 0))
            pret_full = safe_float(p.get("pret_unitar_fara_discount", 0))
            discount = safe_float(p.get("discount_unitar_valoric", 0))

            row_data = [
                order.get("id_comanda", ""),
                order.get("data", ""),
                p.get("nume", ""),
                p.get("brand_nume", ""),
                p.get("categorie_nume", ""),
                qty,
                pret,
                pret_full,
                discount,
                pret * qty,
            ]
            for col, val in enumerate(row_data, 1):
                cell = ws_prod.cell(row=prod_row, column=col, value=val)
                cell.border = thin_border
                if col in (7, 8, 9, 10):
                    cell.number_format = '#,##0.00'
            prod_row += 1

    for col in range(1, len(prod_headers) + 1):
        ws_prod.column_dimensions[get_column_letter(col)].width = 18

    # === Sheet 3: Sumar ===
    ws2 = wb.create_sheet("Sumar")

    total_val = sum(safe_float(o.get("total_comanda", 0)) for o in orders.values())
    total_transport = sum(safe_float(o.get("pret_livrare", 0)) for o in orders.values())

    # Payment methods
    pay_methods = {}
    for o in orders.values():
        pm = o.get("metoda_plata", "Necunoscut") or "Necunoscut"
        pay_methods[pm] = pay_methods.get(pm, 0) + 1

    # Product counts & revenue
    prod_stats = {}
    for o in orders.values():
        produse = o.get("produse", {})
        if not isinstance(produse, dict):
            continue
        for p in produse.values():
            if not isinstance(p, dict):
                continue
            name = p.get("nume", "?")
            brand_name = p.get("brand_nume", "?")
            qty = int(float(p.get("cantitate", 1)))
            pret = safe_float(p.get("pret_unitar", 0))
            key = name
            if key not in prod_stats:
                prod_stats[key] = {"qty": 0, "revenue": 0, "brand": brand_name}
            prod_stats[key]["qty"] += qty
            prod_stats[key]["revenue"] += pret * qty

    top_products = sorted(prod_stats.items(), key=lambda x: -x[1]["revenue"])[:20]

    # Brand summary
    brand_stats = {}
    for name, stats in prod_stats.items():
        b = stats["brand"]
        if b not in brand_stats:
            brand_stats[b] = {"qty": 0, "revenue": 0, "orders": 0}
        brand_stats[b]["qty"] += stats["qty"]
        brand_stats[b]["revenue"] += stats["revenue"]

    summary_data = [
        ["RAPORT VÂNZĂRI - " + label, ""],
        ["", ""],
        ["Total comenzi", len(orders)],
        ["Valoare totală", total_val],
        ["Transport total", total_transport],
        ["Valoare netă (fără transport)", total_val - total_transport],
        ["Medie per comandă", total_val / len(orders) if orders else 0],
        ["", ""],
        ["METODE PLATĂ", "Comenzi"],
    ]
    for pm, cnt in sorted(pay_methods.items(), key=lambda x: -x[1]):
        summary_data.append([pm, cnt])

    summary_data.append(["", ""])
    summary_data.append(["PE BRANDURI", "Venit (RON)"])
    for b, stats in sorted(brand_stats.items(), key=lambda x: -x[1]["revenue"]):
        summary_data.append([f"{b} ({stats['qty']} buc)", stats["revenue"]])

    summary_data.append(["", ""])
    summary_data.append(["TOP 20 PRODUSE", "Venit (RON)"])
    for name, stats in top_products:
        summary_data.append([f"{name} ({stats['qty']} buc)", stats["revenue"]])

    title_font = Font(bold=True, size=14, color="1F4E79")
    section_font = Font(bold=True, size=11, color="1F4E79")

    for row_idx, (a, b) in enumerate(summary_data, 1):
        ws2.cell(row=row_idx, column=1, value=a)
        cell_b = ws2.cell(row=row_idx, column=2, value=b)
        if row_idx == 1:
            ws2.cell(row=row_idx, column=1).font = title_font
        elif a in ("METODE PLATĂ", "PE BRANDURI", "TOP 20 PRODUSE"):
            ws2.cell(row=row_idx, column=1).font = section_font
            cell_b.font = section_font
        if isinstance(b, float):
            cell_b.number_format = '#,##0.00'

    ws2.column_dimensions['A'].width = 55
    ws2.column_dimensions['B'].width = 18

    wb.save(output)
    print(f"✅ Excel salvat: {output}")
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", default="luna trecuta")
    parser.add_argument("--brand", default=None)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    output = export_orders_xlsx(args.period, args.brand, args.output)
    print(f"XLSX {output}")


if __name__ == "__main__":
    main()
