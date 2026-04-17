"""Plateforme camera pour Volkswagen Web."""

from __future__ import annotations

import base64
import logging
from typing import Any

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
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
    """Crée les entités camera."""
    coordinator: VolkswagenWebCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    entities = [
        VolkswagenCamera(coordinator=coordinator, vin=vin)
        for vin in coordinator.vins
    ]
    _LOGGER.debug("Adding %d camera entity(ies)", len(entities))
    async_add_entities(entities)


class VolkswagenCamera(CoordinatorEntity, Camera):
    """Caméra affichant les images extérieures du véhicule (VILMA)."""

    def __init__(
        self,
        coordinator: VolkswagenWebCoordinator,
        vin: str,
    ) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        Camera.__init__(self)
        self._vin = vin
        self._attr_unique_id = f"{vin}-camera-vehicle_images"
        self._attr_translation_key = "vehicle_images"
        self._attr_icon = "mdi:image-multiple"
        self._attr_content_type = "image/jpeg"
        # Pas de streaming live: lecture seule
        self._attr_is_streaming = False
        self._attr_frame_interval = 60.0  # secondes entre rafraîchissements UI

    @property
    def device_info(self) -> dict[str, Any]:
        """Associe la caméra au même device que les sensors."""
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
        vehicle_data = (self.coordinator.data or {}).get(self._vin)
        if not vehicle_data:
            _LOGGER.debug("Camera %s unavailable: no vehicle data", self._vin)
            return False
        images = vehicle_data.get("images") or []
        available = self.coordinator.last_update_success and len(images) > 0
        if not available:
            _LOGGER.debug(
                "Camera %s unavailable: last_update_success=%s image_count=%d",
                self._vin,
                self.coordinator.last_update_success,
                len(images),
            )
        return available

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Retourne la première image extérieure en JPEG (base64 → bytes)."""
        vehicle_data = (self.coordinator.data or {}).get(self._vin)
        if not vehicle_data:
            _LOGGER.debug("Camera fetch %s: no vehicle data", self._vin)
            return None

        images: list[dict[str, Any]] = vehicle_data.get("images") or []
        if not images:
            _LOGGER.debug("Camera fetch %s: no images returned", self._vin)
            return None

        # Première image disponible
        first = images[0]
        image_data = first.get("image_data") or first.get("data")
        if not image_data:
            _LOGGER.debug("Camera fetch %s: first image missing image_data/data", self._vin)
            return None

        try:
            # Décode base64 → bytes JPEG/PNG
            if isinstance(image_data, str):
                image_bytes = base64.b64decode(image_data)
            else:
                image_bytes = image_data
            _LOGGER.debug("Camera fetch %s: decoded %d bytes", self._vin, len(image_bytes))
            return image_bytes
        except Exception as err:
            _LOGGER.error("Erreur décodage image VIN %s: %s", self._vin, err)
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Nombre d'images disponibles et métadonnées."""
        vehicle_data = (self.coordinator.data or {}).get(self._vin) or {}
        images = vehicle_data.get("images") or []
        return {
            "vin": self._vin,
            "image_count": len(images),
            "image_urls": [
                img.get("url") or img.get("imageUrl")
                for img in images
                if img.get("url") or img.get("imageUrl")
            ],
        }
