#!/usr/bin/env python3
"""
brevo_agent.py — Brevo Email Marketing Agent for ejolie.ro
==========================================================
Faza 1: Sync contacte, trimitere campanii, statistici
Integrat cu Extended CMS API + Brevo API v3

Locație pe server: ~/ejolie-openclaw-agent/ejolie-sales/scripts/brevo_agent.py
Rulat de: OpenClaw (via exec) sau manual din terminal
"""

import os
import sys
import json
import argparse
import requests
from datetime import datetime, timedelta

# ============================================================
# 1. CONFIGURARE — citim cheile din .env
# ============================================================

# .env este un nivel deasupra folderului scripts/
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(SCRIPT_DIR, '..', '.env')


def load_env(env_path=ENV_PATH):
    """
    Citește fișierul .env și setează variabilele în os.environ.
    Format: CHEIE=valoare (fără ghilimele, fără spații în jurul =)
    """
    if not os.path.exists(env_path):
        print(f"[EROARE] Fișierul .env nu există la: {env_path}")
        sys.exit(1)

    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            # Ignorăm linii goale și comentarii
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                # Eliminăm ghilimelele dacă există
                value = value.strip().strip('"').strip("'")
                os.environ[key.strip()] = value


# Încărcăm .env
load_env()

# Cheile API
BREVO_API_KEY = os.environ.get('BREVO_API_KEY', '')
EJOLIE_API_KEY = os.environ.get('EJOLIE_API_KEY', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '44151343')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')

# Verificăm că avem cheile necesare
if not BREVO_API_KEY:
    print("[EROARE] BREVO_API_KEY lipsește din .env")
    sys.exit(1)
if not EJOLIE_API_KEY:
    print("[EROARE] EJOLIE_API_KEY lipsește din .env")
    sys.exit(1)

# Configurare Brevo API
BREVO_BASE_URL = "https://api.brevo.com/v3"
BREVO_HEADERS = {
    "accept": "application/json",
    "content-type": "application/json",
    "api-key": BREVO_API_KEY
}

# Configurare Extended API
EXTENDED_BASE_URL = "https://ejolie.ro/api/"
EXTENDED_HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# Lista Brevo implicită (lista #9 = Ejolie recent)
DEFAULT_LIST_ID = 9


# ============================================================
# 2. FUNCȚII HELPER — Extended API
# ============================================================

def extended_get(params):
    """
    Face un GET request la Extended API.
    params = string cu parametri, ex: "comenzi&idstatus=14&limit=100"
    Returnează JSON sau None dacă eroare.
    """
    url = f"{EXTENDED_BASE_URL}?{params}&apikey={EJOLIE_API_KEY}"
    try:
        resp = requests.get(url, headers=EXTENDED_HEADERS, timeout=180)
        if resp.status_code == 200 and resp.text:
            return resp.json()
        else:
            print(
                f"[EROARE] Extended API: status={resp.status_code}, content-length={len(resp.text)}")
            return None
    except Exception as e:
        print(f"[EROARE] Extended API request: {e}")
        return None


def get_recent_orders(days=7):
    """
    Obține comenzile din ultimele N zile de la Extended.
    NOTĂ: Extended API ignoră data_start/data_end — filtrăm client-side.
    """
    cutoff_date = datetime.now() - timedelta(days=days)

    all_orders = []
    pagina = 1
    max_pages = 20  # Limită de siguranță (~4000 comenzi max)
    found_old_order = False

    while pagina <= max_pages:
        data = extended_get(f"comenzi&limit=200&pagina={pagina}")

        if not data:
            break

        # Extended returnează dict {"ID": {order}, "ID2": {order2}}, NU list
        if isinstance(data, dict):
            orders_list = list(data.values())
        elif isinstance(data, list):
            orders_list = data
        else:
            break

        if len(orders_list) == 0:
            break

        # Filtrăm per dată — Extended returnează în ordine descrescătoare (cele mai noi primele)
        for order in orders_list:
            order_date_str = order.get('data', '')  # format DD.MM.YYYY
            try:
                order_date = datetime.strptime(order_date_str, '%d.%m.%Y')
            except (ValueError, TypeError):
                continue

            if order_date >= cutoff_date:
                all_orders.append(order)
            else:
                # Am ajuns la comenzi mai vechi decât perioada cerută — ne oprim
                found_old_order = True

        print(
            f"  Pagina {pagina}: {len(orders_list)} comenzi citite, {len(all_orders)} în perioada")

        # Dacă am găsit comenzi mai vechi, nu mai paginăm
        if found_old_order:
            break

        if len(orders_list) < 200:
            break
        pagina += 1

    print(f"[INFO] Total comenzi în ultimele {days} zile: {len(all_orders)}")
    return all_orders


