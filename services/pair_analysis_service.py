"""
Pair Analysis Service
Provides per-pair buying/selling analysis with percentage breakdown.
Sources: BBMA + SMC (for Summary tab), Volume Delta (for VD tab).
"""

from services.bbma_signal_service import BBMASignalService
from services.smc_signal_service import SMCSignalService
from services.volume_delta_service import VolumeDeltaService


class PairAnalysisService:

    # ---- Summary Analysis (BBMA + SMC combined) ----
    def get_summary_analysis(self, symbol):
        bbma_data = BBMASignalService().get_signals()
        smc_data = SMCSignalService().get_signals()

        buy_score = 0
        sell_score = 0
        details = []

        # --- BBMA signals for this pair ---
        for item in bbma_data['signals']:
            if item['symbol'] != symbol:
                continue

            # Combo signals (heavy weight)
            for group_name, combo in item['combos'].items():
                sig = combo['signal']
                weight = 5 if combo['setup'] == 'DIAMOND' else 3
                if sig == 1:
                    buy_score += weight
                    details.append({'source': f'BBMA {group_name}', 'direction': 'BUY', 'weight': weight})
                elif sig == -1:
                    sell_score += weight
                    details.append({'source': f'BBMA {group_name}', 'direction': 'SELL', 'weight': weight})

            # Single-TF signals (light weight)
            for tf, sigs in item['singleTF'].items():
                for sig_type, val in sigs.items():
                    if val == 1:
                        buy_score += 1
                        details.append({'source': f'BBMA {tf} {sig_type}', 'direction': 'BUY', 'weight': 1})
                    elif val == -1:
                        sell_score += 1
                        details.append({'source': f'BBMA {tf} {sig_type}', 'direction': 'SELL', 'weight': 1})

        # --- SMC signals for this pair ---
        for item in smc_data['signals']:
            if item['symbol'] != symbol:
                continue

            # Bias
            if item['bias']['direction'] == 'BULLISH':
                buy_score += 4
                details.append({'source': 'SMC Bias', 'direction': 'BUY', 'weight': 4})
            elif item['bias']['direction'] == 'BEARISH':
                sell_score += 4
                details.append({'source': 'SMC Bias', 'direction': 'SELL', 'weight': 4})

            # Entry
            if item['entry']['action'] == 'BUY':
                buy_score += 3
                details.append({'source': 'SMC Entry', 'direction': 'BUY', 'weight': 3})
            elif item['entry']['action'] == 'SELL':
                sell_score += 3
                details.append({'source': 'SMC Entry', 'direction': 'SELL', 'weight': 3})

            # Per-TF signals
            for tf, tf_signals in item['signals'].items():
                for key, val in tf_signals.items():
                    if key == 'premium_discount':
                        if val == -2:  # discount = bullish
                            buy_score += 1
                            details.append({'source': f'SMC {tf} Discount', 'direction': 'BUY', 'weight': 1})
                        elif val == 2:  # premium = bearish
                            sell_score += 1
                            details.append({'source': f'SMC {tf} Premium', 'direction': 'SELL', 'weight': 1})
                    else:
                        if val == 1:
                            buy_score += 1
                            details.append({'source': f'SMC {tf} {key}', 'direction': 'BUY', 'weight': 1})
                        elif val == -1:
                            sell_score += 1
                            details.append({'source': f'SMC {tf} {key}', 'direction': 'SELL', 'weight': 1})

        return self._build_result(symbol, buy_score, sell_score, details, 'summary')

    # ---- Volume Delta Analysis ----
    def get_volume_analysis(self, symbol):
        vd_data = VolumeDeltaService().get_volume_delta()

        buy_score = 0
        sell_score = 0
        details = []

        # Find this pair in the volume delta data
        pair_data = None
        for pd in vd_data['pairs']:
            if pd['symbol'] == symbol:
                pair_data = pd
                break

        if not pair_data:
            return self._build_result(symbol, 0, 0, [], 'volume')

        # Weight timeframes: M5 heaviest → D1 lightest
        tf_weights = {'D1': 1.0, 'H4': 1.5, 'H1': 2.0, 'M30': 2.5, 'M15': 3.0, 'M5': 3.5}

        for tf, tf_data in pair_data['timeframes'].items():
            w = tf_weights.get(tf, 1.0)
            buy_vol = tf_data['buyVolume']
            sell_vol = tf_data['sellVolume']
            total = buy_vol + sell_vol
            if total == 0:
                continue

            buy_contrib = round(buy_vol / total * w, 2)
            sell_contrib = round(sell_vol / total * w, 2)
            buy_score += buy_contrib
            sell_score += sell_contrib

            # Distribute into details to accurately populate the buckets
            # Volume signals don't have implicit 'strong'/'moderate' categories determined by high w size like BBMA.
            # However, to be consistent with the _compute_breakdown method expecting weights, we assign the
            # pure buy and sell contributions as their respective weights so they accumulate properly in the buckets.
            # We scale the M5/M15 (larger w) to land in 'moderate' and smaller w in 'slight' automatically based on w size
            # due to _compute_breakdown logic. But to be safe, we can just let it flow into the buckets based on raw w size.
            
            if buy_contrib > 0:
                details.append({
                    'source': f'Vol {tf} (Buy)',
                    'direction': 'BUY',
                    'weight': buy_contrib,
                    'buyPct': round(buy_vol / total * 100, 1)
                })
            if sell_contrib > 0:
                details.append({
                    'source': f'Vol {tf} (Sell)',
                    'direction': 'SELL',
                    'weight': sell_contrib,
                    'sellPct': round(sell_vol / total * 100, 1)
                })

        return self._build_result(symbol, buy_score, sell_score, details, 'volume')

    # ---- Build unified result ----
    @staticmethod
    def _build_result(symbol, buy_score, sell_score, details, source):
        total = buy_score + sell_score
        if total == 0:
            buy_pct = 50.0
            sell_pct = 50.0
        else:
            buy_pct = round(buy_score / total * 100, 1)
            sell_pct = round(sell_score / total * 100, 1)

        # Determine verdict and confidence
        diff = abs(buy_pct - sell_pct)
        if buy_pct > sell_pct:
            if diff >= 40:
                verdict = 'STRONG BUYING'
                verdict_key = 'strong_buying'
            elif diff >= 20:
                verdict = 'MODERATE BUYING'
                verdict_key = 'moderate_buying'
            elif diff >= 5:
                verdict = 'SLIGHT BUYING'
                verdict_key = 'slight_buying'
            else:
                verdict = 'NEUTRAL'
                verdict_key = 'neutral'
        elif sell_pct > buy_pct:
            if diff >= 40:
                verdict = 'STRONG SELLING'
                verdict_key = 'strong_selling'
            elif diff >= 20:
                verdict = 'MODERATE SELLING'
                verdict_key = 'moderate_selling'
            elif diff >= 5:
                verdict = 'SLIGHT SELLING'
                verdict_key = 'slight_selling'
            else:
                verdict = 'NEUTRAL'
                verdict_key = 'neutral'
        else:
            verdict = 'NEUTRAL'
            verdict_key = 'neutral'

        # Build breakdown: what percentage falls into each category
        breakdown = _compute_breakdown(details)

        return {
            'symbol': symbol,
            'verdict': verdict,
            'verdictKey': verdict_key,
            'buyPercent': buy_pct,
            'sellPercent': sell_pct,
            'buyScore': round(buy_score, 2),
            'sellScore': round(sell_score, 2),
            'breakdown': breakdown,
            'details': details,
            'source': source,
        }


