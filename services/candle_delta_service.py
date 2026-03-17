"""
Candle Delta Service
Fetches the last 50 candles for a specific pair and timeframe,
calculates buy/sell volume and delta per candle,
and aggregates delta sums (e.g. last 5, 10... 50 candles).
"""

import time
import random
from datetime import datetime
from zlib import crc32 as _crc32

from services.mt5_data_service import mt5_service
from services.volume_delta_service import PAIR_MAP, TIMEFRAMES, _get_pressure, aggregate_m1_volumes

def crc32(s):
    return _crc32(s.encode('utf-8')) & 0xFFFFFFFF


class CandleDeltaService:

    def get_candle_delta(self, symbol='XAUUSD', tf='M15', count=100):
        # Fallback defaults if invalid symbol or timeframe
        if symbol not in PAIR_MAP:
            symbol = 'XAUUSD'
        if tf not in TIMEFRAMES:
            tf = 'M15'

        use_mt5 = mt5_service.is_connected()
        seed = int(time.time() // 300)

        candles = []
        if use_mt5:
            rates = mt5_service.get_rates(symbol, tf, count)
            if rates and len(rates) > 0:
                rates = aggregate_m1_volumes(symbol, rates)
                for r in rates:
                    vol = r.get('agg_total_volume', r.get('tick_volume', 0))
                    buy_volume = r.get('agg_buy_volume')
                    sell_volume = r.get('agg_sell_volume')

                    if buy_volume is None:
                        o, c, h, l = r['open'], r['close'], r['high'], r['low']
                        full_range = h - l
                        b_pct = ((c - l) / full_range * 100) if full_range > 0 else 50
                        b_pct = max(20, min(80, b_pct))
                        buy_volume = int(vol * b_pct / 100)
                        sell_volume = max(0, vol - buy_volume)
                    
                    delta = buy_volume - sell_volume
                    
                    # Store time as string for frontend
                    t_str = datetime.fromtimestamp(r['time']).strftime('%Y-%m-%d %H:%M')
                    
                    candles.append({
                        'time': t_str,
                        'open': r['open'],
                        'high': r['high'],
                        'low': r['low'],
                        'close': r['close'],
                        'totalVolume': vol,
                        'buyVolume': buy_volume,
                        'sellVolume': sell_volume,
                        'delta': delta,
                        'isBullish': r['close'] >= r['open']
                    })

        # If MT5 fails or is not connected, use simulation
        if not candles:
            base_price = 2000.0 if symbol == 'XAUUSD' else 1.1000
            
            # Determine time multiplier in seconds
            tf_seconds = 900 # default M15
            if tf == 'M1': tf_seconds = 60
            elif tf == 'M5': tf_seconds = 300
            elif tf == 'M15': tf_seconds = 900
            elif tf == 'M30': tf_seconds = 1800
            elif tf == 'H1': tf_seconds = 3600
            elif tf == 'H4': tf_seconds = 14400
            elif tf == 'D1': tf_seconds = 86400

            for i in range(count):
                h_seed = crc32(f"{symbol}{tf}{seed}{i}")
                random.seed(h_seed)
                
                vol = random.randint(500, 5000)
                buy_pct = random.randint(20, 80)
                buy_volume = int(vol * buy_pct / 100)
                sell_volume = vol - buy_volume
                delta = buy_volume - sell_volume
                
                is_bullish = delta > 0
                o = base_price + random.uniform(-0.0010, 0.0010)
                c = o + random.uniform(0.0001, 0.0020) if is_bullish else o - random.uniform(0.0001, 0.0020)
                h = max(o, c) + random.uniform(0, 0.0010)
                l = min(o, c) - random.uniform(0, 0.0010)
                
                
                # Mock time progressing backwards
                mock_time = time.time() - (count - 1 - i) * tf_seconds
                t_str = datetime.fromtimestamp(mock_time).strftime('%Y-%m-%d %H:%M')
                
                candles.append({
                    'time': t_str,
                    'open': round(o, 5),
                    'high': round(h, 5),
                    'low': round(l, 5),
                    'close': round(c, 5),
                    'totalVolume': vol,
                    'buyVolume': buy_volume,
                    'sellVolume': sell_volume,
                    'delta': delta,
                    'isBullish': c >= o
                })

        # Order candles: newest first (index 0 is the most recent candle)
        candles.reverse()

        # Calculate summaries: last 5, 10, 15... 50
        summaries = []
        for n in range(5, count + 1, 5):
            # sum the first 'n' candles in the reversed list (which are the 'n' most recent)
            slice_candles = candles[:n]
            sum_delta = sum(c['delta'] for c in slice_candles)
            sum_vol = sum(c['totalVolume'] for c in slice_candles)
            
            pressure = _get_pressure(round((sum_delta/max(sum_vol, 1))*100, 1))
            
            summaries.append({
                'candles': n,
                'sumDelta': sum_delta,
                'pressure': pressure
            })

        return {
            'symbol': symbol,
            'timeframe': tf,
            'candles': candles,
            'summaries': summaries,
            'updatedAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
