"""Coordinateur pour la synchronisation des données Volkswagen."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, time
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_AUTO_REQUEST_UPDATE,
    CONF_REQUEST_ADVANCE_HOURS,
    CONF_SCAN_DAY_OF_MONTH,
    CONF_SCAN_INTERVAL,
    CONF_SCAN_TIME,
    CONF_SCAN_WEEKDAY,
    DOMAIN,
    SCAN_INTERVAL_BIWEEKLY,
    SCAN_INTERVAL_DAILY,
    SCAN_INTERVAL_MAP,
    SCAN_INTERVAL_MONTHLY,
    SCAN_INTERVAL_WEEKLY,
)

_LOGGER = logging.getLogger(__name__)


class VolkswagenWebCoordinator(DataUpdateCoordinator):
    """Coordinateur pour mettre à jour les données du véhicule."""

    def __init__(
        self,
        hass: HomeAssistant,
        connection: Any,
        vins: list[str],
        config: dict[str, Any],
    ) -> None:
        """Initialiser le coordinateur."""
        self.connection = connection
        self.vins = vins
        self.config = config

        # Récupère les paramètres de configuration
        self.scan_interval_key = config.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL_DAILY)
        self.scan_time_str = config.get(CONF_SCAN_TIME, "10:00")
        self.scan_weekday = int(config.get(CONF_SCAN_WEEKDAY, 0))  # 0 = Monday
        self.scan_day_of_month = int(config.get(CONF_SCAN_DAY_OF_MONTH, 1))

        # Calcule l'intervalle initial
        update_interval = self._calculate_next_update_interval()

        self._last_request_at: dict[str, datetime] = {}
        self._auto_request_enabled = config.get(CONF_AUTO_REQUEST_UPDATE, True)
        self._request_advance_hours = config.get(CONF_REQUEST_ADVANCE_HOURS, 1)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )

    def _parse_scan_time(self) -> time:
        """Parse le temps de scan au format HH:MM."""
        try:
            parts = self.scan_time_str.split(":")
            return time(hour=int(parts[0]), minute=int(parts[1]))
        except (IndexError, ValueError):
            _LOGGER.warning(f"Format d'heure invalide: {self.scan_time_str}, utilise 10:00 par défaut")
            return time(hour=10, minute=0)

    def _calculate_next_update_interval(self) -> timedelta:
        """Calcule l'intervalle jusqu'au prochain refresh basé sur le schedule.
        
        Retourne un timedelta jusqu'au prochain moment de synchronisation.
        """
        now = datetime.now()
        scan_time = self._parse_scan_time()

        if self.scan_interval_key == SCAN_INTERVAL_DAILY:
            # Prochain refresh: aujourd'hui à scan_time (ou demain si l'heure est passée)
            next_refresh = datetime.combine(now.date(), scan_time)
            if next_refresh <= now:
                next_refresh += timedelta(days=1)

        elif self.scan_interval_key == SCAN_INTERVAL_WEEKLY:
            # Prochain refresh: ce jour de la semaine à scan_time (ou la semaine prochaine)
            days_ahead = (self.scan_weekday - now.weekday()) % 7
            if days_ahead == 0:
                # C'est ce jour - vérifie l'heure
                next_refresh = datetime.combine(now.date(), scan_time)
                if next_refresh <= now:
                    days_ahead = 7
                else:
                    next_refresh = datetime.combine((now + timedelta(days=days_ahead)).date(), scan_time)
            else:
                next_refresh = datetime.combine((now + timedelta(days=days_ahead)).date(), scan_time)

        elif self.scan_interval_key == SCAN_INTERVAL_BIWEEKLY:
            # Calcule le prochain cycle de 14 jours
            # Référence: premier jour du scan à l'époque Unix
            reference_date = datetime(2024, 1, 1)  # Jour de référence
            days_since_ref = (now.date() - reference_date.date()).days
            days_into_cycle = days_since_ref % 14
            days_until_next_cycle = (14 - days_into_cycle) % 14

            if days_until_next_cycle == 0:
                # C'est aujourd'hui - vérifie l'heure
                next_refresh = datetime.combine(now.date(), scan_time)
                if next_refresh <= now:
                    days_until_next_cycle = 14

            next_refresh = datetime.combine(
                (now + timedelta(days=days_until_next_cycle)).date(), scan_time
            )

        elif self.scan_interval_key == SCAN_INTERVAL_MONTHLY:
            # Prochain refresh: ce jour du mois à scan_time
            try:
                next_refresh = datetime.combine(
                    datetime(now.year, now.month, min(self.scan_day_of_month, 28)).date(),
                    scan_time,
                )
            except ValueError:
                # Jour invalide pour ce mois (ex: 31 février)
                next_refresh = datetime.combine(
                    datetime(now.year, now.month, 1).date(),
                    scan_time,
                )

            if next_refresh <= now:
                # Mois prochain
                next_month = now.replace(day=1) + timedelta(days=32)
                try:
                    next_refresh = datetime.combine(
                        datetime(next_month.year, next_month.month, min(self.scan_day_of_month, 28)).date(),
                        scan_time,
                    )
                except ValueError:
                    next_refresh = datetime.combine(
                        datetime(next_month.year, next_month.month, 1).date(),
                        scan_time,
                    )

        else:
            # Fallback: demain à scan_time
            next_refresh = datetime.combine((now + timedelta(days=1)).date(), scan_time)

        # Calcule le temps avant le prochain refresh
        time_until_refresh = next_refresh - now
        _LOGGER.debug(f"Prochain refresh dans: {time_until_refresh}, à: {next_refresh}")

        # Min 1 min, max paramétré par l'intervalle
        return max(time_until_refresh, timedelta(minutes=1))

    async def _async_update_data(self) -> dict[str, Any]:
        """Récupère les données du véhicule."""
        try:
            # Assure que la connexion est authentifiée
            if not self.connection._session:
                await self.connection.login()

            # Récupère l'état pour chaque VIN
            data = {}
            tasks = []
            for vin in self.vins:
                tasks.append(self._fetch_vehicle_data(vin))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for vin, result in zip(self.vins, results):
                if isinstance(result, Exception):
                    _LOGGER.error(f"Erreur lors de la récupération du VIN {vin}: {result}")
                    data[vin] = None
                else:
                    data[vin] = result

            # Vérifier si un request_update doit être déclenché automatiquement
            if self._auto_request_enabled:
                await self._async_check_auto_request()

            return data

        except Exception as err:
            raise UpdateFailed(f"Erreur lors de la mise à jour: {err}") from err

    async def _fetch_vehicle_data(self, vin: str) -> dict[str, Any]:
        """Récupère les données pour un véhicule spécifique."""
        vehicles = await self.connection.list_vehicles()
        vehicle = next((v for v in vehicles if v.vin == vin), None)

        if not vehicle:
            _LOGGER.warning(f"Véhicule VIN {vin} non trouvé.")
            return None

        try:
            state = await vehicle.get_state()
            dashboard = vehicle.dashboard()
            images = await vehicle.get_images()

            return {
                "vehicle": vehicle,
                "state": state,
                "dashboard": dashboard,
                "images": images if isinstance(images, list) else [],
                "timestamp": datetime.now(),
            }
        except Exception as err:
            _LOGGER.error(f"Erreur lors de la récupération des données du VIN {vin}: {err}")
            raise

    async def _async_check_auto_request(self) -> None:
        """Vérifie si un request_update doit être déclenché automatiquement.
        
        Logique:
        - Chaque 15 min (interne), vérifie si on doit déclencher en avance
        - Si delai >= advance_hours, déclenche vehicle.request_new_report()
        """
        now = datetime.now()

        for vin in self.vins:
            last_request = self._last_request_at.get(vin, datetime.min)
            time_since_last_request = now - last_request

            # Vérifie si assez de temps est passé depuis le dernier request
            # Pour éviter les spam, on attend au moins advance_hours entre appels
            if time_since_last_request >= timedelta(hours=self._request_advance_hours):
                try:
                    vehicles = await self.connection.list_vehicles()
                    vehicle = next((v for v in vehicles if v.vin == vin), None)

                    if vehicle:
                        _LOGGER.debug(
                            f"Déclenchement auto de request_update pour {vin} "
                            f"(délai avance: {self._request_advance_hours}h)"
                        )
                        result = await vehicle.request_new_report()
                        self._last_request_at[vin] = now
                        _LOGGER.debug(f"Request update déclenché: {result}")

                        # Force un refresh du coordinateur
                        await self.async_request_refresh()

                except Exception as err:
                    _LOGGER.error(f"Erreur lors du request_update auto pour {vin}: {err}")

    async def async_request_report_manual(self, vin: str) -> bool:
        """Déclenche manuellement un request_update pour un véhicule."""
        try:
            vehicles = await self.connection.list_vehicles()
            vehicle = next((v for v in vehicles if v.vin == vin), None)

            if not vehicle:
                _LOGGER.warning(f"Véhicule VIN {vin} non trouvé pour manual request.")
                return False

            _LOGGER.info(f"Déclenchement manuel de request_update pour {vin}")
            result = await vehicle.request_new_report()
            self._last_request_at[vin] = datetime.now()

            # Force un refresh
            await self.async_request_refresh()
            return True

        except Exception as err:
            _LOGGER.error(f"Erreur lors du manual request_update pour {vin}: {err}")
            return False
