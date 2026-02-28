"""
SMC Signal Service
Port of SMCSignalService.php — generates Smart Money Concept signals
with real MT5 data or simulated fallback.
"""

import time
import random
import math
from datetime import datetime
from zlib import crc32 as _crc32

from services.mt5_data_service import mt5_service


def crc32(s):
    return _crc32(s.encode('utf-8')) & 0xFFFFFFFF


# ---------- Configuration ----------

SYMBOLS = [
    'XAUUSD',
    'EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD', 'NZDUSD', 'USDCHF',
    'EURJPY', 'GBPJPY', 'AUDJPY', 'CADJPY', 'CHFJPY', 'NZDJPY',
    'EURGBP', 'EURAUD', 'EURCHF', 'EURCAD', 'EURNZD',
    'GBPAUD', 'GBPCAD', 'GBPCHF', 'GBPNZD',
    'AUDNZD', 'AUDCAD', 'AUDCHF', 'NZDCAD', 'NZDCHF',
    'CADCHF',
]

TIMEFRAMES = ['D1', 'H4', 'H1', 'M15']

INDICATORS = {
    'bos': 'Break of Structure',
    'choch': 'Change of Character',
    'ob': 'Order Block',
    'fvg': 'Fair Value Gap',
    'liquidity': 'Liquidity Sweep',
    'premium_discount': 'Premium/Discount',
}


# ---------- Real MT5 Signal Detection ----------

def _find_swing_points(highs, lows, lookback=5):
    """Find swing highs and swing lows."""
    swing_highs = []
    swing_lows = []
    n = len(highs)
    for i in range(lookback, n - lookback):
        if all(highs[i] >= highs[i - j] for j in range(1, lookback + 1)) and \
           all(highs[i] >= highs[i + j] for j in range(1, lookback + 1)):
            swing_highs.append((i, highs[i]))
        if all(lows[i] <= lows[i - j] for j in range(1, lookback + 1)) and \
           all(lows[i] <= lows[i + j] for j in range(1, lookback + 1)):
            swing_lows.append((i, lows[i]))
    return swing_highs, swing_lows


def _detect_smc_signal_real(rates, indicator_type):
    """Detect SMC signal from real OHLCV data."""
    if not rates or len(rates) < 20:
        return 0

    closes = [r['close'] for r in rates]
    highs = [r['high'] for r in rates]
    lows = [r['low'] for r in rates]
    opens = [r['open'] for r in rates]

    if indicator_type == 'bos':
        # Break of Structure — new higher high or lower low
        swing_highs, swing_lows = _find_swing_points(highs, lows, 3)
        if len(swing_highs) >= 2 and swing_highs[-1][1] > swing_highs[-2][1]:
            return 1
        if len(swing_lows) >= 2 and swing_lows[-1][1] < swing_lows[-2][1]:
            return -1
        return 0

    elif indicator_type == 'choch':
        # Change of Character
        swing_highs, swing_lows = _find_swing_points(highs, lows, 3)
        if len(swing_highs) >= 2 and len(swing_lows) >= 2:
            last_sh = swing_highs[-1][1]
            prev_sh = swing_highs[-2][1]
            last_sl = swing_lows[-1][1]
            prev_sl = swing_lows[-2][1]
            # Bearish CHoCH: was making higher highs, now lower low
            if prev_sh < last_sh and last_sl < prev_sl:
                return -1
            # Bullish CHoCH: was making lower lows, now higher high
            if prev_sl > last_sl and last_sh > prev_sh:
                return 1
        return 0

    elif indicator_type == 'ob':
        # Order Block — last bearish candle before bullish move (or vice versa)
        if len(rates) >= 5:
            # Bullish OB
            if closes[-1] > opens[-1] and closes[-2] < opens[-2] and closes[-1] > highs[-2]:
                return 1
            # Bearish OB
            if closes[-1] < opens[-1] and closes[-2] > opens[-2] and closes[-1] < lows[-2]:
                return -1
        return 0

    elif indicator_type == 'fvg':
        # Fair Value Gap — gap between candle 1 high and candle 3 low
        if len(rates) >= 3:
            # Bullish FVG
            if lows[-1] > highs[-3]:
                return 1
            # Bearish FVG
            if highs[-1] < lows[-3]:
                return -1
        return 0

    elif indicator_type == 'liquidity':
        # Liquidity Sweep — price sweeps recent high/low then reverses
        recent_high = max(highs[-10:-1])
        recent_low = min(lows[-10:-1])
        if highs[-1] > recent_high and closes[-1] < recent_high:
            return -1  # Swept buy-side liquidity, bearish
        if lows[-1] < recent_low and closes[-1] > recent_low:
            return 1  # Swept sell-side liquidity, bullish
        return 0

    elif indicator_type == 'premium_discount':
        # Premium/Discount based on range
        highest = max(highs[-20:])
        lowest = min(lows[-20:])
        mid = (highest + lowest) / 2
        range_size = highest - lowest
        if range_size == 0:
            return 0
        position = (closes[-1] - lowest) / range_size
        if position > 0.7:
            return 2  # Premium
        elif position < 0.3:
            return -2  # Discount
        return 0

    return 0


