---
name: ejolie_profit_margins
description: Analyze profit margins for products
version: 1.0.0
author: Alex
---

# Profit Margins Analysis

Calculate and report profit margins by comparing purchase prices with sale prices.

## Usage

- "Analiza profit februarie"
- "Profit margins last month"
- "Care produse aduc cel mai mult profit?"

## Implementation

```python
import subprocess
import re
from datetime import datetime, timedelta

def extract_dates(message):
    # Same date extraction logic as sales_report
    pattern = r'de la (\d{2}-\d{2}-\d{4}) până la (\d{2}-\d{2}-\d{4})'
    match = re.search(pattern, message)

    if match:
        return match.group(1), match.group(2)

    return None, None

user_message = "{user_input}"
start_date, end_date = extract_dates(user_message)

if start_date and end_date:
    result = subprocess.run(
        ['python3', '/home/ubuntu/ejolie-openclaw-agent/scripts/report_generator.py',
         'profit', start_date, end_date],
        capture_output=True,
        text=True
    )
    print(result.stdout)
else:
    print("Specifică perioada pentru analiza profitului")
```
