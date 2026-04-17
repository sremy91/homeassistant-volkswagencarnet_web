"""Config flow pour Volkswagen Web."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import AbortFlow, FlowResult
from homeassistant.exceptions import HomeAssistantError

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


class VolkswagenWebConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow pour Volkswagen Web."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Étape initiale: authentification."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Vérifie si le compte est déjà configuré
            await self.async_set_unique_id(user_input[CONF_EMAIL])
            self._abort_if_unique_id_configured()

            try:
                # Test la connexion
                connection = VolkswagenWebConnection(
                    user_input[CONF_EMAIL],
                    user_input[CONF_PASSWORD],
                )
                await connection.login()

                # Récupère la liste des véhicules
                vehicles = await connection.list_vehicles()

                if not vehicles:
                    errors["base"] = "no_vehicles"
                else:
                    # Passe les données à l'étape suivante
                    self.vw_connection = connection
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
            description_placeholders={"error_text": errors.get("base", "")},
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
                    vol.Required(
                        CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                    ): vol.In(
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
        if user_input is not None:
            self.scan_data = {
                CONF_SCAN_INTERVAL: self.scan_interval,
                **user_input,
                CONF_AUTO_REQUEST_UPDATE: True,  # Default for now
                CONF_REQUEST_ADVANCE_HOURS: DEFAULT_REQUEST_ADVANCE_HOURS,  # Default
            }
            return await self.async_step_vehicles()

        # Construit le formulaire selon l'intervalle choisi
        schema_dict = {
            vol.Required(CONF_SCAN_TIME, default=DEFAULT_SCAN_TIME): str,
        }

        # Ajoute les champs spécifiques selon l'intervalle
        if self.scan_interval == SCAN_INTERVAL_WEEKLY:
            weekday_options = {str(i): WEEKDAYS.get(i, f"Day {i}") for i in range(7)}
            schema_dict[vol.Required(CONF_SCAN_WEEKDAY, default=str(DEFAULT_SCAN_WEEKDAY))] = vol.In(weekday_options)

        elif self.scan_interval == SCAN_INTERVAL_BIWEEKLY:
            weekday_options = {str(i): WEEKDAYS.get(i, f"Day {i}") for i in range(7)}
            schema_dict[vol.Required(CONF_SCAN_WEEKDAY, default=str(DEFAULT_SCAN_WEEKDAY))] = vol.In(weekday_options)

        elif self.scan_interval == SCAN_INTERVAL_MONTHLY:
            day_options = {str(i): f"Jour {i}" for i in range(1, 32)}
            schema_dict[vol.Required(CONF_SCAN_DAY_OF_MONTH, default=str(DEFAULT_SCAN_DAY_OF_MONTH))] = vol.In(day_options)

        description_key = self.scan_interval
        description_placeholder = {}

        return self.async_show_form(
            step_id="schedule_time",
            data_schema=vol.Schema(schema_dict),
            description_placeholders=description_placeholder,
        )

    async def async_step_vehicles(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Étape 4: Sélectionner les véhicules."""
        if user_input is not None:
            selected_vins = user_input.get(CONF_VEHICLES, [])

            if not selected_vins:
                return self.async_abort(reason="no_vehicles_selected")

            # Combine tous les paramètres
            config_data = {
                **self.auth_data,
                **self.scan_data,
                CONF_VEHICLES: selected_vins,
            }

            return self.async_create_entry(
                title=self.auth_data.get(CONF_NAME, "Volkswagen Web"),
                data=config_data,
            )

        # Crée la liste des véhicules disponibles
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

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Étape initiale: modification de l'intervalle de sync."""
        if user_input is not None:
            self.scan_interval = user_input.get(CONF_SCAN_INTERVAL)
            if self.scan_interval:
                return await self.async_step_schedule_options()
            else:
                # Si pas d'intervalle, crée l'entry avec juste les options d'auto_request
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_AUTO_REQUEST_UPDATE: user_input.get(CONF_AUTO_REQUEST_UPDATE),
                        CONF_REQUEST_ADVANCE_HOURS: user_input.get(CONF_REQUEST_ADVANCE_HOURS),
                    },
                )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.data.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
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
                        default=self.config_entry.data.get(
                            CONF_AUTO_REQUEST_UPDATE, DEFAULT_AUTO_REQUEST_UPDATE
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_REQUEST_ADVANCE_HOURS,
                        default=self.config_entry.data.get(
                            CONF_REQUEST_ADVANCE_HOURS, DEFAULT_REQUEST_ADVANCE_HOURS
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=24)),
                }
            ),
        )

    async def async_step_schedule_options(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configurer l'heure et le jour selon l'intervalle."""
        if user_input is not None:
            # Récupère les valeurs de l'étape précédente aussi
            all_options = {
                CONF_SCAN_INTERVAL: self.scan_interval,
                CONF_AUTO_REQUEST_UPDATE: user_input.get(CONF_AUTO_REQUEST_UPDATE, DEFAULT_AUTO_REQUEST_UPDATE),
                CONF_REQUEST_ADVANCE_HOURS: user_input.get(CONF_REQUEST_ADVANCE_HOURS, DEFAULT_REQUEST_ADVANCE_HOURS),
                CONF_SCAN_TIME: user_input.get(CONF_SCAN_TIME, DEFAULT_SCAN_TIME),
            }

            if self.scan_interval in (SCAN_INTERVAL_WEEKLY, SCAN_INTERVAL_BIWEEKLY):
                all_options[CONF_SCAN_WEEKDAY] = user_input.get(CONF_SCAN_WEEKDAY, str(DEFAULT_SCAN_WEEKDAY))
            elif self.scan_interval == SCAN_INTERVAL_MONTHLY:
                all_options[CONF_SCAN_DAY_OF_MONTH] = user_input.get(CONF_SCAN_DAY_OF_MONTH, str(DEFAULT_SCAN_DAY_OF_MONTH))

            return self.async_create_entry(title="", data=all_options)

        schema_dict = {
            vol.Optional(CONF_SCAN_TIME, default=self.config_entry.data.get(CONF_SCAN_TIME, DEFAULT_SCAN_TIME)): str,
            vol.Optional(
                CONF_AUTO_REQUEST_UPDATE,
                default=self.config_entry.data.get(CONF_AUTO_REQUEST_UPDATE, DEFAULT_AUTO_REQUEST_UPDATE),
            ): bool,
            vol.Optional(
                CONF_REQUEST_ADVANCE_HOURS,
                default=self.config_entry.data.get(CONF_REQUEST_ADVANCE_HOURS, DEFAULT_REQUEST_ADVANCE_HOURS),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=24)),
        }

        if self.scan_interval == SCAN_INTERVAL_WEEKLY:
            weekday_options = {str(i): WEEKDAYS.get(i, f"Day {i}") for i in range(7)}
            schema_dict[vol.Optional(
                CONF_SCAN_WEEKDAY,
                default=self.config_entry.data.get(CONF_SCAN_WEEKDAY, str(DEFAULT_SCAN_WEEKDAY))
            )] = vol.In(weekday_options)

        elif self.scan_interval == SCAN_INTERVAL_BIWEEKLY:
            weekday_options = {str(i): WEEKDAYS.get(i, f"Day {i}") for i in range(7)}
            schema_dict[vol.Optional(
                CONF_SCAN_WEEKDAY,
                default=self.config_entry.data.get(CONF_SCAN_WEEKDAY, str(DEFAULT_SCAN_WEEKDAY))
            )] = vol.In(weekday_options)

        elif self.scan_interval == SCAN_INTERVAL_MONTHLY:
            day_options = {str(i): f"Jour {i}" for i in range(1, 32)}
            schema_dict[vol.Optional(
                CONF_SCAN_DAY_OF_MONTH,
                default=self.config_entry.data.get(CONF_SCAN_DAY_OF_MONTH, str(DEFAULT_SCAN_DAY_OF_MONTH))
            )] = vol.In(day_options)

        return self.async_show_form(
            step_id="schedule_options",
            data_schema=vol.Schema(schema_dict),
        )


# Import cv pour multi_select
from homeassistant.helpers import cv
