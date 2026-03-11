"""
QM Signal Service
Generates Quasimodo (QM) pattern signals with real MT5 data or simulated fallback.
"""

import time
import random
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

TIMEFRAMES = ['D1', 'H4', 'H1', 'M30', 'M15', 'M5']

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

def _detect_qm_signal_real(rates):
    """Detect Quasimodo (QM) signal from real OHLCV data."""
    if not rates or len(rates) < 30:
        return 0

    closes = [r['close'] for r in rates]
    highs = [r['high'] for r in rates]
    lows = [r['low'] for r in rates]
    opens = [r['open'] for r in rates]

    # Find swing points
    swing_highs, swing_lows = _find_swing_points(highs, lows, 4)
    
    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return 0
        
    # Get recent swing points (last 2 of each)
    last_sh_idx, last_sh = swing_highs[-1]
    prev_sh_idx, prev_sh = swing_highs[-2]
    
    last_sl_idx, last_sl = swing_lows[-1]
    prev_sl_idx, prev_sl = swing_lows[-2]
    
    current_close = closes[-1]
    current_high = highs[-1]
    current_low = lows[-1]
    
    # -----------------------------
    # QM BUY Pattern:
    # 1. Low (prev_sl)
    # 2. High (prev_sh)
    # 3. Lower Low (last_sl) -> Break of Structure downside
    # 4. Higher High (last_sh) -> Change of Character upside
    # 5. Retracement to Left Shoulder (prev_sl)
    # -----------------------------
    
    # Check if swing sequence matches QM Buy
    if last_sl < prev_sl and last_sh > prev_sh:
        # Check timeline: Low -> High -> Lower Low -> Higher High
        if prev_sl_idx < prev_sh_idx < last_sl_idx < last_sh_idx:
            # Check if current price is near the Left Shoulder (prev_sl)
            # Allow some tolerance (e.g., 20% of the range between prev_sh and last_sl)
            range_size = prev_sh - last_sl
            tolerance = range_size * 0.2
            
            if abs(current_low - prev_sl) <= tolerance or (current_low <= prev_sl and current_close >= prev_sl):
                return 1 # Buy QM

    # -----------------------------
    # QM SELL Pattern:
    # 1. High (prev_sh)
    # 2. Low (prev_sl)
    # 3. Higher High (last_sh) -> Break of Structure upside
    # 4. Lower Low (last_sl) -> Change of Character downside
    # 5. Retracement to Left Shoulder (prev_sh)
    # -----------------------------
    
    # Check if swing sequence matches QM Sell
    if last_sh > prev_sh and last_sl < prev_sl:
        # Check timeline: High -> Low -> Higher High -> Lower Low
        if prev_sh_idx < prev_sl_idx < last_sh_idx < last_sl_idx:
            # Check if current price is near the Left Shoulder (prev_sh)
            range_size = last_sh - prev_sl
            tolerance = range_size * 0.2
            
            if abs(current_high - prev_sh) <= tolerance or (current_high >= prev_sh and current_close <= prev_sh):
                return -1 # Sell QM

    return 0

# ---------- Simulation Helpers ----------

def _simulate_signal(seed):
    random.seed(seed)
    rand = random.randint(0, 100)

    t = {'buy': 10, 'sell': 20} # 10% chance for each

    if rand < t['buy']:
        return 1
    if rand < t['sell']:
        return -1
    return 0

# ---------- Main Service ----------

class QMSignalService:

    def get_signals(self):
        use_mt5 = mt5_service.is_connected()
        signals = []
        seed = int(time.time() // 300)

        for symbol in SYMBOLS:
            symbol_seed = seed + crc32(symbol) + 7777

            tf_signals = {}
            for tf_idx, tf in enumerate(TIMEFRAMES):
                tf_seed = symbol_seed + tf_idx * 31
                
                signal_val = 0
                if use_mt5:
                    # Request more data for QM calculation to find clear swings
                    rates = mt5_service.get_rates(symbol, tf, 100)
                    if rates and len(rates) >= 40:
                        signal_val = _detect_qm_signal_real(rates)
                    else:
                        signal_val = _simulate_signal(tf_seed)
                else:
                    signal_val = _simulate_signal(tf_seed)

                tf_signals[tf] = signal_val

            signals.append({
                'symbol': symbol,
                'signals': tf_signals,
            })

        return {
            'signals': signals,
            'timeframes': TIMEFRAMES,
            'updatedAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