def extract_contact_from_order(order):
    """
    Extrage datele de contact dintr-o comandă Extended.

    Structura Extended API (reală):
    - client.email, client.nume (nume complet), client.telefon
    - client.facturare.oras, client.livrare.oras
    - total_comanda (nu 'total')
    - id_comanda (nu 'id')
    - data = "15.03.2026" (format DD.MM.YYYY)
    - produse = dict {"143022": {produs}, ...} (NU list!)
    """
    # Client e dict direct (nu list)
    client = order.get('client', {})
    if not isinstance(client, dict):
        client = {}

    email = client.get('email', '')

    if not email or '@' not in email:
        return None

    # Excludem adresele interne
    if 'ejolie.ro' in email.lower():
        return None

    # Numele complet — Extended pune tot în câmpul 'nume'
    full_name = client.get('nume', '').strip()
    name_parts = full_name.split(' ', 1) if full_name else ['', '']
    firstname = name_parts[0] if len(name_parts) > 0 else ''
    lastname = name_parts[1] if len(name_parts) > 1 else ''

    # Orașul — din facturare sau livrare
    facturare = client.get('facturare', {})
    livrare = client.get('livrare', {})
    city = facturare.get('oras', '') or livrare.get('oras', '') or ''

    # Date comandă
    order_value = float(order.get('total_comanda', 0) or 0)
    order_id = order.get('id_comanda', '')
    order_date = order.get('data', '')  # format DD.MM.YYYY

    # Produse — Extended returnează dict, nu list
    products = order.get('produse', {})
    last_product = ''
    if products and isinstance(products, dict):
        # Luăm primul produs
        first_product = next(iter(products.values()), {})
        last_product = first_product.get('nume', '')
    elif isinstance(products, list) and len(products) > 0:
        last_product = products[0].get('nume', '')

    return {
        'email': email.lower().strip(),
        'firstname': firstname.strip(),
        'lastname': lastname.strip(),
        'city': city.strip(),
        'order_value': order_value,
        'order_id': str(order_id),
        'order_date': order_date,
        'last_product': last_product[:100]
    }


# ============================================================
# 3. FUNCȚII BREVO API
# ============================================================

def brevo_request(method, endpoint, data=None):
    """
    Face un request la Brevo API.
    method = 'GET', 'POST', 'PUT', 'DELETE'
    endpoint = calea API, ex: '/contacts'
    data = dict pentru body JSON (opțional)
    Returnează (status_code, response_json)
    """
    url = f"{BREVO_BASE_URL}{endpoint}"
    try:
        if method == 'GET':
            resp = requests.get(url, headers=BREVO_HEADERS, timeout=30)
        elif method == 'POST':
            resp = requests.post(
                url, headers=BREVO_HEADERS, json=data, timeout=30)
        elif method == 'PUT':
            resp = requests.put(url, headers=BREVO_HEADERS,
                                json=data, timeout=30)
        elif method == 'DELETE':
            resp = requests.delete(url, headers=BREVO_HEADERS, timeout=30)
        else:
            return (0, {"error": f"Metodă necunoscută: {method}"})

        # Brevo returnează 204 No Content pe update-uri reușite
        if resp.status_code == 204:
            return (204, {"success": True})

        # Brevo returnează 201 Created pe contact nou
        if resp.text:
            return (resp.status_code, resp.json())
        else:
            return (resp.status_code, {})

    except Exception as e:
        print(f"[EROARE] Brevo API {method} {endpoint}: {e}")
        return (0, {"error": str(e)})


