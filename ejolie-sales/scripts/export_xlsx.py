#!/usr/bin/env python3
"""Export ejolie sales data to Excel"""

import sys
import os
import json
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import parse_period, api_get, fetch_orders, filter_orders_by_brand

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
except ImportError:
    print("Installing openpyxl...")
    os.system("pip3 install openpyxl --break-system-packages -q")
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter


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

    headers = ["Nr Comandă", "Data", "Client", "Telefon", "Status", "Metoda Plată",
               "Valoare", "Transport", "Total", "Produse"]

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
        products_list = []
        produse = order.get("produse", {})
        if isinstance(produse, dict):
            for p in produse.values():
                if isinstance(p, dict):
                    name = p.get("nume", "?")
                    qty = p.get("cantitate", 1)
                    products_list.append(f"{name} x{qty}")

        # Safe extraction - some fields may be str or dict
        status = order.get("status", "")
        status_name = status.get("nume", "") if isinstance(status, dict) else str(status)
        
        plata = order.get("metoda_plata", "")
        plata_name = plata.get("nume", "") if isinstance(plata, dict) else str(plata)
        
        client = order.get("date_client", {})
        if isinstance(client, dict):
            shipping = client.get("shipping", {})
            if isinstance(shipping, dict):
                client_name = shipping.get("nume", "")
                client_phone = shipping.get("telefon", "")
            else:
                client_name = str(shipping)
                client_phone = ""
        else:
            client_name = str(client)
            client_phone = ""

        try:
            valoare = float(order.get("valoare", 0))
        except (ValueError, TypeError):
            valoare = 0.0
        try:
            transport = float(order.get("transport", 0))
        except (ValueError, TypeError):
            transport = 0.0
        try:
            total = float(order.get("total", 0))
        except (ValueError, TypeError):
            total = 0.0

        row_data = [
            order.get("numar_comanda", ""),
            order.get("data", ""),
            client_name,
            client_phone,
            status_name,
            plata_name,
            valoare,
            transport,
            total,
            "; ".join(products_list),
        ]

        for col, val in enumerate(row_data, 1):
            cell = ws.cell(row=row_idx, column=col, value=val)
            cell.border = thin_border
            if col in (7, 8, 9):
                cell.number_format = '#,##0.00'

    # Auto-width
    for col in range(1, len(headers) + 1):
        max_len = len(str(headers[col-1]))
        for row in range(2, min(len(orders) + 2, 50)):
            val = ws.cell(row=row, column=col).value
            if val:
                max_len = max(max_len, min(len(str(val)), 50))
        ws.column_dimensions[get_column_letter(col)].width = max_len + 3

    # === Sheet 2: Sumar ===
    ws2 = wb.create_sheet("Sumar")

    total_val = sum(float(o.get("valoare", 0) or 0) for o in orders.values())
    total_transport = sum(float(o.get("transport", 0) or 0) for o in orders.values())
    total_total = sum(float(o.get("total", 0) or 0) for o in orders.values())

    # Payment methods
    pay_methods = {}
    for o in orders.values():
        plata = o.get("metoda_plata", "")
        pm = plata.get("nume", "Necunoscut") if isinstance(plata, dict) else str(plata) or "Necunoscut"
        pay_methods[pm] = pay_methods.get(pm, 0) + 1

    # Product counts
    prod_counts = {}
    for o in orders.values():
        produse = o.get("produse", {})
        if isinstance(produse, dict):
            for p in produse.values():
                if isinstance(p, dict):
                    name = p.get("nume", "?")
                    qty = int(float(p.get("cantitate", 1)))
                    prod_counts[name] = prod_counts.get(name, 0) + qty

    top_products = sorted(prod_counts.items(), key=lambda x: -x[1])[:20]

    summary_data = [
        ["RAPORT VÂNZĂRI - " + label, ""],
        ["", ""],
        ["Total comenzi", len(orders)],
        ["Valoare totală", total_val],
        ["Transport total", total_transport],
        ["Valoare netă", total_val - total_transport],
        ["Medie per comandă", total_val / len(orders) if orders else 0],
        ["", ""],
        ["METODE PLATĂ", "Comenzi"],
    ]
    for pm, cnt in pay_methods.items():
        summary_data.append([pm, cnt])

    summary_data.append(["", ""])
    summary_data.append(["TOP 20 PRODUSE", "Cantitate"])
    for name, qty in top_products:
        summary_data.append([name, qty])

    title_font = Font(bold=True, size=14, color="1F4E79")
    section_font = Font(bold=True, size=11, color="1F4E79")

    for row_idx, (a, b) in enumerate(summary_data, 1):
        ws2.cell(row=row_idx, column=1, value=a)
        cell_b = ws2.cell(row=row_idx, column=2, value=b)
        if row_idx == 1:
            ws2.cell(row=row_idx, column=1).font = title_font
        elif a in ("METODE PLATĂ", "TOP 20 PRODUSE"):
            ws2.cell(row=row_idx, column=1).font = section_font
            cell_b.font = section_font
        if isinstance(b, float):
            cell_b.number_format = '#,##0.00'

    ws2.column_dimensions['A'].width = 45
    ws2.column_dimensions['B'].width = 15

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
