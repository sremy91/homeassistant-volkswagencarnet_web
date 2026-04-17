"""Plateforme select pour piloter les options Volkswagen Web."""

from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_SCAN_INTERVAL,
    CONF_SCAN_WEEKDAY,
    DATA_COORDINATOR,
    DOMAIN,
    SCAN_INTERVAL_BIWEEKLY,
    SCAN_INTERVAL_DAILY,
    SCAN_INTERVAL_MONTHLY,
    SCAN_INTERVAL_WEEKLY,
)
from .coordinator import VolkswagenWebCoordinator
from .options_helpers import async_update_editable_option, editable_options_from_entry

_INTERVAL_OPTIONS = [
    SCAN_INTERVAL_DAILY,
    SCAN_INTERVAL_WEEKLY,
    SCAN_INTERVAL_BIWEEKLY,
    SCAN_INTERVAL_MONTHLY,
]

_WEEKDAY_TO_LABEL = {
    0: "monday",
    1: "tuesday",
    2: "wednesday",
    3: "thursday",
    4: "friday",
    5: "saturday",
    6: "sunday",
}
_LABEL_TO_WEEKDAY = {v: k for k, v in _WEEKDAY_TO_LABEL.items()}
_WEEKDAY_OPTIONS = list(_LABEL_TO_WEEKDAY.keys())


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Crée les selects de pilotage de planification."""
    coordinator: VolkswagenWebCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities(
        [
            VolkswagenScanIntervalSelect(coordinator, entry),
            VolkswagenScanWeekdaySelect(coordinator, entry),
        ]
    )


class VolkswagenBaseOptionSelect(CoordinatorEntity, SelectEntity):
    """Base commune pour select d'options."""

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
        self._attr_unique_id = f"{entry.entry_id}-select-{unique_suffix}"

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, f"{self._entry.entry_id}-scheduler")},
            "name": "Volkswagen Scheduler",
            "manufacturer": "Volkswagen",
            "model": "Integration settings",
        }


class VolkswagenScanIntervalSelect(VolkswagenBaseOptionSelect):
    """Select de l'intervalle de synchronisation."""

    def __init__(self, coordinator: VolkswagenWebCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, CONF_SCAN_INTERVAL)
        self._attr_translation_key = CONF_SCAN_INTERVAL
        self._attr_options = _INTERVAL_OPTIONS

    @property
    def current_option(self) -> str:
        options = editable_options_from_entry(self._entry)
        return str(options.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL_DAILY))

    async def async_select_option(self, option: str) -> None:
        await async_update_editable_option(
            self.hass,
            self._entry,
            CONF_SCAN_INTERVAL,
            option,
        )


class VolkswagenScanWeekdaySelect(VolkswagenBaseOptionSelect):
    """Select du jour de semaine pour weekly/biweekly."""

    def __init__(self, coordinator: VolkswagenWebCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, CONF_SCAN_WEEKDAY)
        self._attr_translation_key = CONF_SCAN_WEEKDAY
        self._attr_options = _WEEKDAY_OPTIONS

    @property
    def available(self) -> bool:
        base = super().available
        return base and self.coordinator.scan_interval_key in {
            SCAN_INTERVAL_WEEKLY,
            SCAN_INTERVAL_BIWEEKLY,
        }

    @property
    def current_option(self) -> str:
        options = editable_options_from_entry(self._entry)
        weekday = int(options.get(CONF_SCAN_WEEKDAY, 0))
        return _WEEKDAY_TO_LABEL.get(weekday, "monday")

    async def async_select_option(self, option: str) -> None:
        await async_update_editable_option(
            self.hass,
            self._entry,
            CONF_SCAN_WEEKDAY,
            _LABEL_TO_WEEKDAY.get(option, 0),
        )