def sync_contact(contact_data, list_id=DEFAULT_LIST_ID):
    """
    Sincronizează un contact în Brevo (creează sau actualizează).

    contact_data = dict cu:
        email (obligatoriu)
        firstname, lastname, city (opționale)
        order_value, order_id, order_date, last_product (opționale)

    Brevo API: POST /contacts (creează) sau PUT /contacts/{email} (actualizează)

    Returnează: dict cu {success: bool, action: 'created'/'updated'/'error', message: str}
    """
    email = contact_data.get('email', '')
    if not email:
        return {'success': False, 'action': 'error', 'message': 'Email lipsă'}

    # Construim atributele Brevo
    attributes = {}
    if contact_data.get('firstname'):
        attributes['FIRSTNAME'] = contact_data['firstname']
    if contact_data.get('lastname'):
        attributes['LASTNAME'] = contact_data['lastname']
    if contact_data.get('city'):
        attributes['CITY'] = contact_data['city']
    if contact_data.get('order_date'):
        attributes['LAST_ORDER_DATE'] = contact_data['order_date']
    if contact_data.get('order_value'):
        attributes['LAST_ORDER_VALUE'] = float(contact_data['order_value'])
    if contact_data.get('last_product'):
        attributes['LAST_PRODUCT'] = contact_data['last_product']

    # Încercăm mai întâi să actualizăm contactul existent (PUT)
    update_data = {"attributes": attributes}
    if list_id:
        update_data["listIds"] = [list_id]

    status, resp = brevo_request('PUT', f'/contacts/{email}', update_data)

    if status == 204:
        # Contact actualizat cu succes
        return {
            'success': True,
            'action': 'updated',
            'message': f'Contact actualizat: {email}'
        }

    elif status == 404:
        # Contactul nu există — îl creăm
        create_data = {
            "email": email,
            "attributes": attributes,
            "listIds": [list_id] if list_id else [],
            "updateEnabled": True  # Dacă deja există, actualizează
        }

        status2, resp2 = brevo_request('POST', '/contacts', create_data)

        if status2 in [200, 201]:
            return {
                'success': True,
                'action': 'created',
                'message': f'Contact creat: {email}'
            }
        else:
            return {
                'success': False,
                'action': 'error',
                'message': f'Eroare creare {email}: {resp2}'
            }

    else:
        return {
            'success': False,
            'action': 'error',
            'message': f'Eroare update {email}: status={status}, resp={resp}'
        }


def sync_all_contacts(days=7, list_id=DEFAULT_LIST_ID):
    """
    Sincronizează TOȚI clienții din comenzile din ultimele N zile.

    Flux:
    1. Ia comenzile din Extended API (ultimele N zile)
    2. Extrage datele de contact unice (per email)
    3. Pentru fiecare contact, face sync în Brevo

    Returnează: dict cu statistici {total, created, updated, errors, skipped}
    """
    print(f"\n{'='*60}")
    print(f"  SYNC CONTACTE — ultimele {days} zile")
    print(f"  Lista Brevo: #{list_id}")
    print(f"  Data: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}\n")

    # Pasul 1: Ia comenzile din Extended
    print("[1/3] Obțin comenzile din Extended API...")
    orders = get_recent_orders(days=days)

    if not orders:
        print("[INFO] Nicio comandă găsită.")
        return {'total': 0, 'created': 0, 'updated': 0, 'errors': 0, 'skipped': 0}

    # Pasul 2: Extrage contacte unice
    print(f"\n[2/3] Extrag contacte din {len(orders)} comenzi...")
    contacts = {}  # email → contact_data (păstrăm cea mai recentă comandă)

    for order in orders:
        contact = extract_contact_from_order(order)
        if contact:
            email = contact['email']
            # Dacă am mai văzut acest email, păstrăm valoarea mai mare a comenzii
            if email in contacts:
                existing = contacts[email]
                # Adunăm valoarea totală
                existing['total_orders'] = existing.get('total_orders', 1) + 1
                existing['total_spent'] = existing.get(
                    'total_spent', existing['order_value']) + contact['order_value']
                # Păstrăm ultima comandă (cea mai recentă)
                if contact['order_date'] > existing.get('order_date', ''):
                    existing['order_value'] = contact['order_value']
                    existing['order_date'] = contact['order_date']
                    existing['order_id'] = contact['order_id']
                    existing['last_product'] = contact['last_product']
            else:
                contact['total_orders'] = 1
                contact['total_spent'] = contact['order_value']
                contacts[email] = contact

    print(f"  Contacte unice: {len(contacts)}")
    skipped = len(orders) - len(contacts)

    # Pasul 3: Sync în Brevo
    print(f"\n[3/3] Sincronizez {len(contacts)} contacte în Brevo...")
    stats = {'total': len(contacts), 'created': 0,
             'updated': 0, 'errors': 0, 'skipped': skipped}

    for i, (email, contact) in enumerate(contacts.items(), 1):
        # Adăugăm total_orders și total_spent la atribute
        contact_for_sync = dict(contact)

        result = sync_contact(contact_for_sync, list_id=list_id)

        if result['success']:
            if result['action'] == 'created':
                stats['created'] += 1
            else:
                stats['updated'] += 1
            # Afișăm progresul la fiecare 10 contacte
            if i % 10 == 0 or i == len(contacts):
                print(f"  [{i}/{len(contacts)}] {result['message']}")
        else:
            stats['errors'] += 1
            print(f"  [{i}/{len(contacts)}] EROARE: {result['message']}")

    # Sumar
    print(f"\n{'='*60}")
    print(f"  REZULTAT SYNC")
    print(f"  Total contacte procesate: {stats['total']}")
    print(f"  Create noi:    {stats['created']}")
    print(f"  Actualizate:   {stats['updated']}")
    print(f"  Erori:         {stats['errors']}")
    print(f"  Duplicate/skip:{stats['skipped']}")
    print(f"{'='*60}\n")

    return stats


