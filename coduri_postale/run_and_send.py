#!/usr/bin/env python3
"""
run_and_send.py
Rulează extragerea coduri poștale și trimite automat pe Telegram când termină.

UTILIZARE:
  # Un singur județ, o singură sursă
  python3 run_and_send.py --judet cluj --sursa codul-postal

  # Un singur județ, ambele surse
  python3 run_and_send.py --judet brasov --sursa ambele

  # Mai multe județe, ambele surse
  python3 run_and_send.py --judet cluj brasov constanta sibiu --sursa ambele

  # Background (recomandat pentru posta-romana sau ambele)
  nohup python3 run_and_send.py --judet cluj brasov constanta sibiu --sursa ambele > run_log.txt 2>&1 &
"""

import subprocess
import json
import os
import sys
import glob
from datetime import datetime

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(
    __file__)), "scrape_coduri_postale_UNIVERSAL.py")
CHAT_ID = "44151343"


def get_telegram_token():
    try:
        with open(os.path.expanduser('~/.openclaw/openclaw.json')) as f:
            cfg = json.load(f)
        return cfg.get('channels', {}).get('telegram', {}).get('botToken', '')
    except:
        return ''


def send_telegram(filepath, caption):
    token = get_telegram_token()
    if not token:
        print(f"  ⚠️  Nu am găsit token Telegram. Fișierul e la: {filepath}")
        return False

    url = f"https://api.telegram.org/bot{token.strip()}/sendDocument"
    result = subprocess.run(
        ['curl', '-s', '-F', f'document=@{filepath}', '-F',
            f'chat_id={CHAT_ID}', '-F', f'caption={caption}', url],
        capture_output=True, text=True
    )
    if '"ok":true' in result.stdout:
        print(f"  📨 Trimis pe Telegram: {os.path.basename(filepath)}")
        return True
    else:
        print(f"  ❌ Eroare Telegram: {result.stdout[:200]}")
        return False


def run_extraction(judet, sursa):
    """Rulează scriptul universal și returnează fișierul Excel generat."""
    sursa_tag = 'cp' if sursa == 'codul-postal' else 'pr'
    expected_file = os.path.join(os.path.dirname(
        SCRIPT), f"coduri_postale_{judet}_{sursa_tag}_2026.xlsx")

    print(f"\n{'='*60}")
    print(f"  Rulez: {judet} — {sursa}")
    print(f"{'='*60}")

    result = subprocess.run(
        [sys.executable, SCRIPT, '--judet', judet, '--sursa', sursa],
        cwd=os.path.dirname(SCRIPT)
    )

    if result.returncode == 0 and os.path.exists(expected_file):
        return expected_file
    else:
        print(f"  ❌ Eroare la extragere {judet}/{sursa}")
        return None


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description='Extrage + trimite pe Telegram')
    parser.add_argument('--judet', nargs='+', required=True,
                        help='Județele (ex: cluj brasov constanta sibiu)')
    parser.add_argument('--sursa', required=True, choices=['codul-postal', 'posta-romana', 'ambele'],
                        help='Sursa de date')
    args = parser.parse_args()

    start = datetime.now()
    print(f"🚀 Start: {start.strftime('%d.%m.%Y %H:%M')}")
    print(f"   Județe: {', '.join(args.judet)}")
    print(f"   Sursa: {args.sursa}")

    files_generated = []

    for judet in args.judet:
        if args.sursa == 'ambele':
            # Rulează codul-postal.ro (rapid)
            f1 = run_extraction(judet, 'codul-postal')
            if f1:
                files_generated.append(f1)

            # Rulează Poșta Română (lent)
            f2 = run_extraction(judet, 'posta-romana')
            if f2:
                files_generated.append(f2)
        else:
            f = run_extraction(judet, args.sursa)
            if f:
                files_generated.append(f)

    # Trimite toate fișierele pe Telegram
    elapsed = (datetime.now() - start).total_seconds() / 60
    print(f"\n{'='*60}")
    print(f"  FINALIZAT în {elapsed:.1f} minute")
    print(f"  {len(files_generated)} fișiere generate")
    print(f"{'='*60}")

    print(f"\n📨 Trimit pe Telegram...\n")
    for filepath in files_generated:
        filename = os.path.basename(filepath)
        caption = filename.replace('.xlsx', '').replace('_', ' ')
        send_telegram(filepath, caption)

    print(f"\n🎉 GATA! Totul trimis pe Telegram.")


if __name__ == "__main__":
    main()
