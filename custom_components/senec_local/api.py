"""Client for the local web API of a SENEC.Home storage system.

The unit answers a POST to https://<host>/lala.cgi: the request names the
values wanted (as empty strings), the reply fills them in, each encoded as
"<type>_<hex>" -- for example "fl_4393945A" is the float 295.16. No login is
needed for reading. The certificate is self-signed, so it is not verified.
"""

from __future__ import annotations

import asyncio
import json
import struct
from typing import Any

import aiohttp

# What the integration asks for on every poll.
QUERY: dict[str, dict[str, str]] = {
    "ENERGY": {
        "STAT_STATE": "",
        "GUI_HOUSE_POW": "",
        "GUI_INVERTER_POWER": "",
        "GUI_GRID_POW": "",
        "GUI_BAT_DATA_POWER": "",
        "GUI_BAT_DATA_FUEL_CHARGE": "",
        "GUI_BAT_DATA_VOLTAGE": "",
        "GUI_BAT_DATA_CURRENT": "",
    },
    "PM1OBJ1": {"FREQ": "", "U_AC": "", "I_AC": "", "P_AC": ""},
    "PV1": {"POWER_RATIO": "", "MPP_POWER": "", "MPP_VOL": "", "MPP_CUR": ""},
    "TEMPMEASURE": {"BATTERY_TEMP": "", "CASE_TEMP": "", "MCU_TEMP": ""},
    "FACTORY": {"SYS_TYPE": "", "DEVICE_ID": ""},
    "WIZARD": {"APPLICATION_VERSION": ""},
    "BMS": {"NR_INSTALLED": ""},
}

