import numpy as np
import pandas as pd

class IndicatorEngine:
    @staticmethod
    def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        c, h, l, v = df['close'], df['high'], df['low'], df['volume']
        df['ema9'] = c.ewm(span=9, adjust=False).mean()
        df['ema21'] = c.ewm(span=21, adjust=False).mean()
        df['ema50'] = c.ewm(span=50, adjust=False).mean()
        df['ema200'] = c.ewm(span=200, adjust=False).mean()
        df['htf_ema50'] = c.ewm(span=250, adjust=False).mean()
        df['htf_slope'] = df['htf_ema50'].diff(15)
        df['vol_sma'] = v.rolling(20).mean()
        df['don_h'] = h.rolling(24).max()
        df['don_l'] = l.rolling(24).min()

        tr1, tr2, tr3 = h - l, (h - c.shift()).abs(), (l - c.shift()).abs()
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        df['atr'] = tr.ewm(alpha=1/14, adjust=False).mean()

        delta = c.diff()
        gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        rs = gain / (loss + 1e-10)
        df['rsi'] = 100 - (100 / (1 + rs))

        up_move = h - h.shift()
        down_move = l.shift() - l
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
        plus_di = 100 * (pd.Series(plus_dm, index=df.index).ewm(alpha=1/14, adjust=False).mean() / (df['atr'] + 1e-10))
        minus_di = 100 * (pd.Series(minus_dm, index=df.index).ewm(alpha=1/14, adjust=False).mean() / (df['atr'] + 1e-10))
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
        df['adx'] = dx.ewm(alpha=1/14, adjust=False).mean()
        return df

    @staticmethod
    def evaluate_signals(df: pd.DataFrame, config):
        if len(df) < 50: return None
        i = len(df) - 1
        c, o, h, l = df['close'].iloc[i], df['open'].iloc[i], df['high'].iloc[i], df['low'].iloc[i]
        h_prev, l_prev = df['high'].iloc[i-1], df['low'].iloc[i-1]
        ema9, ema21, ema50, ema200 = df['ema9'].iloc[i], df['ema21'].iloc[i], df['ema50'].iloc[i], df['ema200'].iloc[i]
        htf_slope = df['htf_slope'].iloc[i]
        vol, vol_sma = df['volume'].iloc[i], df['vol_sma'].iloc[i]
        don_h, don_l = df['don_h'].iloc[i-1], df['don_l'].iloc[i-1]
        atr, rsi, adx = df['atr'].iloc[i], df['rsi'].iloc[i], df['adx'].iloc[i]

        candle_range = h - l
        body_size = abs(c - o)
        if candle_range < config.FILTER_ATR_MULT * atr or body_size < config.FILTER_BODY_MULT * candle_range:
            return None

        trend_bull = c > ema200 and ema21 > ema50 and htf_slope >= 0
        trend_bear = c < ema200 and ema21 < ema50 and htf_slope <= 0
        hour = pd.to_datetime(df['timestamp'].iloc[i]).hour

        sl_pts = max(config.MIN_SL_POINTS, min(config.MAX_SL_POINTS, config.SL_ATR_MULT * atr))
        tp_pts = sl_pts * config.TREND_RR

        if adx > config.ADX_TREND_TH:
            if trend_bull and (config.RSI_BOUNCE_LONG_ENTER <= rsi <= 68.0) and l <= ema50 and c > ema50:
                return {'side': 'LONG', 'strategy': 'E1_TREND_PULLBACK', 'tp_pts': tp_pts, 'sl_pts': sl_pts, 'adx': adx, 'rsi': rsi}
            elif trend_bear and (32.0 <= rsi <= config.RSI_BOUNCE_SHORT_ENTER) and h >= ema50 and c < ema50:
                return {'side': 'SHORT', 'strategy': 'E1_TREND_PULLBACK', 'tp_pts': tp_pts, 'sl_pts': sl_pts, 'adx': adx, 'rsi': rsi}
            elif trend_bull and ema9 > ema21 and c > h_prev and (52.0 < rsi < config.RSI_BOUNCE_LONG_EXIT):
                return {'side': 'LONG', 'strategy': 'E2_MOMENTUM_SCALP', 'tp_pts': tp_pts, 'sl_pts': sl_pts, 'adx': adx, 'rsi': rsi}
            elif trend_bear and ema9 < ema21 and c < l_prev and (config.RSI_BOUNCE_SHORT_EXIT < rsi < 48.0):
                return {'side': 'SHORT', 'strategy': 'E2_MOMENTUM_SCALP', 'tp_pts': tp_pts, 'sl_pts': sl_pts, 'adx': adx, 'rsi': rsi}
            elif trend_bull and c > don_h and adx > 20.0:
                return {'side': 'LONG', 'strategy': 'E3_SESSION_BREAKOUT', 'tp_pts': tp_pts, 'sl_pts': sl_pts, 'adx': adx, 'rsi': rsi}
            elif trend_bear and c < don_l and adx > 20.0:
                return {'side': 'SHORT', 'strategy': 'E3_SESSION_BREAKOUT', 'tp_pts': tp_pts, 'sl_pts': sl_pts, 'adx': adx, 'rsi': rsi}
            elif hour in [8, 9, 10, 13, 14, 15, 17, 18, 19, 20] and vol > 1.20 * vol_sma and adx > 22.0:
                if trend_bull and c > ema9 and c > h_prev:
                    return {'side': 'LONG', 'strategy': 'E4_SESSION_EXPANSION', 'tp_pts': tp_pts, 'sl_pts': sl_pts, 'adx': adx, 'rsi': rsi}
                elif trend_bear and c < ema9 and c < l_prev:
                    return {'side': 'SHORT', 'strategy': 'E4_SESSION_EXPANSION', 'tp_pts': tp_pts, 'sl_pts': sl_pts, 'adx': adx, 'rsi': rsi}
        return None
