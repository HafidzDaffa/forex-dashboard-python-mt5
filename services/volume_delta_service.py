"""
Volume Delta Service
Port of VolumeDeltaService.php — generates volume delta analysis
per pair and per currency with MT5 or simulation fallback.
"""

import time
import random
from datetime import datetime
from zlib import crc32 as _crc32

from services.mt5_data_service import mt5_service


def crc32(s):
    return _crc32(s.encode('utf-8')) & 0xFFFFFFFF


CURRENCIES = ['USD', 'EUR', 'GBP', 'JPY', 'AUD', 'CAD', 'NZD', 'CHF', 'XAU']

PAIR_MAP = {
    'XAUUSD': {'base': 'XAU', 'quote': 'USD'},
    'EURUSD': {'base': 'EUR', 'quote': 'USD'},
    'GBPUSD': {'base': 'GBP', 'quote': 'USD'},
    'USDJPY': {'base': 'USD', 'quote': 'JPY'},
    'AUDUSD': {'base': 'AUD', 'quote': 'USD'},
    'USDCAD': {'base': 'USD', 'quote': 'CAD'},
    'NZDUSD': {'base': 'NZD', 'quote': 'USD'},
    'USDCHF': {'base': 'USD', 'quote': 'CHF'},
    'EURJPY': {'base': 'EUR', 'quote': 'JPY'},
    'GBPJPY': {'base': 'GBP', 'quote': 'JPY'},
    'AUDJPY': {'base': 'AUD', 'quote': 'JPY'},
    'CADJPY': {'base': 'CAD', 'quote': 'JPY'},
    'CHFJPY': {'base': 'CHF', 'quote': 'JPY'},
    'NZDJPY': {'base': 'NZD', 'quote': 'JPY'},
    'EURGBP': {'base': 'EUR', 'quote': 'GBP'},
    'EURAUD': {'base': 'EUR', 'quote': 'AUD'},
    'EURCHF': {'base': 'EUR', 'quote': 'CHF'},
    'EURCAD': {'base': 'EUR', 'quote': 'CAD'},
    'EURNZD': {'base': 'EUR', 'quote': 'NZD'},
    'GBPAUD': {'base': 'GBP', 'quote': 'AUD'},
    'GBPCAD': {'base': 'GBP', 'quote': 'CAD'},
    'GBPCHF': {'base': 'GBP', 'quote': 'CHF'},
    'GBPNZD': {'base': 'GBP', 'quote': 'NZD'},
    'AUDNZD': {'base': 'AUD', 'quote': 'NZD'},
    'AUDCAD': {'base': 'AUD', 'quote': 'CAD'},
    'AUDCHF': {'base': 'AUD', 'quote': 'CHF'},
    'NZDCAD': {'base': 'NZD', 'quote': 'CAD'},
    'NZDCHF': {'base': 'NZD', 'quote': 'CHF'},
    'CADCHF': {'base': 'CAD', 'quote': 'CHF'},
}

TIMEFRAMES = ['D1', 'H4', 'H1', 'M30', 'M15', 'M5', 'M1']


def _get_pressure(delta):
    if delta > 20:
        return 'HEAVY BUYING'
    if delta > 10:
        return 'STRONG BUYING'
    if delta > 3:
        return 'MODERATE BUYING'
    if delta > 0:
        return 'SLIGHT BUYING'
    if delta < -20:
        return 'HEAVY SELLING'
    if delta < -10:
        return 'STRONG SELLING'
    if delta < -3:
        return 'MODERATE SELLING'
    if delta < 0:
        return 'SLIGHT SELLING'
    return 'NEUTRAL'


