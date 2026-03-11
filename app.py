"""
Forex Dashboard — Flask Application
Port of Laravel forex-dashboard-php.
"""

import logging
from flask import Flask, redirect, url_for, render_template, jsonify, request

from services.mt5_data_service import mt5_service
from services.bbma_signal_service import BBMASignalService
from services.smc_signal_service import SMCSignalService
from services.currency_strength_service import CurrencyStrengthService
from services.volume_delta_service import VolumeDeltaService
from services.pair_analysis_service import PairAnalysisService
from services.candle_delta_service import CandleDeltaService
from services.candle_ranking_service import CandleRankingService
from services.qm_signal_service import QMSignalService

# ---- Logging ----
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# ---- Flask App ----
app = Flask(__name__)

# ---- Try to connect MT5 on startup ----
mt5_service.initialize()


# ================================================================
#  TEMPLATE FILTERS (equivalent to Blade @php helper functions)
# ================================================================

@app.template_filter('signal_badge')
def signal_badge_filter(signal):
    if signal == 1:
        return '<span class="signal-badge signal-buy">B</span>'
    if signal == -1:
        return '<span class="signal-badge signal-sell">S</span>'
    return '<span class="signal-badge signal-none">—</span>'


@app.template_filter('diamond_badge')
def diamond_badge_filter(signal):
    if signal == 1:
        return '<span class="signal-badge signal-diamond">◆B</span>'
    if signal == -1:
        return '<span class="signal-badge signal-diamond-sell">◆S</span>'
    return '<span class="signal-badge signal-none">—</span>'


@app.template_filter('signal_dot')
def signal_dot_filter(signal):
    if signal == 1:
        return '<span class="signal-dot dot-buy" title="Buy">●</span>'
    if signal == -1:
        return '<span class="signal-dot dot-sell" title="Sell">●</span>'
    return '<span class="signal-dot dot-none" title="None">·</span>'


@app.template_filter('smc_dot')
def smc_dot_filter(signal):
    if signal == 1:
        return '<span class="signal-dot dot-buy" title="Bullish">●</span>'
    if signal == -1:
        return '<span class="signal-dot dot-sell" title="Bearish">●</span>'
    return '<span class="signal-dot dot-none" title="None">·</span>'


@app.template_filter('pd_badge')
def pd_badge_filter(signal):
    if signal == 2:
        return '<span class="pd-badge pd-premium" title="Premium Zone">P</span>'
    if signal == -2:
        return '<span class="pd-badge pd-discount" title="Discount Zone">D</span>'
    return '<span class="signal-dot dot-none" title="Equilibrium">·</span>'


@app.template_filter('number_format')
def number_format_filter(value):
    try:
        return f"{int(value):,}"
    except (ValueError, TypeError):
        return str(value)


# ================================================================
#  PAGE ROUTES
# ================================================================

@app.route('/')
def index():
    return redirect(url_for('bbma'))


@app.route('/bbma')
def bbma():
    service = BBMASignalService()
    data = service.get_signals()
    return render_template('dashboard/bbma.html', **data)


@app.route('/smc')
def smc():
    service = SMCSignalService()
    data = service.get_signals()
    return render_template('dashboard/smc.html', **data)


@app.route('/summary')
def summary():
    from services.currency_strength_service import PAIR_MAP
    service = CurrencyStrengthService()
    data = service.get_strength()
    data['pair_list'] = list(PAIR_MAP.keys())
    return render_template('dashboard/summary.html', **data)


@app.route('/volume-delta')
def volume_delta():
    tf = request.args.get('tf', 'default')
    from services.volume_delta_service import PAIR_MAP
    service = VolumeDeltaService()
    data = service.get_volume_delta(target_tf=tf)
    data['pair_list'] = list(PAIR_MAP.keys())
    return render_template('dashboard/volume_delta.html', **data)


@app.route('/candle-delta')
def candle_delta():
    symbol = request.args.get('symbol', 'XAUUSD')
    tf = request.args.get('tf', 'M15')
    from services.volume_delta_service import PAIR_MAP, TIMEFRAMES
    service = CandleDeltaService()
    data = service.get_candle_delta(symbol=symbol, tf=tf)
    data['pair_list'] = list(PAIR_MAP.keys())
    data['tf_list'] = TIMEFRAMES
    return render_template('dashboard/candle_delta.html', **data)


@app.route('/candle-ranking')
def candle_ranking():
    service = CandleRankingService()
    data = service.get_candle_ranking()
    return render_template('dashboard/candle_ranking.html', **data)


@app.route('/qm')
def qm():
    service = QMSignalService()
    data = service.get_signals()
    return render_template('dashboard/qm.html', **data)



# ================================================================
#  API ROUTES (for AJAX auto-refresh)
# ================================================================

@app.route('/api/bbma-signals')
def api_bbma_signals():
    return jsonify(BBMASignalService().get_signals())


@app.route('/api/smc-signals')
def api_smc_signals():
    return jsonify(SMCSignalService().get_signals())


@app.route('/api/currency-strength')
def api_currency_strength():
    return jsonify(CurrencyStrengthService().get_strength())


@app.route('/api/volume-delta')
def api_volume_delta():
    tf = request.args.get('tf', 'default')
    return jsonify(VolumeDeltaService().get_volume_delta(target_tf=tf))


@app.route('/api/candle-delta')
def api_candle_delta():
    symbol = request.args.get('symbol', 'XAUUSD')
    tf = request.args.get('tf', 'M15')
    return jsonify(CandleDeltaService().get_candle_delta(symbol=symbol, tf=tf))


@app.route('/api/candle-ranking')
def api_candle_ranking():
    return jsonify(CandleRankingService().get_candle_ranking())


@app.route('/api/qm-signals')
def api_qm_signals():
    return jsonify(QMSignalService().get_signals())


@app.route('/api/pair-analysis/<symbol>')
def api_pair_analysis(symbol):
    source = request.args.get('source', 'summary')
    service = PairAnalysisService()
    if source == 'volume':
        data = service.get_volume_analysis(symbol)
    else:
        data = service.get_summary_analysis(symbol)
    return jsonify(data)


# ================================================================
#  CONTEXT PROCESSOR (inject variables into all templates)
# ================================================================

@app.context_processor
def inject_globals():
    from datetime import datetime
    return {
        'now': datetime.now(),
        'mt5_connected': mt5_service.is_connected(),
    }


# ================================================================
#  ENTRY POINT
# ================================================================

if __name__ == '__main__':
    logger.info("Starting Forex Dashboard (Flask)")
    logger.info(f"MT5 connected: {mt5_service.is_connected()}")
    app.run(debug=True, host='0.0.0.0', port=5000)
