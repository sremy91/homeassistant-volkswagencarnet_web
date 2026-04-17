"""Plateforme time pour piloter les options Volkswagen Web."""

from __future__ import annotations

import logging
import re
from datetime import time
from typing import Any

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import async_get
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

_LOGGER = logging.getLogger(__name__)

from .const import CONF_SCAN_TIME, DATA_COORDINATOR, DOMAIN
from .coordinator import VolkswagenWebCoordinator
from .options_helpers import async_update_editable_option, editable_options_from_entry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Crée l'entité time de planification."""
    coordinator: VolkswagenWebCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities([VolkswagenScanTimeEntity(coordinator, entry)])


class VolkswagenScanTimeEntity(CoordinatorEntity, TimeEntity):
    """Entité time pour l'heure de synchronisation."""

    def __init__(self, coordinator: VolkswagenWebCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_has_entity_name = True
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_translation_key = CONF_SCAN_TIME
        self._attr_unique_id = f"{entry.entry_id}-time-{CONF_SCAN_TIME}"

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
        translation_key = self._attr_translation_key or CONF_SCAN_TIME
        new_entity_id = f"time.{device_slug}_{translation_key}"

        _LOGGER.debug("Migrating time %s → %s", current_entity_id, new_entity_id)

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
            _LOGGER.info("Migrated time %s → %s", current_entity_id, new_entity_id)
        except Exception as err:
            _LOGGER.error(
                "Failed to migrate time %s → %s: %s",
                current_entity_id,
                new_entity_id,
                err,
            )

    @property
    def native_value(self) -> time | None:
        options = editable_options_from_entry(self._entry)
        raw = str(options.get(CONF_SCAN_TIME, "10:00"))
        try:
            hh, mm = raw.split(":", 1)
            return time(hour=int(hh), minute=int(mm))
        except (TypeError, ValueError):
            return None

    async def async_set_value(self, value: time) -> None:
        await async_update_editable_option(
            self.hass,
            self._entry,
            CONF_SCAN_TIME,
            value.strftime("%H:%M"),
        )
