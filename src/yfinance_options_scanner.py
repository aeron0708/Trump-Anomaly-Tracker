# -*- coding: utf-8 -*-
"""
TSADS - Free Options Anomaly Scanner (yfinance-based)
Uses the free yfinance library to scan SPY, QQQ, and DJT option chains
and flags contracts that exceed Vol/OI and premium thresholds.
"""

import sys
from datetime import datetime, date

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

class YFinanceOptionsScanner:
    def __init__(self, min_vol_oi=2.0, min_premium=100000.0, max_dte=7):
        self.min_vol_oi = min_vol_oi
        self.min_premium = min_premium
        self.max_dte = max_dte
        
        if not HAS_YFINANCE:
            print("[TSADS Scanner] Warning: 'yfinance' library not found. Please install it using: pip install yfinance")

    def get_dte(self, expiration_str):
        """
        Calculates Days to Expiration (DTE) from an expiration date string (YYYY-MM-DD).
        """
        try:
            exp_date = datetime.strptime(expiration_str, "%Y-%m-%d").date()
            today = date.today()
            return (exp_date - today).days
        except Exception:
            return 999

    def scan_ticker(self, ticker):
        """
        Scans all options chains for a given ticker expiring within max_dte.
        Returns list of anomalous contracts.
        """
        if not HAS_YFINANCE:
            print(f"[TSADS Scanner] Cannot scan {ticker}: 'yfinance' is not installed.")
            return []

        print(f"[TSADS Scanner] Scanning {ticker} option chains...")
        anomalies = []
        
        try:
            stock = yf.Ticker(ticker)
            expirations = stock.options
            
            # Filter expirations by DTE
            target_expirations = []
            for exp in expirations:
                dte = self.get_dte(exp)
                if 0 <= dte <= self.max_dte:
                    target_expirations.append((exp, dte))
            
            print(f"[TSADS Scanner] Found {len(target_expirations)} expiration dates within {self.max_dte} days.")
            
            for exp, dte in target_expirations:
                opt_chain = stock.option_chain(exp)
                
                # Scan Calls and Puts
                self._scan_dataframe(opt_chain.calls, ticker, exp, dte, "CALL", anomalies)
                self._scan_dataframe(opt_chain.puts, ticker, exp, dte, "PUT", anomalies)
                
            return anomalies
        except Exception as e:
            print(f"[TSADS Scanner] Error scanning {ticker}: {e}")
            return []

    def _scan_dataframe(self, df, ticker, expiration, dte, direction, anomalies):
        """
        Helper to scan a calls or puts DataFrame and extract anomalies.
        """
        if df is None or df.empty:
            return
            
        # Ensure required columns exist
        required = ["contractSymbol", "volume", "openInterest", "lastPrice", "strike"]
        if not all(col in df.columns for col in required):
            return
            
        for _, row in df.iterrows():
            vol = row["volume"]
            oi = row["openInterest"]
            last_price = row["lastPrice"]
            strike = row["strike"]
            contract = row["contractSymbol"]
            
            # Skip if no volume or OI
            if not vol or vol < 10 or not oi or oi < 5:
                continue
                
            vol_oi_ratio = vol / oi
            premium = last_price * vol * 100  # Standard U.S. option contract multiplier
            
            # 1. Check Vol/OI Ratio threshold
            # 2. Check Premium threshold
            if vol_oi_ratio >= self.min_vol_oi and premium >= self.min_premium:
                # Calculate OTM percentage
                # (Simple estimation: needs current stock price, but we can do a relative check later)
                anomalies.append({
                    "id": contract,
                    "ticker": ticker,
                    "contract": contract,
                    "expiration": expiration,
                    "dte": dte,
                    "strike": strike,
                    "last_price": last_price,
                    "volume": int(vol),
                    "open_interest": int(oi),
                    "vol_oi_ratio": round(vol_oi_ratio, 2),
                    "premium": round(premium, 2),
                    "direction": direction,
                    "is_sweep": True if vol > 100 else False, # Estimate sweep based on high volume
                    "timestamp": datetime.now().isoformat()
                })

if __name__ == "__main__":
    # Self-test code
    # Using small thresholds for demonstration so that it finds some data if yfinance is installed
    scanner = YFinanceOptionsScanner(min_vol_oi=1.5, min_premium=50000.0, max_dte=7)
    
    if HAS_YFINANCE:
        # Scan SPY options as a demonstration
        results = scanner.scan_ticker("SPY")
        print(f"\n--- Scanning Complete. Found {len(results)} anomalies ---")
        for idx, anomaly in enumerate(results[:5]):
            print(f"\n[{idx+1}] Contract: {anomaly['contract']} ({anomaly['direction']})")
            print(f"    DTE: {anomaly['dte']} | Strike: {anomaly['strike']} | Price: ${anomaly['last_price']}")
            print(f"    Volume: {anomaly['volume']} | OI: {anomaly['open_interest']} | Vol/OI: {anomaly['vol_oi_ratio']}x")
            print(f"    Premium: ${anomaly['premium']:,}")
    else:
        print("Please install yfinance to test this script: pip install yfinance")
