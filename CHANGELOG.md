# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Test suite (`pytest` + `pytest-asyncio`) covering the login flow, HTML login-form
  parser, `_api`/`_get_relations`/`_fetch_vehicle` helpers, vehicle-fetch orchestration,
  and the CLI's formatting and entry-point logic. No real network access is used —
  `httpx.MockTransport` stands in for the portal.
- `dev` optional-dependency group in `pyproject.toml` (`pip install -e ".[dev]"`).
- `pytest` configuration (`asyncio_mode = "auto"`) in `pyproject.toml`.
- English-language `README.md`, `CONTRIBUTING.md`, and this changelog.
- Optional `transport` parameter on `MyVWClient.__init__` for injecting a custom
  `httpx.BaseTransport` (used by the test suite; also usable by library consumers who
  need custom networking behavior).

## [0.1.0] - Initial release

### Added

- `MyVWClient` — async client for myvolkswagen.net using a shared `httpx.AsyncClient`
  cookie jar, no headless browser required.
- OIDC Authorization Code Flow login (`login()`), including HTML login-form parsing via
  a minimal `html.parser.HTMLParser` subclass.
- `get_vehicles()` — fetches the account's vehicle relations and, for each vehicle,
  merges data from the portal's data, details, warning-lights, maintenance, and trip
  (short/long/cyclic) endpoints into a `Vehicle` dataclass.
- `Vehicle`, `Maintenance`, `Trip` dataclasses as the public data model.
- `LoginError` exception for authentication failures.
- Optional SOCKS/HTTP proxy support via `MyVWClient(..., proxy=...)`.
- CLI (`myvw` / `python -m myvw`) printing a formatted report of all vehicles on the
  account, with credentials read from environment variables or a `.env` file.
