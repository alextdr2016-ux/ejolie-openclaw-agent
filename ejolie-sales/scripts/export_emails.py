#!/usr/bin/env python3
"""
Export nume, email, data din comenzile incasate pana la o data specificata.
Fetch paralel cu retry automat pentru timeout-uri.
Usage: python3 export_emails.py --pana-la 01-08-2025
"""
import sys, os, json, csv, argparse, urllib.request, urllib.parse, time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import _load_env_file

_load_env_file()
API_KEY = os.environ.get("EJOLIE_API_KEY", "")

def fetch_interval(s: str, e: str, retries: int = 5) -> tuple:
    """Fetch comenzi incasate pentru un interval. Cu retry automat."""
    params = {
        "comenzi": "",
        "data_start": s,
        "data_end": e,
        "limit": "2000",
        "idstatus": "14",
        "apikey": API_KEY,
    }
    query = "&".join(f"{k}={urllib.parse.quote(str(v))}" if v else k for k, v in params.items())
    url = f"https://ejolie.ro/api/?{query}"

    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Extended API"})
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.loads(r.read())
            if isinstance(data, dict) and data.get("eroare") == 1:
                return s, e, {}
            return s, e, data
        except Exception as ex:
            if attempt < retries:
                time.sleep(3 * attempt)  # wait 3s, 6s, 9s, 12s intre retry-uri
            else:
                raise ex

def get_intervals(start_dt: datetime, end_dt: datetime, days: int = 14):
    intervals = []
    current = start_dt
    while current <= end_dt:
        iv_end = current + timedelta(days=days - 1)
        if iv_end > end_dt:
            iv_end = end_dt
        intervals.append((current.strftime("%d-%m-%Y"), iv_end.strftime("%d-%m-%Y")))
        current = iv_end + timedelta(days=1)
    return intervals

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pana-la", required=True, help="Data limita DD-MM-YYYY")
    parser.add_argument("--de-la", default="01-01-2024", help="Data start DD-MM-YYYY")
    parser.add_argument("--output", default="/tmp/emailuri_comenzi.csv")
    parser.add_argument("--workers", default=3, type=int, help="Requesturi paralele (default: 3)")
    args = parser.parse_args()

    start_dt = datetime.strptime(args.de_la, "%d-%m-%Y")
    end_dt   = datetime.strptime(args.pana_la, "%d-%m-%Y")

    intervals = get_intervals(start_dt, end_dt, days=7)
    total = len(intervals)
    print(f"📅 {args.de_la} → {args.pana_la} | {total} intervale | {args.workers} workers | retry x3")

    all_rows = []
    total_comenzi = 0
    done = 0
    failed = []

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(fetch_interval, s, e): (s, e) for s, e in intervals}
        for future in as_completed(futures):
            s, e = futures[future]
            try:
                _, _, data = future.result()
                count = len(data)
                total_comenzi += count
                done += 1
                print(f"  ✅ [{done}/{total}] {s} → {e}: {count} comenzi", flush=True)

                for order_id, order in data.items():
                    if not isinstance(order, dict):
                        continue
                    client = order.get("client", {})
                    email  = client.get("email", "").strip().lower()
                    nume   = client.get("nume", "").strip()
                    data_c = order.get("data", "").strip()
                    if not email or "@" not in email:
                        continue
                    all_rows.append({"nume": nume, "email": email, "data": data_c})

            except Exception as ex:
                done += 1
                failed.append((s, e))
                print(f"  ❌ [{done}/{total}] {s} → {e}: FAILED după 3 retry-uri", flush=True)

    # Retry final pentru cele eșuate - secvențial, cu pauze mai mari
    if failed:
        print(f"\n⚠️ {len(failed)} intervale eșuate — retry final secvențial...")
        for s, e in failed:
            print(f"  🔄 {s} → {e} ...", end=" ", flush=True)
            try:
                time.sleep(3)
                _, _, data = fetch_interval(s, e, retries=5)
                count = len(data)
                total_comenzi += count
                print(f"✅ {count} comenzi")
                for order_id, order in data.items():
                    if not isinstance(order, dict):
                        continue
                    client = order.get("client", {})
                    email  = client.get("email", "").strip().lower()
                    nume   = client.get("nume", "").strip()
                    data_c = order.get("data", "").strip()
                    if not email or "@" not in email:
                        continue
                    all_rows.append({"nume": nume, "email": email, "data": data_c})
            except Exception as ex:
                print(f"❌ SKIP: {ex}")

    # Sortăm după dată
    all_rows.sort(key=lambda x: x["data"])

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["nume", "email", "data"])
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\n✅ Gata!")
    print(f"📦 Total comenzi incasate procesate: {total_comenzi}")
    print(f"📧 Total rânduri exportate: {len(all_rows)}")
    print(f"💾 Salvat în: {args.output}")
    print("\n📋 Preview (primele 5):")
    for r in all_rows[:5]:
        print(f"  {r['nume']} | {r['email']} | {r['data']}")

if __name__ == "__main__":
    main()
