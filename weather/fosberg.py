"""
Fosberg Fire Weather Index (FFWI).

Formula from Fosberg (1978), implemented as a pure function.

Thresholds (approximate):
  < 10  — low risk
  10–25 — moderate
  25–50 — high
  > 50  — very high / critical

Inputs: temperature in °F, relative humidity in %, wind speed in mph.
"""


def fosberg_fwi(temp_f: float, humidity_pct: float, wind_mph: float) -> float:
    """
    Compute Fosberg Fire Weather Index.

    Args:
        temp_f:       Air temperature in degrees Fahrenheit.
        humidity_pct: Relative humidity as a percentage (0–100).
        wind_mph:     Wind speed in miles per hour.

    Returns:
        FFWI value (non-negative float, typically 0–80 in the field).
    """
    rh = max(0.0, min(100.0, humidity_pct))

    # Fine fuel equilibrium moisture content (EMC)
    if rh < 10.0:
        emc = 0.03229 + 0.281073 * rh - 0.000578 * temp_f * rh
    elif rh < 50.0:
        emc = 2.22749 + 0.160107 * rh - 0.014784 * temp_f
    else:
        emc = 21.0606 + 0.005565 * rh ** 2 - 0.00035 * temp_f * rh - 0.483199 * rh

    emc = max(0.0, emc)

    # Fine fuel moisture content, capped at 30 %
    mc = min(30.0, 1.5 * emc)

    # Moisture damping factor (0 = very wet → 1 = bone dry)
    r = mc / 30.0
    eta = 1.0 - 2.0 * r + 1.5 * r ** 2 - 0.5 * r ** 3

    # Index: moisture factor × wind factor
    fwi = eta * (1.0 + wind_mph ** 2) ** 0.5

    return round(max(0.0, fwi), 2)
