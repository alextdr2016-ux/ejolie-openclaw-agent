---
name: ejolie_sales_report
description: Generate sales report for ejolie.ro for a custom date range
version: 1.0.0
author: Alex
---

# Sales Report Generator

This skill generates detailed sales reports from ejolie.ro for any date range.

## Usage

User can request:

- "Raport vânzări de la 01-01-2024 până la 31-01-2024"
- "Sales report for January 2024"
- "Vânzări ultima săptămână"

## How it works

1. Extract date range from user message
2. Call Python script: `python ~/ejolie-openclaw-agent/scripts/report_generator.py sales START_DATE END_DATE`
3. Return formatted report to user

## Implementation

```python
import subprocess
import re
from datetime import datetime, timedelta

def extract_dates(message):
    """Extract start and end dates from user message"""
    # Pattern: "de la DD-MM-YYYY până la DD-MM-YYYY"
    pattern = r'de la (\d{2}-\d{2}-\d{4}) până la (\d{2}-\d{2}-\d{4})'
    match = re.search(pattern, message)

    if match:
        return match.group(1), match.group(2)

    # Handle "ultima săptămână"
    if 'ultima săptămână' in message.lower():
        end = datetime.now()
        start = end - timedelta(days=7)
        return start.strftime('%d-%m-%Y'), end.strftime('%d-%m-%Y')

    # Handle "luna asta"
    if 'luna asta' in message.lower():
        end = datetime.now()
        start = end.replace(day=1)
        return start.strftime('%d-%m-%Y'), end.strftime('%d-%m-%Y')

    return None, None

# Main execution
user_message = "{user_input}"
start_date, end_date = extract_dates(user_message)

if start_date and end_date:
    result = subprocess.run(
        ['python3', '/home/ubuntu/ejolie-openclaw-agent/scripts/report_generator.py',
         'sales', start_date, end_date],
        capture_output=True,
        text=True
    )
    print(result.stdout)
else:
    print("Te rog specifică perioada: 'de la DD-MM-YYYY până la DD-MM-YYYY'")
```

## Example Output

```
📊 **RAPORT VÂNZĂRI**
Perioadă: 01-02-2024 - 29-02-2024

💰 **Rezumat Financiar:**
- Total vânzări: 45,230.50 RON
- Număr comenzi: 127
- Valoare medie comandă: 356.15 RON

📦 **Produse vândute:**
- Total articole: 342 bucăți
- Produse distincte: 89

🔝 **Top 5 Produse:**
1. Rochie Summer Dress: 23 buc
2. Bluza Casual White: 18 buc
3. Pantaloni Denim: 15 buc
4. Geacă Elegantă: 12 buc
5. Fustă Mini Black: 11 buc
```
