"""Tests for the CLI: formatting helpers, report printing, and main()/_run() flow."""

import pytest

from myvw import cli
from myvw.client import LoginError, Maintenance, Trip, Vehicle


# -- _fmt_trip ----------------------------------------------------------------


def test_fmt_trip_includes_all_optional_fields():
    trip = Trip(
        trip_type="short",
        distance_km=12,
        avg_fuel_l100=6.5,
        travel_time_min=15,
        avg_speed_kmh=48,
        end_timestamp="2026-08-01 09:00:00",
    )
    formatted = cli._fmt_trip(trip)
    assert formatted == "12 km  |  6.5 l/100km  |  15 min  |  ⌀ 48 km/h  (2026-08-01)"


def test_fmt_trip_with_only_distance():
    trip = Trip(distance_km=7, end_timestamp="2026-08-01 09:00:00")
    formatted = cli._fmt_trip(trip)
    assert formatted == "7 km  (2026-08-01)"


# -- _fmt_maint -----------------------------------------------------------------


def test_fmt_maint_returns_none_when_both_values_missing():
    m = Maintenance()
    assert cli._fmt_maint(m, "STK za:", "inspection_due_days", "inspection_due_km") is None


def test_fmt_maint_formats_days_and_km():
    m = Maintenance(inspection_due_days=100, inspection_due_km=5000)
    line = cli._fmt_maint(m, "STK za:", "inspection_due_days", "inspection_due_km")
    assert line == "  STK za:       100 dní / 5 000 km"


def test_fmt_maint_formats_days_only():
    m = Maintenance(oil_due_days=30)
    line = cli._fmt_maint(m, "Olej za:", "oil_due_days", "oil_due_km")
    assert line == "  Olej za:      30 dní"


# -- print_vehicle / print_report -----------------------------------------------


def test_print_vehicle_outputs_key_fields(capsys):
    v = Vehicle(
        vin="VIN123",
        nickname="Golfík",
        license_plate="BA123XY",
        role="OWNER",
        model_name="Golf",
        engine="1.5 TSI",
        mileage_km=42000,
        data_timestamp="2026-08-01 10:00:00",
        warning_lights=["oil"],
        maintenance=Maintenance(inspection_due_days=100, inspection_due_km=5000),
    )
    cli.print_vehicle(v)
    out = capsys.readouterr().out

    assert "VIN123" in out
    assert "Golfík" in out and "BA123XY" in out
    assert "Golf" in out
    assert "1.5 TSI" in out
    assert "42 000 km" in out
    assert "oil" in out


def test_print_vehicle_shows_no_lights_message_when_empty(capsys):
    v = Vehicle(vin="VIN123")
    cli.print_vehicle(v)
    out = capsys.readouterr().out
    assert "žiadne" in out


def test_print_report_shows_count_and_all_vehicles(capsys):
    vehicles = [Vehicle(vin="VIN1"), Vehicle(vin="VIN2")]
    cli.print_report(vehicles)
    out = capsys.readouterr().out
    assert "Nájdených vozidiel: 2" in out
    assert "VIN1" in out
    assert "VIN2" in out


# -- _run -----------------------------------------------------------------------


class _FakeClient:
    """Stand-in for MyVWClient used to drive _run() without any network access."""

    instances: list = []

    def __init__(self, username, password, *, proxy=None):
        self.username = username
        self.password = password
        self.proxy = proxy
        _FakeClient.instances.append(self)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return None

    async def get_vehicles(self):
        raise NotImplementedError


@pytest.fixture(autouse=True)
def _reset_fake_client_instances():
    _FakeClient.instances = []
    yield
    _FakeClient.instances = []


@pytest.mark.asyncio
async def test_run_returns_0_and_prints_report_on_success(monkeypatch, capsys):
    async def get_vehicles(self):
        return [Vehicle(vin="VIN1")]

    _FakeClient.get_vehicles = get_vehicles
    monkeypatch.setattr(cli, "MyVWClient", _FakeClient)

    code = await cli._run("user@example.com", "secret", None)

    assert code == 0
    assert "VIN1" in capsys.readouterr().out
    assert _FakeClient.instances[0].username == "user@example.com"


@pytest.mark.asyncio
async def test_run_returns_1_and_prints_error_on_login_failure(monkeypatch, capsys):
    async def get_vehicles(self):
        raise LoginError("bad credentials")

    _FakeClient.get_vehicles = get_vehicles
    monkeypatch.setattr(cli, "MyVWClient", _FakeClient)

    code = await cli._run("user@example.com", "wrong", None)

    assert code == 1
    assert "bad credentials" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_run_passes_proxy_through_to_client(monkeypatch):
    async def get_vehicles(self):
        return []

    _FakeClient.get_vehicles = get_vehicles
    monkeypatch.setattr(cli, "MyVWClient", _FakeClient)

    await cli._run("user@example.com", "secret", "socks5://localhost:8080")

    assert _FakeClient.instances[0].proxy == "socks5://localhost:8080"


# -- main -----------------------------------------------------------------------


def test_main_returns_1_when_credentials_missing(monkeypatch, capsys):
    monkeypatch.delenv("VW_USERNAME", raising=False)
    monkeypatch.delenv("VW_PASSWORD", raising=False)
    monkeypatch.setattr("sys.argv", ["myvw"])

    assert cli.main() == 1
    assert "VW_USERNAME a VW_PASSWORD" in capsys.readouterr().out


def test_main_invokes_run_with_env_credentials(monkeypatch):
    monkeypatch.setenv("VW_USERNAME", "user@example.com")
    monkeypatch.setenv("VW_PASSWORD", "secret")
    monkeypatch.setattr("sys.argv", ["myvw", "--proxy", "socks5://localhost:8080"])

    captured = {}

    async def fake_run(username, password, proxy):
        captured["args"] = (username, password, proxy)
        return 0

    monkeypatch.setattr(cli, "_run", fake_run)

    assert cli.main() == 0
    assert captured["args"] == ("user@example.com", "secret", "socks5://localhost:8080")
