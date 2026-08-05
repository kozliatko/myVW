"""Tests for MyVWClient: login flow, API helper, and vehicle-fetching orchestration."""

from unittest.mock import AsyncMock

import httpx
import pytest

from myvw.client import (
    _AP,
    _LOGIN_URL,
    _PORTAL,
    LoginError,
    MyVWClient,
)

IDENTITY_LOGIN_URL = "https://identity.vwgroup.io/signin/v1/login"
IDENTITY_AUTH_URL = "https://identity.vwgroup.io/signin/v1/authenticate"
PORTAL_HOME_URL = f"{_PORTAL}/sk/sk/myvolkswagen.html"


def _successful_login_handler(request: httpx.Request) -> httpx.Response:
    url = str(request.url)

    if url == _LOGIN_URL and request.method == "GET":
        return httpx.Response(302, headers={"Location": IDENTITY_LOGIN_URL})

    if url == IDENTITY_LOGIN_URL and request.method == "GET":
        html = (
            f'<form action="{IDENTITY_AUTH_URL}" method="post">'
            '<input type="hidden" name="csrf" value="tok-123">'
            '<input type="text" name="username" value="">'
            '<input type="password" name="password" value="">'
            "</form>"
        )
        return httpx.Response(200, text=html)

    if url == IDENTITY_AUTH_URL and request.method == "POST":
        return httpx.Response(302, headers={"Location": PORTAL_HOME_URL})

    if url == PORTAL_HOME_URL and request.method == "GET":
        return httpx.Response(
            200,
            text="<html>ok</html>",
            headers=[
                ("set-cookie", "SESSION=sess-abc; Path=/"),
                ("set-cookie", "csrf_token=csrf-xyz; Path=/"),
            ],
        )

    raise AssertionError(f"Unexpected request: {request.method} {url}")


# -- start() / TLS verification -----------------------------------------------


@pytest.mark.asyncio
async def test_start_verifies_tls_by_default(monkeypatch):
    captured = {}

    class _RecordingAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            captured.update(kwargs)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", _RecordingAsyncClient)

    client = MyVWClient("user@example.com", "secret")
    await client.start()
    await client.close()

    assert captured["verify"] is True


@pytest.mark.asyncio
async def test_start_allows_disabling_tls_verification_explicitly(monkeypatch):
    captured = {}

    class _RecordingAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            captured.update(kwargs)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", _RecordingAsyncClient)

    client = MyVWClient("user@example.com", "secret", verify=False)
    await client.start()
    await client.close()

    assert captured["verify"] is False


@pytest.mark.asyncio
async def test_login_success_sets_session_cookie():
    transport = httpx.MockTransport(_successful_login_handler)
    async with MyVWClient("user@example.com", "secret", transport=transport) as client:
        await client.login()
        assert client._http.cookies.get("SESSION") == "sess-abc"
        assert client._http.cookies.get("csrf_token") == "csrf-xyz"


@pytest.mark.asyncio
async def test_login_raises_when_login_url_does_not_redirect_to_identity():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not a redirect")

    transport = httpx.MockTransport(handler)
    async with MyVWClient("user@example.com", "secret", transport=transport) as client:
        with pytest.raises(LoginError, match="Unexpected URL"):
            await client.login()


@pytest.mark.asyncio
async def test_login_raises_when_identity_page_has_no_form():
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == _LOGIN_URL:
            return httpx.Response(302, headers={"Location": IDENTITY_LOGIN_URL})
        if url == IDENTITY_LOGIN_URL:
            return httpx.Response(200, text="<html>no form here</html>")
        raise AssertionError(f"Unexpected request: {url}")

    transport = httpx.MockTransport(handler)
    async with MyVWClient("user@example.com", "secret", transport=transport) as client:
        with pytest.raises(LoginError):
            await client.login()


@pytest.mark.asyncio
async def test_login_raises_when_credentials_are_rejected():
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == _LOGIN_URL and request.method == "GET":
            return httpx.Response(302, headers={"Location": IDENTITY_LOGIN_URL})
        if url == IDENTITY_LOGIN_URL and request.method == "GET":
            html = (
                f'<form action="{IDENTITY_AUTH_URL}">'
                '<input name="username" value=""><input name="password" value="">'
                "</form>"
            )
            return httpx.Response(200, text=html)
        if url == IDENTITY_AUTH_URL and request.method == "POST":
            # Stays on the identity server: wrong credentials.
            return httpx.Response(200, text="Invalid username or password")
        raise AssertionError(f"Unexpected request: {url}")

    transport = httpx.MockTransport(handler)
    async with MyVWClient("user@example.com", "wrong", transport=transport) as client:
        with pytest.raises(LoginError, match="Login failed"):
            await client.login()


@pytest.mark.asyncio
async def test_login_raises_when_session_cookie_missing():
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == _LOGIN_URL and request.method == "GET":
            return httpx.Response(302, headers={"Location": IDENTITY_LOGIN_URL})
        if url == IDENTITY_LOGIN_URL and request.method == "GET":
            html = f'<form action="{IDENTITY_AUTH_URL}"><input name="username" value=""></form>'
            return httpx.Response(200, text=html)
        if url == IDENTITY_AUTH_URL and request.method == "POST":
            return httpx.Response(302, headers={"Location": PORTAL_HOME_URL})
        if url == PORTAL_HOME_URL and request.method == "GET":
            # Back on the portal, but no SESSION cookie was ever set.
            return httpx.Response(200, text="<html>ok</html>")
        raise AssertionError(f"Unexpected request: {url}")

    transport = httpx.MockTransport(handler)
    async with MyVWClient("user@example.com", "secret", transport=transport) as client:
        with pytest.raises(LoginError, match="SESSION cookie"):
            await client.login()


