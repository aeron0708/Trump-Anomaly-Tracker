# -*- coding: utf-8 -*-
"""
TSADS - Position Manager & Option Greeks Hedging Engine
Calculates dynamic position sizing and generates vertical spread option recommendations.
"""

class PositionManager:
    def __init__(self, account_value=100000.0):
        self.account_value = account_value

    def calculate_position_size(self, anomaly_score, has_resonance=False):
        """
        Calculates position size in dollars and percentage based on Anomaly Score and market resonance.
        Max cap is 5.0% of total account value to protect against tail risk.
        """
        if anomaly_score < 7.0:
            pct = 0.0
        elif anomaly_score < 8.0:
            pct = 1.0
        elif anomaly_score < 9.0:
            pct = 2.0
        elif anomaly_score < 10.0:
            pct = 3.5
        else:
            pct = 5.0
            
        # Boost allocation slightly if there is multi-market resonance (e.g. currency/bond confirmation)
        if has_resonance and pct > 0.0:
            pct = min(5.0, pct + 1.0)
            
        allocated_dollars = self.account_value * (pct / 100.0)
        return {
            "account_value": self.account_value,
            "allocated_percent": pct,
            "allocated_dollars": round(allocated_dollars, 2)
        }

    def generate_spread_recommendation(self, ticker, direction, current_price):
        """
        Generates Options Vertical Spread contract recommendations to hedge against IV Crush.
        """
        if current_price <= 0:
            current_price = 100.0 # Fallback
            
        strike_step = 5.0 if current_price >= 200.0 else 1.0
        
        if direction == "CALL":
            # Bull Call Spread (Buy ATM, Sell OTM)
            buy_strike = round(current_price / strike_step) * strike_step
            sell_strike = buy_strike + strike_step
            strategy = "Bull Call Spread (牛市看漲價差)"
            reason = "透過賣出更高價外 Call 獲取權利金，對沖川普消息公布後隱含波動率（IV）驟降造成的 Delta/Vega 損耗。"
        else:
            # Bear Put Spread (Buy ATM, Sell OTM)
            buy_strike = round(current_price / strike_step) * strike_step
            sell_strike = buy_strike - strike_step
            strategy = "Bear Put Spread (熊市看跌價差)"
            reason = "透過賣出更低價外 Put 獲取權利金，降低買入 Put 的成本，並對抗 IV Crush 的隱含波動率崩潰。"
            
        return {
            "ticker": ticker,
            "strategy": strategy,
            "buy_strike": buy_strike,
            "sell_strike": sell_strike,
            "strike_step": strike_step,
            "greeks_hedging_reason": reason
        }

if __name__ == "__main__":
    pm = PositionManager(account_value=100000.0)
    
    print("\n--- Testing Dynamic Position Sizing ---")
    for score in [6.5, 7.5, 8.8, 10.5]:
        size = pm.calculate_position_size(anomaly_score=score, has_resonance=True)
        print(f"Anomaly Score: {score} | Allocated: {size['allocated_percent']}% (${size['allocated_dollars']:,})")
        
    print("\n--- Testing Greeks Spread Recommendation ---")
    rec_call = pm.generate_spread_recommendation("SPY", "CALL", 503.2)
    print(f"Ticker: {rec_call['ticker']} | Strategy: {rec_call['strategy']}")
    print(f"Buy Strike: {rec_call['buy_strike']} | Sell Strike: {rec_call['sell_strike']}")
    print(f"Reason: {rec_call['greeks_hedging_reason']}")