def _compute_breakdown(details):
    """
    Categorize individual signal details into strength buckets
    and compute percentage for each bucket.
    """
    buckets = {
        'strong_buying': 0,
        'moderate_buying': 0,
        'slight_buying': 0,
        'neutral': 0,
        'slight_selling': 0,
        'moderate_selling': 0,
        'strong_selling': 0,
    }

    for d in details:
        w = d.get('weight', 1)
        direction = d.get('direction', 'NEUTRAL')
        if direction == 'BUY':
            if w >= 4:
                buckets['strong_buying'] += w
            elif w >= 2:
                buckets['moderate_buying'] += w
            else:
                buckets['slight_buying'] += w
        elif direction == 'SELL':
            if w >= 4:
                buckets['strong_selling'] += w
            elif w >= 2:
                buckets['moderate_selling'] += w
            else:
                buckets['slight_selling'] += w
        else:
            buckets['neutral'] += w

    total = sum(buckets.values())
    result = []
    labels = {
        'strong_buying': 'Strong Buying',
        'moderate_buying': 'Moderate Buying',
        'slight_buying': 'Slight Buying',
        'neutral': 'Neutral',
        'slight_selling': 'Slight Selling',
        'moderate_selling': 'Moderate Selling',
        'strong_selling': 'Strong Selling',
    }

    for key in ['strong_buying', 'moderate_buying', 'slight_buying',
                'neutral', 'slight_selling', 'moderate_selling', 'strong_selling']:
        pct = round(buckets[key] / total * 100, 1) if total > 0 else 0
        result.append({
            'key': key,
            'label': labels[key],
            'score': pct,
            'raw': buckets[key],
        })

    return result
