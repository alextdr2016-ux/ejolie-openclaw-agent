#!/usr/bin/env python3
"""Ejolie.ro SEO Product Tool - fetch product details for SEO optimization"""

import sys
import os
import json
import argparse
import re

FEED_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "product_feed.json")


def load_products():
    with open(FEED_FILE) as f:
        return json.load(f)


def get_product(query, limit=5):
    products = load_products()
    query_lower = query.lower().strip()
    words = query_lower.split()

    results = []
    for p in products:
        title = p.get("title", "").lower()
        if all(w in title for w in words):
            results.append(p)

    return results[:limit]


def audit_products():
    """Find products with weak SEO (short/missing descriptions)."""
    products = load_products()

    no_desc = []
    short_desc = []
    good = 0

    for p in products:
        desc = p.get("description", "").strip()
        title = p.get("title", "")
        clean_desc = re.sub(r'&[a-z]+;', '', desc)
        clean_desc = re.sub(r'<[^>]+>', '', clean_desc).strip()

        if len(clean_desc) < 10:
            no_desc.append(title)
        elif len(clean_desc) < 100:
            short_desc.append((title, len(clean_desc)))
        else:
            good += 1

    lines = [
        "🔍 AUDIT SEO PRODUSE",
        "━" * 35,
        f"✅ Descrieri bune (100+ caractere): {good}",
        f"⚠️ Descrieri scurte (<100 char): {len(short_desc)}",
        f"❌ Fără descriere: {len(no_desc)}",
        f"📊 Total produse: {len(products)}",
    ]

    if no_desc:
        lines.append("━" * 35)
        lines.append("❌ Produse FĂRĂ descriere:")
        for title in no_desc[:10]:
            lines.append(f"  • {title}")
        if len(no_desc) > 10:
            lines.append(f"  ... și încă {len(no_desc) - 10}")

    if short_desc:
        lines.append("━" * 35)
        lines.append("⚠️ Descrieri SCURTE:")
        for title, length in short_desc[:10]:
            lines.append(f"  • {title} ({length} char)")
        if len(short_desc) > 10:
            lines.append(f"  ... și încă {len(short_desc) - 10}")

    lines.append("━" * 35)
    return "\n".join(lines)


def format_product_for_seo(product):
    """Format product data for SEO generation."""
    title = product.get("title", "")
    desc = product.get("description", "")
    price = product.get("price", "")
    sale_price = product.get("sale_price", "")
    category = product.get("category", "")
    brand = product.get("brand", "")
    link = product.get("link", "")
    image = product.get("image", "")

    clean_desc = re.sub(r'&[a-z]+;', ' ', desc)
    clean_desc = re.sub(r'<[^>]+>', '', clean_desc).strip()
    clean_desc = re.sub(r'\s+', ' ', clean_desc)

    lines = [
        f"📦 DETALII PRODUS PENTRU SEO",
        "━" * 35,
        f"Titlu actual: {title}",
        f"Brand: {brand}",
        f"Categorie: {category}",
        f"Preț: {price}",
    ]
    if sale_price and sale_price != price:
        lines.append(f"Preț redus: {sale_price}")
    lines.append(f"Link: {link}")
    lines.append(f"Imagine: {image}")
    lines.append("━" * 35)
    lines.append(f"Descriere actuală ({len(clean_desc)} caractere):")
    lines.append(clean_desc if clean_desc else "(LIPSĂ)")
    lines.append("━" * 35)

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Ejolie.ro SEO Product Tool")
    parser.add_argument("--action", choices=["search", "audit"], required=True)
    parser.add_argument("--query", default=None, help="Product name to search")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    if args.action == "audit":
        print(audit_products())
    elif args.action == "search":
        if not args.query:
            print("❌ Specifică --query pentru căutare")
            return
        results = get_product(args.query, args.limit)
        if not results:
            print(f"❌ Nu am găsit produse pentru '{args.query}'")
            return
        for p in results:
            print(format_product_for_seo(p))
            print()


if __name__ == "__main__":
    main()
