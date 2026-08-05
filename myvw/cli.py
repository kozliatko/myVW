#!/usr/bin/env python3
"""
CLI — prints vehicle status from the myVolkswagen portal.

Usage:
    myvw
    myvw --proxy socks5://localhost:8080
    python -m myvw
"""

import argparse
import asyncio
import os
import sys

from .client import LoginError, Maintenance, MyVWClient, Trip, Vehicle


def _fmt_trip(trip: Trip) -> str:
    parts = [f"{trip.distance_km} km"]
    if trip.avg_fuel_l100 is not None:
        parts.append(f"{trip.avg_fuel_l100:.1f} l/100km")
    if trip.travel_time_min is not None:
        parts.append(f"{trip.travel_time_min} min")
    if trip.avg_speed_kmh is not None:
        parts.append(f"⌀ {trip.avg_speed_kmh} km/h")
    return "  |  ".join(parts) + f"  ({trip.end_timestamp[:10]})"


def _fmt_maint(m: Maintenance, label: str, days_key: str, km_key: str) -> str | None:
    days = getattr(m, days_key)
    km = getattr(m, km_key)
    if days is None and km is None:
        return None
    parts = []
    if days is not None:
        parts.append(f"{days} days")
    if km is not None:
        parts.append(f"{km:,} km".replace(",", " "))
    return f"  {label:<18}{' / '.join(parts)}"


def print_vehicle(v: Vehicle) -> None:
    sep = "=" * 56
    print(sep)
    print(f"  {'VIN:':<18}{v.vin}")
    if v.nickname or v.license_plate:
        print(f"  {'Vehicle:':<18}{v.nickname}  ({v.license_plate})  [{v.role}]")
    if v.model_name:
        print(f"  {'Model:':<18}{v.model_name}")
    if v.engine:
        print(f"  {'Engine:':<18}{v.engine}")
    if v.mileage_km is not None:
        km = f"{v.mileage_km:,}".replace(",", " ")
        ts = f"  (as of {v.data_timestamp})" if v.data_timestamp else ""
        print(f"  {'Odometer:':<18}{km} km{ts}")

    m = v.maintenance
    for line in filter(None, [
        _fmt_maint(m, "Inspection due:", "inspection_due_days", "inspection_due_km"),
        _fmt_maint(m, "Oil service due:", "oil_due_days",        "oil_due_km"),
    ]):
        print(line)

    lights = v.warning_lights
    print(f"  {'Warning lights:':<18}{'none' if not lights else ', '.join(str(l) for l in lights)}")

    if v.short_trip:
        print(f"  {'Short trip:':<18}{_fmt_trip(v.short_trip)}")
    if v.long_trip:
        print(f"  {'Long trip:':<18}{_fmt_trip(v.long_trip)}")
    if v.cyclic_trip:
        print(f"  {'Cyclic trip:':<18}{_fmt_trip(v.cyclic_trip)}")


def print_report(vehicles: list[Vehicle]) -> None:
    print(f"\nVehicles found: {len(vehicles)}\n")
    for v in vehicles:
        print_vehicle(v)
    print("=" * 56)


async def _run(username: str, password: str, proxy: str | None) -> int:
    async with MyVWClient(username, password, proxy=proxy) as client:
        print("# Logging in to myVolkswagen...")
        try:
            vehicles = await client.get_vehicles()
        except (LoginError, RuntimeError) as e:
            print(f"Error: {e}")
            return 1

    print_report(vehicles)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Vehicle data from myVolkswagen")
    parser.add_argument("--proxy", metavar="URL", help="e.g. socks5://localhost:8080")
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    username = os.environ.get("VW_USERNAME") or ""
    password = os.environ.get("VW_PASSWORD") or ""
    if not username or not password:
        print("Error: VW_USERNAME and VW_PASSWORD must be set in a .env file or in the environment.")
        return 1

    return asyncio.run(_run(username, password, args.proxy))


if __name__ == "__main__":
    sys.exit(main())
