"""Config flow pour Volkswagen Web."""

from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from volkswagencarnet_web import VolkswagenWebConnection

from .const import (
    CONF_AUTO_REQUEST_UPDATE,
    CONF_EMAIL,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_REQUEST_ADVANCE_HOURS,
    CONF_SCAN_DAY_OF_MONTH,
    CONF_SCAN_INTERVAL,
    CONF_SCAN_TIME,
    CONF_SCAN_WEEKDAY,
    CONF_VEHICLES,
    DEFAULT_AUTO_REQUEST_UPDATE,
    DEFAULT_REQUEST_ADVANCE_HOURS,
    DEFAULT_SCAN_DAY_OF_MONTH,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCAN_TIME,
    DEFAULT_SCAN_WEEKDAY,
    DOMAIN,
    SCAN_INTERVAL_BIWEEKLY,
    SCAN_INTERVAL_DAILY,
    SCAN_INTERVAL_MONTHLY,
    SCAN_INTERVAL_WEEKLY,
    WEEKDAYS,
)

_LOGGER = logging.getLogger(__name__)
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def _weekday_options() -> dict[str, str]:
    return {str(i): WEEKDAYS.get(i, f"Day {i}") for i in range(7)}


def _day_of_month_options() -> dict[str, str]:
    return {str(i): f"Jour {i}" for i in range(1, 32)}


def _build_schedule_schema(
    interval: str,
    *,
    is_options: bool = False,
    defaults: dict[str, Any] | None = None,
) -> vol.Schema:
    defaults = defaults or {}
    key_fn = vol.Optional if is_options else vol.Required

    schema_dict: dict[Any, Any] = {
        key_fn(CONF_SCAN_TIME, default=defaults.get(CONF_SCAN_TIME, DEFAULT_SCAN_TIME)): str,
        key_fn(
            CONF_AUTO_REQUEST_UPDATE,
            default=defaults.get(CONF_AUTO_REQUEST_UPDATE, DEFAULT_AUTO_REQUEST_UPDATE),
        ): bool,
        key_fn(
            CONF_REQUEST_ADVANCE_HOURS,
            default=defaults.get(CONF_REQUEST_ADVANCE_HOURS, DEFAULT_REQUEST_ADVANCE_HOURS),
        ): vol.All(vol.Coerce(int), vol.Range(min=1, max=24)),
    }

    if interval in (SCAN_INTERVAL_WEEKLY, SCAN_INTERVAL_BIWEEKLY):
        schema_dict[
            key_fn(
                CONF_SCAN_WEEKDAY,
                default=str(defaults.get(CONF_SCAN_WEEKDAY, DEFAULT_SCAN_WEEKDAY)),
            )
        ] = vol.In(_weekday_options())
    elif interval == SCAN_INTERVAL_MONTHLY:
        schema_dict[
            key_fn(
                CONF_SCAN_DAY_OF_MONTH,
                default=str(defaults.get(CONF_SCAN_DAY_OF_MONTH, DEFAULT_SCAN_DAY_OF_MONTH)),
            )
        ] = vol.In(_day_of_month_options())

    return vol.Schema(schema_dict)


