"""
BBMA Signal Service
Port of BBMASignalService.php — generates BBMA trading signals
with real MT5 data or simulated fallback.
"""

import time
import random
import math
from datetime import datetime
from zlib import crc32 as _crc32

from services.mt5_data_service import mt5_service


def crc32(s):
    """Consistent unsigned CRC32 matching PHP's crc32()."""
    return _crc32(s.encode('utf-8')) & 0xFFFFFFFF


# ---------- Configuration ----------

SYMBOLS = [
    # Metals
    'XAUUSD',
    # Major Pairs
    'EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD', 'NZDUSD', 'USDCHF',
    # Cross Pairs (JPY)
    'EURJPY', 'GBPJPY', 'AUDJPY', 'CADJPY', 'CHFJPY', 'NZDJPY',
    # Cross Pairs (EUR)
    'EURGBP', 'EURAUD', 'EURCHF', 'EURCAD', 'EURNZD',
    # Cross Pairs (GBP)
    'GBPAUD', 'GBPCAD', 'GBPCHF', 'GBPNZD',
    # Cross Pairs (AUD/NZD/CAD/CHF)
    'AUDNZD', 'AUDCAD', 'AUDCHF', 'NZDCAD', 'NZDCHF',
    'CADCHF',
]

TF_GROUPS = {
    'Day Trading': ['H4', 'H1', 'M15'],
    'Scalping': ['H1', 'M15', 'M5'],
}

TIMEFRAMES = ['D1', 'H4', 'H1', 'M30', 'M15', 'M5']


# ---------- Real MT5 Signal Helpers ----------

def _calculate_bollinger(closes, period=20, std_dev=2):
    """Calculate Bollinger Bands from close prices."""
    if len(closes) < period:
        return None, None, None
    sma = sum(closes[-period:]) / period
    variance = sum((c - sma) ** 2 for c in closes[-period:]) / period
    sd = math.sqrt(variance)
    upper = sma + std_dev * sd
    lower = sma - std_dev * sd
    return upper, sma, lower


def _calculate_ma(closes, period):
    """Simple Moving Average."""
    if len(closes) < period:
        return None
    return sum(closes[-period:]) / period


def _detect_bbma_signal_real(rates, indicator_type):
    """
    Detect BBMA signal from real OHLCV data.
    Returns 1 (buy), -1 (sell), or 0 (no signal).
    """
    if not rates or len(rates) < 25:
        return 0

    closes = [r['close'] for r in rates]
    highs = [r['high'] for r in rates]
    lows = [r['low'] for r in rates]

    upper, mid, lower = _calculate_bollinger(closes, 20, 2)
    if upper is None:
        return 0

    last_close = closes[-1]
    last_high = highs[-1]
    last_low = lows[-1]
    prev_close = closes[-2]

    if indicator_type == 'extreme':
        # Price touches/exceeds Bollinger Band
        if last_low <= lower and last_close > lower:
            return 1  # Buy extreme
        if last_high >= upper and last_close < upper:
            return -1  # Sell extreme
        return 0

    elif indicator_type == 'reentry':
        # Price re-enters after being outside bands
        ma5 = _calculate_ma(closes, 5)
        ma10 = _calculate_ma(closes, 10)
        if ma5 and ma10:
            if ma5 > ma10 and last_close > mid and prev_close <= mid:
                return 1
            if ma5 < ma10 and last_close < mid and prev_close >= mid:
                return -1
        return 0

    elif indicator_type == 'mhv':
        # MHV — candle with high volume near MA
        ma5 = _calculate_ma(closes, 5)
        ma10 = _calculate_ma(closes, 10)
        if ma5 and ma10:
            spread = abs(last_high - last_low)
            avg_spread = sum(abs(h - l) for h, l in zip(highs[-10:], lows[-10:])) / 10
            if spread > avg_spread * 1.5:
                if last_close > ma5:
                    return 1
                elif last_close < ma5:
                    return -1
        return 0

    elif indicator_type == 'csm':
        # Candlestick momentum
        body = abs(last_close - rates[-1]['open'])
        total_range = last_high - last_low
        if total_range > 0 and body / total_range > 0.6:
            if last_close > rates[-1]['open']:
                return 1
            else:
                return -1
        return 0

    elif indicator_type == 'csak':
        # CSAK — strong candle after consolidation
        recent_ranges = [abs(highs[i] - lows[i]) for i in range(-5, -1)]
        if recent_ranges:
            avg_range = sum(recent_ranges) / len(recent_ranges)
            current_range = last_high - last_low
            if current_range > avg_range * 1.8:
                if last_close > rates[-1]['open']:
                    return 1
                else:
                    return -1
        return 0

    return 0


# ---------- Simulation Helpers (PHP-compatible) ----------

