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


def _calculate_sma(prices, period):
    """Simple Moving Average."""
    if len(prices) < period:
        return None
    return sum(prices[-period:]) / period


def _calculate_lwma(prices, period):
    """Linear Weighted Moving Average."""
    if len(prices) < period:
        return None
    weight_sum = period * (period + 1) / 2
    lwma = sum(price * (i + 1) for i, price in enumerate(prices[-period:])) / weight_sum
    return lwma


def _detect_bbma_signal_real(rates, indicator_type):
    """
    Detect BBMA signal from real OHLCV data based on Oma Ally rules.
    Returns 1 (buy), -1 (sell), or 0 (no signal).
    """
    if not rates or len(rates) < 25:
        return 0

    closes = [r['close'] for r in rates]
    highs = [r['high'] for r in rates]
    lows = [r['low'] for r in rates]
    opens = [r['open'] for r in rates]

    upper, mid, lower = _calculate_bollinger(closes, 20, 2)
    prev_upper, prev_mid, prev_lower = _calculate_bollinger(closes[:-1], 20, 2)
    if upper is None or prev_upper is None:
        return 0

    ma5_high = _calculate_lwma(highs, 5)
    ma5_low = _calculate_lwma(lows, 5)
    ma10_high = _calculate_lwma(highs, 10)
    ma10_low = _calculate_lwma(lows, 10)

    if not all([ma5_high, ma5_low, ma10_high, ma10_low]):
        return 0

    last_close = closes[-1]
    last_high = highs[-1]
    last_low = lows[-1]
    last_open = opens[-1]

    prev_close = closes[-2]
    prev_high = highs[-2]
    prev_low = lows[-2]

    if indicator_type == 'extreme':
        # Extreme Buy: Prev candle breached lower BB, current candle reverses & closes inside
        if prev_low < prev_lower and last_close > last_open and last_close > lower:
            return 1
        # Extreme Sell: Prev candle breached upper BB, current candle reverses & closes inside
        if prev_high > prev_upper and last_close < last_open and last_close < upper:
            return -1
        return 0

    elif indicator_type == 'mhv':
        # MHV: Market Fails to continue momentum (fails to touch/break BB)
        # Look back slightly to see if previously touched BB but now reversing
        recent_highs = highs[-4:-1]
        recent_lows = lows[-4:-1]
        
        recently_touched_upper = any(h >= prev_upper for h in recent_highs)
        if recently_touched_upper and last_high < upper and last_close < last_open:
            return -1  # Sell MHV
            
        recently_touched_lower = any(l <= prev_lower for l in recent_lows)
        if recently_touched_lower and last_low > lower and last_close > last_open:
            return 1  # Buy MHV
            
        return 0

    elif indicator_type == 'csm':
        # Candlestick Momentum (CSM): Candle closes completely outside the Bollinger Bands
        if last_close > upper:
            return 1  # Buy CSM
        elif last_close < lower:
            return -1  # Sell CSM
        return 0

    elif indicator_type == 'csak':
        # Candlestick Arah Kukuh (CSAK)
        # Strong directional candle breaking MA5, MA10, and Mid BB
        if prev_close < mid and last_close > mid and last_close > ma5_high and last_close > ma10_high:
            return 1
        if prev_close > mid and last_close < mid and last_close < ma5_low and last_close < ma10_low:
            return -1
        return 0

    elif indicator_type == 'reentry':
        # Reentry: Price retraces back to MA5/MA10
        # Buy Reentry happens in an uptrend (price > mid BB), retraces to MA5/MA10 low
        if last_close > mid and last_low <= ma5_low and last_close >= ma5_low:
            return 1
        # Sell Reentry happens in a downtrend (price < mid BB), retraces to MA5/MA10 high
        if last_close < mid and last_high >= ma5_high and last_close <= ma5_high:
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
            symbol_rates = {}
            for tf_idx, tf in enumerate(TIMEFRAMES):
                tf_seed = symbol_seed + tf_idx * 17

                if use_mt5:
                    rates = mt5_service.get_rates(symbol, tf, 45)
                    if rates and len(rates) >= 25:
                        symbol_rates[tf] = rates
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
                
                rem, ree, rme, zzl, diamond = 0, 0, 0, 0, 0
                
                if use_mt5 and len(tfs) >= 3:
                    tf1, tf2, tf3 = tfs[0], tfs[1], tfs[2]
                    
                    if tf1 in symbol_rates and tf2 in symbol_rates and tf3 in symbol_rates:
                        r1 = symbol_rates[tf1]
                        r2 = symbol_rates[tf2]
                        r3 = symbol_rates[tf3]

                        def _check_recent(r, cond, lookback):
                            for i in range(lookback):
                                subset = r if i == 0 else r[:-i]
                                sig = _detect_bbma_signal_real(subset, cond)
                                if sig != 0:
                                    return sig
                            return 0

                        def _check_combo(cond1, cond2, cond3):
                            sig1 = _check_recent(r1, cond1, 4) # HTF allowed last 4 candles
                            sig2 = _check_recent(r2, cond2, 6) # MTF allowed last 6 candles
                            sig3 = _check_recent(r3, cond3, 8) # LTF allowed last 8 candles
                            
                            if sig1 == 1 and sig2 == 1 and sig3 == 1:
                                return 1
                            if sig1 == -1 and sig2 == -1 and sig3 == -1:
                                return -1
                            return 0

                        # REM = Reentry -> Extreme -> MHV
                        rem = _check_combo('reentry', 'extreme', 'mhv')
                        # REE = Reentry -> Extreme -> Extreme
                        ree = _check_combo('reentry', 'extreme', 'extreme')
                        # RME = Reentry -> MHV -> Extreme
                        rme = _check_combo('reentry', 'mhv', 'extreme')
                        # ZZL = CSM -> Reentry -> Extreme
                        zzl = _check_combo('csm', 'reentry', 'extreme')
                        # DIAMOND = Reentry -> Reentry -> Reentry
                        diamond = _check_combo('reentry', 'reentry', 'reentry')
                else:
                    # Simulated fallback for isolated tests
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
