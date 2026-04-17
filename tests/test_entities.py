"""Tests pour les entités button, camera et image du composant Volkswagen Web."""

from __future__ import annotations

import base64
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.volkswagen_web.button import VolkswagenRequestUpdateButton
from custom_components.volkswagen_web.camera import VolkswagenCamera
from custom_components.volkswagen_web.image import VolkswagenImageEntity


def _make_coordinator(vin: str = "WVWTEST0000000001") -> MagicMock:
    """Crée un coordinateur mock avec données de test."""
    vehicle = MagicMock()
    vehicle.vin = vin
    vehicle.nickname = "Mon Golf"
    vehicle.license_plate = "AA-123-AA"

    # Image test: 4 octets PNG minimal encodé en base64
    fake_bytes = b"\x89PNG\r\n"
    image_b64 = base64.b64encode(fake_bytes).decode()

    coordinator = MagicMock()
    coordinator.vins = [vin]
    coordinator.last_update_success = True
    coordinator.async_request_report_manual = AsyncMock(return_value=True)
    coordinator.data = {
        vin: {
            "vehicle": vehicle,
            "state": MagicMock(mileage_km=42000, model_name="Golf"),
            "images": [{"image_data": image_b64, "url": "https://example.com/car.jpg"}],
            "timestamp": datetime.now(),
        }
    }
    return coordinator


# ── Tests Button ─────────────────────────────────────────────────────────────

def test_button_unique_id():
    coordinator = _make_coordinator()
    btn = VolkswagenRequestUpdateButton(coordinator, "WVWTEST0000000001")
    assert btn._attr_unique_id == "WVWTEST0000000001-button-request_update"


def test_button_icon():
    coordinator = _make_coordinator()
    btn = VolkswagenRequestUpdateButton(coordinator, "WVWTEST0000000001")
    assert btn._attr_icon == "mdi:refresh"


def test_button_available():
    coordinator = _make_coordinator()
    btn = VolkswagenRequestUpdateButton(coordinator, "WVWTEST0000000001")
    assert btn.available is True


def test_button_unavailable_when_no_data():
    coordinator = MagicMock()
    coordinator.last_update_success = True
    coordinator.data = {}
    btn = VolkswagenRequestUpdateButton(coordinator, "UNKNOWNVIN")
    assert btn.available is False


def test_button_device_info():
    coordinator = _make_coordinator()
    btn = VolkswagenRequestUpdateButton(coordinator, "WVWTEST0000000001")
    info = btn.device_info
    assert info["manufacturer"] == "Volkswagen"
    assert info["name"] == "Mon Golf"
    assert ("volkswagen_web", "WVWTEST0000000001") in info["identifiers"]


@pytest.mark.asyncio
async def test_button_press_calls_coordinator():
    """async_press doit appeler coordinator.async_request_report_manual avec le VIN."""
    coordinator = _make_coordinator()
    btn = VolkswagenRequestUpdateButton(coordinator, "WVWTEST0000000001")
    await btn.async_press()
    coordinator.async_request_report_manual.assert_awaited_once_with("WVWTEST0000000001")


@pytest.mark.asyncio
async def test_button_press_logs_warning_on_failure():
    """async_press doit logger un warning si la demande échoue."""
    coordinator = _make_coordinator()
    coordinator.async_request_report_manual = AsyncMock(return_value=False)
    btn = VolkswagenRequestUpdateButton(coordinator, "WVWTEST0000000001")

    # Ne doit pas lever d'exception
    await btn.async_press()
    coordinator.async_request_report_manual.assert_awaited_once()


# ── Tests Camera ─────────────────────────────────────────────────────────────

def test_camera_unique_id():
    coordinator = _make_coordinator()
    cam = VolkswagenCamera(coordinator, "WVWTEST0000000001")
    assert cam._attr_unique_id == "WVWTEST0000000001-camera-vehicle_images"


def test_camera_content_type():
    coordinator = _make_coordinator()
    cam = VolkswagenCamera(coordinator, "WVWTEST0000000001")
    assert cam._attr_content_type == "image/jpeg"


def test_camera_available():
    coordinator = _make_coordinator()
    cam = VolkswagenCamera(coordinator, "WVWTEST0000000001")
    assert cam.available is True


def test_camera_unavailable_when_no_images():
    coordinator = _make_coordinator()
    coordinator.data["WVWTEST0000000001"]["images"] = []
    cam = VolkswagenCamera(coordinator, "WVWTEST0000000001")
    assert cam.available is False


@pytest.mark.asyncio
async def test_camera_image_returns_bytes():
    """async_camera_image doit retourner des bytes décodés depuis base64."""
    fake_bytes = b"\x89PNG\r\n"
    image_b64 = base64.b64encode(fake_bytes).decode()

    coordinator = _make_coordinator()
    coordinator.data["WVWTEST0000000001"]["images"] = [
        {"image_data": image_b64}
    ]
    cam = VolkswagenCamera(coordinator, "WVWTEST0000000001")
    result = await cam.async_camera_image()
    assert result == fake_bytes


