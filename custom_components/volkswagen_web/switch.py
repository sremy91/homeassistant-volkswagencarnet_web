"""Plateforme switch pour piloter les options Volkswagen Web."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_AUTO_REQUEST_UPDATE,
    CONF_FETCH_HISTORY_ON_SETUP,
    DATA_COORDINATOR,
    DOMAIN,
)
from .coordinator import VolkswagenWebCoordinator
from .options_helpers import async_update_editable_option, editable_options_from_entry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Crée les switches de pilotage de planification."""
    coordinator: VolkswagenWebCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities(
        [
            VolkswagenAutoRequestSwitch(coordinator, entry),
            VolkswagenFetchHistoryOnSetupSwitch(coordinator, entry),
        ]
    )


class VolkswagenBaseOptionSwitch(CoordinatorEntity, SwitchEntity):
    """Base commune pour switch d'options."""

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
        self._attr_unique_id = f"{entry.entry_id}-switch-{unique_suffix}"

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, f"{self._entry.entry_id}-scheduler")},
            "name": "Volkswagen Scheduler",
            "manufacturer": "Volkswagen",
            "model": "Integration settings",
        }


class VolkswagenAutoRequestSwitch(VolkswagenBaseOptionSwitch):
    """Active/desactive la demande auto de rapport."""

    def __init__(self, coordinator: VolkswagenWebCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, CONF_AUTO_REQUEST_UPDATE)
        self._attr_translation_key = CONF_AUTO_REQUEST_UPDATE

    @property
    def is_on(self) -> bool:
        options = editable_options_from_entry(self._entry)
        return bool(options.get(CONF_AUTO_REQUEST_UPDATE, True))

    async def async_turn_on(self, **kwargs: Any) -> None:
        await async_update_editable_option(self.hass, self._entry, CONF_AUTO_REQUEST_UPDATE, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await async_update_editable_option(self.hass, self._entry, CONF_AUTO_REQUEST_UPDATE, False)


class VolkswagenFetchHistoryOnSetupSwitch(VolkswagenBaseOptionSwitch):
    """Active/desactive la recuperation historique au demarrage."""

    def __init__(self, coordinator: VolkswagenWebCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, CONF_FETCH_HISTORY_ON_SETUP)
        self._attr_translation_key = CONF_FETCH_HISTORY_ON_SETUP

    @property
    def is_on(self) -> bool:
        options = editable_options_from_entry(self._entry)
        return bool(options.get(CONF_FETCH_HISTORY_ON_SETUP, True))

    async def async_turn_on(self, **kwargs: Any) -> None:
        await async_update_editable_option(self.hass, self._entry, CONF_FETCH_HISTORY_ON_SETUP, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await async_update_editable_option(self.hass, self._entry, CONF_FETCH_HISTORY_ON_SETUP, False)
