"""Plateforme button pour Volkswagen Web."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import VolkswagenWebCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Crée les entités button."""
    coordinator: VolkswagenWebCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    entities = []
    for vin in coordinator.vins:
        entities.append(VolkswagenRequestUpdateButton(coordinator=coordinator, vin=vin))
        entities.append(VolkswagenRequestHistoryButton(coordinator=coordinator, vin=vin))
    async_add_entities(entities)


class VolkswagenRequestUpdateButton(CoordinatorEntity, ButtonEntity):
    """Bouton pour déclencher une demande de rapport véhicule."""

    def __init__(
        self,
        coordinator: VolkswagenWebCoordinator,
        vin: str,
    ) -> None:
        super().__init__(coordinator)
        self._vin = vin
        self._attr_unique_id = f"{vin}-button-request_update"
        self._attr_translation_key = "request_update"
        self._attr_icon = "mdi:refresh"

    @property
    def device_info(self) -> dict[str, Any]:
        """Associe le bouton au même device que les sensors."""
        vehicle_data = (self.coordinator.data or {}).get(self._vin) or {}
        vehicle = vehicle_data.get("vehicle")
        nickname = getattr(vehicle, "nickname", None) or self._vin

        return {
            "identifiers": {(DOMAIN, self._vin)},
            "name": nickname,
            "manufacturer": "Volkswagen",
        }

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and (self.coordinator.data or {}).get(self._vin) is not None
        )

    async def async_press(self) -> None:
        """Déclenche une demande de rapport véhicule."""
        _LOGGER.info("Demande manuelle de rapport pour VIN %s", self._vin)
        success = await self.coordinator.async_request_report_manual(self._vin)
        if not success:
            _LOGGER.warning("Échec de la demande de rapport pour VIN %s", self._vin)


class VolkswagenRequestHistoryButton(CoordinatorEntity, ButtonEntity):
    """Bouton pour déclencher une récupération de l'historique véhicule."""

    def __init__(
        self,
        coordinator: VolkswagenWebCoordinator,
        vin: str,
    ) -> None:
        super().__init__(coordinator)
        self._vin = vin
        self._attr_unique_id = f"{vin}-button-request_history"
        self._attr_translation_key = "request_history"
        self._attr_icon = "mdi:history"

    @property
    def device_info(self) -> dict[str, Any]:
        """Associe le bouton au même device que les sensors."""
        vehicle_data = (self.coordinator.data or {}).get(self._vin) or {}
        vehicle = vehicle_data.get("vehicle")
        nickname = getattr(vehicle, "nickname", None) or self._vin

        return {
            "identifiers": {(DOMAIN, self._vin)},
            "name": nickname,
            "manufacturer": "Volkswagen",
        }

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and (self.coordinator.data or {}).get(self._vin) is not None
        )

    async def async_press(self) -> None:
        """Déclenche une récupération manuelle de l'historique véhicule."""
        _LOGGER.info("Demande manuelle d'historique pour VIN %s", self._vin)
        success = await self.coordinator.async_request_history_manual(self._vin)
        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.warning("Échec de la récupération d'historique pour VIN %s", self._vin)
