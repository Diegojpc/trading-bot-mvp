import logging
import ccxt
import os
from typing import Dict, Any, Tuple
from dotenv import load_dotenv

# Load env vars from .env file
load_dotenv()

logger = logging.getLogger(__name__)

class BinanceExchange:
    """
    Wrapper around CCXT for Binance Spot and USD(S)-M Futures.
    Implements extreme traceability and safe execution limits.
    """

    def __init__(self, market_type: str = "spot", testnet: bool = False):
        self.market_type = market_type.lower()
        if self.market_type not in ["spot", "future"]:
            raise ValueError("market_type must be 'spot' or 'future'")

        api_key = os.getenv("BINANCE_API_KEY")
        secret = os.getenv("BINANCE_SECRET_KEY")

        if not api_key or not secret:
            logger.warning("BINANCE_API_KEY or BINANCE_SECRET_KEY not found in environment. Running in Read-Only / Mock mode.")

        # Initialize CCXT
        self.exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': self.market_type,
            }
        })

        if testnet:
            self.exchange.set_sandbox_mode(True)
            logger.info("BinanceExchange initialized in TESTNET mode.")
        else:
            logger.info(f"BinanceExchange initialized in LIVE mode for {self.market_type.upper()}.")

        self._load_markets()

    def _load_markets(self):
        try:
            logger.info("Loading Binance markets via CCXT...")
            self.exchange.load_markets()
            logger.info("Markets loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load markets: {str(e)}", exc_info=True)
            raise

    def get_usdt_balance(self) -> float:
        """Fetch total free USDT available in the account."""
        logger.info(f"Fetching USDT balance for {self.market_type} account...")
        try:
            balance = self.exchange.fetch_balance()
            free_usdt = balance.get('USDT', {}).get('free', 0.0)
            logger.info(f"Fetched USDT balance: ${free_usdt:.2f}")
            return free_usdt
        except Exception as e:
            logger.error(f"Failed to fetch balance: {str(e)}", exc_info=True)
            raise

    def get_position(self, symbol: str) -> float:
        """
        Get current position size for a symbol.
        Returns the amount of base currency held (e.g., amount of BTC).
        """
        logger.info(f"Fetching position for {symbol}...")
        try:
            if self.market_type == "spot":
                # For spot, position is just the free balance of the base currency
                base_currency = symbol.split('/')[0]
                balance = self.exchange.fetch_balance()
                pos = balance.get(base_currency, {}).get('total', 0.0)
                logger.info(f"Spot position for {symbol}: {pos} {base_currency}")
                return pos
            else:
                # For futures, fetch the actual position
                positions = self.exchange.fetch_positions([symbol])
                if not positions:
                    logger.info(f"No open futures position found for {symbol}.")
                    return 0.0
                
                pos = positions[0]['contracts']
                side = positions[0]['side']
                if side == 'short':
                    pos = -pos
                logger.info(f"Futures position for {symbol}: {pos} contracts ({side})")
                return float(pos)
        except Exception as e:
            logger.error(f"Failed to fetch position for {symbol}: {str(e)}", exc_info=True)
            raise

    def execute_market_order(self, symbol: str, side: str, amount: float) -> Dict[str, Any]:
        """
        Execute a market order.
        side: 'buy' or 'sell'
        amount: size in base currency (e.g., BTC)
        """
        logger.info(f"Attempting to execute MARKET {side.upper()} order for {amount} {symbol}")
        
        if amount <= 0:
            logger.warning("Order amount is <= 0. Aborting execution.")
            return {"status": "aborted", "reason": "Amount <= 0"}

        try:
            # Check market limits
            market = self.exchange.market(symbol)
            min_amount = market['limits']['amount']['min']
            if amount < min_amount:
                logger.error(f"Order amount {amount} is below market minimum {min_amount}.")
                raise ValueError(f"Amount {amount} too small.")

            logger.info(f"Sending order to Binance: symbol={symbol}, type=market, side={side}, amount={amount}")
            order = self.exchange.create_market_order(symbol, side, amount)
            
            logger.info(f"Order executed successfully. Order ID: {order['id']}")
            return {
                "status": "success",
                "order_id": order['id'],
                "price": order.get('average', order.get('price')),
                "filled": order.get('filled'),
                "cost": order.get('cost')
            }
        except ccxt.InsufficientFunds as e:
            logger.error(f"Insufficient funds to execute {side} of {amount} {symbol}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Order execution failed: {str(e)}", exc_info=True)
            raise
