---
name: ejolie_stock_alert
description: Check low stock items on ejolie.ro
version: 1.0.0
author: Alex
---

# Stock Alert System

Monitor inventory levels and alert when products are running low.

## Usage

User requests:

- "Stoc critic"
- "Ce produse au stoc scăzut?"
- "Check inventory"

## Implementation

```python
import subprocess

result = subprocess.run(
    ['python3', '/home/ubuntu/ejolie-openclaw-agent/scripts/report_generator.py', 'stock'],
    capture_output=True,
    text=True
)

print(result.stdout)
```

## Threshold

Default: Products with less than 5 units in stock
Can be customized by passing threshold parameter.