def _validate_schedule_input(interval: str, data: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    errors: dict[str, str] = {}
    normalized = dict(data)

    scan_time = str(data.get(CONF_SCAN_TIME, "")).strip()
    if not _TIME_RE.match(scan_time):
        errors[CONF_SCAN_TIME] = "invalid_time_format"
    else:
        normalized[CONF_SCAN_TIME] = scan_time

    if interval in (SCAN_INTERVAL_WEEKLY, SCAN_INTERVAL_BIWEEKLY):
        try:
            weekday = int(str(data.get(CONF_SCAN_WEEKDAY, DEFAULT_SCAN_WEEKDAY)))
            if weekday < 0 or weekday > 6:
                raise ValueError()
            normalized[CONF_SCAN_WEEKDAY] = weekday
        except (TypeError, ValueError):
            errors[CONF_SCAN_WEEKDAY] = "invalid_weekday"

    if interval == SCAN_INTERVAL_MONTHLY:
        try:
            day = int(str(data.get(CONF_SCAN_DAY_OF_MONTH, DEFAULT_SCAN_DAY_OF_MONTH)))
            if day < 1 or day > 31:
                raise ValueError()
            normalized[CONF_SCAN_DAY_OF_MONTH] = day
        except (TypeError, ValueError):
            errors[CONF_SCAN_DAY_OF_MONTH] = "invalid_day_of_month"

    return normalized, errors


class VolkswagenWebConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow pour Volkswagen Web."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Étape initiale: authentification."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_EMAIL])
            self._abort_if_unique_id_configured()

            try:
                async with VolkswagenWebConnection() as connection:
                    await connection.login(
                        username=user_input[CONF_EMAIL],
                        password=user_input[CONF_PASSWORD],
                    )
                    vehicles = await connection.list_vehicles()

                if not vehicles:
                    errors["base"] = "no_vehicles"
                else:
                    self.vw_vehicles = vehicles
                    self.auth_data = user_input
                    return await self.async_step_scan_settings()

            except Exception as err:
                _LOGGER.exception("Erreur lors de la connexion: %s", err)
                errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMAIL): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional(CONF_NAME, default="Volkswagen Web"): str,
                }
            ),
            errors=errors,
        )

    async def async_step_scan_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Étape 2: Sélectionner l'intervalle de synchronisation."""
        if user_input is not None:
            self.scan_interval = user_input[CONF_SCAN_INTERVAL]
            return await self.async_step_schedule_time()

        return self.async_show_form(
            step_id="scan_settings",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.In(
                        {
                            SCAN_INTERVAL_DAILY: "quotidienne (chaque jour)",
                            SCAN_INTERVAL_WEEKLY: "hebdomadaire (chaque semaine)",
                            SCAN_INTERVAL_BIWEEKLY: "14 jours (bihebdomadaire)",
                            SCAN_INTERVAL_MONTHLY: "mensuelle (chaque mois)",
                        }
                    ),
                }
            ),
        )

    async def async_step_schedule_time(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Étape 3: Configurer l'heure et le jour de synchronisation."""
        errors: dict[str, str] = {}

        interval = getattr(self, "scan_interval", DEFAULT_SCAN_INTERVAL)

        if user_input is not None:
            normalized, errors = _validate_schedule_input(interval, user_input)
            if not errors:
                self.scan_data = {
                    CONF_SCAN_INTERVAL: interval,
                    **normalized,
                }
                return await self.async_step_vehicles()

        schema = _build_schedule_schema(interval)
        return self.async_show_form(
            step_id="schedule_time",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_vehicles(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Étape 4: Sélectionner les véhicules."""
        if user_input is not None:
            selected_vins = user_input.get(CONF_VEHICLES, [])
            if not selected_vins:
                return self.async_abort(reason="no_vehicles_selected")

            config_data = {
                **self.auth_data,
                **self.scan_data,
                CONF_VEHICLES: selected_vins,
            }

            return self.async_create_entry(
                title=self.auth_data.get(CONF_NAME, "Volkswagen Web"),
                data=config_data,
            )

        vehicle_options = {
            v.vin: f"{v.nickname or 'Unknown'} ({v.license_plate or v.vin})"
            for v in self.vw_vehicles
        }

        return self.async_show_form(
            step_id="vehicles",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_VEHICLES): cv.multi_select(vehicle_options),
                }
            ),
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        """Retourne le options flow."""
        return VolkswagenWebOptionsFlow(config_entry)


class VolkswagenWebOptionsFlow(config_entries.OptionsFlow):
    """Options flow pour Volkswagen Web."""

    def __init__(self, config_entry) -> None:
        """Initialize options flow with current config entry."""
        self.config_entry = config_entry
        self.scan_interval = config_entry.options.get(
            CONF_SCAN_INTERVAL,
            config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        self._init_data: dict[str, Any] = {}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Étape initiale: modification de l'intervalle de sync."""
        if user_input is not None:
            self.scan_interval = user_input.get(CONF_SCAN_INTERVAL, self.scan_interval)
            self._init_data = {
                CONF_SCAN_INTERVAL: self.scan_interval,
                CONF_AUTO_REQUEST_UPDATE: user_input.get(CONF_AUTO_REQUEST_UPDATE, DEFAULT_AUTO_REQUEST_UPDATE),
                CONF_REQUEST_ADVANCE_HOURS: user_input.get(CONF_REQUEST_ADVANCE_HOURS, DEFAULT_REQUEST_ADVANCE_HOURS),
            }
            return await self.async_step_schedule_options()

        current = {**self.config_entry.data, **self.config_entry.options}

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): vol.In(
                        {
                            SCAN_INTERVAL_DAILY: "quotidienne",
                            SCAN_INTERVAL_WEEKLY: "hebdomadaire",
                            SCAN_INTERVAL_BIWEEKLY: "14 jours",
                            SCAN_INTERVAL_MONTHLY: "mensuelle",
                        }
                    ),
                    vol.Optional(
                        CONF_AUTO_REQUEST_UPDATE,
                        default=current.get(CONF_AUTO_REQUEST_UPDATE, DEFAULT_AUTO_REQUEST_UPDATE),
                    ): bool,
                    vol.Optional(
                        CONF_REQUEST_ADVANCE_HOURS,
                        default=current.get(CONF_REQUEST_ADVANCE_HOURS, DEFAULT_REQUEST_ADVANCE_HOURS),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=24)),
                }
            ),
        )

    async def async_step_schedule_options(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configurer l'heure et le jour selon l'intervalle."""
        errors: dict[str, str] = {}

        if user_input is not None:
            normalized, errors = _validate_schedule_input(self.scan_interval, user_input)
            if not errors:
                all_options = {
                    **self._init_data,
                    CONF_SCAN_TIME: normalized.get(CONF_SCAN_TIME, DEFAULT_SCAN_TIME),
                }

                if self.scan_interval in (SCAN_INTERVAL_WEEKLY, SCAN_INTERVAL_BIWEEKLY):
                    all_options[CONF_SCAN_WEEKDAY] = normalized.get(CONF_SCAN_WEEKDAY, DEFAULT_SCAN_WEEKDAY)
                    all_options.pop(CONF_SCAN_DAY_OF_MONTH, None)
                elif self.scan_interval == SCAN_INTERVAL_MONTHLY:
                    all_options[CONF_SCAN_DAY_OF_MONTH] = normalized.get(CONF_SCAN_DAY_OF_MONTH, DEFAULT_SCAN_DAY_OF_MONTH)
                    all_options.pop(CONF_SCAN_WEEKDAY, None)
                else:
                    all_options.pop(CONF_SCAN_WEEKDAY, None)
                    all_options.pop(CONF_SCAN_DAY_OF_MONTH, None)

                return self.async_create_entry(title="", data=all_options)

        current = {**self.config_entry.data, **self.config_entry.options}
        schema = _build_schedule_schema(self.scan_interval, is_options=True, defaults=current)

        return self.async_show_form(
            step_id="schedule_options",
            data_schema=schema,
            errors=errors,
        )
