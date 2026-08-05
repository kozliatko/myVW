"""Tests for the plain data classes: Vehicle, Maintenance, Trip."""

from myvw.client import Maintenance, Trip, Vehicle


def test_maintenance_defaults_to_all_none():
    m = Maintenance()
    assert m.inspection_due_days is None
    assert m.inspection_due_km is None
    assert m.oil_due_days is None
    assert m.oil_due_km is None


def test_trip_defaults():
    t = Trip()
    assert t.trip_type == ""
    assert t.distance_km is None
    assert t.avg_fuel_l100 is None
    assert t.travel_time_min is None
    assert t.avg_speed_kmh is None
    assert t.end_timestamp == ""


def test_vehicle_requires_only_vin():
    v = Vehicle(vin="WVWZZZ1KZAW000000")
    assert v.vin == "WVWZZZ1KZAW000000"
    assert v.nickname == ""
    assert v.license_plate == ""
    assert v.role == ""
    assert v.model_name == ""
    assert v.engine == ""
    assert v.mileage_km is None
    assert v.data_timestamp == ""
    assert v.warning_lights == []
    assert isinstance(v.maintenance, Maintenance)
    assert v.short_trip is None
    assert v.long_trip is None
    assert v.cyclic_trip is None


def test_vehicle_default_collections_are_not_shared_between_instances():
    v1 = Vehicle(vin="VIN1")
    v2 = Vehicle(vin="VIN2")

    v1.warning_lights.append("engine")

    assert v1.warning_lights == ["engine"]
    assert v2.warning_lights == []
    assert v1.maintenance is not v2.maintenance


def test_vehicle_accepts_full_data():
    maint = Maintenance(inspection_due_days=100, inspection_due_km=5000)
    trip = Trip(trip_type="short", distance_km=12)
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
        maintenance=maint,
        short_trip=trip,
    )
    assert v.model_name == "Golf"
    assert v.maintenance.inspection_due_km == 5000
    assert v.short_trip.distance_km == 12
