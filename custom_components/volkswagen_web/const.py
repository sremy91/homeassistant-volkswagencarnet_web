"""Constants pour le composant Volkswagen Web."""

from datetime import timedelta

DOMAIN = "volkswagen_web"

# Configuration
CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_NAME = "name"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_SCAN_TIME = "scan_time"           # HH:MM (ex: "14:30")
CONF_SCAN_WEEKDAY = "scan_weekday"     # 0-6 (Monday-Sunday)
CONF_SCAN_DAY_OF_MONTH = "scan_day_of_month"  # 1-31
CONF_AUTO_REQUEST_UPDATE = "auto_request_update"
CONF_REQUEST_ADVANCE_HOURS = "request_advance_hours"
CONF_FETCH_HISTORY_ON_SETUP = "fetch_history_on_setup"
CONF_VEHICLES = "vehicles"

# Valeurs d'intervalle de scan
SCAN_INTERVAL_DAILY = "daily"              # Avec heure
SCAN_INTERVAL_WEEKLY = "weekly"            # Avec jour + heure
SCAN_INTERVAL_BIWEEKLY = "biweekly"        # Avec jour + heure (tous les 14j)
SCAN_INTERVAL_MONTHLY = "monthly"          # Avec jour + heure

SCAN_INTERVAL_MAP = {
    SCAN_INTERVAL_DAILY: timedelta(days=1),
    SCAN_INTERVAL_WEEKLY: timedelta(weeks=1),
    SCAN_INTERVAL_BIWEEKLY: timedelta(days=14),
    SCAN_INTERVAL_MONTHLY: timedelta(days=30),
}

# Jours de la semaine (pour affichage)
WEEKDAYS = {
    0: "Lundi",
    1: "Mardi",
    2: "Mercredi",
    3: "Jeudi",
    4: "Vendredi",
    5: "Samedi",
    6: "Dimanche",
}

WEEKDAYS_EN = {
    0: "Monday",
    1: "Tuesday",
    2: "Wednesday",
    3: "Thursday",
    4: "Friday",
    5: "Saturday",
    6: "Sunday",
}

DEFAULT_SCAN_INTERVAL = SCAN_INTERVAL_DAILY
DEFAULT_SCAN_TIME = "10:00"
DEFAULT_SCAN_WEEKDAY = 0           # Lundi
DEFAULT_SCAN_DAY_OF_MONTH = 1      # 1er du mois
DEFAULT_AUTO_REQUEST_UPDATE = True
DEFAULT_REQUEST_ADVANCE_HOURS = 1
DEFAULT_FETCH_HISTORY_ON_SETUP = True

# Données interne
DATA_COORDINATOR = "coordinator"
DATA_VW_CONN = "vw_connection"
DATA_UNDO_UPDATE_LISTENER = "undo_update_listener"
DATA_LAST_REQUEST_AT = "last_request_at"

# Plateformes
PLATFORMS = ["sensor", "button", "camera"]

# Service (futur)
SERVICE_REQUEST_REPORT = "request_vehicle_report"

# Entités & symboles
ATTR_VIN = "vin"
ATTR_COMPONENT = "component"
ATTR_ATTRIBUTE = "attribute"

# Entity categories
ENTITY_CATEGORY_DIAGNOSTIC = "diagnostic"
ENTITY_CATEGORY_CONFIG = "config"
