# Volkswagen Connect Web - A Home Assistant custom component for VW Connect Web (EU only)

Custom component for Home Assistant that integrates the **Volkswagen France web portal** (`www.volkswagen.fr`) 
into Home Assistant using the [`volkswagencarnet_web`](https://github.com/sremy91/volkswagencarnet_web) Python module.

## Features

- 🚗 **Per-vehicle entities** grouped by VIN/device
- 📊 **Vehicle Health sensors**: mileage, last report date, status by system, contracts, service partner
- 🧭 **Diagnostic sensors**: VIN, model, license plate, report summary
- 📷 **Images support**: camera + one image entity per available vehicle image
- 🔘 **Action buttons**: request new report + fetch history
- ⚙️ **Configurable sync**: hourly or monthly refresh intervals
- 🔄 **Auto report request scheduling** with pre-trigger option
- 🕘 **Optional history fetch on setup/startup**
- 🌐 **Multi-language**: French (FR) and English (EN)

## Installation

### Manual

1. Clone this repository:
   ```bash
   git clone https://github.com/sremy91/homeassistant-volkswagencarnet_web.git
   cd homeassistant-volkswagencarnet_web
   ```

2. Copy the `volkswagen_web` directory to your Home Assistant `custom_components` folder:
   ```bash
   cp -r custom_components/volkswagen_web ~/.homeassistant/custom_components/
   ```

3. Restart Home Assistant

### Via HACS

With HACS:

1. In Home Assistant, go to **Settings** → **Devices & Services** → **Custom Repositories**
2. Add: `https://github.com/sremy91/homeassistant-volkswagencarnet_web` (Type: Integration)
3. Search for "Volkswagen Connect Web" and install
4. Restart Home Assistant

## Configuration

### Step 1: Add the integration

1. In Home Assistant, go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for "Volkswagen Connect Web"

### Step 2: Enter credentials

- **Email**: Your Volkswagen France web account e-mail
- **Password**: Your password
- **Name** (optional): Custom name for this integration

### Step 3: Configure sync settings

- **Sync interval**: Choose between:
  - **Hourly** (recommended): Refresh every 1 hour
  - **Monthly**: Refresh every 30 days
- **Fetch history on startup**: fetch warning lights history after setup/startup
- **Auto health reports**: Enable automatic vehicle report requests
- **Pre-trigger hours**: Hours to request the report in advance (1-24, default: 1)
  - Example: If set to `1` hour and a report is due at 18:00, it will be triggered at 17:00

### Step 4: Select vehicles

Choose which vehicles to integrate into Home Assistant.

## Available Entities

### Sensors

| Sensor | Device Class | Unit | Description |
|---|---|---|---|
| `vin` | — | — | Vehicle VIN |
| `mileage_km` | `distance` | km | Current mileage |
| `last_report_timestamp` | `timestamp` | — | Datetime of last vehicle report |
| `model_name` | — | — | Vehicle commercial model |
| `license_plate` | — | — | License plate number |
| `vehicle_status` | — | — | Aggregated vehicle status |
| `status_freins` | — | — | Brake system status |
| `status_pneus` | — | — | Tyre system status |
| `status_transmission` | — | — | Transmission status |
| `status_feux_de_route` | — | — | Lighting system status |
| `status_assistants` | — | — | Driver assistance status |
| `status_confort` | — | — | Comfort system status |
| `warninglights_last` | — | — | Number of active warning lights |
| `contracts` | — | — | Number of connected contracts |
| `service_partner` | — | — | Service partner info |

### Buttons

| Button | Description |
|---|---|
| `request_update` | Request a new vehicle health report |
| `request_history` | Fetch warning lights history |

### Camera

| Camera | Description |
|---|---|
| `vehicle_images` | Exterior images from VILMA |

### Image

| Image | Description |
|---|---|
| `vehicle_image` | One entity per image (Image 1, Image 2, ...) |

## Services

### `request_vehicle_report`

Request a new health report for a specific vehicle.

**Parameters:**
- `device_id` (required): Vehicle to request report for

**Example automation:**
```yaml
- alias: "Request VW Health Report Daily"
  trigger:
    platform: time
    at: "07:00:00"
  action:
    service: volkswagen_web.request_vehicle_report
    data:
      device_id: "sensor.volkswagen_fr_mileage_km"  # Device ID of the vehicle
```

## Advanced Options

After initial setup, you can modify:

1. **Sync interval**: Adjust how frequently data is refreshed
2. **Fetch history on startup**: Enable/disable history retrieval when integration starts
3. **Auto health reports**: Enable/disable automatic report requests
4. **Pre-trigger hours**: Change the advance warning time

Go to **Settings** → **Devices & Services** → **Volkswagen Connect Web** → Click your device → **Options**

## Troubleshooting

### Configuration rejected: "Invalid credentials"
- Verify your email and password
- Try logging in to the Volkswagen France website manually to confirm access

### No vehicles found
- Ensure your account has at least one registered vehicle on the Volkswagen France portal
- Try re-authenticating

### Data is not refreshing
- Check your configured sync interval
- In Home Assistant logs, look for `volkswagen_web` errors
- Verify your internet connection

### Images not loading
- VILMA (image service) may be temporarily unavailable
- Restart the integration

### Contracts show `0 contract(s)`
- Trigger a manual `New report` (`Nouveau rapport`) and refresh once the report is available
- Verify contracts are visible in the Volkswagen web portal account
- Some accounts expose contracts with delay depending on backend sync

## License

GPLv3 - See LICENSE file

## Credits

- [robinostlund](https://github.com/robinostlund) for the original `homeassistant-volkswagencarnet` component (API-based)
- [sremy91](https://github.com/sremy91) for the web-only `volkswagencarnet_web` module and this component

## Support

For issues, questions, or suggestions, please open an issue on the [GitHub repository](https://github.com/sremy91/homeassistant-volkswagencarnet_web/issues).
