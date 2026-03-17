"""
Candle Ranking Service
Calculates currency volume delta rankings based on the last closed candle
across multiple timeframes simultaneously (D1, H4, H1, M30, M15).
"""

import time
import random
from datetime import datetime
from zlib import crc32 as _crc32

from services.mt5_data_service import mt5_service
from services.volume_delta_service import PAIR_MAP, CURRENCIES, _get_pressure, calculate_volumes_from_ohlc

def crc32(s):
    return _crc32(s.encode('utf-8')) & 0xFFFFFFFF

class CandleRankingService:

    def __init__(self):
        self.target_timeframes = ['M15', 'M30', 'H1', 'H4', 'D1']

    def get_candle_ranking(self):
        use_mt5 = mt5_service.is_connected()
        seed = int(time.time() // 300)

        # Dictionary to hold the final rankings per timeframe
        # tf_rankings[tf] = list of currency dictionaries
        tf_rankings = {}
        prev_rankings = {}

        for tf in self.target_timeframes:
            # Initialize currency data for this timeframe
            currency_data = {
                cur: {
                    'buyVolume': 0, 
                    'sellVolume': 0, 
                    'delta': 0,
                    'pairDetails': []
                }
                for cur in CURRENCIES
            }
            # List of 5 past currency data
            prev_currency_data_list = [
                {cur: {'buyVolume': 0, 'sellVolume': 0, 'delta': 0} for cur in CURRENCIES}
                for _ in range(5)
            ]

            for symbol, pm in PAIR_MAP.items():
                base = pm['base']
                quote = pm['quote']

                tf_buy_vol = 0
                tf_sell_vol = 0
                tf_delta = 0

                prev_vols = [{'buyVolume': 0, 'sellVolume': 0, 'delta': 0} for _ in range(5)]

                if use_mt5:
                    # Fetch 7 candles to get the last closed (-2) and previous 1-5 closed (-3 to -7)
                    rates = mt5_service.get_rates(symbol, tf, 7)
                    if rates and len(rates) >= 2:
                        rates = calculate_volumes_from_ohlc(rates)

                        # Last closed candle
                        r = rates[-2]
                        vol = r.get('agg_total_volume', r.get('tick_volume', 0))
                        tf_buy_vol = r.get('agg_buy_volume')
                        tf_sell_vol = r.get('agg_sell_volume')

                        if tf_buy_vol is None:
                            o, c, h, l = r['open'], r['close'], r['high'], r['low']
                            full_range = h - l
                            if full_range > 0:
                                b_pct = ((c - l) / full_range) * 100
                            else:
                                b_pct = 50
                            b_pct = max(20, min(80, b_pct))
                            
                            tf_buy_vol = int(vol * b_pct / 100)
                            tf_sell_vol = max(0, vol - tf_buy_vol)
                        
                        tf_delta = tf_buy_vol - tf_sell_vol
                        tf_vol = tf_buy_vol + tf_sell_vol
                        tf_delta_pct = round((tf_delta / max(tf_vol, 1)) * 100, 1)

                        # Previous 1 to 5 closed candles
                        for i in range(5):
                            idx = -3 - i
                            if len(rates) >= abs(idx):
                                pr = rates[idx]
                                p_vol = pr.get('agg_total_volume', pr.get('tick_volume', 0))
                                prev_buy_vol = pr.get('agg_buy_volume')
                                prev_sell_vol = pr.get('agg_sell_volume')

                                if prev_buy_vol is None:
                                    p_o, p_c, p_h, p_l = pr['open'], pr['close'], pr['high'], pr['low']
                                    p_full_range = p_h - p_l
                                    if p_full_range > 0:
                                        p_b_pct = ((p_c - p_l) / p_full_range) * 100
                                    else:
                                        p_b_pct = 50
                                    p_b_pct = max(20, min(80, p_b_pct))
                                    
                                    prev_buy_vol = int(p_vol * p_b_pct / 100)
                                    prev_sell_vol = max(0, p_vol - prev_buy_vol)
                                
                                prev_delta = prev_buy_vol - prev_sell_vol
                                
                                prev_vols[i]['buyVolume'] = prev_buy_vol
                                prev_vols[i]['sellVolume'] = prev_sell_vol
                                prev_vols[i]['delta'] = prev_delta
                            else:
                                # Not enough data for this previous candle, fallback to previous one or current
                                prev_vols[i]['buyVolume'] = prev_vols[i-1]['buyVolume'] if i > 0 else tf_buy_vol
                                prev_vols[i]['sellVolume'] = prev_vols[i-1]['sellVolume'] if i > 0 else tf_sell_vol
                                prev_vols[i]['delta'] = prev_vols[i-1]['delta'] if i > 0 else tf_delta

                if not use_mt5 or (tf_buy_vol == 0 and tf_sell_vol == 0):
                    # Simulation fallback
                    h = crc32(symbol + tf + str(seed))
                    random.seed(h)
                    total_volume = random.randint(500, 10000)
                    buy_pct = random.randint(20, 80)
                    
                    tf_buy_vol = int(total_volume * buy_pct / 100)
                    tf_sell_vol = total_volume - tf_buy_vol
                    tf_delta = tf_buy_vol - tf_sell_vol
                    tf_vol = tf_buy_vol + tf_sell_vol
                    tf_delta_pct = round((tf_delta / max(tf_vol, 1)) * 100, 1)
                    
                    # Simulation fallback for previous candles
                    for i in range(5):
                        h_prev = crc32(symbol + tf + str(seed - 1 - i))
                        random.seed(h_prev)
                        p_total_volume = random.randint(500, 10000)
                        p_buy_pct = random.randint(20, 80)
                        p_buy_vol = int(p_total_volume * p_buy_pct / 100)
                        p_sell_vol = p_total_volume - p_buy_vol
                        p_delta = p_buy_vol - p_sell_vol
                        
                        prev_vols[i]['buyVolume'] = p_buy_vol
                        prev_vols[i]['sellVolume'] = p_sell_vol
                        prev_vols[i]['delta'] = p_delta

                if base in currency_data:
                    currency_data[base]['buyVolume'] += tf_buy_vol
                    currency_data[base]['sellVolume'] += tf_sell_vol
                    currency_data[base]['delta'] += tf_delta
                    currency_data[base]['pairDetails'].append({
                        'symbol': symbol,
                        'delta': tf_delta_pct,
                        'role': 'base'
                    })

                if quote in currency_data:
                    currency_data[quote]['buyVolume'] += tf_sell_vol
                    currency_data[quote]['sellVolume'] += tf_buy_vol
                    currency_data[quote]['delta'] -= tf_delta
                    currency_data[quote]['pairDetails'].append({
                        'symbol': symbol,
                        'delta': -tf_delta_pct,
                        'role': 'quote'
                    })

                # Aggregate previous to base and quote currency
                for i in range(5):
                    if base in prev_currency_data_list[i]:
                        prev_currency_data_list[i][base]['buyVolume'] += prev_vols[i]['buyVolume']
                        prev_currency_data_list[i][base]['sellVolume'] += prev_vols[i]['sellVolume']
                        prev_currency_data_list[i][base]['delta'] += prev_vols[i]['delta']

                    if quote in prev_currency_data_list[i]:
                        prev_currency_data_list[i][quote]['buyVolume'] += prev_vols[i]['sellVolume']
                        prev_currency_data_list[i][quote]['sellVolume'] += prev_vols[i]['buyVolume']
                        prev_currency_data_list[i][quote]['delta'] -= prev_vols[i]['delta']

            # Calculate percentages and formatting for this timeframe
            currencies_list = []
            for cur in CURRENCIES:
                cd = currency_data[cur]
                total_vol = cd['buyVolume'] + cd['sellVolume']
                net_delta = cd['delta']
                
                # Percentage of total volume that is delta
                # (Can be negative if sell volume > buy volume)
                delta_percent = round((net_delta / max(total_vol, 1)) * 100, 1)
                
                # Sort pairs by absolute delta strength
                details = sorted(cd['pairDetails'], key=lambda x: abs(x['delta']), reverse=True)
                
                currencies_list.append({
                    'currency': cur,
                    'buyVolume': cd['buyVolume'],
                    'sellVolume': cd['sellVolume'],
                    'totalVolume': total_vol,
                    'netDelta': net_delta,
                    'deltaPercent': delta_percent,
                    'pressure': _get_pressure(delta_percent),
                    'trend': 'bullish' if delta_percent > 0 else ('bearish' if delta_percent < 0 else 'neutral'),
                    'pairDetails': details
                })

            # Sort by delta (strongest first)
            currencies_list.sort(key=lambda x: x['netDelta'], reverse=True)
            tf_rankings[tf] = currencies_list

            # Calculate percentages and formatting for previous timeframes
            tf_prev_rankings_list = []
            for i in range(5):
                prev_currencies_list = []
                for cur in CURRENCIES:
                    cd = prev_currency_data_list[i][cur]
                    total_vol = cd['buyVolume'] + cd['sellVolume']
                    net_delta = cd['delta']
                    delta_percent = round((net_delta / max(total_vol, 1)) * 100, 1)
                    prev_currencies_list.append({
                        'currency': cur,
                        'deltaPercent': delta_percent
                    })
                
                # Sort previous by delta percent (strongest first)
                prev_currencies_list.sort(key=lambda x: x['deltaPercent'], reverse=True)
                
                # Format previous ranking string horizontally: EUR(20%), USD(34%) dst
                prev_rankings_str = ", ".join([f"{c['currency']}({c['deltaPercent']}%)" for c in prev_currencies_list])
                tf_prev_rankings_list.append(prev_rankings_str)
                
            prev_rankings[tf] = tf_prev_rankings_list

        return {
            'timeframes': self.target_timeframes,
            'rankings': tf_rankings,
            'prev_rankings': prev_rankings,
            'updatedAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
