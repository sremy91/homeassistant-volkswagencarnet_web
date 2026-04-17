# Mise à jour : Scan Intervals avancés avec horaires configurables

## Changements effectués

### 1. **const.py** - Nouveaux intervalles et configurations
```python
# Nouveaux intervalles disponibles
SCAN_INTERVAL_DAILY = "daily"              # Avec heure
SCAN_INTERVAL_WEEKLY = "weekly"            # Avec jour + heure  
SCAN_INTERVAL_BIWEEKLY = "biweekly"        # Avec jour + heure (14 jours)
SCAN_INTERVAL_MONTHLY = "monthly"          # Avec jour + heure

# Nouvelles clés de configuration
CONF_SCAN_TIME = "scan_time"               # HH:MM (ex: "14:30")
CONF_SCAN_WEEKDAY = "scan_weekday"         # 0-6 (lundi-dimanche)
CONF_SCAN_DAY_OF_MONTH = "scan_day_of_month"  # 1-31

# Dictionnaire des jours de la semaine
WEEKDAYS = {0: "Lundi", 1: "Mardi", ..., 6: "Dimanche"}
WEEKDAYS_EN = {0: "Monday", 1: "Tuesday", ..., 6: "Sunday"}
```

### 2. **config_flow.py** - Flow restructuré en 4 étapes

#### Étapes du ConfigFlow:
1. **async_step_user** — Authentification
2. **async_step_scan_settings** — Sélectionne l'intervalle (daily/weekly/biweekly/monthly)
3. **async_step_schedule_time** — Configure l'heure et le jour
   - Daily: affiche input heure
   - Weekly/Biweekly: affiche sélecteur jour semaine + heure
   - Monthly: affiche sélecteur jour mois + heure
4. **async_step_vehicles** — Sélectionne les véhicules

#### OptionsFlow restructuré en 2 étapes:
1. **async_step_init** — Modifie l'intervalle + auto_request
2. **async_step_schedule_options** — Modifie l'heure/jour si intervalle changé

### 3. **coordinator.py** - Logique de planification intelligente

```python
def _calculate_next_update_interval() -> timedelta:
    """Calcule dynamiquement le délai jusqu'au prochain refresh"""
    
    # DAILY: aujourd'hui à scan_time (ou demain si l'heure est passée)
    # WEEKLY: ce jour de semaine à scan_time (ou semaine prochaine)
    # BIWEEKLY: cycle de 14 jours basé sur date de référence
    # MONTHLY: ce jour du mois à scan_time (ou mois prochain)
```

**Comportement:**
- Calcul automatique du délai jusqu'au prochain refresh
- Gestion des cas limites (jours invalides comme 31 février)
- Logs de debug pour tracer les calculs
- Minimum 1 minute, maximum paramétré par intervalle

### 4. **Traductions** - FR et EN
- Nouvelles sections pour `schedule_time` et `schedule_options`
- Descriptions claires pour chaque intervalle
- Support multilingue français/anglais

## Exemples d'utilisation

### Configuration quotidienne
- Intervalle: **quotidienne**
- Heure: **14:30**
→ Refresh each day at 14:30

### Configuration hebdomadaire
- Intervalle: **hebdomadaire**
- Jour: **Lundi**
- Heure: **10:00**
→ Refresh every Monday at 10:00

### Configuration mensuelle
- Intervalle: **mensuelle**
- Jour: **1er**
- Heure: **09:00**
→ Refresh on the 1st of each month at 09:00

## Comportement après modification

Les paramètres peuvent être modifiés via **Options** dans Home Assistant:
- Changer l'intervalle → affiche l'étape de configuration horaire
- Changer l'heure/jour → mise à jour immédiate
- Aucune interruption du service

## Tests recommandés

1. ✅ DAILY with various times
2. ✅ WEEKLY with each weekday
3. ✅ BIWEEKLY (vérifier cycle 14j)
4. ✅ MONTHLY edge cases (31 Feb → 28 Feb)
5. ✅ Options flow modifications
6. ✅ Refresh timing accuracy

---

**Version:** 0.2.0  
**Date:** April 17, 2026  
**Status:** ✅ Prêt pour test