# Texts of ENERGY.STAT_STATE, as the unit's own web page shows them (DE-de.js).
SYSTEM_STATES: dict[int, str] = {
    0: "INITIALZUSTAND", 1: "KEINE KOMMUNIKATION LADEGERAET",
    2: "FEHLER LEISTUNGSMESSGERAET", 3: "RUNDSTEUEREMPFAENGER", 4: "ERSTLADUNG",
    5: "WARTUNGSLADUNG", 6: "WARTUNGSLADUNG FERTIG", 7: "WARTUNG NOTWENDIG",
    8: "MAN. SICHERHEITSLADUNG", 9: "SICHERHEITSLADUNG FERTIG", 10: "VOLLLADUNG",
    11: "AUSGLEICHSLADUNG: LADEN", 12: "SULFATLADUNG: LADEN", 13: "AKKU VOLL",
    14: "LADEN", 15: "AKKU LEER", 16: "ENTLADEN", 17: "PV + ENTLADEN",
    18: "NETZ + ENTLADEN", 19: "PASSIV", 20: "AUSGESCHALTET", 21: "EIGENVERBRAUCH",
    22: "NEUSTART", 23: "MAN. AUSGLEICHSLADUNG: LADEN", 24: "MAN. SULFATLADUNG: LADEN",
    25: "SICHERHEITSLADUNG", 26: "AKKU-SCHUTZBETRIEB", 27: "EG FEHLER", 28: "EG LADEN",
    29: "EG ENTLADEN", 30: "EG PASSIV", 31: "EG LADEN VERBOTEN",
    32: "EG ENTLADEN VERBOTEN", 33: "NOTLADUNG", 34: "SOFTWAREAKTUALISIERUNG",
    35: "FEHLER: NA-SCHUTZ", 36: "FEHLER: NA-SCHUTZ NETZ",
    37: "FEHLER: NA-SCHUTZ HARDWARE", 38: "KEINE SERVERVERBINDUNG", 39: "BMS FEHLER",
    40: "WARTUNG: FILTER", 41: "ABSCHALTUNG LITHIUM", 42: "WARTE AUF ÜBERSCHUSS",
    43: "KAPAZITÄTSTEST: LADEN", 44: "KAPAZITÄTSTEST: ENTLADEN",
    45: "MAN. SULFATLADUNG: WARTEN", 46: "MAN. SULFATLADUNG: FERTIG",
    47: "MAN. SULFATLADUNG: FEHLER", 48: "AUSGLEICHSLADUNG: WARTEN",
    49: "NOTLADUNG: FEHLER", 50: "MAN: AUSGLEICHSLADUNG: WARTEN",
    51: "MAN: AUSGLEICHSLADUNG: FEHLER", 52: "MAN: AUSGLEICHSLADUNG: FERTIG",
    53: "AUTO: SULFATLADUNG: WARTEN", 54: "LADESCHLUSSPHASE",
    55: "BATTERIETRENNSCHALTER AUS", 56: "PEAK-SHAVING: WARTEN",
    57: "FEHLER LADEGERAET", 58: "NPU-FEHLER", 59: "BMS OFFLINE",
    60: "WARTUNGSLADUNG FEHLER", 61: "MAN. SICHERHEITSLADUNG FEHLER",
    62: "SICHERHEITSLADUNG FEHLER", 63: "KEINE MASTERVERBINDUNG",
    64: "LITHIUM SICHERHEITSMODUS AKTIV", 65: "LITHIUM SICHERHEITSMODUS BEENDET",
    66: "FEHLER BATTERIESPANNUNG", 67: "BMS DC AUSGESCHALTET", 68: "NETZINITIALISIERUNG",
    69: "NETZSTABILISIERUNG", 70: "FERNABSCHALTUNG", 71: "OFFPEAK-LADEN",
    72: "FEHLER HALBBRÜCKE", 73: "BMS: FEHLER BETRIEBSTEMPERATUR",
    74: "FACTORY SETTINGS NICHT GEFUNDEN", 75: "NETZERSATZBETRIEB",
    76: "NETZERSATZBETRIEB AKKU LEER", 77: "NETZERSATZBETRIEB FEHLER",
    78: "INITIALISIERUNG", 79: "INSTALLATIONSMODUS", 80: "NETZAUSFALL",
    81: "BMS UPDATE ERFORDERLICH", 82: "BMS KONFIGURATION ERFORDERLICH",
    83: "ISOLATIONSTEST", 84: "SELBSTTEST", 85: "EXTERNE STEUERUNG",
    86: "TEMPERATUR SENSOR FEHLER", 87: "LADEN GESPERRT", 88: "ENTLADEN GESPERRT",
    89: "RESERVEKAPAZITÄT", 90: "SELBSTTEST FEHLER", 91: "ISOLATIONSFEHLER",
    92: "PV-MODUS", 93: "FERNABSCHALTUNG NETZBETREIBER", 94: "FEHLER DRM0",
    95: "BATTERIEDIAGNOSE", 96: "BALANCING", 97: "SICHERHEITSENTLADUNG",
    98: "BMS FEHLER - MODULUNGLEICHGEWICHT", 99: "AUFWACHLADUNG",
    100: "SOX-KALIBRIERUNG",
}


class SenecError(Exception):
    """The unit could not be read."""


def decode(value: Any) -> Any:
    """Turn one encoded value (or a list of them) into a Python value.

    Returns None for anything the unit does not know ("VARIABLE_NOT_FOUND")
    or that cannot be parsed, so a missing value never breaks a whole poll.
    """
    if isinstance(value, list):
        return [decode(item) for item in value]
    if not isinstance(value, str) or "_" not in value:
        return None
    kind, raw = value.split("_", 1)
    try:
        if kind == "fl":
            return struct.unpack(">f", bytes.fromhex(raw.zfill(8)))[0]
        if kind.startswith("u"):
            return int(raw, 16)
        if kind.startswith("i"):
            number, bits = int(raw, 16), len(raw) * 4
            return number - (1 << bits) if number >> (bits - 1) else number
        if kind == "st":
            return raw
    except ValueError:
        return None
    return None


def _at(values: Any, index: int) -> Any:
    if isinstance(values, list) and index < len(values):
        return values[index]
    return None


