"""
Currency Strength Service
Port of CurrencyStrengthService.php — aggregates BBMA + SMC signals
to compute per-currency strength/direction.
"""

from datetime import datetime
from services.bbma_signal_service import BBMASignalService
from services.smc_signal_service import SMCSignalService


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


class CurrencyStrengthService:

    def get_strength(self):
        bbma_data = BBMASignalService().get_signals()
        smc_data = SMCSignalService().get_signals()

        scores = {c: {'bullish': 0, 'bearish': 0, 'total': 0} for c in CURRENCIES}

        # ---- Score from BBMA ----
        for item in bbma_data['signals']:
            symbol = item['symbol']
            if symbol not in PAIR_MAP:
                continue
            base = PAIR_MAP[symbol]['base']
            quote = PAIR_MAP[symbol]['quote']

            # Combo signals (heavy weight)
            for combo in item['combos'].values():
                signal = combo['signal']
                weight = 5 if combo['setup'] == 'DIAMOND' else 3
                if signal == 1:
                    scores[base]['bullish'] += weight
                    scores[base]['total'] += weight
                    scores[quote]['bearish'] += weight
                    scores[quote]['total'] += weight
                elif signal == -1:
                    scores[base]['bearish'] += weight
                    scores[base]['total'] += weight
                    scores[quote]['bullish'] += weight
                    scores[quote]['total'] += weight

            # Single-TF signals (light weight)
            for tf, sigs in item['singleTF'].items():
                for sig_type, val in sigs.items():
                    if val == 1:
                        scores[base]['bullish'] += 1
                        scores[base]['total'] += 1
                        scores[quote]['bearish'] += 1
                        scores[quote]['total'] += 1
                    elif val == -1:
                        scores[base]['bearish'] += 1
                        scores[base]['total'] += 1
                        scores[quote]['bullish'] += 1
                        scores[quote]['total'] += 1

        # ---- Score from SMC ----
        for item in smc_data['signals']:
            symbol = item['symbol']
            if symbol not in PAIR_MAP:
                continue
            base = PAIR_MAP[symbol]['base']
            quote = PAIR_MAP[symbol]['quote']

            # Bias (heavy weight)
            bias_weight = 4
            if item['bias']['direction'] == 'BULLISH':
                scores[base]['bullish'] += bias_weight
                scores[base]['total'] += bias_weight
                scores[quote]['bearish'] += bias_weight
                scores[quote]['total'] += bias_weight
            elif item['bias']['direction'] == 'BEARISH':
                scores[base]['bearish'] += bias_weight
                scores[base]['total'] += bias_weight
                scores[quote]['bullish'] += bias_weight
                scores[quote]['total'] += bias_weight

            # Entry signals
            entry_weight = 3
            if item['entry']['action'] == 'BUY':
                scores[base]['bullish'] += entry_weight
                scores[base]['total'] += entry_weight
                scores[quote]['bearish'] += entry_weight
                scores[quote]['total'] += entry_weight
            elif item['entry']['action'] == 'SELL':
                scores[base]['bearish'] += entry_weight
                scores[base]['total'] += entry_weight
                scores[quote]['bullish'] += entry_weight
                scores[quote]['total'] += entry_weight

            # Individual SMC signals per TF
            for tf, tf_signals in item['signals'].items():
                for key, val in tf_signals.items():
                    if key == 'premium_discount':
                        if val == 2:
                            scores[base]['bearish'] += 1
                            scores[base]['total'] += 1
                            scores[quote]['bullish'] += 1
                            scores[quote]['total'] += 1
                        elif val == -2:
                            scores[base]['bullish'] += 1
                            scores[base]['total'] += 1
                            scores[quote]['bearish'] += 1
                            scores[quote]['total'] += 1
                    else:
                        if val == 1:
                            scores[base]['bullish'] += 1
                            scores[base]['total'] += 1
                            scores[quote]['bearish'] += 1
                            scores[quote]['total'] += 1
                        elif val == -1:
                            scores[base]['bearish'] += 1
                            scores[base]['total'] += 1
                            scores[quote]['bullish'] += 1
                            scores[quote]['total'] += 1

        # ---- Calculate strength + direction ----
        result = []
        for currency in CURRENCIES:
            s = scores[currency]
            net = s['bullish'] - s['bearish']
            max_possible = max(s['total'], 1)
            strength_pct = round(abs(net) / max_possible * 100)

            if net > 2:
                direction = 'STRONG UP'
                trend = 'bullish'
            elif net > 0:
                direction = 'SLIGHTLY UP'
                trend = 'bullish'
            elif net < -2:
                direction = 'STRONG DOWN'
                trend = 'bearish'
            elif net < 0:
                direction = 'SLIGHTLY DOWN'
                trend = 'bearish'
            else:
                direction = 'NEUTRAL'
                trend = 'neutral'

            top_pairs = self._get_top_pairs(currency, bbma_data, smc_data)

            result.append({
                'currency': currency,
                'bullish': s['bullish'],
                'bearish': s['bearish'],
                'net': net,
                'strength': strength_pct,
                'direction': direction,
                'trend': trend,
                'topPairs': top_pairs,
            })

        result.sort(key=lambda x: x['net'], reverse=True)

        strongest = result[0] if result else None
        weakest = result[-1] if result else None

        opportunities = self._find_opportunities(result)

        return {
            'currencies': result,
            'strongest': strongest,
            'weakest': weakest,
            'opportunities': opportunities,
            'updatedAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }

    @staticmethod
    def _get_top_pairs(currency, bbma_data, smc_data):
        pairs = []

        for item in bbma_data['signals']:
            symbol = item['symbol']
            if symbol not in PAIR_MAP:
                continue
            pm = PAIR_MAP[symbol]
            if pm['base'] != currency and pm['quote'] != currency:
                continue

            buy_count = sum(1 for c in item['combos'].values() if c['signal'] == 1)
            sell_count = sum(1 for c in item['combos'].values() if c['signal'] == -1)

            if buy_count > 0 or sell_count > 0:
                is_base = pm['base'] == currency
                pair_dir = 'BUY' if buy_count > sell_count else ('SELL' if sell_count > buy_count else 'MIXED')
                impact = 'neutral'
                if pair_dir == 'BUY':
                    impact = 'bullish' if is_base else 'bearish'
                elif pair_dir == 'SELL':
                    impact = 'bearish' if is_base else 'bullish'

                pairs.append({
                    'symbol': symbol,
                    'direction': pair_dir,
                    'impact': impact,
                    'source': 'BBMA',
                })

        for item in smc_data['signals']:
            symbol = item['symbol']
            if symbol not in PAIR_MAP:
                continue
            pm = PAIR_MAP[symbol]
            if pm['base'] != currency and pm['quote'] != currency:
                continue

            if item['entry']['action'] != 'WAIT':
                is_base = pm['base'] == currency
                impact = 'neutral'
                if item['entry']['action'] == 'BUY':
                    impact = 'bullish' if is_base else 'bearish'
                elif item['entry']['action'] == 'SELL':
                    impact = 'bearish' if is_base else 'bullish'

                pairs.append({
                    'symbol': symbol,
                    'direction': item['entry']['action'],
                    'impact': impact,
                    'source': 'SMC',
                })

        return pairs[:5]

    @staticmethod
    def _find_opportunities(currencies):
        bullish = [c for c in currencies if c['trend'] == 'bullish']
        bearish = [c for c in currencies if c['trend'] == 'bearish']

        opportunities = []
        for strong in bullish:
            for weak in bearish:
                pair_info = _find_pair_symbol(strong['currency'], weak['currency'])
                if not pair_info:
                    continue
                score = abs(strong['net']) + abs(weak['net'])
                opportunities.append({
                    'pair': pair_info['symbol'],
                    'action': pair_info['action'],
                    'strong': strong['currency'],
                    'weak': weak['currency'],
                    'score': score,
                    'reasoning': f"{strong['currency']} {strong['direction']} vs {weak['currency']} {weak['direction']}",
                })

        opportunities.sort(key=lambda x: x['score'], reverse=True)
        return opportunities[:8]


def _find_pair_symbol(strong, weak):
    direct = strong + weak
    inverse = weak + strong
    if direct in PAIR_MAP:
        return {'symbol': direct, 'action': 'BUY'}
    if inverse in PAIR_MAP:
        return {'symbol': inverse, 'action': 'SELL'}
    return None