# ============================================================
# 4. FUNCȚII CAMPANII BREVO
# ============================================================

def list_campaigns(status_filter=None, limit=10):
    """
    Listează campaniile Brevo.
    status_filter = 'sent', 'draft', 'queued', 'suspended' sau None (toate)
    """
    endpoint = f"/emailCampaigns?limit={limit}&sort=desc"
    if status_filter:
        endpoint += f"&status={status_filter}"

    status, resp = brevo_request('GET', endpoint)

    if status == 200 and 'campaigns' in resp:
        campaigns = resp['campaigns']
        print(f"\n  {'='*70}")
        print(
            f"  CAMPANII BREVO {'(' + status_filter + ')' if status_filter else '(toate)'}")
        print(f"  {'='*70}")

        for c in campaigns:
            c_status = c.get('status', '?')
            c_name = c.get('name', 'Fără nume')
            c_id = c.get('id', '?')
            c_date = c.get('sentDate', c.get(
                'scheduledAt', c.get('createdAt', '?')))

            # Statistici — Brevo pune datele reale în campaignStats[0], NU în globalStats
            campaign_stats = c.get('statistics', {}).get('campaignStats', [])
            if campaign_stats:
                # Agregăm din toate listele (dacă sunt mai multe)
                delivered = sum(s.get('delivered', 0) for s in campaign_stats)
                opens = sum(s.get('uniqueViews', 0) for s in campaign_stats)
                clicks = sum(s.get('clickers', 0) for s in campaign_stats)
                unsubs = sum(s.get('unsubscriptions', 0)
                             for s in campaign_stats)
                sent = sum(s.get('sent', 0) for s in campaign_stats)
            else:
                delivered = opens = clicks = unsubs = sent = 0

            print(f"\n  #{c_id} | {c_status.upper()} | {c_name}")
            print(f"    Data: {c_date}")
            if delivered > 0:
                open_rate = f"{(opens/delivered*100):.1f}%"
                click_rate = f"{(clicks/delivered*100):.1f}%"
                print(
                    f"    Sent: {sent} | Delivered: {delivered} | Opens: {opens} ({open_rate}) | Clicks: {clicks} ({click_rate}) | Unsubs: {unsubs}")
            else:
                print(f"    Sent: {sent} | Delivered: {delivered}")

        print(f"\n  Total: {resp.get('count', len(campaigns))} campanii")
        return campaigns
    else:
        print(f"[EROARE] Nu pot lista campaniile: {resp}")
        return []