def _simulate_signal(seed, sig_type):
    """Simulate individual signal (-1, 0, or 1). Matches PHP logic."""
    random.seed(seed)
    rand = random.randint(0, 100)

    thresholds = {
        'extreme':  {'buy': 12, 'sell': 24},
        'reentry':  {'buy': 18, 'sell': 36},
        'mhv':      {'buy': 10, 'sell': 20},
        'csm':      {'buy': 25, 'sell': 50},
        'csak':     {'buy': 20, 'sell': 40},
    }
    t = thresholds.get(sig_type, {'buy': 15, 'sell': 30})

    if rand < t['buy']:
        return 1
    if rand < t['sell']:
        return -1
    return 0


def _simulate_combo(seed, combo_type):
    """Simulate combo setup signal. Matches PHP logic."""
    random.seed(seed)
    rand = random.randint(0, 100)

    thresholds = {
        'rem':     {'buy': 8, 'sell': 16},
        'ree':     {'buy': 6, 'sell': 12},
        'rme':     {'buy': 7, 'sell': 14},
        'zzl':     {'buy': 10, 'sell': 20},
        'diamond': {'buy': 3, 'sell': 6},
    }
    t = thresholds.get(combo_type, {'buy': 5, 'sell': 10})

    if rand < t['buy']:
        return 1
    if rand < t['sell']:
        return -1
    return 0


# ---------- Main Service ----------

class BBMASignalService:

    def get_signals(self):
        use_mt5 = mt5_service.is_connected()
        signals = []
        seed = int(time.time() // 300)

        for idx, symbol in enumerate(SYMBOLS):
            symbol_seed = seed + crc32(symbol)

            # --- Single-TF signals ---
            single_tf = {}
            for tf_idx, tf in enumerate(TIMEFRAMES):
                tf_seed = symbol_seed + tf_idx * 17

                if use_mt5:
                    rates = mt5_service.get_rates(symbol, tf, 30)
                    if rates and len(rates) >= 25:
                        single_tf[tf] = {
                            'extreme': _detect_bbma_signal_real(rates, 'extreme'),
                            'reentry': _detect_bbma_signal_real(rates, 'reentry'),
                            'mhv':     _detect_bbma_signal_real(rates, 'mhv'),
                            'csm':     _detect_bbma_signal_real(rates, 'csm'),
                            'csak':    _detect_bbma_signal_real(rates, 'csak'),
                        }
                    else:
                        single_tf[tf] = self._simulated_single(tf_seed)
                else:
                    single_tf[tf] = self._simulated_single(tf_seed)

            # --- Multi-TF combo signals ---
            combos = {}
            for group_name, tfs in TF_GROUPS.items():
                g_seed = symbol_seed + crc32(group_name)
                rem     = _simulate_combo(g_seed, 'rem')
                ree     = _simulate_combo(g_seed + 10, 'ree')
                rme     = _simulate_combo(g_seed + 20, 'rme')
                zzl     = _simulate_combo(g_seed + 30, 'zzl')
                diamond = _simulate_combo(g_seed + 40, 'diamond')

                # Priority: Diamond > REM > REE > RME > ZZL
                active_setup = None
                active_signal = 0
                if diamond != 0:
                    active_setup = 'DIAMOND'
                    active_signal = diamond
                elif rem != 0:
                    active_setup = 'REM'
                    active_signal = rem
                elif ree != 0:
                    active_setup = 'REE'
                    active_signal = ree
                elif rme != 0:
                    active_setup = 'RME'
                    active_signal = rme
                elif zzl != 0:
                    active_setup = 'ZZL'
                    active_signal = zzl

                action = 'WAIT'
                if active_signal == 1:
                    action = 'BUY'
                elif active_signal == -1:
                    action = 'SELL'

                combos[group_name] = {
                    'timeframes': tfs,
                    'rem': rem,
                    'ree': ree,
                    'rme': rme,
                    'zzl': zzl,
                    'diamond': diamond,
                    'setup': active_setup,
                    'signal': active_signal,
                    'action': action,
                }

            signals.append({
                'symbol': symbol,
                'singleTF': single_tf,
                'combos': combos,
            })

        return {
            'signals': signals,
            'timeframes': TIMEFRAMES,
            'tfGroups': TF_GROUPS,
            'updatedAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }

    @staticmethod
    def _simulated_single(tf_seed):
        return {
            'extreme': _simulate_signal(tf_seed, 'extreme'),
            'reentry': _simulate_signal(tf_seed + 1, 'reentry'),
            'mhv':     _simulate_signal(tf_seed + 2, 'mhv'),
            'csm':     _simulate_signal(tf_seed + 3, 'csm'),
            'csak':    _simulate_signal(tf_seed + 4, 'csak'),
        }
