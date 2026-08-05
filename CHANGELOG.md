# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.1] - 2026-08-05

### Security

- **`MyVWClient` now verifies TLS certificates by default** (`verify=True`).
  Previously `verify=False` was hardcoded in `start()`, disabling certificate
  verification unconditionally on every request (initial login, the identity-server
  POST, and every `authproxy` API call), justified by a code comment claiming
  portal-side certificate issues. That claim was tested end-to-end against the live
  portal — full `login()` + `get_vehicles()` flow against both
  `www.myvolkswagen.net` and `identity.vwgroup.io` with verification enabled — and
  completed successfully; both hosts present valid, publicly-trusted certificates
  (DigiCert and Amazon RSA respectively). No functional reason for disabling
  verification was found, while it did expose plaintext credentials to any
  on-path attacker. `verify=False` remains available as an explicit,
  caller-opted-in constructor argument for edge cases (e.g. a corporate MITM
  proxy) — see the Caveats section in the README.

## [0.2.0] - 2026-08-05

### Changed

- Translated all library-facing text to English: docstrings and comments in
  `myvw/client.py`, CLI output labels and messages in `myvw/cli.py`
  (`Vehicles found:`, `Warning lights:`, `Inspection due:`, `Oil service due:`,
  `Short/Long/Cyclic trip:`, error messages, etc.), and the `pyproject.toml`
  description. No Slovak strings remain in the codebase. Portal protocol
  parameters (the `sk-SK` locale and `/sk/sk/` redirect path used to talk to
  myvolkswagen.net) are intentionally left unchanged, since they affect what
  the third-party API returns rather than being text authored by this library.
- Fixed a test-isolation bug where `test_main_returns_1_when_credentials_missing`
  could silently read a real local `.env` file via `dotenv.load_dotenv()` and
  perform a live login against the portal; the CLI tests now stub out
  `dotenv.load_dotenv` so the suite never depends on what's on disk.

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

## [0.1.0] - 2026-08-05 - Initial release

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
