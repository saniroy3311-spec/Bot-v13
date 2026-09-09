import numpy as np
import pandas as pd
import os
import config

class IndicatorEngine:
    @staticmethod
    def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        c, h, l, v = df['close'], df['high'], df['low'], df['volume']
        df['ema9']   = c.ewm(span=9, adjust=False).mean()
        df['ema15']  = c.ewm(span=15, adjust=False).mean()
        df['ema21']  = c.ewm(span=21, adjust=False).mean()
        df['ema50']  = c.ewm(span=50, adjust=False).mean()
        df['ema100'] = c.ewm(span=100, adjust=False).mean()
        df['ema200'] = c.ewm(span=200, adjust=False).mean()
        df['vol_sma'] = v.rolling(20).mean()

        # ATR
        tr1, tr2, tr3 = h - l, (h - c.shift()).abs(), (l - c.shift()).abs()
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        df['atr'] = tr.ewm(alpha=1/14, adjust=False).mean()

        # RSI
        delta = c.diff()
        gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        rs = gain / (loss + 1e-10)
        df['rsi'] = 100 - (100 / (1 + rs))

        # ADX
        up_move = h - h.shift()
        down_move = l.shift() - l
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
        plus_di = 100 * (pd.Series(plus_dm, index=df.index).ewm(alpha=1/14, adjust=False).mean() / (df['atr'] + 1e-10))
        minus_di = 100 * (pd.Series(minus_dm, index=df.index).ewm(alpha=1/14, adjust=False).mean() / (df['atr'] + 1e-10))
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
        df['adx'] = dx.ewm(alpha=1/14, adjust=False).mean()

        # 30m Slope Angle in Degrees on EMA15
        ema15_delta = (df['ema15'] - df['ema15'].shift(3)) / (3 * (df['atr'] + 1e-10))
        df['ema_angle'] = np.degrees(np.arctan(ema15_delta * 2.0))
        return df

    @staticmethod
    def evaluate_signals(df: pd.DataFrame, config):
        if len(df) < 50: return None
        i = len(df) - 1
        c, o, h, l = df['close'].iloc[i], df['open'].iloc[i], df['high'].iloc[i], df['low'].iloc[i]
        c_prev, o_prev, h_prev, l_prev = df['close'].iloc[i-1], df['open'].iloc[i-1], df['high'].iloc[i-1], df['low'].iloc[i-1]
        
        ema9, ema15, ema100 = df['ema9'].iloc[i], df['ema15'].iloc[i], df['ema100'].iloc[i]
        vol, vol_sma = df['volume'].iloc[i], df['vol_sma'].iloc[i]
        atr, rsi, adx, angle = df['atr'].iloc[i], df['rsi'].iloc[i], df['adx'].iloc[i], df['ema_angle'].iloc[i]

        candle_range = h - l
        body_size = abs(c - o)
        if candle_range < config.FILTER_ATR_MULT * atr or body_size < config.FILTER_BODY_MULT * candle_range:
            return None

        # Anti-Exhaustion Guard (Stretched > 2.5x ATR from EMA15)
        max_ema_dist = float(getattr(config, "MAX_EMA_DIST_ATR", 2.5)) * atr
        if abs(c - ema15) > max_ema_dist:
            return None

        # Macro Trend Alignment: EMA 100 Baseline + Steep EMA 15 Angle (> 15°)
        is_bull_trend = angle > 15.0 and c > ema100 and ema9 > ema15
        is_bear_trend = angle < -15.0 and c < ema100 and ema9 < ema15

        if not is_bull_trend and not is_bear_trend:
            return None

        sl_pts = max(config.MIN_SL_POINTS, min(config.MAX_SL_POINTS, config.SL_ATR_MULT * atr))
        tp_pts = sl_pts * config.TREND_RR

        # 1. ENGINE 1: Railway Track Retest on EMA 15
        b1, b2 = abs(c_prev - o_prev), abs(c - o)
        is_rw_body = (b1 >= 0.20 * atr) and (b2 >= 0.20 * atr)
        rw_bull = is_rw_body and (c_prev < o_prev) and (c > o) and (l_prev <= ema15 + 0.35 * atr)
        rw_bear = is_rw_body and (c_prev > o_prev) and (c < o) and (h_prev >= ema15 - 0.35 * atr)

        if is_bull_trend and rw_bull:
            return {'side': 'LONG', 'strategy': 'E1_RAILWAY_EMA15', 'tp_pts': tp_pts, 'sl_pts': sl_pts, 'adx': adx, 'rsi': rsi}
        elif is_bear_trend and rw_bear:
            return {'side': 'SHORT', 'strategy': 'E1_RAILWAY_EMA15', 'tp_pts': tp_pts, 'sl_pts': sl_pts, 'adx': adx, 'rsi': rsi}

        # 2. ENGINE 2: Shallow Trend Pullback into EMA 15
        if is_bull_trend and (40.0 <= rsi <= 65.0) and l <= ema15 + 0.25 * atr and c > ema15:
            return {'side': 'LONG', 'strategy': 'E2_PULLBACK_EMA15', 'tp_pts': tp_pts, 'sl_pts': sl_pts, 'adx': adx, 'rsi': rsi}
        elif is_bear_trend and (35.0 <= rsi <= 60.0) and h >= ema15 - 0.25 * atr and c < ema15:
            return {'side': 'SHORT', 'strategy': 'E2_PULLBACK_EMA15', 'tp_pts': tp_pts, 'sl_pts': sl_pts, 'adx': adx, 'rsi': rsi}

        # 3. ENGINE 3: Volume Momentum Expansion
        if vol > 1.30 * vol_sma and adx > 18.0:
            if is_bull_trend and c > ema9 and c > h_prev:
                return {'side': 'LONG', 'strategy': 'E3_VOL_EXPANSION', 'tp_pts': tp_pts, 'sl_pts': sl_pts, 'adx': adx, 'rsi': rsi}
            elif is_bear_trend and c < ema9 and c < l_prev:
                return {'side': 'SHORT', 'strategy': 'E3_VOL_EXPANSION', 'tp_pts': tp_pts, 'sl_pts': sl_pts, 'adx': adx, 'rsi': rsi}

        return None
