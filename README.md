# myVW

[![Security](https://github.com/kozliatko/myVW/actions/workflows/security.yml/badge.svg)](https://github.com/kozliatko/myVW/actions/workflows/security.yml)
[![Tests](https://github.com/kozliatko/myVW/actions/workflows/tests.yml/badge.svg)](https://github.com/kozliatko/myVW/actions/workflows/tests.yml)
[![CodeQL](https://github.com/kozliatko/myVW/actions/workflows/codeql.yml/badge.svg)](https://github.com/kozliatko/myVW/actions/workflows/codeql.yml)
[![Snyk security](https://snyk.io/test/github/kozliatko/myVW/badge.svg)](https://snyk.io/test/github/kozliatko/myVW)
[![codecov](https://codecov.io/gh/kozliatko/myVW/branch/main/graph/badge.svg)](https://codecov.io/gh/kozliatko/myVW)
![Version](https://img.shields.io/github/v/release/kozliatko/myVW)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/github/license/kozliatko/myVW)
![Last commit](https://img.shields.io/github/last-commit/kozliatko/myVW)
![Issues](https://img.shields.io/github/issues/kozliatko/myVW)

An async Python client for [myvolkswagen.net](https://www.myvolkswagen.net) — sign in and
pull vehicle data (odometer, service intervals, trips, warning lights) via direct HTTP
calls, with no Playwright or other headless browser involved.

> **Unofficial project.** The portal exposes no public API. Endpoints, form fields, and
> response shapes can change at any time without notice — see [Caveats](#caveats).

## Contents

- [How login works](#how-login-works)
- [Installation](#installation)
- [Library usage](#library-usage)
- [CLI usage](#cli-usage)
- [Data model](#data-model)
- [Testing](#testing)
- [Caveats](#caveats)
- [Contributing](#contributing)

## How login works

The portal uses a standard OIDC Authorization Code Flow:

1. `GET /app/authproxy/login` → redirects to `identity.vwgroup.io`.
2. The client parses the login form served by the identity provider and POSTs it back
   with the supplied email and password.
3. On success, the identity server redirects back to the portal, which sets `SESSION`
   and `csrf_token` cookies.
4. Every subsequent call hits an `/app/authproxy/*` endpoint with `X-Csrf-Token` and
   `user-id` headers attached.

The whole flow runs over a single shared `httpx.AsyncClient` cookie jar, so no browser or
JavaScript execution is required — just following redirects and posting a form.

## Installation

```bash
pip install -e .
# or, without packaging:
pip install -r requirements.txt
```

Installing with the `cli` (or `dev`) extra pulls in `python-dotenv` so the CLI can read a
`.env` file:

```bash
pip install -e ".[cli]"
```

### Installing without PyPI

This project isn't published on PyPI, so `pip install myvw` doesn't work. `pip` can still
install it directly, since `pyproject.toml` already declares a proper build backend
(`setuptools.build_meta`):

```bash
# latest commit on the default branch
pip install git+https://github.com/kozliatko/myVW.git

# a specific tagged release (recommended, so upgrades are intentional)
pip install git+https://github.com/kozliatko/myVW.git@v0.2.2

# with the CLI extra
pip install "myvw[cli] @ git+https://github.com/kozliatko/myVW.git@v0.2.2"
```

Or build a wheel locally and install/distribute that file directly:

```bash
pip install build
python -m build            # writes dist/myvw-<version>-py3-none-any.whl
pip install dist/myvw-*.whl
```

## Library usage

```python
import asyncio
from myvw import MyVWClient

async def main():
    async with MyVWClient("email@example.com", "password") as client:
        for v in await client.get_vehicles():
            print(v.vin, v.model_name, v.mileage_km, "km")

asyncio.run(main())
```

Optional SOCKS/HTTP proxy:

```python
async with MyVWClient(username, password, proxy="socks5://localhost:8080") as client:
    ...
```

Optional custom `httpx` transport (useful for tests or advanced networking setups):

```python
import httpx
from myvw import MyVWClient

transport = httpx.HTTPTransport(...)
async with MyVWClient(username, password, transport=transport) as client:
    ...
```

TLS certificate verification is **on by default**. It can be turned off explicitly if you
hit a certificate problem in your own network (e.g. a corporate MITM proxy) — see
[Caveats](#caveats) before doing so, since it removes protection against
man-in-the-middle attacks:

```python
async with MyVWClient(username, password, verify=False) as client:
    ...
```

A failed login raises `myvw.LoginError`. Any other unexpected portal response (e.g. a
missing vehicle list) raises `RuntimeError`.

## CLI usage

```bash
cp .env.example .env   # fill in VW_USERNAME and VW_PASSWORD
myvw
# or:
python -m myvw
python -m myvw --proxy socks5://localhost:8080
```

Prints a human-readable summary of every vehicle on the account: odometer, days/km until
next inspection and oil service, active warning lights, and the most recent short, long,
and cyclic trips.

### Example output

Sample run against an account with three vehicles (VINs, plates, nicknames, and mileage
below are anonymized/fabricated — not a real account; the `warningLights` icon payload,
a base64 PNG, is truncated with `...` for readability):

```
# Logging in to myVolkswagen...

Vehicles found: 3

========================================================
  VIN:              WVWZZZ1KZXX000001
  Vehicle:          Vehicle One  (XX111AA)  [UNKNOWN]
  Model:            Volkswagen
  Warning lights:   none
========================================================
  VIN:              WVGZZZ5NZXX000002
  Vehicle:          Vehicle Two  (XX222BB)  [PRIMARY_USER]
  Model:            Tiguan Life 2.0 l TDI SCR
  Engine:           110 kW (150 PS)
  Odometer:         100 000 km  (as of 2026-01-01 12:00:00)
  Inspection due:   280 days / 15 000 km
  Oil service due:  230 days / 13 000 km
  Warning lights:   {'text': 'Fuel low, please refuel. Range: n/a', 'category': 'ENGINE', 'priority': '117', 'icon': 'data:image/png;base64,...', 'iconName': 'G_2_01_y.png', 'messageId': '0xA222', 'customerRelevance': False, 'iconColor': 'Yellow'}
  Short trip:       7 km  |  8.2 l/100km  |  17 min  |  ⌀ 26 km/h  (2026-01-01)
  Long trip:        1800 km  |  6.4 l/100km  |  2900 min  |  ⌀ 38 km/h  (2026-01-01)
  Cyclic trip:      900 km  |  6.0 l/100km  |  1280 min  |  ⌀ 42 km/h  (2026-01-01)
========================================================
  VIN:              WV1ZZZ7HZXX000003
  Vehicle:          Vehicle Three  (XX333CC)  [GUEST_USER]
  Model:            Transporter panel van 2.0 l
  Warning lights:   none
========================================================
```

Note: the `text` field inside `warningLights` entries is returned by the portal in
whatever locale the client requests (currently `sk-SK`); the value above is an English
translation for readability, not what the live API actually returns.

Vehicles without a recent MBB data sync (e.g. `Vehicle One` and `Vehicle Three` above)
only show what the `relations` and `details` endpoints return — odometer, maintenance,
and trip data stay empty until the vehicle reports in.

## Data model

`client.get_vehicles()` returns a list of `Vehicle` objects (all `myvw.client` dataclasses,
also re-exported from the top-level `myvw` package):

| Field | Type | Description |
|---|---|---|
| `vin`, `nickname`, `license_plate`, `role` | `str` | Vehicle identification |
| `model_name`, `engine` | `str` | Model and engine |
| `mileage_km` | `int \| None` | Current odometer reading |
| `data_timestamp` | `str` | Timestamp of the last data capture (`YYYY-MM-DD HH:MM:SS`) |
| `warning_lights` | `list` | Active warning lights |
| `maintenance` | `Maintenance` | Days/km until inspection (STK) and oil service |
| `short_trip`, `long_trip`, `cyclic_trip` | `Trip \| None` | Most recently recorded trips |

`Maintenance`:

| Field | Type |
|---|---|
| `inspection_due_days`, `inspection_due_km` | `int \| None` |
| `oil_due_days`, `oil_due_km` | `int \| None` |

`Trip`:

| Field | Type |
|---|---|
| `trip_type` | `str` |
| `distance_km` | `int \| None` |
| `avg_fuel_l100` | `float \| None` |
| `travel_time_min` | `int \| None` |
| `avg_speed_kmh` | `int \| None` |
| `end_timestamp` | `str` |

Each of the underlying portal endpoints (vehicle data, details, warning lights,
maintenance status, and the three trip types) is fetched independently and merged into
one `Vehicle`. If any individual endpoint fails or returns an unexpected shape, the
corresponding field is simply left at its default rather than aborting the whole fetch.

## Testing

The test suite uses `pytest` + `pytest-asyncio` and `httpx.MockTransport` — no real
network access and no extra mocking dependency required.

```bash
pip install -e ".[dev]"
pytest
# with a coverage report:
pytest --cov=myvw --cov-report=term-missing
```

See [tests/](tests/) for coverage of the login flow (success and every failure branch),
the `_api`/`_get_relations`/`_fetch_vehicle` helpers, vehicle-fetch orchestration, the
HTML login-form parser, and the CLI's formatting and entry-point logic.

Every push and pull request runs the suite on Python 3.11–3.13 via
[GitHub Actions](.github/workflows/tests.yml), runs [CodeQL](.github/workflows/codeql.yml)
static analysis and a [Snyk](.github/workflows/snyk.yml) dependency vulnerability scan, and
uploads a coverage report to [Codecov](https://codecov.io/gh/kozliatko/myVW).

## Caveats

- **Unofficial client.** The portal has no public/supported API. Endpoints, form
  structure, and JSON response shapes can change at any time; this client may break
  without warning when they do.
- **TLS certificate verification is enabled by default** (`verify=True`). It was
  previously hardcoded to `False`, allegedly to work around portal-side certificate
  issues; that claim was tested end-to-end against the live portal (full login +
  `get_vehicles()` flow, both `www.myvolkswagen.net` and `identity.vwgroup.io`) with
  verification on, and no certificate problem was found — both hosts present valid,
  publicly-trusted certificates. `verify=False` is still available as an explicit
  opt-out (`MyVWClient(..., verify=False)`) for edge cases like a corporate MITM proxy,
  but using it removes protection against man-in-the-middle attacks, including exposure
  of your plaintext myvolkswagen.net credentials — only disable it if you understand
  and accept that risk for your specific network.
- Credentials are read from environment variables (or a local `.env` file via the CLI).
  Never commit a populated `.env` — see `.env.example` for the expected shape.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the development setup, coding conventions, and
how to submit changes. Notable changes are tracked in [CHANGELOG.md](CHANGELOG.md).
