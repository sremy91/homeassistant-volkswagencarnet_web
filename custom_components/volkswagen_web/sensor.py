"""Plateforme sensor pour Volkswagen Web."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import VolkswagenWebCoordinator

_LOGGER = logging.getLogger(__name__)

# (attr, device_class, state_class, unit, entity_category, icon)
SENSOR_DESCRIPTIONS: list[tuple[str, str | None, str | None, str | None, str | None, str | None]] = [
    ("vin",                   None,                         None,                              None,  EntityCategory.DIAGNOSTIC,    "mdi:identifier"),
    ("next_scheduled_request", SensorDeviceClass.TIMESTAMP, None,                              None,  EntityCategory.DIAGNOSTIC,    "mdi:clock-start"),
    ("next_scheduled_refresh", SensorDeviceClass.TIMESTAMP, None,                              None,  EntityCategory.DIAGNOSTIC,    "mdi:clock-end"),
    ("mileage_km",            SensorDeviceClass.DISTANCE,   SensorStateClass.TOTAL_INCREASING, "km",  None,                         "mdi:counter"),
    ("last_report_timestamp", SensorDeviceClass.TIMESTAMP,  None,                              None,  EntityCategory.DIAGNOSTIC,    "mdi:clock-outline"),
    ("model_name",            None,                         None,                              None,  EntityCategory.DIAGNOSTIC,    "mdi:car-info"),
    ("license_plate",         None,                         None,                              None,  EntityCategory.DIAGNOSTIC,    "mdi:car"),
    ("vehicle_status",        None,                         None,                              None,  None,                         "mdi:shield-car"),
    ("status_freins",         None,                         None,                              None,  None,                         "mdi:car-brake-alert"),
    ("status_pneus",          None,                         None,                              None,  None,                         "mdi:tire"),
    ("status_transmission",   None,                         None,                              None,  None,                         "mdi:engine"),
    ("status_feux_de_route",  None,                         None,                              None,  None,                         "mdi:car-light-high"),
    ("status_assistants",     None,                         None,                              None,  None,                         "mdi:car-cruise-control"),
    ("status_confort",        None,                         None,                              None,  None,                         "mdi:car-seat"),
    ("warninglights_last",    None,                         None,                              None,  EntityCategory.DIAGNOSTIC,    "mdi:car-wrench"),
    ("contracts",             None,                         None,                              None,  EntityCategory.DIAGNOSTIC,    "mdi:file-document-multiple"),
    ("service_partner",       None,                         None,                              None,  EntityCategory.DIAGNOSTIC,    "mdi:garage"),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Crée les entités sensor."""
    coordinator: VolkswagenWebCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    entities = []
    for vin in coordinator.vins:
        for (attr, device_class, state_class, unit, category, icon) in SENSOR_DESCRIPTIONS:
            entities.append(
                VolkswagenSensor(
                    coordinator=coordinator,
                    vin=vin,
                    attr=attr,
                    device_class=device_class,
                    state_class=state_class,
                    native_unit=unit,
                    entity_category=category,
                    icon=icon,
                )
            )

    async_add_entities(entities)


