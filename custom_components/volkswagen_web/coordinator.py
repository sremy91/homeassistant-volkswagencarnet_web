"""Coordinateur pour la synchronisation des données Volkswagen."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, time
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_AUTO_REQUEST_UPDATE,
    CONF_EMAIL,
    CONF_FETCH_HISTORY_ON_SETUP,
    CONF_MANUAL_REQUEST_REFRESH_DELAY_MINUTES,
    CONF_PASSWORD,
    CONF_REQUEST_ADVANCE_HOURS,
    CONF_SCAN_DAY_OF_MONTH,
    CONF_SCAN_INTERVAL,
    CONF_SCAN_TIME,
    CONF_SCAN_WEEKDAY,
    DEFAULT_MANUAL_REQUEST_REFRESH_DELAY_MINUTES,
    DOMAIN,
    SCAN_INTERVAL_BIWEEKLY,
    SCAN_INTERVAL_DAILY,
    SCAN_INTERVAL_MAP,
    SCAN_INTERVAL_MONTHLY,
    SCAN_INTERVAL_WEEKLY,
)

_LOGGER = logging.getLogger(__name__)


def _to_int_or_default(value: Any, default: int) -> int:
    """Convert a value to int with a safe default when value is None/invalid."""
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_bool_or_default(value: Any, default: bool) -> bool:
    """Convert a value to bool while keeping a fallback for missing values."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


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
        self.scan_interval_key = config.get(CONF_SCAN_INTERVAL) or SCAN_INTERVAL_DAILY
        self.scan_time_str = str(config.get(CONF_SCAN_TIME) or "10:00")
        self.scan_weekday = _to_int_or_default(config.get(CONF_SCAN_WEEKDAY), 0)  # 0 = Monday
        self.scan_day_of_month = _to_int_or_default(config.get(CONF_SCAN_DAY_OF_MONTH), 1)

        # Calcule l'intervalle initial
        update_interval = self._calculate_next_update_interval()

        self._last_request_at: dict[str, datetime] = {}
        self._auto_request_retry_not_before: dict[str, datetime] = {}
        self._pending_manual_refresh: dict[str, asyncio.TimerHandle] = {}
        self._history_cache: dict[str, dict[str, Any]] = {}
        self._auto_request_enabled = _to_bool_or_default(
            config.get(CONF_AUTO_REQUEST_UPDATE),
            True,
        )
        self._fetch_history_on_setup = _to_bool_or_default(
            config.get(CONF_FETCH_HISTORY_ON_SETUP),
            True,
        )
        self._request_advance_hours = _to_int_or_default(
            config.get(CONF_REQUEST_ADVANCE_HOURS),
            1,
        )
        self._manual_request_refresh_delay_minutes = _to_int_or_default(
            config.get(CONF_MANUAL_REQUEST_REFRESH_DELAY_MINUTES),
            DEFAULT_MANUAL_REQUEST_REFRESH_DELAY_MINUTES,
        )
        self._username = config.get(CONF_EMAIL)
        self._password = config.get(CONF_PASSWORD)

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

    @staticmethod
    def _as_local_aware(value: datetime | None) -> datetime | None:
        """Convertit un datetime naïf en datetime local timezone-aware."""
        if value is None:
            return None
        if value.tzinfo is not None:
            return value
        local_tz = dt_util.now().tzinfo
        return value.replace(tzinfo=local_tz)

    def _calculate_next_refresh_datetime(self, now: datetime | None = None) -> datetime:
        """Calcule la prochaine date de synchronisation."""
        now = now or datetime.now()
        scan_time = self._parse_scan_time()

        if self.scan_interval_key == SCAN_INTERVAL_DAILY:
            next_refresh = datetime.combine(now.date(), scan_time)
            if next_refresh <= now:
                next_refresh += timedelta(days=1)

        elif self.scan_interval_key == SCAN_INTERVAL_WEEKLY:
            days_ahead = (self.scan_weekday - now.weekday()) % 7
            if days_ahead == 0:
                next_refresh = datetime.combine(now.date(), scan_time)
                if next_refresh <= now:
                    days_ahead = 7
                    next_refresh = datetime.combine((now + timedelta(days=days_ahead)).date(), scan_time)
            else:
                next_refresh = datetime.combine((now + timedelta(days=days_ahead)).date(), scan_time)

        elif self.scan_interval_key == SCAN_INTERVAL_BIWEEKLY:
            reference_date = datetime(2024, 1, 1)
            days_since_ref = (now.date() - reference_date.date()).days
            days_into_cycle = days_since_ref % 14
            days_until_next_cycle = (14 - days_into_cycle) % 14

            next_refresh = datetime.combine(
                (now + timedelta(days=days_until_next_cycle)).date(),
                scan_time,
            )
            if next_refresh <= now:
                next_refresh = datetime.combine(
                    (now + timedelta(days=14)).date(),
                    scan_time,
                )

        elif self.scan_interval_key == SCAN_INTERVAL_MONTHLY:
            try:
                next_refresh = datetime.combine(
                    datetime(now.year, now.month, min(self.scan_day_of_month, 28)).date(),
                    scan_time,
                )
            except ValueError:
                next_refresh = datetime.combine(
                    datetime(now.year, now.month, 1).date(),
                    scan_time,
                )

            if next_refresh <= now:
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
            next_refresh = datetime.combine((now + timedelta(days=1)).date(), scan_time)

        return next_refresh

    def _calculate_next_update_interval(self) -> timedelta:
        """Calcule l'intervalle jusqu'au prochain refresh basé sur le schedule.
        
        Retourne un timedelta jusqu'au prochain moment de synchronisation.
        """
        now = datetime.now()  # Locale naive datetime pour les calculs internes
        next_refresh = self._calculate_next_refresh_datetime(now)

        # Calcule le temps avant le prochain refresh
        time_until_refresh = next_refresh - now
        _LOGGER.debug(f"Prochain refresh dans: {time_until_refresh}, à: {next_refresh}")

        # Min 1 min, max paramétré par l'intervalle
        return max(time_until_refresh, timedelta(minutes=1))

    def get_next_refresh_at(self) -> datetime | None:
        """Retourne la prochaine date de récupération planifiée."""
        try:
            return self._as_local_aware(self._calculate_next_refresh_datetime())
        except Exception as err:
            _LOGGER.debug("Impossible de calculer la prochaine récupération: %s", err)
            return None

    def get_next_request_at(self, vin: str) -> datetime | None:
        """Retourne la prochaine date de demande automatique de rapport."""
        if not self._auto_request_enabled:
            return None

        next_refresh = self.get_next_refresh_at()
        if not next_refresh:
            return None

        next_request = next_refresh - timedelta(hours=self._request_advance_hours)
        now = dt_util.now()  # datetime aware

        # Rend next_request aware avant la comparaison
        next_request = self._as_local_aware(next_request)

        if next_request <= now:
            # Passe un datetime naive à la méthode interne
            next_refresh = self._as_local_aware(
                self._calculate_next_refresh_datetime(now.replace(tzinfo=None) + timedelta(seconds=1))
            )
            next_request = self._as_local_aware(next_refresh - timedelta(hours=self._request_advance_hours))

        last_request = self._last_request_at.get(vin)
        if last_request and next_request <= last_request:
            # Passe un datetime naive à la méthode interne
            next_refresh = self._as_local_aware(
                self._calculate_next_refresh_datetime(next_refresh.replace(tzinfo=None) + timedelta(seconds=1))
            )
            next_request = self._as_local_aware(next_refresh - timedelta(hours=self._request_advance_hours))

        return next_request

    async def _async_update_data(self) -> dict[str, Any]:
        """Récupère les données du véhicule."""
        try:
            # Assure que la connexion est authentifiée
            if not self.connection._session:
                await self.connection.__aenter__()
                if not self._username or not self._password:
                    raise UpdateFailed("Credentials manquants pour la reconnexion.")
                await self.connection.login(
                    username=self._username,
                    password=self._password,
                )

            # Récupère la liste des véhicules une seule fois par cycle.
            vehicles = await self.connection.list_vehicles()
            vehicles_by_vin = {v.vin: v for v in vehicles}

            # Récupère l'état pour chaque VIN
            data = {}
            tasks = []
            for vin in self.vins:
                tasks.append(self._fetch_vehicle_data(vin, vehicles_by_vin.get(vin)))

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

    async def _fetch_vehicle_data(self, vin: str, vehicle: Any | None) -> dict[str, Any]:
        """Récupère les données pour un véhicule spécifique."""
        if not vehicle:
            _LOGGER.warning(f"Véhicule VIN {vin} non trouvé.")
            return None

        try:
            state = await vehicle.get_state()
            dashboard = vehicle.dashboard()
            images_dict = await vehicle.get_images()
            images_list = images_dict.get("images", []) if isinstance(images_dict, dict) else []
            normalized_images: list[dict[str, Any]] = []
            if isinstance(images_list, list):
                for item in images_list:
                    if not isinstance(item, dict):
                        continue
                    normalized = dict(item)
                    # Le backend web renvoie actuellement {base64, source_url, content_type}.
                    # On ajoute les alias historiques consommés par l'intégration.
                    if "image_data" not in normalized and "base64" in normalized:
                        normalized["image_data"] = normalized.get("base64")
                    if "data" not in normalized and "base64" in normalized:
                        normalized["data"] = normalized.get("base64")
                    if "url" not in normalized and "source_url" in normalized:
                        normalized["url"] = normalized.get("source_url")
                    normalized_images.append(normalized)

            # Compat: get_state() peut contenir contracts=[] si la librairie renvoie
            # un dict {overview, summary}. On recalcule la liste de contrats ici.
            contracts_count = len(getattr(state, "contracts", []) or [])
            _LOGGER.debug(
                "VIN %s contracts from get_state(): %d",
                vin,
                contracts_count,
            )
            if contracts_count == 0:
                contracts_payload = await vehicle.get_contracts()
                contracts_list: list[Any] = []
                _LOGGER.debug(
                    "VIN %s contracts fallback payload type=%s",
                    vin,
                    type(contracts_payload).__name__,
                )
                if isinstance(contracts_payload, list):
                    contracts_list = contracts_payload
                    _LOGGER.debug(
                        "VIN %s contracts fallback from list: %d",
                        vin,
                        len(contracts_list),
                    )
                elif isinstance(contracts_payload, dict):
                    _LOGGER.debug(
                        "VIN %s contracts fallback payload keys=%s",
                        vin,
                        sorted(contracts_payload.keys()),
                    )
                    if isinstance(contracts_payload.get("contracts"), list):
                        contracts_list = contracts_payload.get("contracts") or []
                        _LOGGER.debug(
                            "VIN %s contracts fallback from dict.contracts: %d",
                            vin,
                            len(contracts_list),
                        )
                    else:
                        summary = contracts_payload.get("summary")
                        if isinstance(summary, dict) and isinstance(summary.get("contracts"), list):
                            contracts_list = summary.get("contracts") or []
                            _LOGGER.debug(
                                "VIN %s contracts fallback from dict.summary.contracts: %d",
                                vin,
                                len(contracts_list),
                            )
                state.contracts = contracts_list
                contracts_count = len(contracts_list)

            if contracts_count:
                first_contract = (state.contracts or [None])[0]
                if isinstance(first_contract, dict):
                    _LOGGER.debug(
                        "VIN %s first contract keys=%s status=%s name=%s",
                        vin,
                        sorted(first_contract.keys()),
                        first_contract.get("status") or first_contract.get("contract_status"),
                        first_contract.get("name") or first_contract.get("name_display_fr"),
                    )
            else:
                _LOGGER.debug("VIN %s contracts resolved to 0 after fallback", vin)

            _LOGGER.debug(
                "VIN %s fetched: images=%d history_cached=%s contracts=%d",
                vin,
                len(normalized_images),
                vin in self._history_cache,
                contracts_count,
            )

            return {
                "vehicle": vehicle,
                "state": state,
                "dashboard": dashboard,
                "images": normalized_images,
                "history": self._history_cache.get(vin),
                "timestamp": datetime.now(),
            }
        except Exception as err:
            _LOGGER.error(f"Erreur lors de la récupération des données du VIN {vin}: {err}")
            raise

    @property
    def fetch_history_on_setup(self) -> bool:
        """Indique si l'historique doit être récupéré au démarrage."""
        return self._fetch_history_on_setup

    async def async_request_history_manual(self, vin: str) -> bool:
        """Déclenche manuellement la récupération des informations historiques."""
        try:
            vehicles = await self.connection.list_vehicles()
            vehicle = next((v for v in vehicles if v.vin == vin), None)

            if not vehicle:
                _LOGGER.warning("Véhicule VIN %s non trouvé pour history request.", vin)
                return False

            _LOGGER.info("Récupération manuelle de l'historique pour VIN %s", vin)
            history = await vehicle.get_warninglights_history()
            self._history_cache[vin] = {
                "data": history,
                "fetched_at": datetime.now().isoformat(),
            }
            return True

        except Exception as err:
            _LOGGER.error("Erreur lors de la récupération d'historique pour %s: %s", vin, err)
            return False

    async def async_fetch_history_for_all(self) -> None:
        """Récupère l'historique pour tous les VINs configurés."""
        tasks = [self.async_request_history_manual(vin) for vin in self.vins]
        await asyncio.gather(*tasks, return_exceptions=True)
        await self.async_request_refresh()

    async def _async_check_auto_request(self) -> None:
        """Vérifie si un request_update doit être déclenché automatiquement.
        
        Logique:
        - Chaque 15 min (interne), vérifie si on doit déclencher en avance
        - Si delai >= advance_hours, déclenche vehicle.request_new_report()
        """
        now = dt_util.now()
        vehicles = await self.connection.list_vehicles()
        vehicles_by_vin = {v.vin: v for v in vehicles}

        for vin in self.vins:
            next_request_at = self.get_next_request_at(vin)
            if not next_request_at or now < next_request_at:
                continue

            retry_not_before = self._auto_request_retry_not_before.get(vin)
            if retry_not_before and now < retry_not_before:
                _LOGGER.debug(
                    "Auto request ignoré pour %s jusqu'à %s (backoff 429)",
                    vin,
                    retry_not_before,
                )
                continue

            vehicle = vehicles_by_vin.get(vin)
            if not vehicle:
                continue

            try:
                _LOGGER.debug(
                    "Déclenchement auto de request_update pour %s (prévu à %s)",
                    vin,
                    next_request_at,
                )
                result = await vehicle.request_new_report()
                self._last_request_at[vin] = now
                self._auto_request_retry_not_before.pop(vin, None)
                _LOGGER.debug("Request update auto déclenché pour %s: %s", vin, result)

                # Pas de refresh immédiat ici: les données seront récupérées au scan planifié.
            except Exception as err:
                err_str = str(err)
                if "429" in err_str:
                    backoff_until = now + timedelta(hours=1)
                    self._auto_request_retry_not_before[vin] = backoff_until
                    _LOGGER.warning(
                        "Auto request rate-limited pour %s, pause jusqu'à %s: %s",
                        vin,
                        backoff_until,
                        err,
                    )
                else:
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
            self._last_request_at[vin] = dt_util.now()  # Stocke un datetime aware
            _LOGGER.debug("Réponse request_update manuel pour %s: %s", vin, result)

            # Programme une récupération différée après demande manuelle.
            self._schedule_delayed_refresh_after_manual_request(vin)
            return True

        except Exception as err:
            _LOGGER.error(f"Erreur lors du manual request_update pour {vin}: {err}")
            return False

    def _manual_request_delay(self) -> timedelta:
        """Délai avant récupération après demande manuelle de rapport.

        Basé sur l'option utilisateur (minutes), plafonné par l'intervalle configuré.
        """
        requested_delay = timedelta(minutes=max(1, self._manual_request_refresh_delay_minutes))
        interval_cap = SCAN_INTERVAL_MAP.get(self.scan_interval_key, requested_delay)
        return min(requested_delay, interval_cap)

    def _schedule_delayed_refresh_after_manual_request(self, vin: str) -> None:
        """Planifie un refresh différé après un request_update manuel."""
        previous = self._pending_manual_refresh.pop(vin, None)
        if previous:
            previous.cancel()

        delay = self._manual_request_delay()

        def _run_refresh() -> None:
            self._pending_manual_refresh.pop(vin, None)
            _LOGGER.info(
                "Exécution de la récupération programmée après request_update (VIN=%s)",
                vin,
            )
            self.hass.async_create_task(self.async_request_refresh())

        handle = self.hass.loop.call_later(delay.total_seconds(), _run_refresh)
        self._pending_manual_refresh[vin] = handle
        _LOGGER.info(
            "Récupération programmée pour VIN %s dans %s",
            vin,
            delay,
        )

    def cancel_scheduled_manual_refreshes(self) -> None:
        """Annule les récupérations programmées."""
        for handle in self._pending_manual_refresh.values():
            handle.cancel()
        self._pending_manual_refresh.clear()
