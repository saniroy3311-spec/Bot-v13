
def calculate_directional_brackets(side, fill_price, risk_points, rr_multiple=3.6):
    fill_price = float(fill_price)
    risk_points = float(risk_points)
    rr_multiple = float(rr_multiple)
    target_points = risk_points * rr_multiple
    
    if 'LONG' in str(side).upper() or 'BUY' in str(side).upper():
        sl = round(fill_price - risk_points, 1)
        tp = round(fill_price + target_points, 1)
    else:
        sl = round(fill_price + risk_points, 1)
        tp = round(fill_price - target_points, 1)
    return sl, tp

"""
strategy/signal.py — Bot v13
══════════════════════════════════════════════════════════════════════════════

Thin re-export layer so main.py can import from a clean 'strategy' namespace:

    from strategy.signal import evaluate, SignalType

The actual implementation lives in indicators/engine.py alongside the
indicator computation — keeping all Pine-parity signal logic in one place.

    evaluate(snap, has_position) -> Signal
        Maps 1:1 to Pine's entry conditions (trendLong / trendShort /
        rangeLong / rangeShort) evaluated at bar close with no position.

    SignalType  — NONE | TREND_LONG | TREND_SHORT | RANGE_LONG | RANGE_SHORT
    Signal      — dataclass(signal_type, is_long, is_trend, regime)
══════════════════════════════════════════════════════════════════════════════
"""

from indicators.engine import (   # noqa: F401  (re-exports)
    evaluate,
    SignalType,
    Signal,
    IndicatorSnapshot,
)
