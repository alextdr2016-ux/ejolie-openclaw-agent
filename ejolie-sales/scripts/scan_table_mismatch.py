#!/usr/bin/env python3
"""
scan_table_mismatch.py - Verifică dacă produsele au tabelul de mărimi corect
Compară tabelul din descriere (3col/4col) cu specificația "Croi" din API
"""

import json, requests, re, os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(SCRIPT_DIR, '..', '.env')

def load_env(path):
    env = {}
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    k, v = line.strip().split('=', 1)
                    env[k] = v
    return env

env = load_env(ENV_PATH)

with open(os.path.join(SCRIPT_DIR, 'generated_descriptions.json')) as f:
    descriptions = {str(p['id']): p for p in json.load(f)}

print(f"📋 {len(descriptions)} descrieri loaded")
print("🔄 Fetch produse din API...")

url = f"https://ejolie.ro/api/?produse&apikey={env['EJOLIE_API_KEY']}"
r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=300)
all_products = r.json()
print(f"✅ {len(all_products)} produse din API")

TABLE_4COL = 'Tabel%20M%20General%20Trendya'
TABLE_3COL = 'Tabel-Marimi-3col'

MULAT_KEYWORDS = ['mulat', 'cambrat', 'sirena', 'conic']
LEJER_KEYWORDS = ['lejer', 'evazat', 'in a', 'clos', 'drept', 'plisat', 'volane']

ok = []
mismatch_needs_3 = []
mismatch_needs_4 = []
no_table = []
no_croi = []

for pid, desc in descriptions.items():
    html = desc['description_html']
    name = desc['name']

    has_4col = TABLE_4COL in html
    has_3col = TABLE_3COL in html
    has_table = has_4col or has_3col

    if not has_table:
        no_table.append(f'[{pid}] {name}')
        continue

    prod = all_products.get(str(pid))
    croi = ''
    if prod:
        specs = prod.get('specificatii', [])
        for s in specs:
            if s.get('nume', '').lower() == 'croi':
                croi = ', '.join(s.get('valoare', []))

    if not croi:
        tbl = "4col" if has_4col else "3col"
        no_croi.append(f'[{pid}] {name} — tabel {tbl} dar FARA specificatie croi')
        continue

    croi_lower = croi.lower()
    is_mulat = any(x in croi_lower for x in MULAT_KEYWORDS)
    is_lejer = any(x in croi_lower for x in LEJER_KEYWORDS)

    if has_4col and is_lejer:
        mismatch_needs_3.append(f'[{pid}] {name} — Croi: {croi} → ARE 4col, TREBUIE 3col')
    elif has_3col and is_mulat:
        mismatch_needs_4.append(f'[{pid}] {name} — Croi: {croi} → ARE 3col, TREBUIE 4col')
    elif has_4col and is_mulat:
        ok.append(f'[{pid}] {name} — Croi: {croi} ✅ 4col')
    elif has_3col and is_lejer:
        ok.append(f'[{pid}] {name} — Croi: {croi} ✅ 3col')
    else:
        tbl = "4col" if has_4col else "3col"
        no_croi.append(f'[{pid}] {name} — Croi: {croi}, tabel {tbl} (croi necunoscut)')

print('=' * 80)
print('📊 SCAN TABEL MĂRIMI vs CROI')
print('=' * 80)

print(f'\n✅ CORECT: {len(ok)}')
for p in ok:
    print(f'  {p}')

print(f'\n🔴 GREȘIT — Are 4col dar trebuie 3col (croi lejer): {len(mismatch_needs_3)}')
for p in mismatch_needs_3:
    print(f'  {p}')

print(f'\n🔴 GREȘIT — Are 3col dar trebuie 4col (croi mulat): {len(mismatch_needs_4)}')
for p in mismatch_needs_4:
    print(f'  {p}')

print(f'\n⚪ Fără tabel imagine (au Extended table): {len(no_table)}')

print(f'\n❓ Fără specificație croi sau croi necunoscut: {len(no_croi)}')
for p in no_croi:
    print(f'  {p}')

print(f'\n📊 TOTAL: {len(descriptions)} produse scanate')