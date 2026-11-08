# SENEC.Home (local) for Home Assistant

Shows the live values of a SENEC.Home storage system in Home Assistant. It
reads them directly from the unit in your network (`https://<ip>/lala.cgi`,
the same source as the unit's own web page): no SENEC account, no cloud.

Tested with a SENEC.Home (system type 21, firmware 0842, 2 battery modules)
and Home Assistant 2026.10.

## What you get

Every 10 seconds:

| Shown by default | Diagnostic (sensor page) | Disabled, enable if needed |
|---|---|---|
| House consumption, solar power | Battery voltage/current | Phase voltages and currents |
| Grid power (+ import / − export), grid import, grid export | Grid frequency | String voltages and currents |
| Battery power (+ charging / − discharging), charging, discharging | Power per phase | Controller temperature |
| Battery charge (%) | Power per string (MPP tracker) | |
| System state (as on the unit, e.g. "AKKU LEER"; code as attribute) | Battery and case temperature, inverter power limit | |

**Energy totals (kWh)** for solar, house, grid import/export and battery
charged/discharged. This firmware keeps no totals of its own, so the
integration adds them up from the power values. They survive restarts; gaps
longer than 5 minutes (unit unreachable, Home Assistant off) are not filled in.
Use them in **Settings → Dashboards → Energy**:

- Grid consumption: *Grid import energy*; return to grid: *Grid export energy*
- Solar production: *Solar energy*
- Home battery: *Battery charged energy* / *Battery discharged energy*

## Install

**Manually:** copy `custom_components/senec_local` into the `config/custom_components/`
folder of your Home Assistant, then restart it.

**HACS:** HACS → ⋮ → Custom repositories → add this repository's URL as type
"Integration", install "SENEC.Home (local)", restart.

Then **Settings → Devices & services → Add integration → SENEC.Home (local)**
and enter the unit's IP address (e.g. `192.168.178.154`). Give the unit a fixed
IP in your router; if it changes anyway, use *Reconfigure* on the integration.

## Development

```sh
uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python pytest-homeassistant-custom-component
.venv/bin/python -m pytest -q
```