def get_campaign_stats(campaign_id):
    """
    Returnează statisticile detaliate pentru o campanie.
    """
    status, resp = brevo_request('GET', f'/emailCampaigns/{campaign_id}')

    if status == 200:
        name = resp.get('name', '?')
        c_status = resp.get('status', '?')

        # Brevo pune datele reale în campaignStats[0], NU în globalStats
        campaign_stats = resp.get('statistics', {}).get('campaignStats', [])
        if campaign_stats:
            # Agregăm din toate listele
            sent = sum(s.get('sent', 0) for s in campaign_stats)
            delivered = sum(s.get('delivered', 0) for s in campaign_stats)
            opens = sum(s.get('uniqueViews', 0) for s in campaign_stats)
            clicks = sum(s.get('clickers', 0) for s in campaign_stats)
            unsubs = sum(s.get('unsubscriptions', 0) for s in campaign_stats)
            hard_bounces = sum(s.get('hardBounces', 0) for s in campaign_stats)
            soft_bounces = sum(s.get('softBounces', 0) for s in campaign_stats)
            complaints = sum(s.get('complaints', 0) for s in campaign_stats)
        else:
            sent = delivered = opens = clicks = unsubs = hard_bounces = soft_bounces = complaints = 0

        bounces = hard_bounces + soft_bounces

        print(f"\n  {'='*60}")
        print(f"  STATISTICI CAMPANIE #{campaign_id}")
        print(f"  Nume: {name}")
        print(f"  Status: {c_status}")
        print(f"  {'='*60}")

        open_rate = f"{(opens/delivered*100):.1f}%" if delivered > 0 else '0%'
        click_rate = f"{(clicks/delivered*100):.1f}%" if delivered > 0 else '0%'
        unsub_rate = f"{(unsubs/delivered*100):.2f}%" if delivered > 0 else '0%'

        print(f"  Trimise:      {sent}")
        print(f"  Livrate:      {delivered}")
        print(f"  Deschise:     {opens} ({open_rate})")
        print(f"  Click-uri:    {clicks} ({click_rate})")
        print(f"  Dezabonări:   {unsubs} ({unsub_rate})")
        print(
            f"  Bounce-uri:   {bounces} (hard: {hard_bounces}, soft: {soft_bounces})")
        print(f"  Reclamații:   {complaints}")
        print(f"  {'='*60}\n")

        return {
            'name': name,
            'status': c_status,
            'sent': sent,
            'delivered': delivered,
            'opens': opens,
            'open_rate': open_rate,
            'clicks': clicks,
            'click_rate': click_rate,
            'unsubs': unsubs,
            'bounces': bounces
        }
    else:
        print(
            f"[EROARE] Nu pot obține statisticile campaniei #{campaign_id}: {resp}")
        return None


def send_campaign(campaign_id):
    """
    Trimite o campanie draft (o pune în coada de trimitere).
    ATENȚIE: Campania trebuie să fie în status 'draft' și să aibă
    subject, sender, recipients, design configurate.
    """
    status, resp = brevo_request(
        'POST', f'/emailCampaigns/{campaign_id}/sendNow')

    if status == 204:
        print(f"[OK] Campania #{campaign_id} a fost trimisă!")
        return True
    else:
        print(f"[EROARE] Nu pot trimite campania #{campaign_id}: {resp}")
        return False


# ============================================================
# 5. FUNCȚII LISTE ȘI SEGMENTE
# ============================================================

def get_lists():
    """
    Returnează toate listele Brevo cu numărul de contacte.
    """
    status, resp = brevo_request('GET', '/contacts/lists?limit=50')

    if status == 200 and 'lists' in resp:
        lists = resp['lists']
        print(f"\n  {'='*50}")
        print(f"  LISTE BREVO")
        print(f"  {'='*50}")

        for lst in lists:
            l_id = lst.get('id', '?')
            l_name = lst.get('name', '?')
            l_count = lst.get('uniqueSubscribers', 0)
            print(f"  #{l_id} | {l_name} | {l_count} contacte")

        print(f"\n  Total: {resp.get('count', len(lists))} liste")
        return lists
    else:
        print(f"[EROARE] Nu pot lista listele: {resp}")
        return []


