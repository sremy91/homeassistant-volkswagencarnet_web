"""Plateforme camera pour Volkswagen Web."""

from __future__ import annotations

import asyncio
import base64
import logging
import re
import time as time_module
from typing import Any, AsyncGenerator

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import async_get
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

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

    # Initialise le dictionnaire de caméras par VIN si nécessaire
    if "cameras_by_vin" not in hass.data[DOMAIN]:
        hass.data[DOMAIN]["cameras_by_vin"] = {}

    entities = [
        VolkswagenCamera(coordinator=coordinator, vin=vin, hass=hass)
        for vin in coordinator.vins
    ]
    _LOGGER.debug("Adding %d camera entity(ies)", len(entities))
    async_add_entities(entities)


class VolkswagenCamera(CoordinatorEntity, Camera):
    """Caméra affichant les images extérieures du véhicule (VILMA) avec stream MJPEG."""

    def __init__(
        self,
        coordinator: VolkswagenWebCoordinator,
        vin: str,
        hass: HomeAssistant,
    ) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        Camera.__init__(self)
        self._vin = vin
        self._hass = hass
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{vin}-camera-vehicle_images"
        self._attr_translation_key = "vehicle_images"
        self._attr_icon = "mdi:image-multiple"
        self._attr_content_type = "image/jpeg"
        # Stream MJPEG activé
        self._attr_is_streaming = True
        self._attr_supported_features = CameraEntityFeature.STREAM
        self._attr_frame_interval = 1.0  # mis à jour par rotation_seconds
        self._streaming_task: asyncio.Task | None = None

    async def async_added_to_hass(self) -> None:
        """Enregistre cette caméra dans le dictionnaire global et migre l'entity_id."""
        await super().async_added_to_hass()
        if "cameras_by_vin" not in self._hass.data[DOMAIN]:
            self._hass.data[DOMAIN]["cameras_by_vin"] = {}
        self._hass.data[DOMAIN]["cameras_by_vin"][self._vin] = self
        _LOGGER.debug("Camera registered for MJPEG streaming: %s", self._vin)

        # Migre l'entity_id s'il a un suffixe numérique
        entity_registry = async_get(self._hass)
        current_entity_id = self.entity_id

        if not current_entity_id or not re.search(r"_\d+$", current_entity_id):
            return

        # Génère le nouvel entity_id descriptif
        nickname = self.device_info.get("name", self._vin)
        device_slug = slugify(nickname)
        new_entity_id = f"camera.{device_slug}_vehicle_images"

        _LOGGER.debug("Migrating camera %s → %s", current_entity_id, new_entity_id)

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
            _LOGGER.info("Migrated camera %s → %s", current_entity_id, new_entity_id)
        except Exception as err:
            _LOGGER.error(
                "Failed to migrate camera %s → %s: %s",
                current_entity_id,
                new_entity_id,
                err,
            )

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
        """Retourne une image extérieure (rotation toutes les N secondes)."""
        vehicle_data = (self.coordinator.data or {}).get(self._vin)
        if not vehicle_data:
            _LOGGER.debug("Camera fetch %s: no vehicle data", self._vin)
            return None

        images: list[dict[str, Any]] = vehicle_data.get("images") or []
        if not images:
            _LOGGER.debug("Camera fetch %s: no images returned", self._vin)
            return None

        rotation_seconds = max(1, int(self.coordinator.camera_rotation_seconds))
        current_index = (int(time_module.time()) // rotation_seconds) % len(images)

        return self._get_image_bytes(images, current_index)

    def _get_image_bytes(
        self, images: list[dict[str, Any]], index: int
    ) -> bytes | None:
        """Extrait et décode une image par son index."""
        if not images or index >= len(images):
            return None

        current = images[index]
        image_data = (
            current.get("image_data")
            or current.get("data")
            or current.get("base64")
            or current.get("b64")
        )
        if not image_data:
            _LOGGER.debug(
                "Camera fetch %s: image[%d] missing payload key (known keys=%s)",
                self._vin,
                index,
                sorted(current.keys()),
            )
            return None

        try:
            # Décode base64 → bytes JPEG/PNG
            if isinstance(image_data, str):
                image_bytes = base64.b64decode(image_data)
            else:
                image_bytes = image_data
            _LOGGER.debug(
                "Camera fetch %s: image[%d] decoded %d bytes",
                self._vin,
                index,
                len(image_bytes),
            )
            return image_bytes
        except Exception as err:
            _LOGGER.error("Erreur décodage image VIN %s[%d]: %s", self._vin, index, err)
            return None

    async def stream_source(self) -> str | None:
        """Retourne l'URL du stream MJPEG personnalisé."""
        # Construit l'URL du stream basée sur le VIN
        # Exemple: /api/volkswagen_web/mjpeg/{vin}
        return f"/api/{DOMAIN}/mjpeg/{self._vin}"

    @property
    def stream_source(self) -> str | None:
        """Retourne l'URL du stream MJPEG (property version)."""
        return f"/api/{DOMAIN}/mjpeg/{self._vin}"

    async def async_get_stream_source(self) -> str | None:
        """Retourne None pour indiquer un stream personnalisé."""
        return None

    async def async_handle_web_request(
        self, request, prefix: str | None = None
    ) -> None:
        """Stream MJPEG personnalisé."""
        # Cette méthode est appelée par Home Assistant quand un client accède au stream
        pass

    async def async_mjpeg_stream(self, request) -> AsyncGenerator[bytes, None]:
        """Génère un stream MJPEG continu des images en rotation.
        
        Le délai de rotation défini le rythme des frames.
        """
        rotation_seconds = max(1, int(self.coordinator.camera_rotation_seconds))
        boundary = b"--frame"
        
        _LOGGER.debug(
            "Camera stream starting for %s with rotation=%ss",
            self._vin,
            rotation_seconds,
        )

        try:
            image_index = 0
            while True:
                # Récupère les données actuelles
                vehicle_data = (self.coordinator.data or {}).get(self._vin)
                if not vehicle_data:
                    await asyncio.sleep(rotation_seconds)
                    continue

                images: list[dict[str, Any]] = vehicle_data.get("images") or []
                if not images:
                    await asyncio.sleep(rotation_seconds)
                    continue

                # Récupère l'image à l'index actuel
                image_bytes = self._get_image_bytes(images, image_index % len(images))
                
                if image_bytes:
                    # Formate en MJPEG
                    frame = (
                        boundary
                        + b"\r\nContent-Type: image/jpeg\r\n"
                        + f"Content-length: {len(image_bytes)}\r\n".encode()
                        + b"\r\n"
                        + image_bytes
                        + b"\r\n"
                    )
                    
                    yield frame
                    
                    _LOGGER.debug(
                        "Camera stream %s: frame %d (%d bytes, rotation=%ss)",
                        self._vin,
                        image_index,
                        len(image_bytes),
                        rotation_seconds,
                    )

                # Avance au prochain frame après le délai de rotation
                image_index += 1
                await asyncio.sleep(rotation_seconds)

        except asyncio.CancelledError:
            _LOGGER.debug("Camera stream cancelled for %s", self._vin)
            raise
        except Exception as err:
            _LOGGER.error("Camera stream error for %s: %s", self._vin, err)
            raise

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Nombre d'images disponibles et métadonnées."""
        vehicle_data = (self.coordinator.data or {}).get(self._vin) or {}
        images = vehicle_data.get("images") or []
        rotation_seconds = max(1, int(self.coordinator.camera_rotation_seconds))
        current_index = (int(time_module.time()) // rotation_seconds) % len(images) if images else 0
        return {
            "vin": self._vin,
            "image_count": len(images),
            "rotation_seconds": rotation_seconds,
            "current_image_index": current_index,
            "image_urls": [
                img.get("url") or img.get("imageUrl") or img.get("source_url")
                for img in images
                if img.get("url") or img.get("imageUrl") or img.get("source_url")
            ],
        }