@pytest.mark.asyncio
async def test_api_returns_json_on_200():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"hello": "world"})

    transport = httpx.MockTransport(handler)
    async with MyVWClient("user@example.com", "secret", transport=transport) as client:
        result = await client._api(f"{_AP}/some/path")
        assert result == {"hello": "world"}


@pytest.mark.asyncio
async def test_api_returns_none_on_non_200():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="forbidden")

    transport = httpx.MockTransport(handler)
    async with MyVWClient("user@example.com", "secret", transport=transport) as client:
        result = await client._api(f"{_AP}/some/path")
        assert result is None


@pytest.mark.asyncio
async def test_api_sends_csrf_token_from_cookie():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["csrf"] = request.headers.get("x-csrf-token")
        return httpx.Response(200, json={})

    transport = httpx.MockTransport(handler)
    async with MyVWClient("user@example.com", "secret", transport=transport) as client:
        client._http.cookies.set("csrf_token", "my-token")
        await client._api(f"{_AP}/some/path")

    assert captured["csrf"] == "my-token"


@pytest.mark.asyncio
async def test_get_relations_returns_relations_list():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"relations": [{"vehicle": {"vin": "VIN1"}}]})

    transport = httpx.MockTransport(handler)
    async with MyVWClient("user@example.com", "secret", transport=transport) as client:
        relations = await client._get_relations()
        assert relations == [{"vehicle": {"vin": "VIN1"}}]


@pytest.mark.asyncio
async def test_get_relations_raises_when_response_has_no_relations_key():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": True})

    transport = httpx.MockTransport(handler)
    async with MyVWClient("user@example.com", "secret", transport=transport) as client:
        with pytest.raises(RuntimeError, match="Failed to fetch the vehicle list"):
            await client._get_relations()


@pytest.mark.asyncio
async def test_fetch_vehicle_assembles_full_vehicle_from_endpoints():
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/data/sk-SK"):
            return httpx.Response(200, json={"modelName": "Golf"})
        if path.endswith("/details/sk-SK"):
            return httpx.Response(200, json={"engine": "1.5 TSI"})
        if path.endswith("/warninglights/last"):
            return httpx.Response(
                200,
                json={
                    "data": {
                        "mileage_km": 42000,
                        "warningLights": ["oil"],
                        "carCapturedTimestamp": "2026-08-01T10:00:00Z",
                    }
                },
            )
        if path.endswith("/maintenance/status"):
            return httpx.Response(
                200,
                json={
                    "data": {
                        "inspectionDue_days": 100,
                        "inspectionDue_km": 5000,
                        "oilServiceDue_days": 30,
                        "oilServiceDue_km": 1000,
                    }
                },
            )
        if path.endswith("/tripdata/shortterm/last"):
            return httpx.Response(
                200,
                json={
                    "data": {
                        "tripType": "short",
                        "mileage_km": 12,
                        "averageFuelConsumption": 6.5,
                        "travelTime": 15,
                        "averageSpeed_kmph": 48,
                        "tripEndTimestamp": "2026-08-01T09:00:00Z",
                    }
                },
            )
        if path.endswith("/tripdata/longterm/last"):
            return httpx.Response(200, json={})
        if path.endswith("/tripdata/cyclic/last"):
            return httpx.Response(404)
        raise AssertionError(f"Unexpected request: {path}")

    transport = httpx.MockTransport(handler)
    async with MyVWClient("user@example.com", "secret", transport=transport) as client:
        vehicle = await client._fetch_vehicle(
            {
                "vehicle": {"vin": "VIN123"},
                "vehicleNickname": "MyCar",
                "licensePlate": "BA123XY",
                "role": "OWNER",
            }
        )

    assert vehicle.vin == "VIN123"
    assert vehicle.nickname == "MyCar"
    assert vehicle.license_plate == "BA123XY"
    assert vehicle.role == "OWNER"
    assert vehicle.model_name == "Golf"
    assert vehicle.engine == "1.5 TSI"
    assert vehicle.mileage_km == 42000
    assert vehicle.warning_lights == ["oil"]
    assert vehicle.data_timestamp == "2026-08-01 10:00:00"
    assert vehicle.maintenance.inspection_due_days == 100
    assert vehicle.maintenance.oil_due_km == 1000
    assert vehicle.short_trip.distance_km == 12
    assert vehicle.short_trip.avg_fuel_l100 == 6.5
    assert vehicle.long_trip is None
    assert vehicle.cyclic_trip is None


@pytest.mark.asyncio
async def test_get_vehicles_logs_in_then_fetches_each_relation():
    client = MyVWClient("user@example.com", "secret")
    client.login = AsyncMock()
    client._get_relations = AsyncMock(
        return_value=[{"vehicle": {"vin": "VIN1"}}, {"vehicle": {"vin": "VIN2"}}]
    )
    client._fetch_vehicle = AsyncMock(side_effect=lambda rel: rel["vehicle"]["vin"])

    result = await client.get_vehicles()

    client.login.assert_awaited_once()
    assert result == ["VIN1", "VIN2"]
    assert client._fetch_vehicle.await_count == 2
