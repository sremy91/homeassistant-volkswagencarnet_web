"""Helpers pour modifier les options de planning depuis des entites dashboard."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_AUTO_REQUEST_UPDATE,
    CONF_FETCH_HISTORY_ON_SETUP,
    CONF_MANUAL_REQUEST_REFRESH_DELAY_MINUTES,
    CONF_REQUEST_ADVANCE_HOURS,
    CONF_SCAN_DAY_OF_MONTH,
    CONF_SCAN_INTERVAL,
    CONF_SCAN_TIME,
    CONF_SCAN_WEEKDAY,
    DEFAULT_AUTO_REQUEST_UPDATE,
    DEFAULT_FETCH_HISTORY_ON_SETUP,
    DEFAULT_MANUAL_REQUEST_REFRESH_DELAY_MINUTES,
    DEFAULT_REQUEST_ADVANCE_HOURS,
    DEFAULT_SCAN_DAY_OF_MONTH,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCAN_TIME,
    DEFAULT_SCAN_WEEKDAY,
)


def editable_options_from_entry(entry: ConfigEntry) -> dict[str, Any]:
    """Retourne toutes les options éditables (hors login/vehicules)."""
    merged = {**entry.data, **entry.options}
    return {
        CONF_SCAN_INTERVAL: merged.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        CONF_SCAN_TIME: merged.get(CONF_SCAN_TIME, DEFAULT_SCAN_TIME),
        CONF_SCAN_WEEKDAY: int(merged.get(CONF_SCAN_WEEKDAY, DEFAULT_SCAN_WEEKDAY)),
        CONF_SCAN_DAY_OF_MONTH: int(merged.get(CONF_SCAN_DAY_OF_MONTH, DEFAULT_SCAN_DAY_OF_MONTH)),
        CONF_FETCH_HISTORY_ON_SETUP: bool(
            merged.get(CONF_FETCH_HISTORY_ON_SETUP, DEFAULT_FETCH_HISTORY_ON_SETUP)
        ),
        CONF_AUTO_REQUEST_UPDATE: bool(
            merged.get(CONF_AUTO_REQUEST_UPDATE, DEFAULT_AUTO_REQUEST_UPDATE)
        ),
        CONF_REQUEST_ADVANCE_HOURS: int(
            merged.get(CONF_REQUEST_ADVANCE_HOURS, DEFAULT_REQUEST_ADVANCE_HOURS)
        ),
        CONF_MANUAL_REQUEST_REFRESH_DELAY_MINUTES: int(
            merged.get(
                CONF_MANUAL_REQUEST_REFRESH_DELAY_MINUTES,
                DEFAULT_MANUAL_REQUEST_REFRESH_DELAY_MINUTES,
            )
        ),
    }


async def async_update_editable_option(
    hass: HomeAssistant,
    entry: ConfigEntry,
    key: str,
    value: Any,
) -> None:
    """Met a jour une option editable; le listener recharge l'integration."""
    options = editable_options_from_entry(entry)
    options[key] = value
    hass.config_entries.async_update_entry(entry, options=options)
