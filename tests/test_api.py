"""Decoding the unit's values."""

import pytest

from custom_components.senec_local.api import decode


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("fl_4393945A", pytest.approx(295.16, abs=0.01)),
        ("fl_00000000", 0.0),
        ("fl_C3894BC8", pytest.approx(-274.59, abs=0.01)),
        ("u8_0F", 15),
        ("u1_0C03", 3075),
        ("i8_FF", -1),
        ("i8_11", 17),
        ("st_0842", "0842"),
        ("VARIABLE_NOT_FOUND", None),
        ("fl_zz", None),
        (None, None),
        (["u8_01", "VARIABLE_NOT_FOUND"], [1, None]),
    ],
)
def test_decode(raw, expected):
    assert decode(raw) == expected


def test_flatten(reply):
    assert reply["system_state"] == "AKKU LEER"
    assert reply["house_power"] == pytest.approx(3063.41, abs=0.01)
    # Grid import is positive; the split never gives -0.0.
    assert reply["grid_import_power"] == pytest.approx(2768.25, abs=0.01)
    assert str(reply["grid_export_power"]) == "0.0"
    assert str(reply["battery_discharge_power"]) == "0.0"
    assert reply["l2_power"] == pytest.approx(1903.93, abs=0.01)
    assert reply["mpp3_voltage"] == pytest.approx(145.51, abs=0.01)
    assert reply["device_id"] == "20316761110462487540422709"
