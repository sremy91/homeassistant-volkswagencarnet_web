"""Tests pour les entités sensor du composant Volkswagen Web."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.volkswagen_web.sensor import (
    SENSOR_DESCRIPTIONS,
    VolkswagenSensor,
    async_setup_entry,
)


# ── Fixtures ────────────────────────────────────────────────────────────────

@dataclass
class FakeVehicleState:
    mileage_km: int = 42000
    data_timestamp: str = "2026-04-17T10:00:00"
    last_report_timestamp: str = "2026-04-17T10:00:00"
    model_name: str = "Golf 8 1.5 eTSI"
    systems: list = field(default_factory=lambda: [
        {"id": "freins", "label": "Freins", "status": "OK"},
        {"id": "pneus", "label": "Pneus", "status": "OK"},
        {"id": "transmission", "label": "Transmission", "status": "OK"},
        {"id": "feux_de_route", "label": "Éclairage", "status": "OK"},
        {"id": "assistants", "label": "Assistants", "status": "OK"},
        {"id": "confort", "label": "Confort", "status": "OK"},
    ])
    warning_lights: list = field(default_factory=list)
    contracts: list = field(default_factory=lambda: [
        {"id": "1", "productName": "Connectivity Plus"},
        {"id": "2", "productName": "Care Parking"},
    ])
    service_partner: dict = field(default_factory=lambda: {
        "name": "VW Paris Nord",
        "address": "123 Rue de Paris",
    })


def _make_coordinator(vin: str = "WVWTEST0000000001") -> MagicMock:
    """Crée un coordinateur mock avec données de test."""
    state = FakeVehicleState()

    vehicle = MagicMock()
    vehicle.vin = vin
    vehicle.nickname = "Mon Golf"
    vehicle.license_plate = "AA-123-AA"

    coordinator = MagicMock()
    coordinator.vins = [vin]
    coordinator.last_update_success = True
    coordinator.data = {
        vin: {
            "vehicle": vehicle,
            "state": state,
            "images": [{"image_data": "AAAA", "url": "https://example.com/car.jpg"}],
            "timestamp": datetime.now(),
        }
    }
    return coordinator


# ── Tests SENSOR_DESCRIPTIONS ────────────────────────────────────────────────

def test_sensor_descriptions_count():
    """14 sensors doivent être définis."""
    assert len(SENSOR_DESCRIPTIONS) == 14


def test_sensor_descriptions_structure():
    """Chaque description doit avoir 6 champs."""
    for desc in SENSOR_DESCRIPTIONS:
        assert len(desc) == 6, f"descriptor '{desc[0]}' ne contient pas 6 éléments"


# ── Tests VolkswagenSensor ───────────────────────────────────────────────────

@pytest.mark.parametrize("attr,expected", [
    ("mileage_km", 42000),
    ("model_name", "Golf 8 1.5 eTSI"),
    ("license_plate", "AA-123-AA"),
    ("status_freins", "OK"),
    ("status_pneus", "OK"),
    ("status_transmission", "OK"),
])
def test_sensor_native_value_direct(attr, expected):
    """Vérifie les valeurs natives des capteurs directs."""
    coordinator = _make_coordinator()
    sensor = VolkswagenSensor(
        coordinator=coordinator,
        vin="WVWTEST0000000001",
        attr=attr,
        device_class=None,
        state_class=None,
        native_unit=None,
        entity_category=None,
        icon=None,
    )
    assert sensor.native_value == expected


def test_sensor_vehicle_status_value():
    """vehicle_status doit inclure le nombre de systèmes et le km."""
    coordinator = _make_coordinator()
    sensor = VolkswagenSensor(
        coordinator=coordinator,
        vin="WVWTEST0000000001",
        attr="vehicle_status",
        device_class=None,
        state_class=None,
        native_unit=None,
        entity_category=None,
        icon=None,
    )
    value = sensor.native_value
    assert "6 système" in value
    assert "42000" in value


def test_sensor_warninglights_last_value():
    """warninglights_last doit retourner le nombre d'alertes."""
    coordinator = _make_coordinator()
    sensor = VolkswagenSensor(
        coordinator=coordinator,
        vin="WVWTEST0000000001",
        attr="warninglights_last",
        device_class=None,
        state_class=None,
        native_unit=None,
        entity_category=None,
        icon=None,
    )
    assert sensor.native_value == "0 alerte(s)"


