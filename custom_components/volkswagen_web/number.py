"""Plateforme number pour piloter les options Volkswagen Web."""

from __future__ import annotations

import logging
import re
from typing import Any

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import async_get
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

_LOGGER = logging.getLogger(__name__)

from .const import (
    CONF_MANUAL_REQUEST_REFRESH_DELAY_MINUTES,
    CONF_REQUEST_ADVANCE_HOURS,
    CONF_SCAN_DAY_OF_MONTH,
    DATA_COORDINATOR,
    DOMAIN,
    SCAN_INTERVAL_MONTHLY,
)
from .coordinator import VolkswagenWebCoordinator
from .options_helpers import async_update_editable_option, editable_options_from_entry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Crée les numbers de pilotage de planification."""
    coordinator: VolkswagenWebCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities(
        [
            VolkswagenRequestAdvanceHoursNumber(coordinator, entry),
            VolkswagenManualRequestRefreshDelayNumber(coordinator, entry),
            VolkswagenScanDayOfMonthNumber(coordinator, entry),
        ]
    )


class VolkswagenBaseOptionNumber(CoordinatorEntity, NumberEntity):
    """Base commune pour number d'options."""

    def __init__(
        self,
        coordinator: VolkswagenWebCoordinator,
        entry: ConfigEntry,
        unique_suffix: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_has_entity_name = True
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_mode = "box"
        self._attr_unique_id = f"{entry.entry_id}-number-{unique_suffix}"

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, f"{self._entry.entry_id}-scheduler")},
            "name": "Volkswagen Scheduler",
            "manufacturer": "Volkswagen",
            "model": "Integration settings",
        }

    async def async_added_to_hass(self) -> None:
        """Migre l'entity_id s'il a un suffixe numérique."""
        await super().async_added_to_hass()

        # Récupère le registre d'entités
        entity_registry = async_get(self.hass)
        current_entity_id = self.entity_id

        if not current_entity_id or not re.search(r"_\d+$", current_entity_id):
            return

        # Génère le nouvel entity_id descriptif
        device_slug = slugify(self.device_info.get("name", "volkswagen_scheduler"))
        translation_key = self._attr_translation_key or "unknown"
        new_entity_id = f"number.{device_slug}_{translation_key}"

        _LOGGER.debug("Migrating number %s → %s", current_entity_id, new_entity_id)

        # Vérifie que le nouvel ID n'existe pas déjà
        existing = entity_registry.async_get(new_entity_id)
        if existing and existing.unique_id != self.unique_id:
            _LOGGER.warning(
                "Cannot migrate %s to %s: target exists with different unique_id",
                current_entity_id,
                new_entity_id,
            )
            return

        # Effectue la migration
        try:
            entity_registry.async_update_entity(
                current_entity_id,
                new_entity_id=new_entity_id,
            )
            _LOGGER.info("Migrated number %s → %s", current_entity_id, new_entity_id)
        except Exception as err:
            _LOGGER.error(
                "Failed to migrate number %s → %s: %s",
                current_entity_id,
                new_entity_id,
                err,
            )


class VolkswagenRequestAdvanceHoursNumber(VolkswagenBaseOptionNumber):
    """Nombre d'heures d'avance pour la demande auto."""

    def __init__(self, coordinator: VolkswagenWebCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, CONF_REQUEST_ADVANCE_HOURS)
        self._attr_translation_key = CONF_REQUEST_ADVANCE_HOURS
        self._attr_native_min_value = 1
        self._attr_native_max_value = 24
        self._attr_native_step = 1

    @property
    def native_value(self) -> float:
        options = editable_options_from_entry(self._entry)
        return float(options.get(CONF_REQUEST_ADVANCE_HOURS, 1))

    async def async_set_native_value(self, value: float) -> None:
        await async_update_editable_option(
            self.hass,
            self._entry,
            CONF_REQUEST_ADVANCE_HOURS,
            int(value),
        )


class VolkswagenScanDayOfMonthNumber(VolkswagenBaseOptionNumber):
    """Jour du mois pour planification mensuelle."""

    def __init__(self, coordinator: VolkswagenWebCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, CONF_SCAN_DAY_OF_MONTH)
        self._attr_translation_key = CONF_SCAN_DAY_OF_MONTH
        self._attr_native_min_value = 1
        self._attr_native_max_value = 31
        self._attr_native_step = 1

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.scan_interval_key == SCAN_INTERVAL_MONTHLY

    @property
    def native_value(self) -> float:
        options = editable_options_from_entry(self._entry)
        return float(options.get(CONF_SCAN_DAY_OF_MONTH, 1))

    async def async_set_native_value(self, value: float) -> None:
        await async_update_editable_option(
            self.hass,
            self._entry,
            CONF_SCAN_DAY_OF_MONTH,
            int(value),
        )


class VolkswagenManualRequestRefreshDelayNumber(VolkswagenBaseOptionNumber):
    """Délai en minutes avant refresh après request_update manuel."""

    def __init__(self, coordinator: VolkswagenWebCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, CONF_MANUAL_REQUEST_REFRESH_DELAY_MINUTES)
        self._attr_translation_key = CONF_MANUAL_REQUEST_REFRESH_DELAY_MINUTES
        self._attr_native_min_value = 1
        self._attr_native_max_value = 720
        self._attr_native_step = 1

    @property
    def native_value(self) -> float:
        options = editable_options_from_entry(self._entry)
        return float(options.get(CONF_MANUAL_REQUEST_REFRESH_DELAY_MINUTES, 60))

    async def async_set_native_value(self, value: float) -> None:
        await async_update_editable_option(
            self.hass,
            self._entry,
            CONF_MANUAL_REQUEST_REFRESH_DELAY_MINUTES,
            int(value),
        )
