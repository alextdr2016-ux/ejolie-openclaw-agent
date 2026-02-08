#!/usr/bin/env python3
"""Ejolie.ro Product Search"""

import sys
import os
import json
import argparse

FEED_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "product_feed.json")


def load_products():
    with open(FEED_FILE) as f:
        return json.load(f)


def search_products(query, limit=10):
    products = load_products()
    query_lower = query.lower().strip()
    words = query_lower.split()

    results = []
    for p in products:
        title = p.get("title", "").lower()
        category = p.get("category", "").lower()
        brand = p.get("brand", "").lower()
        desc = p.get("description", "").lower()

        # All words must match in title, category, brand or description
        if all(w in title or w in category or w in brand or w in desc for w in words):
            results.append(p)

    return results[:limit]


def format_results(results, query):
    if not results:
        return f"❌ Nu am găsit produse pentru '{query}'. Încearcă alt cuvânt cheie."

    lines = [
        f"🔍 Rezultate pentru '{query}': {len(results)} produse",
        "━" * 35,
    ]

    for i, p in enumerate(results, 1):
        title = p["title"]
        price = p.get("price", "N/A")
        sale = p.get("sale_price", "")
        link = p.get("link", "")
        image = p.get("image", "")
        available = p.get("available", "")

        lines.append(f"{i}. 👗 {title}")

        if sale and sale != price:
            lines.append(f"   💰 {sale} (redus de la {price})")
        else:
            lines.append(f"   💰 {price}")

        if available == "in stock":
            lines.append(f"   ✅ În stoc")
        else:
            lines.append(f"   ❌ Indisponibil")

        lines.append(f"   🔗 {link}")
        if image:
            lines.append(f"   🖼️ {image}")
        lines.append("")

    lines.append("━" * 35)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Ejolie.ro Product Search")
    parser.add_argument("--query", required=True, help="Search query")
    parser.add_argument("--limit", type=int, default=10, help="Max results")
    args = parser.parse_args()

    results = search_products(args.query, args.limit)
    print(format_results(results, args.query))


if __name__ == "__main__":
    main()
