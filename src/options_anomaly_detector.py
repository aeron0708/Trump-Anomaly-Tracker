# -*- coding: utf-8 -*-
"""
TSADS - Options Anomaly Detector
Calculates the multi-factor Anomaly Score (AS) for options transaction streams.
"""

from datetime import datetime, time
import random

class OptionsAnomalyDetector:
    def __init__(self, threshold=7.0):
        self.threshold = threshold
        # Roll average database simulator: Stores average premium per ticker
        self.avg_premium_db = {
            "SPY": 500000.0,   # $500k avg premium per sweep block
            "QQQ": 400000.0,   # $400k
            "DJT": 50000.0,    # $50k
            "IWM": 150000.0    # $150k
        }

    def is_market_off_peak(self, timestamp_str):
        """
        Determines if a given timestamp falls in non-peak hours (Pre-market, Post-market, or Lunch).
        Market open: 09:30 - 16:00 EST. Lunch: 11:30 - 13:00 EST.
        """
        try:
            dt = datetime.fromisoformat(timestamp_str)
            t = dt.time()
            
            pre_market = t < time(9, 30)
            post_market = t > time(16, 0)
            lunch_hour = time(11, 30) <= t <= time(13, 0)
            
            return pre_market or post_market or lunch_hour
        except Exception:
            # Fallback if parsing fails
            return False

    def calculate_anomaly_score(self, trade):
        """
        Calculates the Anomaly Score (0.0 to 10.0+) for a single option transaction.
        Formula: AS = w_vol_oi + w_premium + w_dte + w_direction + w_timing
        """
        score = 0.0
        details = {}

        ticker = trade.get("ticker", "UNKNOWN")
        vol_oi_ratio = trade.get("vol_oi_ratio", 0.0)
        premium = trade.get("premium", 0.0)
        dte = trade.get("dte", 30)
        is_sweep = trade.get("is_sweep", False)
        direction = trade.get("direction", "CALL")  # CALL / PUT
        timestamp = trade.get("timestamp", datetime.now().isoformat())
        
        # 1. Vol/OI Factor (Max: 3.0)
        if vol_oi_ratio >= 5.0:
            w_vol_oi = 3.0
        elif vol_oi_ratio >= 2.0:
            w_vol_oi = 2.0
        elif vol_oi_ratio >= 1.0:
            w_vol_oi = 1.0
        else:
            w_vol_oi = vol_oi_ratio * 0.8
        score += w_vol_oi
        details["Vol_OI_Factor"] = w_vol_oi

        # 2. Premium Factor (Max: 3.0 + 1.0 bonus for Sweeps)
        avg_prem = self.avg_premium_db.get(ticker, 100000.0)
        prem_ratio = premium / avg_prem
        
        if prem_ratio >= 5.0:
            w_premium = 3.0
        elif prem_ratio >= 3.0:
            w_premium = 2.0
        elif prem_ratio >= 1.5:
            w_premium = 1.0
        else:
            w_premium = 0.0
            
        # Sweep Bonus (Sweep represents urgency)
        if is_sweep and premium > 1000000.0:
            w_premium += 1.0
            
        score += w_premium
        details["Premium_Factor"] = w_premium

        # 3. DTE Factor (Max: 2.5)
        if dte == 0:
            w_dte = 2.5
        elif dte <= 1:
            w_dte = 2.0
        elif dte <= 3:
            w_dte = 1.5
        elif dte <= 7:
            w_dte = 1.0
        else:
            w_dte = 0.0
        score += w_dte
        details["DTE_Factor"] = w_dte

        # 4. Directional Concentration Factor (Max: 1.5)
        # In this transaction itself, if it is a highly aggressive sweep, we score it.
        w_direction = 0.0
        if is_sweep:
            w_direction += 1.0
        # If it's deep out-of-the-money (OTM) but heavily traded
        if trade.get("otm_pct", 0.0) > 0.10: # > 10% OTM
            w_direction += 0.5
        score += w_direction
        details["Direction_Factor"] = w_direction

        # 5. Timing Factor (Max: 1.0)
        w_timing = 1.0 if self.is_market_off_peak(timestamp) else 0.0
        score += w_timing
        details["Timing_Factor"] = w_timing

        # Final score rounding
        final_score = round(score, 2)
        is_anomaly = final_score >= self.threshold

        return {
            "trade_id": trade.get("id"),
            "ticker": ticker,
            "contract": trade.get("contract"),
            "direction": direction,
            "premium": premium,
            "vol_oi_ratio": vol_oi_ratio,
            "dte": dte,
            "anomaly_score": final_score,
            "is_anomaly": is_anomaly,
            "score_details": details
        }

    def generate_mock_option_flow(self):
        """
        Generates mock option flow containing both normal noise and highly anomalous trades.
        """
        # Get simulated timestamp during lunch hour to test off-peak factor
        lunch_time = datetime.now().replace(hour=12, minute=15, second=0).isoformat()
        normal_time = datetime.now().replace(hour=10, minute=0, second=0).isoformat()
        
        return [
            # 1. Normal Retail / Small Hedging Noise
            {
                "id": "opt_noise_001",
                "ticker": "SPY",
                "contract": "SPY 260619C00550000",
                "premium": 45000.0,
                "vol_oi_ratio": 0.15,
                "dte": 7,
                "is_sweep": False,
                "otm_pct": 0.02,
                "direction": "CALL",
                "timestamp": normal_time
            },
            # 2. Institutional Standard Hedging (Large but far DTE)
            {
                "id": "opt_hedge_002",
                "ticker": "QQQ",
                "contract": "QQQ 260918P00380000",
                "premium": 1200000.0,
                "vol_oi_ratio": 0.8,
                "dte": 90,
                "is_sweep": False,
                "otm_pct": 0.05,
                "direction": "PUT",
                "timestamp": normal_time
            },
            # 3. Anomaly Case 1: Tariff Leaker (SPY Massive Short-term Put Sweep during lunch)
            {
                "id": "opt_anomaly_003",
                "ticker": "SPY",
                "contract": "SPY 260615P00500000",
                "premium": 4800000.0, # $4.8 Million
                "vol_oi_ratio": 4.5,  # 4.5x OI
                "dte": 1,             # 1 Day to expiration
                "is_sweep": True,
                "otm_pct": 0.12,      # 12% Out of the Money
                "direction": "PUT",
                "timestamp": lunch_time
            },
            # 4. Anomaly Case 2: Crypto Deregulation Leaker (DJT 0DTE OTM Call Sweep)
            {
                "id": "opt_anomaly_004",
                "ticker": "DJT",
                "contract": "DJT 260612C00060000",
                "premium": 450000.0,  # $450k (huge for DJT, avg is $50k)
                "vol_oi_ratio": 5.2,  # 5.2x OI
                "dte": 0,             # 0DTE (Expiring today!)
                "is_sweep": True,
                "otm_pct": 0.20,      # 20% OTM
                "direction": "CALL",
                "timestamp": normal_time
            }
        ]

if __name__ == "__main__":
    detector = OptionsAnomalyDetector(threshold=7.0)
    mock_trades = detector.generate_mock_option_flow()
    
    print("\n--- Running Options Anomaly Detection ---")
    for trade in mock_trades:
        res = detector.calculate_anomaly_score(trade)
        print(f"\nID: {res['trade_id']} | Ticker: {res['ticker']} | Contract: {res['contract']}")
        print(f"Direction: {res['direction']} | Premium: ${res['premium']:,} | Vol/OI: {res['vol_oi_ratio']}x | DTE: {res['dte']}")
        print(f"-> Anomaly Score: {res['anomaly_score']} | Is Anomaly: {res['is_anomaly']}")
        print(f"   Breakdown: {res['score_details']}")
