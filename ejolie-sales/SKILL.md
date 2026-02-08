---
name: ejolie-sales
description: >
  Generate sales, revenue, and return reports for ejolie.ro e-commerce store.
  Use when the user asks for sales reports, revenue reports, order summaries,
  collected/paid orders, returned orders, or any e-commerce analytics.
  Triggers: "raport vanzari", "raport incasate", "raport returnate",
  "sales report", "revenue", "comenzi", "vanzari azi", "vanzari luna".
---

# Ejolie Sales Reports

Generate sales and order reports for ejolie.ro via the Extended API.

## Commands

The user sends WhatsApp messages in Romanian. Parse the intent:

| Message Pattern             | Action                                    |
| --------------------------- | ----------------------------------------- |
| `raport vanzari {period}`   | All orders for period                     |
| `raport incasate {period}`  | Only paid/collected orders (status_id=14) |
| `raport returnate {period}` | Only returned orders (status_id=9)        |

## Period Parsing

| Input                                 | Meaning                                     |
| ------------------------------------- | ------------------------------------------- |
| `azi`                                 | Today                                       |
| `ieri`                                | Yesterday                                   |
| `luna asta` / `luna aceasta`          | 1st of current month → today                |
| `luna trecuta`                        | 1st → last day of previous month            |
| `ianuarie` ... `decembrie`            | 1st → last day of that month (current year) |
| `de la DD-MM-YYYY pana la DD-MM-YYYY` | Exact date range                            |

## Running Reports

Execute the sales report script:

```bash
python3 ejolie-sales/scripts/sales_report.py --type {vanzari|incasate|returnate} --period "{period_text}"
```

The script reads `EJOLIE_API_KEY` and `EJOLIE_DOMAIN` from environment variables.

## Output Format

```
📊 RAPORT VÂNZĂRI - Azi (08-02-2026)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📦 Total comenzi: 15
💰 Valoare totală: 4.250,00 RON
🚚 Transport total: 375,00 RON
💵 Valoare netă: 3.875,00 RON
📈 Medie per comandă: 283,33 RON
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💳 Metode plată:
  • Ramburs: 10 comenzi
  • Card: 5 comenzi
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏆 Top produse:
  1. Rochie Summer Blue - 5 buc
  2. Bluza Elegance White - 3 buc
  3. Fusta Classic Black - 2 buc
```

## Status IDs Reference

| ID  | Status                |
| --- | --------------------- |
| 1   | Comanda NOUA          |
| 2   | Comanda in PROCESARE  |
| 4   | Comanda in ASTEPTARE  |
| 9   | Comanda RETURNATA     |
| 10  | Comanda ANULATA       |
| 14  | Comanda INCASATA      |
| 37  | Comanda SCHIMB        |
| 38  | Comanda REFUZATA      |
| 40  | Storno partial Manual |
| 41  | Merchant REV          |
| 43  | Trendya               |
| 44  | Smartex               |

## API Reference

For detailed Extended API documentation, see [references/api_docs.md](references/api_docs.md).
