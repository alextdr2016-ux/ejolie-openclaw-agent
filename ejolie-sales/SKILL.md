---
name: ejolie-sales
description: >
  Complete skill set for ejolie.ro e-commerce management.
  Covers: sales reports, product descriptions, blog content,
  stock management, SEO, specs, and Trendyol export.
  All scripts in: ~/ejolie-openclaw-agent/ejolie-sales/scripts/
  Env vars in: ~/ejolie-openclaw-agent/ejolie-sales/.env
---

# Ejolie Sales Reports

Generate sales and order reports for ejolie.ro via the Extended API.

## Commands

The user sends WhatsApp messages in Romanian. Parse the intent:

| Message Pattern             | Action                                     |
| --------------------------- | ------------------------------------------ |
| `raport vanzari {period}`   | All orders for period                      |
| `raport incasate {period}`  | Only paid/collected orders (status_id=14)  |
| `raport returnate {period}` | Only returned orders (status_id=9)         |

## Period Parsing

| Input                           | Meaning                                          |
| ------------------------------- | ------------------------------------------------ |
| `azi` / `today`                 | Today only                                       |
| `ieri` / `yesterday`            | Yesterday only                                   |
| `saptamana` / `week`            | Current week (Monday to now)                     |
| `luna` / `month`                | Current month (1st to now)                       |
| `luna trecuta` / `last month`   | Previous full month                              |
| `ianuarie` ... `decembrie`      | Named month of current year                      |

## Script

```bash
cd /home/ubuntu/ejolie-openclaw-agent/ejolie-sales && source .env
python3 scripts/sales_report.py --period {period} [--status {status_id}]
```

## Output Format

```
📊Total comenzi: 15
💰Valoare totală: 4.250,00 RON
🚚Transport total: 375,00 RON
💵Valoare netă: 3.875,00 RON
💳Medie per comandă: 283,33 RON

💳Metode plată:
• Ramburs: 10 comenzi
• Card: 5 comenzi

🏆Top produse:
1. Rochie Summer Blue - 5 buc
2. Bluza Elegance White - 3 buc
```

---

# Product Descriptions Pipeline

Generate and upload product descriptions using Gemini Vision.

## Trigger Words
"adaugă descrieri", "descrieri produse", "produse fără descriere", "descrieri noi", "descriptions"

## Pipeline Steps

```bash
cd /home/ubuntu/ejolie-openclaw-agent/ejolie-sales && source .env

# Step 1: Scan products without descriptions
python3 scripts/scan_no_description.py

# Step 2: Generate descriptions with Gemini 2.5 Flash Vision
python3 scripts/generate_descriptions.py

# Step 3: Upload to Extended admin
python3 scripts/upload_descriptions.py
```

## Technical Details
- Gemini 2.5 Flash Vision with thinkingBudget: 0 (MANDATORY - otherwise outputs only 17 words)
- Each description: 100-150 words Romanian, 2 paragraphs + "Detalii produs" bullets + "Sugestie styling"
- Extended admin field: camp_descriere (hidden by elRTE editor)
- Login verification: check for camp_nume in product page response
- Size table: mulat croi = 4-col image (ejolie.ro), lejer = 3-col image (S3)
- 4-col URL: https://ejolie.ro/continut/upload/Tabel%20M%20General%20Trendya.png
- 3-col URL: https://ejolie-assets.s3.eu-north-1.amazonaws.com/images/Tabel-Marimi-3col.png

## Report After Completion
Tell Alex: how many scanned, generated, uploaded, any failures.

---

# Blog Pipeline

Auto-generate and publish SEO blog articles.

## Trigger Words
"blog", "articol", "publică articol", "SEO content", "blog post"

## Script

```bash
cd /home/ubuntu/ejolie-openclaw-agent/ejolie-sales && source .env
python3 scripts/blog_autopublish.py
```

## What It Does
1. Picks keyword from 40 predefined SEO keywords
2. Generates article with Claude Sonnet (primary) or Gemini Flash (fallback)
3. Generates hero image with Gemini nano-banana-pro-preview
4. Publishes to Extended admin blog
5. Sends Telegram notification

## Technical Details
- Product cache: blog_products.json (670 products)
- Images log: images_log.json (uniqueness tracking)
- Cron: Monday + Thursday at 08:00
- Allowed HTML: h2, h3, p, strong, em, a, img, ul, li, br
- FORBIDDEN: div, span, style, hr, CSS inline

## Report: article title, URL, keyword used.

---

# Stock Reports

## Trigger Words
"stoc", "stock", "inventar", "mărimi", "ce avem în stoc"

## Scripts

```bash
cd /home/ubuntu/ejolie-openclaw-agent/ejolie-sales && source .env

# Quick text report
python3 scripts/stock_report.py --brand ejolie --format text

# Excel report
python3 scripts/stock_report.py --brand ejolie --format xlsx

# Update cache (also runs every 4h via cron)
python3 scripts/stock_cache_update.py
```

## Details
- Cache: scripts/stock_cache.json (677 products)
- Flags: --all (include out of stock), --brand ejolie/trendya/artista
- stoc_fizic field has exact quantity per size

---

# SEO Management

## SEO Audit
```bash
cd /home/ubuntu/ejolie-openclaw-agent/ejolie-sales && source .env
python3 scripts/seo_audit.py --brand ejolie --format xlsx
```

## SEO Programmatic Pages
32 pages at /manager/seo_link_filtru. Script: scripts/seo_all_30.py

## SEO Meta Optimize
```bash
python3 scripts/seo_optimize.py --limit 109
```
Note: Extended has NO API for meta updates - manual only.

---

# Specs & Product Management

## Trigger Words
"specificatii", "specs", "filtre", "update produse", "export trendyol"

## Scripts
```bash
cd /home/ubuntu/ejolie-openclaw-agent/ejolie-sales && source .env
python3 scripts/specs_audit_and_fill.py    # Audit + GPT fill
python3 scripts/export_trendyol.py          # Trendyol export
python3 scripts/export_import_template.py   # Extended import
```

## 6 Specifications
Culoare, Material, Lungime, Croi, Stil, Model (all are filters)

---

# Status IDs Reference

| ID | Status | ID | Status |
|----|--------|----|--------|
| 1  | NOUA   | 10 | ANULATA |
| 2  | PROCESARE | 14 | INCASATA |
| 4  | ASTEPTARE | 37 | SCHIMB |
| 9  | RETURNATA | 38 | REFUZATA |

## API Reference
See [references/api_docs.md](references/api_docs.md).
