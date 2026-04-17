"""Plateforme image pour Volkswagen Web."""

from __future__ import annotations

import base64
import collections
import logging
from datetime import datetime
from typing import Any

from homeassistant.components.image import ImageEntity
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
    """Crée les entités image (une par image disponible)."""
    coordinator: VolkswagenWebCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    entities = []
    for vin in coordinator.vins:
        vehicle_data = (coordinator.data or {}).get(vin) or {}
        images = vehicle_data.get("images") or []
        _LOGGER.debug("Image setup VIN %s: %d image(s) available", vin, len(images))
        
        # Une entité image par image disponible
        for idx, image in enumerate(images):
            entities.append(
                VolkswagenImageEntity(
                    coordinator=coordinator,
                    vin=vin,
                    image_index=idx,
                )
            )

    _LOGGER.debug("Adding %d image entity(ies)", len(entities))
    async_add_entities(entities)


class VolkswagenImageEntity(CoordinatorEntity, ImageEntity):
    """Entité image affichant une photo extérieure du véhicule."""

    def __init__(
        self,
        coordinator: VolkswagenWebCoordinator,
        vin: str,
        image_index: int,
    ) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        self._vin = vin
        self._image_index = image_index
        self._attr_unique_id = f"{vin}-image-{image_index}"
        self._attr_translation_key = "vehicle_image"
        # ImageEntity.__init__ requires hass; initialize its state manually
        self.access_tokens: collections.deque = collections.deque([], 2)
        self._cache = None

    @property
    def device_info(self) -> dict[str, Any]:
        """Associe l'image au même device que les sensors."""
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
        """Disponible si l'image existe et le coordinateur a des données."""
        vehicle_data = (self.coordinator.data or {}).get(self._vin)
        if not vehicle_data:
            _LOGGER.debug("Image %s[%d] unavailable: no vehicle data", self._vin, self._image_index)
            return False
        images = vehicle_data.get("images") or []
        available = self.coordinator.last_update_success and self._image_index < len(images)
        if not available:
            _LOGGER.debug(
                "Image %s[%d] unavailable: last_update_success=%s image_count=%d",
                self._vin,
                self._image_index,
                self.coordinator.last_update_success,
                len(images),
            )
        return available

    @property
    def name(self) -> str | None:
        """Nom de l'entité: "Image N+1"."""
        return f"Image {self._image_index + 1}"

    async def async_added_to_hass(self) -> None:
        """Appelé quand l'entité est ajoutée à HA: génère le token d'accès."""
        await super().async_added_to_hass()
        # Génère un token d'accès initial pour les requêtes HTTP de l'image
        import secrets
        self.access_tokens.append(secrets.token_hex(32))
        _LOGGER.debug(
            "Image entity added for VIN %s index %d (access_tokens=%d)",
            self._vin,
            self._image_index,
            len(self.access_tokens),
        )

    @property
    def image_last_updated(self) -> datetime | None:
        """Timestamp de la mise à jour du coordinateur."""
        if not self.coordinator.last_update_success:
            return None
        vehicle_data = (self.coordinator.data or {}).get(self._vin) or {}
        return vehicle_data.get("timestamp")  # datetime object, not string

    async def async_image(self) -> bytes | None:
        """Retourne les bytes JPEG/PNG de l'image (base64 → bytes)."""
        vehicle_data = (self.coordinator.data or {}).get(self._vin)
        if not vehicle_data:
            _LOGGER.debug("Image fetch VIN %s[%d]: no vehicle data", self._vin, self._image_index)
            return None

        images: list[dict[str, Any]] = vehicle_data.get("images") or []
        if self._image_index >= len(images):
            _LOGGER.debug(
                "Image fetch VIN %s[%d]: index out of range (count=%d)",
                self._vin,
                self._image_index,
                len(images),
            )
            return None

        image_dict = images[self._image_index]
        image_data = image_dict.get("image_data") or image_dict.get("data")
        if not image_data:
            _LOGGER.debug("Image fetch VIN %s[%d]: missing image_data/data key", self._vin, self._image_index)
            return None

        try:
            # Décode base64 → bytes JPEG/PNG
            if isinstance(image_data, str):
                image_bytes = base64.b64decode(image_data)
            else:
                image_bytes = image_data
            _LOGGER.debug(
                "Image fetch VIN %s[%d]: decoded %d bytes",
                self._vin,
                self._image_index,
                len(image_bytes),
            )
            return image_bytes
        except Exception as err:
            _LOGGER.error(
                "Erreur décodage image %d du VIN %s: %s",
                self._image_index,
                self._vin,
                err,
            )
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Métadonnées de l'image."""
        vehicle_data = (self.coordinator.data or {}).get(self._vin) or {}
        images = vehicle_data.get("images") or []
        
        attrs: dict[str, Any] = {
            "vin": self._vin,
            "image_index": self._image_index,
        }
        
        if self._image_index < len(images):
            image_dict = images[self._image_index]
            if url := image_dict.get("url") or image_dict.get("imageUrl"):
                attrs["url"] = url
        
        return attrs