class VolumeDeltaService:

    def get_volume_delta(self, target_tf='default'):
        use_mt5 = mt5_service.is_connected()
        seed = int(time.time() // 300)

        # --- Per-pair volume delta per timeframe ---
        pair_deltas = []
        for symbol, pm in PAIR_MAP.items():
            tf_data = {}
            for tf in TIMEFRAMES:
                if use_mt5:
                    rates = mt5_service.get_rates(symbol, tf, 20)
                    if rates and len(rates) > 0:
                        total_volume = sum(r.get('tick_volume', 0) for r in rates) or 1
                        buy_volume = 0
                        sell_volume = 0
                        
                        for r in rates:
                            vol = r.get('tick_volume', 0)
                            o, c, h, l = r['open'], r['close'], r['high'], r['low']
                            full_range = h - l
                            if full_range > 0:
                                b_pct = ((c - l) / full_range) * 100
                            else:
                                b_pct = 50
                            b_pct = max(20, min(80, b_pct))
                            buy_volume += int(vol * b_pct / 100)
                        
                        sell_volume = total_volume - buy_volume
                        delta = buy_volume - sell_volume
                        delta_pct = round((delta / max(total_volume, 1)) * 100, 1)
                        cum_delta = self._generate_cum_delta_real(rates)

                        tf_data[tf] = {
                            'totalVolume': total_volume,
                            'buyVolume': buy_volume,
                            'sellVolume': sell_volume,
                            'delta': delta,
                            'deltaPercent': delta_pct,
                            'cumDelta': cum_delta,
                            'pressure': _get_pressure(delta_pct),
                        }
                        continue

                # Simulation fallback
                h = crc32(symbol + tf + str(seed))
                random.seed(h)
                total_volume = random.randint(500, 50000)
                buy_pct = random.randint(20, 80)
                sell_pct = 100 - buy_pct
                buy_volume = int(total_volume * buy_pct / 100)
                sell_volume = total_volume - buy_volume
                delta_val = buy_volume - sell_volume
                delta_pct = round((delta_val / max(total_volume, 1)) * 100, 1)

                h2 = crc32('cum' + symbol + tf + str(seed))
                random.seed(h2)
                cum_delta = random.randint(-15000, 15000)

                tf_data[tf] = {
                    'totalVolume': total_volume,
                    'buyVolume': buy_volume,
                    'sellVolume': sell_volume,
                    'delta': delta_val,
                    'deltaPercent': delta_pct,
                    'cumDelta': cum_delta,
                    'pressure': _get_pressure(delta_pct),
                }

            # Overall pair delta (weighted by recency)
            weights = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
            weighted_sum = 0
            total_weight = 0
            for i, tf in enumerate(TIMEFRAMES):
                weighted_sum += tf_data[tf]['deltaPercent'] * weights[i]
                total_weight += weights[i]
            overall_delta_pct = round(weighted_sum / max(total_weight, 1), 1)

            pair_deltas.append({
                'symbol': symbol,
                'base': pm['base'],
                'quote': pm['quote'],
                'timeframes': tf_data,
                'overallDelta': overall_delta_pct,
                'pressure': _get_pressure(overall_delta_pct),
            })

        # --- Aggregate per-currency ---
        currency_data = {}
        for cur in CURRENCIES:
            currency_data[cur] = {
                'buyVolume': 0, 'sellVolume': 0, 'delta': 0,
                'pairCount': 0, 'deltaSum': 0, 'pairDetails': [],
            }

        for pd in pair_deltas:
            base = pd['base']
            quote = pd['quote']

            if target_tf != 'default' and target_tf in pd['timeframes']:
                # Use the specific timeframe for deltaSum and volumes
                tf_data = pd['timeframes'][target_tf]
                tf_buy_vol = tf_data['buyVolume']
                tf_sell_vol = tf_data['sellVolume']
                tf_delta = tf_data['delta']
                tf_delta_pct = tf_data['deltaPercent']
                tf_pressure = tf_data['pressure']
            else:
                # Default: use H1 for volume as proxy, but overallDelta for rating
                tf_buy_vol = pd['timeframes']['H1']['buyVolume']
                tf_sell_vol = pd['timeframes']['H1']['sellVolume']
                tf_delta = pd['timeframes']['H1']['delta']
                tf_delta_pct = pd['overallDelta']
                tf_pressure = pd['pressure']

            if base in currency_data:
                currency_data[base]['buyVolume'] += tf_buy_vol
                currency_data[base]['sellVolume'] += tf_sell_vol
                currency_data[base]['delta'] += tf_delta
                currency_data[base]['pairCount'] += 1
                currency_data[base]['deltaSum'] += tf_delta_pct
                currency_data[base]['pairDetails'].append({
                    'symbol': pd['symbol'],
                    'delta': tf_delta_pct,
                    'role': 'base',
                    'pressure': tf_pressure,
                })

            if quote in currency_data:
                currency_data[quote]['buyVolume'] += tf_sell_vol
                currency_data[quote]['sellVolume'] += tf_buy_vol
                currency_data[quote]['delta'] -= tf_delta
                currency_data[quote]['pairCount'] += 1
                currency_data[quote]['deltaSum'] -= tf_delta_pct
                currency_data[quote]['pairDetails'].append({
                    'symbol': pd['symbol'],
                    'delta': -tf_delta_pct,
                    'role': 'quote',
                    'pressure': _get_pressure(-tf_delta_pct),
                })

        currencies = []
        for cur in CURRENCIES:
            cd = currency_data[cur]
            total_vol = cd['buyVolume'] + cd['sellVolume']
            avg_delta = round(cd['deltaSum'] / cd['pairCount'], 1) if cd['pairCount'] > 0 else 0
            buy_pct = round(cd['buyVolume'] / total_vol * 100, 1) if total_vol > 0 else 50
            sell_pct = round(100 - buy_pct, 1)
            net_delta = cd['delta']

            details = sorted(cd['pairDetails'], key=lambda x: abs(x['delta']), reverse=True)

            currencies.append({
                'currency': cur,
                'buyVolume': cd['buyVolume'],
                'sellVolume': cd['sellVolume'],
                'totalVolume': total_vol,
                'buyPercent': buy_pct,
                'sellPercent': sell_pct,
                'netDelta': net_delta,
                'avgDelta': avg_delta,
                'pressure': _get_pressure(avg_delta),
                'trend': 'bullish' if avg_delta > 5 else ('bearish' if avg_delta < -5 else 'neutral'),
                'pairCount': cd['pairCount'],
                'topPairs': details[:5],
            })

        currencies.sort(key=lambda x: x['avgDelta'], reverse=True)

        most_buying = currencies[0] if currencies else None
        most_selling = currencies[-1] if currencies else None

        return {
            'currencies': currencies,
            'pairs': pair_deltas,
            'mostBuying': most_buying,
            'mostSelling': most_selling,
            'timeframes': TIMEFRAMES,
            'targetTf': target_tf,
            'updatedAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }

    @staticmethod
    def _generate_cum_delta_real(rates):
        """Calculate cumulative delta from tick volumes and candle direction."""
        cum = 0
        for r in rates:
            vol = r.get('tick_volume', 0)
            if r['close'] >= r['open']:
                cum += vol
            else:
                cum -= vol
        return cum
