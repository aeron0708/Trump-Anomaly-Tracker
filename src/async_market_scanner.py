# -*- coding: utf-8 -*-
"""
TSADS - Asynchronous Multi-Market Scanner
Concurrently scans equity, bond (TLT), and safe-haven (GLD) option chains
using asyncio to minimize network latency. Includes a robust fallback mock mode.
"""

import asyncio
import sys
from datetime import datetime

# Reconfigure stdout to UTF-8 on Windows
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False

class AsyncMarketScanner:
    def __init__(self, tickers=None, use_mock=True):
        self.tickers = tickers or ["SPY", "QQQ", "DJT", "TLT", "GLD", "USO"]
        self.use_mock = use_mock or not HAS_YFINANCE
        
        if not HAS_YFINANCE:
            print("[TSADS Scanner] yfinance library not found. Running in MOCK Mode.")

    async def fetch_ticker_data(self, ticker):
        """
        Concurrently fetches live ticker price and basic statistics.
        Falls back to Mock data if use_mock=True.
        """
        if self.use_mock:
            await asyncio.sleep(0.1) # Simulate network call
            mock_prices = {"SPY": 500.0, "QQQ": 400.0, "DJT": 50.0, "TLT": 95.0, "GLD": 220.0}
            return {
                "ticker": ticker,
                "price": mock_prices.get(ticker, 100.0),
                "timestamp": datetime.now().isoformat(),
                "mode": "MOCK"
            }
            
        # Actual yfinance fetch wrapped in an async thread to prevent blocking
        return await asyncio.to_thread(self._sync_fetch, ticker)

    def _sync_fetch(self, ticker):
        try:
            stock = yf.Ticker(ticker)
            # Fetch history for close price
            hist = stock.history(period="1d")
            price = hist["Close"].iloc[-1] if not hist.empty else 100.0
            return {
                "ticker": ticker,
                "price": round(price, 2),
                "timestamp": datetime.now().isoformat(),
                "mode": "LIVE"
            }
        except Exception as e:
            print(f"[TSADS Scanner] Failed to fetch {ticker} live: {e}. Falling back to default.")
            return {"ticker": ticker, "price": 100.0, "timestamp": datetime.now().isoformat(), "mode": "FALLBACK"}

    async def scan_all_markets(self):
        """
        Runs concurrent fetches for all registered tickers.
        """
        tasks = [self.fetch_ticker_data(t) for t in self.tickers]
        results = await asyncio.gather(*tasks)
        return {res["ticker"]: res for res in results}

if __name__ == "__main__":
    # Test scan
    scanner = AsyncMarketScanner(use_mock=True)
    
    print("\n--- Starting Async Multi-Market Scan ---")
    start = datetime.now()
    loop = asyncio.get_event_loop()
    results = loop.run_until_complete(scanner.scan_all_markets())
    duration = (datetime.now() - start).total_seconds()
    
    for ticker, data in results.items():
        print(f"Ticker: {ticker} | Price: ${data['price']} | Mode: {data['mode']}")
    print(f"Scan Completed in {duration:.4f} seconds.")
