# myVW

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
```

See [tests/](tests/) for coverage of the login flow (success and every failure branch),
the `_api`/`_get_relations`/`_fetch_vehicle` helpers, vehicle-fetch orchestration, the
HTML login-form parser, and the CLI's formatting and entry-point logic.

## Caveats

- **Unofficial client.** The portal has no public/supported API. Endpoints, form
  structure, and JSON response shapes can change at any time; this client may break
  without warning when they do.
- **TLS verification is disabled** (`verify=False`) in the HTTP client, to work around
  known certificate issues on the portal side from some networks. Review this setting
  for your own environment/threat model before relying on it — disabling TLS
  verification removes protection against man-in-the-middle attacks.
- Credentials are read from environment variables (or a local `.env` file via the CLI).
  Never commit a populated `.env` — see `.env.example` for the expected shape.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the development setup, coding conventions, and
how to submit changes. Notable changes are tracked in [CHANGELOG.md](CHANGELOG.md).