@pytest.mark.asyncio
async def test_camera_image_returns_none_when_no_data():
    coordinator = MagicMock()
    coordinator.last_update_success = True
    coordinator.data = {}
    cam = VolkswagenCamera(coordinator, "UNKNOWNVIN")
    result = await cam.async_camera_image()
    assert result is None


def test_camera_extra_attributes():
    coordinator = _make_coordinator()
    cam = VolkswagenCamera(coordinator, "WVWTEST0000000001")
    attrs = cam.extra_state_attributes
    assert attrs["image_count"] == 1
    assert attrs["vin"] == "WVWTEST0000000001"
    assert "https://example.com/car.jpg" in attrs["image_urls"]


def test_camera_device_info():
    coordinator = _make_coordinator()
    cam = VolkswagenCamera(coordinator, "WVWTEST0000000001")
    info = cam.device_info
    assert ("volkswagen_web", "WVWTEST0000000001") in info["identifiers"]


# ── Tests Image Entity ───────────────────────────────────────────────────────

def test_image_entity_unique_id():
    coordinator = _make_coordinator()
    img = VolkswagenImageEntity(coordinator, "WVWTEST0000000001", image_index=0)
    assert img._attr_unique_id == "WVWTEST0000000001-image-0"


def test_image_entity_name():
    coordinator = _make_coordinator()
    img = VolkswagenImageEntity(coordinator, "WVWTEST0000000001", image_index=0)
    assert img.name == "Image 1"
    
    img2 = VolkswagenImageEntity(coordinator, "WVWTEST0000000001", image_index=2)
    assert img2.name == "Image 3"


def test_image_entity_available():
    coordinator = _make_coordinator()
    img = VolkswagenImageEntity(coordinator, "WVWTEST0000000001", image_index=0)
    assert img.available is True


def test_image_entity_unavailable_when_index_out_of_range():
    coordinator = _make_coordinator()
    img = VolkswagenImageEntity(coordinator, "WVWTEST0000000001", image_index=5)
    assert img.available is False


def test_image_entity_unavailable_when_no_data():
    coordinator = MagicMock()
    coordinator.last_update_success = True
    coordinator.data = {}
    img = VolkswagenImageEntity(coordinator, "UNKNOWNVIN", image_index=0)
    assert img.available is False


@pytest.mark.asyncio
async def test_image_entity_async_image_returns_bytes():
    """async_image doit retourner des bytes décodés depuis base64."""
    fake_bytes = b"\x89PNG\r\n\x1a\n"
    image_b64 = base64.b64encode(fake_bytes).decode()

    coordinator = _make_coordinator()
    coordinator.data["WVWTEST0000000001"]["images"] = [
        {"image_data": image_b64, "url": "https://example.com/img1.jpg"},
        {"image_data": image_b64, "url": "https://example.com/img2.jpg"},
    ]
    
    img = VolkswagenImageEntity(coordinator, "WVWTEST0000000001", image_index=0)
    result = await img.async_image()
    assert result == fake_bytes


@pytest.mark.asyncio
async def test_image_entity_async_image_second_index():
    """async_image doit retourner l'image à l'index correct."""
    fake_bytes1 = b"IMAGE1"
    fake_bytes2 = b"IMAGE2"
    image_b64_1 = base64.b64encode(fake_bytes1).decode()
    image_b64_2 = base64.b64encode(fake_bytes2).decode()

    coordinator = _make_coordinator()
    coordinator.data["WVWTEST0000000001"]["images"] = [
        {"image_data": image_b64_1},
        {"image_data": image_b64_2},
    ]
    
    img = VolkswagenImageEntity(coordinator, "WVWTEST0000000001", image_index=1)
    result = await img.async_image()
    assert result == fake_bytes2


@pytest.mark.asyncio
async def test_image_entity_async_image_returns_none_when_out_of_range():
    coordinator = _make_coordinator()
    img = VolkswagenImageEntity(coordinator, "WVWTEST0000000001", image_index=10)
    result = await img.async_image()
    assert result is None


@pytest.mark.asyncio
async def test_image_entity_async_image_returns_none_when_no_data():
    coordinator = MagicMock()
    coordinator.last_update_success = True
    coordinator.data = {}
    img = VolkswagenImageEntity(coordinator, "UNKNOWNVIN", image_index=0)
    result = await img.async_image()
    assert result is None


def test_image_entity_extra_attributes():
    coordinator = _make_coordinator()
    img = VolkswagenImageEntity(coordinator, "WVWTEST0000000001", image_index=0)
    attrs = img.extra_state_attributes
    assert attrs["vin"] == "WVWTEST0000000001"
    assert attrs["image_index"] == 0
    assert attrs["url"] == "https://example.com/car.jpg"


def test_image_entity_device_info():
    coordinator = _make_coordinator()
    img = VolkswagenImageEntity(coordinator, "WVWTEST0000000001", image_index=0)
    info = img.device_info
    assert ("volkswagen_web", "WVWTEST0000000001") in info["identifiers"]
    assert info["manufacturer"] == "Volkswagen"