def add_to_list(list_id, emails):
    """
    Adaugă o listă de email-uri într-o listă Brevo.
    emails = lista de string-uri cu adrese email
    """
    if not emails:
        print("[INFO] Lista de emailuri este goală.")
        return False

    data = {"emails": emails}
    status, resp = brevo_request(
        'POST', f'/contacts/lists/{list_id}/contacts/add', data)

    if status == 201:
        added = resp.get('contacts', {}).get('success', [])
        failed = resp.get('contacts', {}).get('failure', [])
        print(
            f"[OK] Adăugate {len(added)} contacte în lista #{list_id}. Eșuate: {len(failed)}")
        return True
    else:
        print(f"[EROARE] Nu pot adăuga contacte în lista #{list_id}: {resp}")
        return False


def get_contact(email):
    """
    Obține detaliile unui contact din Brevo.
    """
    status, resp = brevo_request('GET', f'/contacts/{email}')

    if status == 200:
        attrs = resp.get('attributes', {})
        lists = resp.get('listIds', [])
        print(f"\n  Contact: {email}")
        print(f"  Liste: {lists}")
        print(f"  Atribute: {json.dumps(attrs, indent=2, ensure_ascii=False)}")
        return resp
    elif status == 404:
        print(f"  Contact {email} NU există în Brevo.")
        return None
    else:
        print(f"[EROARE] Nu pot obține contactul {email}: {resp}")
        return None


# ============================================================
# 6. FUNCȚII TELEGRAM (notificări)
# ============================================================

def send_telegram(message):
    """
    Trimite un mesaj pe Telegram via OpenClaw sau direct API.
    """
    # Încercăm mai întâi cu OpenClaw
    try:
        result = os.popen(
            f'openclaw message send --channel telegram '
            f'--target {TELEGRAM_CHAT_ID} --text "{message}" 2>/dev/null'
        ).read()
        if result:
            return True
    except Exception:
        pass

    # Fallback: direct Telegram API
    if TELEGRAM_BOT_TOKEN:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            resp = requests.post(url, json={
                'chat_id': TELEGRAM_CHAT_ID,
                'text': message,
                'parse_mode': 'HTML'
            }, timeout=10)
            return resp.status_code == 200
        except Exception:
            pass

    return False


