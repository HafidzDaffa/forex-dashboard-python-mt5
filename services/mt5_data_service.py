"""
MetaTrader5 Data Service
Handles connection to MT5 terminal and fetching market data.
Falls back gracefully when MT5 is not available.
"""

import logging

logger = logging.getLogger(__name__)

# Try to import MetaTrader5
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    logger.warning("MetaTrader5 package not installed. Running in simulation mode.")

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False


# MT5 Timeframe mapping
TIMEFRAME_MAP = {
    'M1': 1,
    'M5': 5,
    'M15': 15,
    'M30': 30,
    'H1': 60,
    'H4': 240,
    'D1': 1440,
    'W1': 10080,
    'MN1': 43200,
}

if MT5_AVAILABLE:
    TIMEFRAME_MT5 = {
        'M1': mt5.TIMEFRAME_M1,
        'M5': mt5.TIMEFRAME_M5,
        'M15': mt5.TIMEFRAME_M15,
        'M30': mt5.TIMEFRAME_M30,
        'H1': mt5.TIMEFRAME_H1,
        'H4': mt5.TIMEFRAME_H4,
        'D1': mt5.TIMEFRAME_D1,
        'W1': mt5.TIMEFRAME_W1,
        'MN1': mt5.TIMEFRAME_MN1,
    }
else:
    TIMEFRAME_MT5 = {}


class MT5DataService:
    """Wrapper around MetaTrader5 Python API with graceful fallback."""

    def __init__(self):
        self._connected = False

    def initialize(self):
        """Try to connect to MT5 terminal."""
        if not MT5_AVAILABLE:
            logger.info("MT5 package not available. Simulation mode active.")
            return False

        try:
            # Shutdown any existing connection first
            try:
                mt5.shutdown()
            except Exception:
                pass

            if mt5.initialize():
                self._connected = True
                info = mt5.terminal_info()
                if info:
                    logger.info(f"MT5 connected: {info.name} (build {info.build})")
                acct = mt5.account_info()
                if acct:
                    logger.info(f"MT5 account: {acct.login} @ {acct.server}")
                return True
            else:
                error = mt5.last_error()
                logger.warning(f"MT5 initialize failed: {error}")
                self._connected = False
                return False
        except Exception as e:
            logger.warning(f"MT5 initialize exception: {e}")
            self._connected = False
            return False

    def shutdown(self):
        """Disconnect from MT5."""
        if MT5_AVAILABLE and self._connected:
            mt5.shutdown()
            self._connected = False

    def is_connected(self):
        """Check if MT5 is connected and working. Auto-reconnects if needed."""
        if not MT5_AVAILABLE:
            return False

        # Try to check existing connection
        if self._connected:
            try:
                info = mt5.terminal_info()
                if info is not None:
                    return True
            except Exception:
                pass

        # Connection lost or not yet established — try to reconnect
        logger.info("MT5 connection not active, attempting to reconnect...")
        return self.initialize()

    def get_rates(self, symbol, timeframe, count=100):
        """
        Fetch OHLCV rates from MT5.
        Returns list of dicts with keys: time, open, high, low, close, tick_volume
        Returns None if not connected.
        """
        if not self.is_connected():
            return None

        tf = TIMEFRAME_MT5.get(timeframe)
        if tf is None:
            return None

        try:
            rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
            if rates is None or len(rates) == 0:
                return None

            result = []
            for r in rates:
                result.append({
                    'time': int(r['time']),
                    'open': float(r['open']),
                    'high': float(r['high']),
                    'low': float(r['low']),
                    'close': float(r['close']),
                    'tick_volume': int(r['tick_volume']),
                    'real_volume': int(r['real_volume']) if 'real_volume' in r.dtype.names else 0,
                })
            return result
        except Exception as e:
            logger.error(f"Error fetching rates for {symbol}/{timeframe}: {e}")
            return None

    def get_rates_range(self, symbol, timeframe, start_time, end_time):
        """
        Fetch OHLCV rates from MT5 between start_time and end_time.
        """
        if not self.is_connected():
            return None

        tf = TIMEFRAME_MT5.get(timeframe)
        if tf is None:
            return None

        try:
            rates = mt5.copy_rates_range(symbol, tf, start_time, end_time)
            if rates is None or len(rates) == 0:
                return None

            result = []
            for r in rates:
                result.append({
                    'time': int(r['time']),
                    'open': float(r['open']),
                    'high': float(r['high']),
                    'low': float(r['low']),
                    'close': float(r['close']),
                    'tick_volume': int(r['tick_volume']),
                    'real_volume': int(r['real_volume']) if 'real_volume' in r.dtype.names else 0,
                })
            return result
        except Exception as e:
            logger.error(f"Error fetching rates range for {symbol}/{timeframe}: {e}")
            return None

    def get_tick(self, symbol):
        """
        Get the latest tick for a symbol.
        Returns dict with bid, ask, last, volume or None.
        """
        if not self.is_connected():
            return None

        try:
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                return None
            return {
                'bid': float(tick.bid),
                'ask': float(tick.ask),
                'last': float(tick.last),
                'volume': int(tick.volume),
                'time': int(tick.time),
            }
        except Exception as e:
            logger.error(f"Error fetching tick for {symbol}: {e}")
            return None

    def get_symbol_info(self, symbol):
        """Get symbol information."""
        if not self.is_connected():
            return None

        try:
            info = mt5.symbol_info(symbol)
            if info is None:
                return None
            return {
                'name': info.name,
                'digits': info.digits,
                'point': info.point,
                'spread': info.spread,
                'trade_mode': info.trade_mode,
            }
        except Exception as e:
            logger.error(f"Error fetching symbol info for {symbol}: {e}")
            return None


# Singleton instance
mt5_service = MT5DataService()
