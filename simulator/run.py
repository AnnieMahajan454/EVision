"""Generate a simulated fleet and stream it into the EVision API.

    python -m simulator.run --api http://localhost:8000 --vehicles 20 --days 180

Everything goes through the public REST endpoints (register -> create vehicles -> bulk
telemetry -> charging sessions), so this also acts as an end-to-end load test of ingestion.
Re-running with the same seed is safe: duplicates are skipped server-side.
"""

import argparse
import sys
import time
from datetime import date, timedelta

import httpx2 as httpx

from simulator.fleet import FleetSimulator

TELEMETRY_BATCH = 2000
SESSION_BATCH = 500


def authenticate(client: httpx.Client, email: str, password: str) -> None:
    payload = {"email": email, "password": password, "full_name": "Fleet Operations"}
    response = client.post("/api/v1/auth/register", json=payload)
    if response.status_code == 409:
        response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    response.raise_for_status()
    client.headers["Authorization"] = f"Bearer {response.json()['access_token']}"


def ensure_vehicle(client: httpx.Client, payload: dict, existing: dict[str, str]) -> str:
    if payload["vin"] in existing:
        return existing[payload["vin"]]
    response = client.post("/api/v1/vehicles", json=payload)
    response.raise_for_status()
    return response.json()["id"]


def post_in_batches(
    client: httpx.Client, url: str, key: str, items: list[dict], size: int
) -> tuple[int, int]:
    inserted = duplicates = 0
    for i in range(0, len(items), size):
        response = client.post(url, json={key: items[i : i + size]})
        response.raise_for_status()
        body = response.json()
        inserted += body["inserted"]
        duplicates += body["duplicates"]
    return inserted, duplicates


def show_progress(day: int, total: int) -> None:
    if day % 10 == 0 or day == total:
        print(f"\r  day {day}/{total}", end="", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--email", default="fleet-ops@evision.dev")
    parser.add_argument("--password", default="evision-demo-2026")
    parser.add_argument("--vehicles", type=int, default=20)
    parser.add_argument("--days", type=int, default=180)
    parser.add_argument(
        "--end",
        type=date.fromisoformat,
        default=date.today() - timedelta(days=1),
        help="Last simulated day (default: yesterday)",
    )
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    start = args.end - timedelta(days=args.days - 1)
    print(f"Simulating {args.vehicles} vehicles from {start} to {args.end} ...")
    t0 = time.perf_counter()
    simulator = FleetSimulator(args.vehicles, start, args.days, seed=args.seed)
    vehicles = simulator.run(progress=show_progress)
    print(f"\n  done in {time.perf_counter() - t0:.0f}s")

    with httpx.Client(base_url=args.api, timeout=120) as client:
        authenticate(client, args.email, args.password)
        existing = {v["vin"]: v["id"] for v in client.get("/api/v1/vehicles").json()}

        totals = [0, 0, 0]
        t0 = time.perf_counter()
        for v in vehicles:
            vehicle_id = ensure_vehicle(client, v.api_payload(), existing)
            base = f"/api/v1/vehicles/{vehicle_id}"
            t_ins, t_dup = post_in_batches(
                client, f"{base}/telemetry", "readings", v.readings, TELEMETRY_BATCH
            )
            s_ins, _ = post_in_batches(
                client, f"{base}/charging/sessions", "sessions", v.sessions, SESSION_BATCH
            )
            totals[0] += t_ins
            totals[1] += t_dup
            totals[2] += s_ins
            print(
                f"  {v.nickname:<26} {v.spec.make + ' ' + v.spec.model:<17} "
                f"{t_ins:>7,} readings  {s_ins:>4} charging sessions"
            )

        elapsed = time.perf_counter() - t0
        print(
            f"Ingested {totals[0]:,} readings ({totals[1]:,} duplicates skipped) and {totals[2]:,} "
            f"charging sessions in {elapsed:.0f}s ({totals[0] / elapsed:,.0f} readings/s)"
        )


if __name__ == "__main__":
    main()
