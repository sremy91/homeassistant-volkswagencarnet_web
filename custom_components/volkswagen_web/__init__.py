"""Composant Home Assistant pour Volkswagen Web."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.components.http import HomeAssistantView
from aiohttp import web

from volkswagencarnet_web import VolkswagenWebConnection

import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_AUTO_REQUEST_UPDATE,
    CONF_CAMERA_ROTATION_SECONDS,
    CONF_EMAIL,
    CONF_FETCH_HISTORY_ON_SETUP,
    CONF_MANUAL_REQUEST_REFRESH_DELAY_MINUTES,
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

# Configuration : supports config entries uniquement (pas de YAML)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


SERVICE_SCHEMA = vol.Schema({vol.Required("device_id"): cv.string})


class MJPEGStreamHandler(HomeAssistantView):
    """Gestionnaire pour les requêtes de stream MJPEG."""

    url = "/api/volkswagen_web/mjpeg/{vin}"
    name = "api:volkswagen_web:mjpeg"
    requires_auth = False  # Pas d'auth requise pour le stream vidéo

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialise le gestionnaire."""
        self.hass = hass

    async def get(self, request: web.Request, vin: str) -> web.StreamResponse:
        """Gère les requêtes GET pour le stream MJPEG."""
        vin = vin or request.match_info.get("vin", "")
        
        # Récupère la caméra depuis le dictionnaire de caméras
        cameras_by_vin = self.hass.data.get(DOMAIN, {}).get("cameras_by_vin", {})
        camera = cameras_by_vin.get(vin)

        if not camera:
            _LOGGER.warning("Camera MJPEG stream requested but not found for VIN: %s", vin)
            return web.json_response(
                {"error": "Camera not found"},
                status=404,
            )

        # Prépare la réponse de streaming
        response = web.StreamResponse()
        response.content_type = "multipart/x-mixed-replace; boundary=--frame"
        await response.prepare(request)

        try:
            async for chunk in camera.async_mjpeg_stream(request):
                await response.write(chunk)
                # Laisse respirer l'event loop
                await asyncio.sleep(0)
        except asyncio.CancelledError:
            _LOGGER.debug("MJPEG stream cancelled for VIN: %s", vin)
        except Exception as err:
            _LOGGER.error("MJPEG stream error for VIN %s: %s", vin, err)

        return response


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Setup du domaine — enregistre les services et les vues HTTP."""
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

    # Enregistre la vue HTTP pour le streaming MJPEG
    hass.http.register_view(MJPEGStreamHandler(hass))

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Setup d'une entry de configuration."""
    hass.data.setdefault(DOMAIN, {})
    connection: VolkswagenWebConnection | None = None

    try:
        # Crée la connexion et initialise la session HTTP persistante.
        connection = VolkswagenWebConnection()
        await connection.__aenter__()

        # Authentifie la session avec les credentials de l'entry.
        merged_config = {**entry.data, **entry.options}

        await connection.login(
            username=entry.data[CONF_EMAIL],
            password=entry.data[CONF_PASSWORD],
        )

        # Récupère les véhicules sélectionnés
        selected_vins = entry.data.get(CONF_VEHICLES, [])

        if not selected_vins:
            _LOGGER.error("Aucun véhicule sélectionné")
            await connection.__aexit__(None, None, None)
            return False

        # Crée le coordinateur (transmet tous les paramètres de planification)
        coordinator = VolkswagenWebCoordinator(
            hass=hass,
            connection=connection,
            vins=selected_vins,
            config={
                CONF_EMAIL: entry.data.get(CONF_EMAIL),
                CONF_PASSWORD: entry.data.get(CONF_PASSWORD),
                CONF_SCAN_INTERVAL: merged_config.get(CONF_SCAN_INTERVAL),
                CONF_SCAN_TIME: merged_config.get(CONF_SCAN_TIME),
                CONF_SCAN_WEEKDAY: merged_config.get(CONF_SCAN_WEEKDAY),
                CONF_SCAN_DAY_OF_MONTH: merged_config.get(CONF_SCAN_DAY_OF_MONTH),
                CONF_FETCH_HISTORY_ON_SETUP: merged_config.get(CONF_FETCH_HISTORY_ON_SETUP),
                CONF_AUTO_REQUEST_UPDATE: merged_config.get(CONF_AUTO_REQUEST_UPDATE),
                CONF_REQUEST_ADVANCE_HOURS: merged_config.get(CONF_REQUEST_ADVANCE_HOURS),
                CONF_MANUAL_REQUEST_REFRESH_DELAY_MINUTES: merged_config.get(
                    CONF_MANUAL_REQUEST_REFRESH_DELAY_MINUTES
                ),
                CONF_CAMERA_ROTATION_SECONDS: merged_config.get(CONF_CAMERA_ROTATION_SECONDS),
            },
        )

        # Effectue la première récupération de données
        await coordinator.async_config_entry_first_refresh()

        # Optionnel: récupère l'historique au setup de l'intégration.
        if coordinator.fetch_history_on_setup:
            await coordinator.async_fetch_history_for_all()

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
        if connection and connection._session is not None:
            await connection.__aexit__(None, None, None)
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
        entry_data = hass.data[DOMAIN].pop(entry.entry_id)
        coordinator = entry_data.get(DATA_COORDINATOR)
        if coordinator:
            coordinator.cancel_scheduled_manual_refreshes()
        connection = entry_data.get(DATA_VW_CONN)
        if connection:
            await connection.__aexit__(None, None, None)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Recharge une entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