def test_sensor_contracts_value():
    """contracts doit retourner le nombre de contrats."""
    coordinator = _make_coordinator()
    sensor = VolkswagenSensor(
        coordinator=coordinator,
        vin="WVWTEST0000000001",
        attr="contracts",
        device_class=None,
        state_class=None,
        native_unit=None,
        entity_category=None,
        icon=None,
    )
    assert sensor.native_value == "2 contrat(s)"


def test_sensor_service_partner_value():
    """service_partner doit retourner le nom du partenaire."""
    coordinator = _make_coordinator()
    sensor = VolkswagenSensor(
        coordinator=coordinator,
        vin="WVWTEST0000000001",
        attr="service_partner",
        device_class=None,
        state_class=None,
        native_unit=None,
        entity_category=None,
        icon=None,
    )
    assert sensor.native_value == "VW Paris Nord"


def test_sensor_unavailable_when_no_data():
    """Sensor doit être unavailable si le VIN n'est pas dans les données."""
    coordinator = MagicMock()
    coordinator.last_update_success = True
    coordinator.data = {}  # pas de données

    sensor = VolkswagenSensor(
        coordinator=coordinator,
        vin="UNKNOWNVIN",
        attr="mileage_km",
        device_class=None,
        state_class=None,
        native_unit=None,
        entity_category=None,
        icon=None,
    )
    assert sensor.available is False
    assert sensor.native_value is None


def test_sensor_unavailable_when_coordinator_failed():
    """Sensor doit être unavailable si le coordinator a échoué."""
    coordinator = _make_coordinator()
    coordinator.last_update_success = False

    sensor = VolkswagenSensor(
        coordinator=coordinator,
        vin="WVWTEST0000000001",
        attr="mileage_km",
        device_class=None,
        state_class=None,
        native_unit=None,
        entity_category=None,
        icon=None,
    )
    assert sensor.available is False


def test_sensor_extra_attributes_vehicle_status():
    """vehicle_status doit exposer systems + mileage_km dans les attributs."""
    coordinator = _make_coordinator()
    sensor = VolkswagenSensor(
        coordinator=coordinator,
        vin="WVWTEST0000000001",
        attr="vehicle_status",
        device_class=None,
        state_class=None,
        native_unit=None,
        entity_category=None,
        icon=None,
    )
    attrs = sensor.extra_state_attributes
    assert "systems" in attrs
    assert "mileage_km" in attrs
    assert attrs["mileage_km"] == 42000


def test_sensor_extra_attributes_contracts():
    coordinator = _make_coordinator()
    sensor = VolkswagenSensor(
        coordinator=coordinator,
        vin="WVWTEST0000000001",
        attr="contracts",
        device_class=None,
        state_class=None,
        native_unit=None,
        entity_category=None,
        icon=None,
    )
    attrs = sensor.extra_state_attributes
    assert "contracts_detail" in attrs
    assert len(attrs["contracts_detail"]) == 2


def test_sensor_device_info_model():
    """device_info doit retourner le modèle depuis state.model_name."""
    coordinator = _make_coordinator()
    sensor = VolkswagenSensor(
        coordinator=coordinator,
        vin="WVWTEST0000000001",
        attr="mileage_km",
        device_class=None,
        state_class=None,
        native_unit=None,
        entity_category=None,
        icon=None,
    )
    info = sensor.device_info
    assert info["manufacturer"] == "Volkswagen"
    assert ("volkswagen_web", "WVWTEST0000000001") in info["identifiers"]
    assert info["model"] == "Golf 8 1.5 eTSI"
