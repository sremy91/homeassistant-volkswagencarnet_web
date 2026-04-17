"""Tests pour le config flow du composant Volkswagen Web."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from custom_components.volkswagen_web.const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_AUTO_REQUEST_UPDATE,
    CONF_REQUEST_ADVANCE_HOURS,
    DOMAIN,
)


@pytest.fixture
def mock_vw_connection():
    """Mock de VolkswagenWebConnection."""
    with patch("custom_components.volkswagen_web.config_flow.VolkswagenWebConnection") as mock:
        connection = AsyncMock()
        mock.return_value = connection

        # Mock vehicles
        vehicles = []
        for i in range(2):
            vehicle = MagicMock()
            vehicle.vin = f"WVWZZZ{i}Z0000000{i}"
            vehicle.nickname = f"Vehicle {i}"
            vehicle.license_plate = f"AA-{i:03d}-AA"
            vehicles.append(vehicle)

        connection.login = AsyncMock()
        connection.list_vehicles = AsyncMock(return_value=vehicles)

        yield mock


@pytest.mark.asyncio
async def test_user_step_success(hass: HomeAssistant, mock_vw_connection):
    """Test l'étape user du config flow."""
    from custom_components.volkswagen_web.config_flow import VolkswagenWebConfigFlow

    flow = VolkswagenWebConfigFlow()
    flow.hass = hass

    user_input = {
        CONF_EMAIL: "test@example.com",
        CONF_PASSWORD: "password123",
        CONF_NAME: "Test VW",
    }

    # Patch async_set_unique_id et _abort_if_unique_id_configured
    with patch.object(flow, "async_set_unique_id"):
        with patch.object(flow, "_abort_if_unique_id_configured"):
            result = await flow.async_step_user(user_input)

    # Doit retourner le formulaire de l'étape suivante (scan_settings)
    assert result["type"] == "form"
    assert result["step_id"] == "scan_settings"


@pytest.mark.asyncio
async def test_user_step_invalid_auth(hass: HomeAssistant):
    """Test l'étape user avec authentification invalide."""
    from custom_components.volkswagen_web.config_flow import VolkswagenWebConfigFlow

    flow = VolkswagenWebConfigFlow()
    flow.hass = hass

    user_input = {
        CONF_EMAIL: "test@example.com",
        CONF_PASSWORD: "wrongpassword",
        CONF_NAME: "Test VW",
    }

    # Mock une erreur de connexion
    with patch(
        "custom_components.volkswagen_web.config_flow.VolkswagenWebConnection"
    ) as mock_conn:
        mock_conn.return_value.login.side_effect = Exception("Invalid credentials")
        with patch.object(flow, "async_set_unique_id"):
            result = await flow.async_step_user(user_input)

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert "invalid_auth" in result["errors"]["base"]


@pytest.mark.asyncio
async def test_scan_settings_step(hass: HomeAssistant):
    """Test l'étape scan_settings du config flow."""
    from custom_components.volkswagen_web.config_flow import VolkswagenWebConfigFlow

    flow = VolkswagenWebConfigFlow()
    flow.hass = hass

    scan_input = {
        CONF_SCAN_INTERVAL: "hourly",
        CONF_AUTO_REQUEST_UPDATE: True,
        CONF_REQUEST_ADVANCE_HOURS: 1,
    }

    # Mock l'étape précédente
    flow.auth_data = {
        CONF_EMAIL: "test@example.com",
        CONF_PASSWORD: "password",
        CONF_NAME: "Test",
    }

    with patch.object(flow, "async_step_vehicles") as mock_next:
        mock_next.return_value = FlowResult(
            type="form",
            step_id="vehicles",
            data_schema=None,
        )
        result = await flow.async_step_scan_settings(scan_input)

    # Doit appeler async_step_vehicles
    mock_next.assert_called_once()


@pytest.mark.asyncio
async def test_vehicles_step(hass: HomeAssistant, mock_vw_connection):
    """Test l'étape vehicles du config flow."""
    from custom_components.volkswagen_web.config_flow import VolkswagenWebConfigFlow

    flow = VolkswagenWebConfigFlow()
    flow.hass = hass

    vehicles = [
        MagicMock(vin="WVWZZZ0Z0000000", nickname="Vehicle 0", license_plate="AA-001-AA"),
        MagicMock(vin="WVWZZZ1Z0000001", nickname="Vehicle 1", license_plate="AA-002-AA"),
    ]

    flow.auth_data = {CONF_EMAIL: "test@example.com", CONF_PASSWORD: "pass", CONF_NAME: "Test"}
    flow.scan_data = {CONF_SCAN_INTERVAL: "hourly"}
    flow.vw_vehicles = vehicles

    vehicles_input = {
        "vehicles": ["WVWZZZ0Z0000000"],  # Sélectionne le premier véhicule
    }

    with patch.object(flow, "async_create_entry") as mock_create:
        mock_create.return_value = FlowResult(
            type="create_entry",
            version=1,
            flow_id="test",
            handler=DOMAIN,
            title="Test VW",
            data={},
        )
        result = await flow.async_step_vehicles(vehicles_input)

    # Vérifie que create_entry a été appelé
    mock_create.assert_called_once()
    call_args = mock_create.call_args
    assert "Test VW" in call_args[1]["title"]
    assert "WVWZZZ0Z0000000" in call_args[1]["data"]["vehicles"]


@pytest.mark.asyncio
async def test_vehicles_step_no_selection(hass: HomeAssistant):
    """Test l'étape vehicles avec aucun véhicule sélectionné."""
    from custom_components.volkswagen_web.config_flow import VolkswagenWebConfigFlow

    flow = VolkswagenWebConfigFlow()
    flow.hass = hass

    vehicles_input = {
        "vehicles": [],  # Aucune sélection
    }

    result = await flow.async_step_vehicles(vehicles_input)

    # Doit aborter
    assert result["type"] == "abort"
    assert result["reason"] == "no_vehicles_selected"
