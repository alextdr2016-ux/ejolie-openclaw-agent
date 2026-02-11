#!/usr/bin/env python3
"""Ejolie.ro Stock Report - per size, per brand"""

import sys
import os
import json
import argparse
import urllib.request
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FEED_FILE = os.path.join(SCRIPT_DIR, "product_feed.json")

# Load API config
env_path = os.path.join(SCRIPT_DIR, ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                k, v = line.strip().split('=', 1)
                os.environ[k] = v

API_KEY = os.environ.get("EJOLIE_API_KEY", "")
API_URL = os.environ.get("EJOLIE_API_URL", "https://ejolie.ro/api/")


def load_feed():
    with open(FEED_FILE) as f:
        return json.load(f)


def fetch_products_batch(product_ids, batch_size=20):
    """Fetch product details in batches to avoid timeout"""
    all_products = {}
    total = len(product_ids)
    
    for i in range(0, total, batch_size):
        batch = product_ids[i:i+batch_size]
        ids_str = ",".join(batch)
        url = f"{API_URL}?produse&id_produse={ids_str}&apikey={API_KEY}"
        
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            data = json.loads(urllib.request.urlopen(req, timeout=120).read().decode("utf-8"))
            all_products.update(data)
            done = min(i + batch_size, total)
            print(f"  📡 {done}/{total} produse preluate...")
        except Exception as e:
            print(f"  ⚠️ Eroare batch {i}-{i+batch_size}: {e}")
        
        time.sleep(0.5)  # Be nice to API
    
    return all_products


def generate_stock_report(brand=None, only_in_stock=True):
    """Generate stock report per product per size"""
    print("📦 Se generează raportul de stoc...")
    
    # Get product IDs from feed, filtered by brand
    feed = load_feed()
    product_ids = []
    
    for p in feed:
        pid = p.get("id", "")
        p_brand = p.get("brand", "").lower()
        
        if brand:
            if brand.lower() not in p_brand:
                continue
        
        if pid:
            product_ids.append(pid)
    
    print(f"📋 {len(product_ids)} produse găsite{f' (brand: {brand})' if brand else ''}")
    
    if not product_ids:
        print("❌ Nu am găsit produse!")
        return []
    
    # Fetch all product details with stock
    products = fetch_products_batch(product_ids)
    
    # Build stock data
    rows = []
    total_in_stock = 0
    total_out_stock = 0
    
    for pid, prod in products.items():
        prod_name = prod.get("nume", "?")
        prod_code = prod.get("cod_produs", "")
        prod_brand = prod.get("brand", {})
        brand_name = prod_brand.get("nume", "?") if isinstance(prod_brand, dict) else str(prod_brand)
        prod_price = prod.get("pret_discount") or prod.get("pret", "0")
        prod_stoc_general = prod.get("stoc", "?")
        
        optiuni = prod.get("optiuni", {})
        if not isinstance(optiuni, dict) or not optiuni:
            # No sizes
            in_stock = "In stoc" in str(prod_stoc_general)
            if only_in_stock and not in_stock:
                continue
            rows.append({
                "produs": prod_name,
                "cod": prod_code,
                "brand": brand_name,
                "marime": "-",
                "stoc": prod_stoc_general,
                "in_stock": in_stock,
                "pret": float(prod_price) if prod_price else 0,
            })
            if in_stock:
                total_in_stock += 1
            else:
                total_out_stock += 1
            continue
        
        for oid, opt in optiuni.items():
            size_name = opt.get("nume_optiune", "?")
            size_stock = opt.get("stoc", "?")
            size_price = opt.get("pret", prod_price)
            in_stock = "In stoc" in str(size_stock)
            
            if only_in_stock and not in_stock:
                continue
            
            rows.append({
                "produs": prod_name,
                "cod": prod_code,
                "brand": brand_name,
                "marime": size_name,
                "stoc": size_stock,
                "in_stock": in_stock,
                "pret": float(size_price) if size_price else 0,
            })
            
            if in_stock:
                total_in_stock += 1
            else:
                total_out_stock += 1
    
    print(f"✅ {total_in_stock} mărimi în stoc, {total_out_stock} fără stoc")
    return rows


def export_xlsx(rows, brand=None, output=None):
    """Export stock to Excel"""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        os.system("pip3 install openpyxl --break-system-packages -q")
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
    
    if output is None:
        brand_label = f"_{brand}" if brand else ""
        output = f"/home/ubuntu/raport_stoc{brand_label}.xlsx"
    
    wb = openpyxl.Workbook()
    
    # Sheet 1: Stoc Detaliat
    ws = wb.active
    ws.title = "Stoc pe Mărimi"
    
    headers = ["Produs", "Cod", "Brand", "Mărime", "Stoc", "Preț (RON)"]
    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)
    green_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    red_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
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
    
    for row_idx, r in enumerate(rows, 2):
        data = [r["produs"], r["cod"], r["brand"], r["marime"], r["stoc"], r["pret"]]
        for col, val in enumerate(data, 1):
            cell = ws.cell(row=row_idx, column=col, value=val)
            cell.border = thin_border
            if col == 5:  # Stoc column
                cell.fill = green_fill if r["in_stock"] else red_fill
            if col == 6:
                cell.number_format = '#,##0.00'
    
    # Auto-width
    widths = [45, 15, 12, 10, 12, 12]
    for col, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(col)].width = w
    
    # Sheet 2: Sumar per Produs
    ws2 = wb.create_sheet("Sumar Produse")
    sum_headers = ["Produs", "Cod", "Brand", "Mărimi în Stoc", "Total Mărimi", "Preț"]
    
    for col, h in enumerate(sum_headers, 1):
        cell = ws2.cell(row=1, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")
        cell.border = thin_border
    
    # Group by product
    prod_summary = {}
    for r in rows:
        key = r["cod"] or r["produs"]
        if key not in prod_summary:
            prod_summary[key] = {
                "produs": r["produs"], "cod": r["cod"], "brand": r["brand"],
                "in_stock": 0, "total": 0, "pret": r["pret"]
            }
        prod_summary[key]["total"] += 1
        if r["in_stock"]:
            prod_summary[key]["in_stock"] += 1
    
    for row_idx, (key, s) in enumerate(sorted(prod_summary.items(), key=lambda x: x[1]["produs"]), 2):
        data = [s["produs"], s["cod"], s["brand"], s["in_stock"], s["total"], s["pret"]]
        for col, val in enumerate(data, 1):
            cell = ws2.cell(row=row_idx, column=col, value=val)
            cell.border = thin_border
            if col == 6:
                cell.number_format = '#,##0.00'
    
    widths2 = [45, 15, 12, 15, 15, 12]
    for col, w in enumerate(widths2, 1):
        ws2.column_dimensions[get_column_letter(col)].width = w
    
    wb.save(output)
    print(f"✅ Excel salvat: {output}")
    return output


def main():
    parser = argparse.ArgumentParser(description="Ejolie.ro Stock Report")
    parser.add_argument("--brand", default=None, help="Filter by brand: ejolie, trendya, artista")
    parser.add_argument("--all", action="store_true", help="Include out of stock items")
    parser.add_argument("--output", default=None)
    parser.add_argument("--format", choices=["text", "xlsx"], default="xlsx")
    args = parser.parse_args()
    
    rows = generate_stock_report(brand=args.brand, only_in_stock=not args.all)
    
    if args.format == "xlsx":
        output = export_xlsx(rows, brand=args.brand, output=args.output)
        print(f"XLSX {output}")
    else:
        # Text output
        print(f"\n📦 RAPORT STOC{f' - {args.brand.upper()}' if args.brand else ''}")
        print("━" * 60)
        current_prod = ""
        for r in rows:
            if r["produs"] != current_prod:
                current_prod = r["produs"]
                print(f"\n{r['produs']} ({r['cod']}) - {r['pret']} RON")
            status = "✅" if r["in_stock"] else "❌"
            print(f"  {status} Mărime {r['marime']}: {r['stoc']}")


if __name__ == "__main__":
    main()
