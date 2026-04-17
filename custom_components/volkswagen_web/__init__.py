"""Composant Home Assistant pour Volkswagen Web."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed

from volkswagencarnet_web import VolkswagenWebConnection

import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_AUTO_REQUEST_UPDATE,
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_REQUEST_ADVANCE_HOURS,
    CONF_SCAN_DAY_OF_MONTH,
    CONF_SCAN_INTERVAL,
    CONF_SCAN_TIME,
    CONF_SCAN_WEEKDAY,
    CONF_VEHICLES,
    DATA_COORDINATOR,
    DATA_VW_CONN,
    DOMAIN,
    PLATFORMS,
    SERVICE_REQUEST_REPORT,
)
from .coordinator import VolkswagenWebCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "button", "camera"]


SERVICE_SCHEMA = vol.Schema({vol.Required("device_id"): cv.string})


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Setup du domaine — enregistre les services."""
    hass.data.setdefault(DOMAIN, {})

    async def handle_request_report(call) -> None:
        """Service: demande un rapport véhicule manuel."""
        device_id = call.data["device_id"]
        # Parcourt tous les coordinateurs enregistrés
        for entry_data in hass.data.get(DOMAIN, {}).values():
            coordinator = entry_data.get(DATA_COORDINATOR)
            if not coordinator:
                continue
            for vin in coordinator.vins:
                if vin == device_id or device_id in vin:
                    await coordinator.async_request_report_manual(vin)
                    return
        _LOGGER.warning("Service request_report: VIN/device '%s' non trouvé", device_id)

    hass.services.async_register(
        DOMAIN,
        SERVICE_REQUEST_REPORT,
        handle_request_report,
        schema=SERVICE_SCHEMA,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Setup d'une entry de configuration."""
    hass.data.setdefault(DOMAIN, {})

    try:
        # Crée la connexion
        connection = VolkswagenWebConnection(
            email=entry.data[CONF_EMAIL],
            password=entry.data[CONF_PASSWORD],
        )

        # Test la connexion
        await connection.login()

        # Récupère les véhicules sélectionnés
        all_vehicles = await connection.list_vehicles()
        selected_vins = entry.data.get(CONF_VEHICLES, [])

        if not selected_vins:
            _LOGGER.error("Aucun véhicule sélectionné")
            return False

        # Crée le coordinateur (transmet tous les paramètres de planification)
        coordinator = VolkswagenWebCoordinator(
            hass=hass,
            connection=connection,
            vins=selected_vins,
            config={
                CONF_SCAN_INTERVAL: entry.data.get(CONF_SCAN_INTERVAL),
                CONF_SCAN_TIME: entry.data.get(CONF_SCAN_TIME),
                CONF_SCAN_WEEKDAY: entry.data.get(CONF_SCAN_WEEKDAY),
                CONF_SCAN_DAY_OF_MONTH: entry.data.get(CONF_SCAN_DAY_OF_MONTH),
                CONF_AUTO_REQUEST_UPDATE: entry.data.get(CONF_AUTO_REQUEST_UPDATE),
                CONF_REQUEST_ADVANCE_HOURS: entry.data.get(CONF_REQUEST_ADVANCE_HOURS),
            },
        )

        # Effectue la première récupération de données
        await coordinator.async_config_entry_first_refresh()

        # Stocke les données
        hass.data[DOMAIN][entry.entry_id] = {
            DATA_VW_CONN: connection,
            DATA_COORDINATOR: coordinator,
        }

        # Setup les plateformes
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

        # Ajoute un listener pour les mises à jour d'options
        entry.async_on_unload(entry.add_update_listener(async_update_options))

        return True

    except Exception as err:
        _LOGGER.exception("Erreur lors du setup de l'entry: %s", err)
        if "auth" in str(err).lower():
            raise ConfigEntryAuthFailed from err
        return False


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Met à jour les options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Décharge une entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Recharge une entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