# ============================================================
# 7. CLI — Interfață linie de comandă
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description='Brevo Agent — Email Marketing Automation pentru ejolie.ro',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemple:
  python3 brevo_agent.py --sync-all                     # Sync contacte ultimele 7 zile
  python3 brevo_agent.py --sync-all --days 30           # Sync contacte ultimele 30 zile
  python3 brevo_agent.py --sync-contact test@email.com  # Sync un contact specific
  python3 brevo_agent.py --campaigns                    # Lista campanii
  python3 brevo_agent.py --campaigns --status sent      # Doar campaniile trimise
  python3 brevo_agent.py --stats 7                      # Statistici campanie #7
  python3 brevo_agent.py --send 7                       # Trimite campanie #7 (draft)
  python3 brevo_agent.py --lists                        # Lista toate listele
  python3 brevo_agent.py --contact test@email.com       # Verifică un contact în Brevo
  python3 brevo_agent.py --weekly-report                # Raport săptămânal pe Telegram
        """
    )

    # Comenzi principale
    parser.add_argument('--sync-all', action='store_true',
                        help='Sincronizează toți clienții din comenzile recente')
    parser.add_argument('--sync-contact', type=str,
                        help='Sincronizează un contact specific (email)')
    parser.add_argument('--campaigns', action='store_true',
                        help='Listează campaniile Brevo')
    parser.add_argument('--stats', type=int,
                        help='Statistici pentru o campanie (ID)')
    parser.add_argument('--send', type=int,
                        help='Trimite o campanie draft (ID)')
    parser.add_argument('--lists', action='store_true',
                        help='Listează toate listele Brevo')
    parser.add_argument('--contact', type=str,
                        help='Verifică un contact în Brevo (email)')
    parser.add_argument('--weekly-report', action='store_true',
                        help='Generează raport săptămânal pe Telegram')

    # Opțiuni
    parser.add_argument('--days', type=int, default=7,
                        help='Număr de zile pentru sync (default: 7)')
    parser.add_argument('--list-id', type=int, default=DEFAULT_LIST_ID,
                        help=f'ID-ul listei Brevo (default: {DEFAULT_LIST_ID})')
    parser.add_argument('--status', type=str, choices=['sent', 'draft', 'queued', 'suspended'],
                        help='Filtru status campanii')
    parser.add_argument('--telegram', action='store_true',
                        help='Trimite rezultatul pe Telegram')

    args = parser.parse_args()

    # Dacă nu s-a specificat nicio comandă, afișăm help
    if not any([args.sync_all, args.sync_contact, args.campaigns,
                args.stats, args.send, args.lists, args.contact,
                args.weekly_report]):
        parser.print_help()
        return

    # ---- SYNC ALL ----
    if args.sync_all:
        stats = sync_all_contacts(days=args.days, list_id=args.list_id)

        if args.telegram:
            msg = (
                f"📧 <b>Brevo Sync Contacte</b>\n"
                f"Ultimele {args.days} zile\n\n"
                f"✅ Create: {stats['created']}\n"
                f"🔄 Actualizate: {stats['updated']}\n"
                f"❌ Erori: {stats['errors']}\n"
                f"📊 Total: {stats['total']}"
            )
            send_telegram(msg)

    # ---- SYNC CONTACT ----
    elif args.sync_contact:
        email = args.sync_contact
        # Sync minimal — doar email, fără date din Extended
        result = sync_contact({'email': email}, list_id=args.list_id)
        print(f"  Rezultat: {result['message']}")

    # ---- CAMPANII ----
    elif args.campaigns:
        list_campaigns(status_filter=args.status)

    # ---- STATS ----
    elif args.stats:
        stats = get_campaign_stats(args.stats)

        if stats and args.telegram:
            msg = (
                f"📊 <b>Stats Campanie #{args.stats}</b>\n"
                f"{stats['name']}\n\n"
                f"📬 Livrate: {stats['delivered']}\n"
                f"👁 Deschise: {stats['opens']} ({stats['open_rate']})\n"
                f"🖱 Click-uri: {stats['clicks']} ({stats['click_rate']})\n"
                f"🚫 Dezabonări: {stats['unsubs']}"
            )
            send_telegram(msg)

    # ---- SEND ----
    elif args.send:
        confirm = input(
            f"Sigur vrei să trimiți campania #{args.send}? (da/nu): ")
        if confirm.lower() in ['da', 'yes', 'y']:
            send_campaign(args.send)
        else:
            print("Trimitere anulată.")

    # ---- LISTE ----
    elif args.lists:
        get_lists()

    # ---- CONTACT ----
    elif args.contact:
        get_contact(args.contact)

    # ---- WEEKLY REPORT ----
    elif args.weekly_report:
        # Statistici din ultima săptămână
        print("\n📊 Generez raportul săptămânal...\n")

        # 1. Statistici campanii trimise
        campaigns = list_campaigns(status_filter='sent', limit=5)

        # 2. Statistici liste
        lists = get_lists()

        # 3. Trimite pe Telegram
        total_contacts = sum(l.get('uniqueSubscribers', 0)
                             for l in lists) if lists else 0

        msg = f"📧 <b>Raport Email Marketing — {datetime.now().strftime('%d.%m.%Y')}</b>\n\n"
        msg += f"📋 Total contacte: {total_contacts}\n"

        if campaigns:
            msg += f"\n<b>Ultimele campanii:</b>\n"
            for c in campaigns[:3]:
                campaign_stats = c.get('statistics', {}).get(
                    'campaignStats', [])
                if campaign_stats:
                    delivered = sum(s.get('delivered', 0)
                                    for s in campaign_stats)
                    opens = sum(s.get('uniqueViews', 0)
                                for s in campaign_stats)
                else:
                    delivered = opens = 0
                open_rate = f"{(opens/delivered*100):.0f}%" if delivered > 0 else '0%'
                msg += f"• {c.get('name', '?')}: {delivered} livrate, {open_rate} open rate\n"

        send_telegram(msg)
        print("Raport trimis pe Telegram!")


if __name__ == '__main__':
    main()