# ---------- Simulation Helpers ----------

def _simulate_signal(seed, sig_type):
    random.seed(seed)
    rand = random.randint(0, 100)

    if sig_type == 'premium_discount':
        if rand < 30:
            return 2
        if rand < 60:
            return -2
        return 0

    thresholds = {
        'bos':       {'buy': 20, 'sell': 40},
        'choch':     {'buy': 10, 'sell': 20},
        'ob':        {'buy': 22, 'sell': 44},
        'fvg':       {'buy': 18, 'sell': 36},
        'liquidity': {'buy': 12, 'sell': 24},
    }
    t = thresholds.get(sig_type, {'buy': 15, 'sell': 30})

    if rand < t['buy']:
        return 1
    if rand < t['sell']:
        return -1
    return 0


# ---------- Main Service ----------

class SMCSignalService:

    def get_signals(self):
        use_mt5 = mt5_service.is_connected()
        signals = []
        seed = int(time.time() // 300)

        for symbol in SYMBOLS:
            symbol_seed = seed + crc32(symbol) + 9999

            tf_signals = {}
            for tf_idx, tf in enumerate(TIMEFRAMES):
                tf_seed = symbol_seed + tf_idx * 31
                tf_data = {}

                if use_mt5:
                    rates = mt5_service.get_rates(symbol, tf, 30)
                    if rates and len(rates) >= 20:
                        for key in INDICATORS:
                            tf_data[key] = _detect_smc_signal_real(rates, key)
                    else:
                        for key in INDICATORS:
                            sig_seed = tf_seed + crc32(key)
                            tf_data[key] = _simulate_signal(sig_seed, key)
                else:
                    for key in INDICATORS:
                        sig_seed = tf_seed + crc32(key)
                        tf_data[key] = _simulate_signal(sig_seed, key)

                tf_signals[tf] = tf_data

            bias = self._calculate_bias(tf_signals)
            entry = self._calculate_entry(tf_signals)
            structure = self._get_market_structure(symbol_seed)

            signals.append({
                'symbol': symbol,
                'signals': tf_signals,
                'bias': bias,
                'entry': entry,
                'structure': structure,
            })

        return {
            'signals': signals,
            'indicators': INDICATORS,
            'timeframes': TIMEFRAMES,
            'updatedAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }

    @staticmethod
    def _calculate_bias(tf_signals):
        bullish = 0
        bearish = 0
        total = 0

        for tf in ['D1', 'H4']:
            if tf not in tf_signals:
                continue
            for key, val in tf_signals[tf].items():
                if key == 'premium_discount':
                    if val == -2:
                        bullish += 1
                    elif val == 2:
                        bearish += 1
                else:
                    if val == 1:
                        bullish += 1
                    elif val == -1:
                        bearish += 1
                total += 1

        if total == 0:
            return {'direction': 'NEUTRAL', 'strength': 0, 'bullish': 0, 'bearish': 0}

        strength = abs(bullish - bearish) / total * 100
        direction = 'NEUTRAL'
        if bullish > bearish + 1:
            direction = 'BULLISH'
        elif bearish > bullish + 1:
            direction = 'BEARISH'

        return {
            'direction': direction,
            'strength': round(strength),
            'bullish': bullish,
            'bearish': bearish,
        }

    @staticmethod
    def _calculate_entry(tf_signals):
        buy_score = 0
        sell_score = 0

        for tf in ['H1', 'M15']:
            if tf not in tf_signals:
                continue
            for key, val in tf_signals[tf].items():
                if key == 'premium_discount':
                    continue
                if val == 1:
                    buy_score += 1
                elif val == -1:
                    sell_score += 1

        action = 'WAIT'
        if buy_score >= 3 and buy_score > sell_score:
            action = 'BUY'
        elif sell_score >= 3 and sell_score > buy_score:
            action = 'SELL'

        return {
            'action': action,
            'buyScore': buy_score,
            'sellScore': sell_score,
        }

    @staticmethod
    def _get_market_structure(seed):
        random.seed(seed + 777)
        structures = [
            'Bullish Trending',
            'Bearish Trending',
            'Ranging',
            'Bullish Reversal',
            'Bearish Reversal',
            'Consolidation',
            'Bullish Expansion',
            'Bearish Expansion',
        ]
        return structures[random.randint(0, len(structures) - 1)]