def _split(value: float | None) -> tuple[float | None, float | None]:
    """(positive part, negative part as a positive number) -- never -0.0."""
    if value is None:
        return None, None
    return (value, 0.0) if value > 0 else (0.0, -value if value < 0 else 0.0)


def _flatten(raw: dict[str, Any]) -> dict[str, Any]:
    """Map the reply onto the flat keys the sensors use."""

    def get(section: str, key: str) -> Any:
        return decode(raw.get(section, {}).get(key))

    data: dict[str, Any] = {
        "system_state_code": get("ENERGY", "STAT_STATE"),
        "house_power": get("ENERGY", "GUI_HOUSE_POW"),
        "solar_power": get("ENERGY", "GUI_INVERTER_POWER"),
        # Positive: drawn from the grid; negative: fed into it.
        "grid_power": get("ENERGY", "GUI_GRID_POW"),
        # Positive: charging; negative: discharging.
        "battery_power": get("ENERGY", "GUI_BAT_DATA_POWER"),
        "battery_soc": get("ENERGY", "GUI_BAT_DATA_FUEL_CHARGE"),
        "battery_voltage": get("ENERGY", "GUI_BAT_DATA_VOLTAGE"),
        "battery_current": get("ENERGY", "GUI_BAT_DATA_CURRENT"),
        "grid_frequency": get("PM1OBJ1", "FREQ"),
        "power_ratio": get("PV1", "POWER_RATIO"),
        "battery_temperature": get("TEMPMEASURE", "BATTERY_TEMP"),
        "case_temperature": get("TEMPMEASURE", "CASE_TEMP"),
        "mcu_temperature": get("TEMPMEASURE", "MCU_TEMP"),
        "battery_modules": get("BMS", "NR_INSTALLED"),
        "system_type": get("FACTORY", "SYS_TYPE"),
        "device_id": get("FACTORY", "DEVICE_ID"),
        "firmware": get("WIZARD", "APPLICATION_VERSION"),
    }
    code = data["system_state_code"]
    data["system_state"] = (
        SYSTEM_STATES.get(code, f"UNBEKANNT ({code})") if code is not None else None
    )

    # Split the signed values into two always-positive ones (the energy
    # dashboard wants import and export as separate meters).
    data["grid_import_power"], data["grid_export_power"] = _split(data["grid_power"])
    data["battery_charge_power"], data["battery_discharge_power"] = _split(
        data["battery_power"]
    )

    for name, (section, key) in {
        "power": ("PM1OBJ1", "P_AC"),
        "voltage": ("PM1OBJ1", "U_AC"),
        "current": ("PM1OBJ1", "I_AC"),
    }.items():
        values = get(section, key)
        for phase in range(3):
            data[f"l{phase + 1}_{name}"] = _at(values, phase)

    for name, key in {"power": "MPP_POWER", "voltage": "MPP_VOL", "current": "MPP_CUR"}.items():
        values = get("PV1", key)
        for tracker in range(3):
            data[f"mpp{tracker + 1}_{name}"] = _at(values, tracker)

    return data


class SenecClient:
    """Reads one SENEC unit."""

    def __init__(self, session: aiohttp.ClientSession, host: str) -> None:
        self.host = host
        self._session = session
        self._url = f"https://{host}/lala.cgi"

    async def async_get_data(self) -> dict[str, Any]:
        """Poll the unit once and return the decoded values."""
        try:
            async with asyncio.timeout(10):
                response = await self._session.post(
                    self._url, json=QUERY, ssl=False
                )
                response.raise_for_status()
                # The unit answers with text/html, so parse the body ourselves.
                raw = json.loads(await response.text())
        except (aiohttp.ClientError, TimeoutError) as err:
            raise SenecError(f"Cannot reach SENEC at {self.host}: {err}") from err
        except ValueError as err:
            raise SenecError(f"Unexpected answer from {self.host}: {err}") from err
        if not isinstance(raw, dict) or "ENERGY" not in raw:
            raise SenecError(f"{self.host} does not look like a SENEC unit")
        return _flatten(raw)
