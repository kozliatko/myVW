# Contributing to myVW

Thanks for considering a contribution. This is a small, single-purpose client, so the bar
is: keep it simple, keep it tested, and don't grow scope beyond what the portal actually
needs.

## Development setup

```bash
git clone <this repo>
cd myVW
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

The `dev` extra installs `pytest`, `pytest-asyncio`, and `python-dotenv`.

## Running the test suite

```bash
pytest
```

Tests must not perform real network calls. Login-flow and API tests use
`httpx.MockTransport` — `MyVWClient` accepts an optional `transport=` argument for exactly
this purpose. If you add a code path that talks to the portal, add a mocked test for it
rather than depending on a live account.

Run a single file or test while iterating:

```bash
pytest tests/test_client.py -v
pytest tests/test_client.py::test_login_success_sets_session_cookie -v
```

## Code style

- Python 3.11+, type hints on public functions and dataclass fields.
- No unrelated formatting churn in a change — keep diffs focused.
- Prefer small, direct functions over abstractions; this codebase favors explicitness
  over cleverness (see `myvw/client.py` for the existing tone).
- Comments explain *why*, not *what* — only add one where the code itself can't make the
  reasoning obvious (e.g. a portal quirk, a workaround for a known bug).

## Making changes

1. Open an issue or PR describing what portal behavior changed or what's being fixed —
   include a short repro or the relevant endpoint/response shape if you have it.
2. Keep the change scoped: a bug fix shouldn't carry along unrelated refactors.
3. Add or update tests covering the change. A PR that changes `client.py` behavior
   without a matching test change will likely get asked for one.
4. Update [CHANGELOG.md](CHANGELOG.md) under an `Unreleased` section.
5. Make sure `pytest` passes before opening the PR.

## Reporting portal changes

Since this is an unofficial client scraping an undocumented API, the most valuable
contributions are often just reports: "endpoint X now returns field Y instead of Z",
"login form gained a new hidden field", etc. Please include:

- The endpoint path (with any identifying values redacted).
- The old vs. new response/request shape.
- Whether the change broke `login()`, `get_vehicles()`, or a specific field.

Never include real credentials, session cookies, VINs, or other personal data in an
issue or PR.

## Security

If you find a security issue (e.g. something worse than the documented `verify=False`
TLS caveat), please open an issue describing the concern without including exploit
details or personal account data, so it can be triaged privately if needed.
