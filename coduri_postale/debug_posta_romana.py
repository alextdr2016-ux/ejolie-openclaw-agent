#!/usr/bin/env python3
"""Debug: vezi ce returneaza exact API-ul Postei Romane"""

import requests
import json

BASE_URL = "https://www.posta-romana.ro"
URL_CAUTARE = f"{BASE_URL}/cnpr-app/modules/cauta-cod-postal/ajax/cautare_pentru_cod.php?q="

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "ro-RO,ro;q=0.9,en;q=0.8",
    "Referer": "https://www.posta-romana.ro/ccp.html",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": "https://www.posta-romana.ro",
}

session = requests.Session()

# 1. Mai intai incarcam pagina principala (pentru cookies)
print("[1] Incarc pagina ccp.html pentru cookies...")
resp = session.get(f"{BASE_URL}/ccp.html", headers=HEADERS, timeout=10)
print(f"    Status: {resp.status_code}")
print(f"    Cookies: {dict(session.cookies)}")

# 2. Incarcam localitati (cauta_orase) - asta seteaza sesiunea
print("\n[2] Incarc localitati Dolj...")
resp2 = session.post(
    f"{BASE_URL}/cnpr-app/modules/cauta-cod-postal/ajax/cauta_orase.php?q=",
    data={"judet": "Dolj"},
    headers=HEADERS,
    timeout=10
)
print(f"    Status: {resp2.status_code}")
print(f"    Response (first 500): {resp2.text[:500]}")

# 3. Cautam Calea Bucuresti in Craiova
print("\n[3] Caut 'Calea Bucuresti' in Craiova...")
resp3 = session.post(
    URL_CAUTARE,
    data={
        "judet": "Dolj",
        "localitate": "Craiova",
        "adresa": "Calea Bucuresti",
    },
    headers=HEADERS,
    timeout=10
)
print(f"    Status: {resp3.status_code}")
print(f"    Content-Type: {resp3.headers.get('Content-Type')}")
print(f"    Response length: {len(resp3.text)}")
print(f"\n    RAW RESPONSE:")
print(resp3.text[:3000])

# 4. Cautam cu litera 'a'
print("\n\n[4] Caut litera 'a' in Craiova...")
resp4 = session.post(
    URL_CAUTARE,
    data={
        "judet": "Dolj",
        "localitate": "Craiova",
        "adresa": "a",
    },
    headers=HEADERS,
    timeout=10
)
print(f"    Status: {resp4.status_code}")
print(f"    Response length: {len(resp4.text)}")
print(f"\n    RAW RESPONSE:")
print(resp4.text[:3000])

# 5. Cautam fara adresa (Almaj - sat cu cod unic)
print("\n\n[5] Caut Almaj fara adresa...")
resp5 = session.post(
    URL_CAUTARE,
    data={
        "judet": "Dolj",
        "localitate": "Almăj",
        "adresa": "",
    },
    headers=HEADERS,
    timeout=10
)
print(f"    Status: {resp5.status_code}")
print(f"    Response length: {len(resp5.text)}")
print(f"\n    RAW RESPONSE:")
print(resp5.text[:3000])