class VolkswagenSensor(CoordinatorEntity, SensorEntity):
    """Entité sensor pour un instrument Volkswagen Web."""

    def __init__(
        self,
        coordinator: VolkswagenWebCoordinator,
        vin: str,
        attr: str,
        device_class: str | None,
        state_class: str | None,
        native_unit: str | None,
        entity_category: str | None,
        icon: str | None,
    ) -> None:
        super().__init__(coordinator)
        self._vin = vin
        self._attr = attr
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{vin}-sensor-{attr}"
        self._attr_translation_key = attr
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_native_unit_of_measurement = native_unit
        self._attr_entity_category = entity_category
        self._attr_icon = icon

    @property
    def device_info(self) -> dict[str, Any]:
        """Informations du device (regroupe toutes les entités par VIN)."""
        vehicle_data = (self.coordinator.data or {}).get(self._vin) or {}
        vehicle = vehicle_data.get("vehicle")
        nickname = getattr(vehicle, "nickname", None) or self._vin

        return {
            "identifiers": {(DOMAIN, self._vin)},
            "name": nickname,
            "manufacturer": "Volkswagen",
            "model": self._get_model_name(),
        }

    def _get_model_name(self) -> str | None:
        """Récupère le nom du modèle depuis le state."""
        vehicle_data = (self.coordinator.data or {}).get(self._vin) or {}
        state = vehicle_data.get("state")
        return getattr(state, "model_name", None) if state else None

    def _get_vehicle_data(self) -> dict[str, Any] | None:
        """Récupère les données du véhicule depuis le coordinateur."""
        return (self.coordinator.data or {}).get(self._vin)

    @property
    def available(self) -> bool:
        """Disponible si le coordinator a des données pour ce VIN."""
        return (
            self.coordinator.last_update_success
            and self._get_vehicle_data() is not None
        )

    @property
    def native_value(self) -> Any:
        """Retourne la valeur de l'instrument."""
        vehicle_data = self._get_vehicle_data()
        if not vehicle_data:
            return None

        # VIN
        if self._attr == "vin":
            return self._vin

        # Planification prochaine demande / récupération
        if self._attr == "next_scheduled_request":
            return self.coordinator.get_next_request_at(self._vin)

        if self._attr == "next_scheduled_refresh":
            return self.coordinator.get_next_refresh_at()

        state = vehicle_data.get("state")
        if not state:
            return None

        # Attributs directs sur VehicleState
        direct_attrs = {
            "mileage_km", "model_name",
            "data_timestamp",
        }
        if self._attr in direct_attrs:
            return getattr(state, self._attr, None)

        # last_report_timestamp: data_timestamp parsé en datetime
        if self._attr == "last_report_timestamp":
            raw = getattr(state, "data_timestamp", None)
            if not raw:
                return None
            if isinstance(raw, datetime):
                return raw
            try:
                return datetime.fromisoformat(raw)
            except (ValueError, TypeError):
                return None

        # license_plate depuis le vehicle
        if self._attr == "license_plate":
            vehicle = vehicle_data.get("vehicle")
            return getattr(vehicle, "license_plate", None) if vehicle else None

        # vehicle_status: résumé JSON (mileage + systems)
        if self._attr == "vehicle_status":
            systems = state.systems or []
            return f"{len(systems)} système(s) — {state.mileage_km or '?'} km"

        # Statuts individuels des systèmes
        if self._attr.startswith("status_"):
            system_id = self._attr[len("status_"):]
            for sys in (state.systems or []):
                if sys.get("id") == system_id:
                    return sys.get("status")
            return None

        # warninglights_last: len(warning_lights)
        if self._attr == "warninglights_last":
            lights = state.warning_lights or []
            return f"{len(lights)} alerte(s)"

        # contracts: nombre de contrats actifs
        if self._attr == "contracts":
            contracts = state.contracts or []
            _LOGGER.debug(
                "Contracts sensor VIN %s render count=%d",
                self._vin,
                len(contracts),
            )
            return f"{len(contracts)} contrat(s)"

        # service_partner: nom du partenaire
        if self._attr == "service_partner":
            partner = state.service_partner
            if isinstance(partner, dict):
                return partner.get("name") or partner.get("partnerName")
            return None

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Attributs supplémentaires exposés dans HA."""
        vehicle_data = self._get_vehicle_data()
        if not vehicle_data:
            return {}

        state = vehicle_data.get("state")
        if not state:
            return {}

        attrs: dict[str, Any] = {"vin": self._vin}

        if self._attr in {"next_scheduled_request", "next_scheduled_refresh"}:
            attrs["scan_interval"] = self.coordinator.scan_interval_key
            attrs["scan_time"] = self.coordinator.scan_time_str
            attrs["scan_weekday"] = self.coordinator.scan_weekday
            attrs["scan_day_of_month"] = self.coordinator.scan_day_of_month
            attrs["auto_request_update"] = self.coordinator._auto_request_enabled
            attrs["request_advance_hours"] = self.coordinator._request_advance_hours
            attrs["next_scheduled_refresh"] = self.coordinator.get_next_refresh_at()
            if self._attr == "next_scheduled_request":
                attrs["next_scheduled_request"] = self.coordinator.get_next_request_at(self._vin)
            return attrs

        if self._attr == "vehicle_status":
            attrs["systems"] = state.systems
            attrs["mileage_km"] = state.mileage_km
            attrs["data_timestamp"] = state.data_timestamp

        elif self._attr == "warninglights_last":
            attrs["warning_lights"] = state.warning_lights
            attrs["systems"] = state.systems
            attrs["data_timestamp"] = state.data_timestamp

        elif self._attr == "contracts":
            attrs["contracts_detail"] = state.contracts
            _LOGGER.debug(
                "Contracts sensor VIN %s attrs contracts_detail count=%d",
                self._vin,
                len(state.contracts or []),
            )

        elif self._attr == "service_partner":
            attrs["partner_detail"] = state.service_partner

        elif self._attr.startswith("status_"):
            system_id = self._attr[len("status_"):]
            for sys in (state.systems or []):
                if sys.get("id") == system_id:
                    attrs.update({k: v for k, v in sys.items() if k != "id"})

        return attrs
