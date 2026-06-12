# -*- coding: utf-8 -*-
"""
TSADS - Alert Alignment Engine (v2.1)
Aligns options anomalies with social media posts, executing cross-validation,
calculating Greeks-hedged option spreads, logging to SQLite, and sending Telegram alerts.
Now includes TLT (Bond) resonance as a signal boost and extra alert warning.
"""

from datetime import datetime, timedelta
import urllib.request
import urllib.parse
import json
import sys
import os

# Reconfigure stdout to UTF-8 on Windows if possible to support emojis and Unicode symbols
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Import TSADS components
from sqlite_logger import SQLiteLogger
from position_manager import PositionManager

class AlertAlignmentEngine:
    def __init__(self, tg_token=None, tg_chat_id=None, db_path="tsads_history.db"):
        self.tg_token = tg_token or os.environ.get("TELEGRAM_BOT_TOKEN")
        self.tg_chat_id = tg_chat_id or os.environ.get("TELEGRAM_CHAT_ID")
        
        # In-memory history for matching within time windows (default: 30 minutes)
        self.post_history = []
        self.option_history = []
        self.alignment_window_minutes = 30
        
        # Initialize TSADS v2.0 managers
        self.db_logger = SQLiteLogger(db_path)
        self.pos_manager = PositionManager(account_value=100000.0)

    def map_ticker_to_sectors(self, ticker):
        """
        Maps trading tickers/ETFs to system defined sectors.
        """
        mapping = {
            "SPY": ["General Market", "Automotive", "Semiconductors", "Steel & Metals", "China-Exposure"],
            "QQQ": ["General Market", "Semiconductors", "China-Exposure"],
            "DJT": ["General Market", "Financials"],
            "USO": ["Energy & Oil"],
            "BTC": ["Cryptocurrency"],
            "ETH": ["Cryptocurrency"],
            "TLT": ["Bonds & Rates"],
            "GLD": ["Safe-Haven & Gold"]
        }
        return mapping.get(ticker.upper(), ["General Market"])

    def process_new_post(self, post_analysis):
        """
        Saves a new post analysis, logs to SQLite, and checks for matching option anomalies in history.
        """
        self.post_history.append(post_analysis)
        self._clean_expired_history()
        
        # TSADS v2.0: Log post to SQLite
        self.db_logger.log_post(post_analysis)
        
        print(f"[TSADS Engine] Processed Truth Social Post. Sectors: {post_analysis['sectors']} | Direction: {post_analysis['trading_direction']}")
        
        if not post_analysis.get("has_impact", False):
            return None
            
        alignments = []
        # Look for matching options in history
        for opt in self.option_history:
            if self._are_aligned(post_analysis, opt):
                alert = self._create_aligned_alert(post_analysis, opt)
                alignments.append(alert)
                self.dispatch_alert(alert, level="RED")
                
        return alignments

    def process_new_option_anomaly(self, opt_anomaly):
        """
        Saves a new option anomaly, logs to SQLite, and checks for matching posts in history.
        If no post matches but the score is exceptionally high, triggers a YELLOW alert.
        """
        self.option_history.append(opt_anomaly)
        self._clean_expired_history()
        
        # TSADS v2.0: Log option anomaly to SQLite
        self.db_logger.log_option(opt_anomaly)
        
        ticker = opt_anomaly["ticker"]
        score = opt_anomaly["anomaly_score"]
        direction = opt_anomaly["direction"]
        
        print(f"[TSADS Engine] Processed Option Anomaly. Ticker: {ticker} | Score: {score} | Direction: {direction}")
        
        # Look for matching posts in history
        matched = False
        for post in self.post_history:
            if self._are_aligned(post, opt_anomaly):
                alert = self._create_aligned_alert(post, opt_anomaly)
                self.dispatch_alert(alert, level="RED")
                matched = True
                return alert
                
        if not matched:
            # Check if standalone anomaly score is high (e.g. >= 8.0)
            if score >= 8.0:
                alert = self._create_standalone_alert(opt_anomaly)
                self.dispatch_alert(alert, level="YELLOW")
                return alert
        return None

    def _are_aligned(self, post, opt):
        """
        Core alignment logic: Check if option flow direction and ticker sectors
        align with the LLM/Rule semantic analysis of the post.
        """
        # Time check
        post_time = datetime.fromisoformat(post["timestamp"])
        opt_time = datetime.now() # Simulated current time
        
        time_diff = abs((opt_time - post_time).total_seconds()) / 60.0
        if time_diff > self.alignment_window_minutes:
            return False

        # Direction check
        post_dir = post.get("trading_direction", "NONE")
        opt_dir = opt.get("direction", "NONE")
        if post_dir != opt_dir:
            return False
            
        # DJT (Trump concept stock) directly aligns with any market-impacting Trump post if direction matches
        if opt["ticker"].upper() == "DJT":
            return True
            
        # Sector check
        opt_sectors = self.map_ticker_to_sectors(opt["ticker"])
        post_sectors = post.get("sectors", [])
        
        # Check intersection
        has_common_sector = any(sector in opt_sectors for sector in post_sectors)
        
        # Map general market or bond/rate scenarios
        if "General Market" in post_sectors and "General Market" in opt_sectors:
            has_common_sector = True
            
        # Map macro sectors (e.g. "Bonds & Rates" triggered by Fed/Rate talk)
        if "Financials" in post_sectors and "Bonds & Rates" in opt_sectors:
            has_common_sector = True
            
        # Map macro safe-haven (e.g. Geopolitics/War or China Tariffs boosts Gold CALLs)
        if ("Defense" in post_sectors or "China-Exposure" in post_sectors) and "Safe-Haven & Gold" in opt_sectors and opt_dir == "CALL":
            has_common_sector = True
            
        return has_common_sector

    def _clean_expired_history(self):
        """
        Cleans up items older than the alignment window to prevent memory leaks.
        """
        now = datetime.now()
        threshold_time = now - timedelta(minutes=self.alignment_window_minutes)
        
        self.post_history = [
            p for p in self.post_history 
            if datetime.fromisoformat(p["timestamp"]) > threshold_time
        ]

    def _create_aligned_alert(self, post, opt):
        """
        Combines post metadata and option metadata into a structured RED Alert with Greeks hedging.
        Checks for TLT (Bond) resonance as a signal boost.
        """
        ticker = opt["ticker"]
        direction = opt["direction"]
        score = opt["anomaly_score"]
        
        # TSADS v2.1: Check for TLT (Bond) resonance if we are processing SPY/QQQ
        has_tlt_resonance = False
        tlt_msg = ""
        if ticker.upper() in ["SPY", "QQQ"]:
            for hist_opt in self.option_history:
                # If TLT has an anomaly in the same direction recently (within window)
                if hist_opt["ticker"].upper() == "TLT" and hist_opt["direction"] == direction:
                    has_tlt_resonance = True
                    tlt_msg = f"【美債共振提醒】偵測到美債 TLT 期權同步出現 {direction} 異常流，債市同步押注政策預期，訊號可信度加分！"
                    break
        
        # Dynamic position (boosted if TLT resonance exists) and Greeks hedging spreads calculation
        pos_info = self.pos_manager.calculate_position_size(score, has_resonance=has_tlt_resonance)
        
        # Assume an estimated spot price for spread strike calculations
        spot_prices = {"SPY": 500.0, "QQQ": 400.0, "DJT": 50.0, "TLT": 95.0, "GLD": 220.0}
        spot = spot_prices.get(ticker, 100.0)
        spread_info = self.pos_manager.generate_spread_recommendation(ticker, direction, current_price=spot)
        
        reason = f"川普發言提及板塊 {post['sectors']}，與 {ticker} 短期 {direction} 掃單方向高度一致。"
        if has_tlt_resonance:
            reason += " 且觀測到美債 TLT 同步共振！"
            
        alert = {
            "alert_id": f"ALERT_RED_{int(datetime.now().timestamp())}",
            "level": "RED",
            "timestamp": datetime.now().isoformat(),
            "ticker": ticker,
            "contract": opt["contract"],
            "action": direction,
            "vol_oi_ratio": opt["vol_oi_ratio"],
            "premium": opt["premium"],
            "dte": opt["dte"],
            "source_post": post["text"],
            "reason": reason,
            "trading_guideline": f"【跟單建議】買入 {spread_info['strategy']}。買入 Strike {spread_info['buy_strike']} / 賣出 Strike {spread_info['sell_strike']}。執行限價單，且進場後 45-60 分鐘內不論盈虧強制平倉。",
            "allocated_dollars": pos_info["allocated_dollars"],
            "allocated_percent": pos_info["allocated_percent"],
            "buy_strike": float(spread_info["buy_strike"]),
            "sell_strike": float(spread_info["sell_strike"]),
            "hedging_reason": spread_info["greeks_hedging_reason"],
            "tlt_resonance_msg": tlt_msg # v2.1 warning note
        }
        
        # TSADS v2.0: Log alert to SQLite db
        self.db_logger.log_alert(alert)
        return alert

    def _create_standalone_alert(self, opt):
        """
        Creates a structured YELLOW Alert for standalone high-score anomalies.
        """
        ticker = opt["ticker"]
        direction = opt["direction"]
        score = opt["anomaly_score"]
        
        pos_info = self.pos_manager.calculate_position_size(score, has_resonance=False)
        spot_prices = {"SPY": 500.0, "QQQ": 400.0, "DJT": 50.0, "TLT": 95.0, "GLD": 220.0}
        spot = spot_prices.get(ticker, 100.0)
        spread_info = self.pos_manager.generate_spread_recommendation(ticker, direction, current_price=spot)
        
        alert = {
            "alert_id": f"ALERT_YELLOW_{int(datetime.now().timestamp())}",
            "level": "YELLOW",
            "timestamp": datetime.now().isoformat(),
            "ticker": ticker,
            "contract": opt["contract"],
            "action": direction,
            "vol_oi_ratio": opt["vol_oi_ratio"],
            "premium": opt["premium"],
            "dte": opt["dte"],
            "source_post": "N/A (無近期對齊貼文，可能是提前洩露或市場噪音)",
            "reason": f"市場期權流在 {ticker} 出現非典型 {direction} 掃單，異常分數高達 {score}，尚未觀測到發言對齊。",
            "trading_guideline": f"【觀望建議】建立防守型 {spread_info['strategy']}。買入 Strike {spread_info['buy_strike']} / 賣出 Strike {spread_info['sell_strike']}。控制總倉位在 {pos_info['allocated_percent']}% 內，設好嚴格停損。",
            "allocated_dollars": pos_info["allocated_dollars"],
            "allocated_percent": pos_info["allocated_percent"],
            "buy_strike": float(spread_info["buy_strike"]),
            "sell_strike": float(spread_info["sell_strike"]),
            "hedging_reason": spread_info["greeks_hedging_reason"],
            "tlt_resonance_msg": ""
        }
        
        # TSADS v2.0: Log alert to SQLite db
        self.db_logger.log_alert(alert)
        return alert

    def dispatch_alert(self, alert, level="RED"):
        """
        Dispatches alert to Telegram and outputs formatted console log.
        """
        emoji = "🔴 [TSADS RED ALERT] 雙重對齊警報" if level == "RED" else "🟡 [TSADS YELLOW ALERT] 前置期權異常"
        
        # Build extra Bond resonance line if active
        tlt_part = ""
        if alert.get("tlt_resonance_msg"):
            tlt_part = f"\n■ 債市指標: {alert['tlt_resonance_msg']}\n"
            
        msg = f"""
{emoji}
━━━━━━━━━━━━━━━━━━
■ 交易標的: {alert['ticker']} ({alert['action']})
■ 合約名稱: {alert['contract']}
■ 異常倍數: Vol/OI {alert['vol_oi_ratio']}x | 規模: ${alert['premium']:,} (DTE: {alert['dte']}){tlt_part}
■ 建議倉位: {alert['allocated_percent']}% (${alert['allocated_dollars']:,} USD)
■ 對沖策略: 建立 {alert['buy_strike']} / {alert['sell_strike']} 垂直價差
■ 避險理由: {alert.get('hedging_reason', '')}
■ 警報原因: {alert['reason']}
■ 實戰建議: {alert['trading_guideline']}
━━━━━━━━━━━━━━━━━━
"""
        try:
            print(msg)
        except UnicodeEncodeError:
            # Fallback for environments CP950 console without UTF-8 reconfigure
            clean_msg = msg.replace("🔴", "[RED]").replace("🟡", "[YELLOW]")
            clean_msg = clean_msg.replace("━━━━━━━━━━━━━━━━━━", "----------------------------------")
            clean_msg = clean_msg.replace("■", "-")
            try:
                enc = sys.stdout.encoding or 'ascii'
                print(clean_msg.encode(enc, errors='replace').decode(enc))
            except Exception:
                print(f"[{level} ALERT] {alert['ticker']} {alert['action']} - Premium: ${alert['premium']:,} - DTE: {alert['dte']}")
        
        # Send via Telegram API if configured
        if self.tg_token and self.tg_chat_id:
            try:
                tg_url = f"https://api.telegram.org/bot{self.tg_token}/sendMessage"
                data = urllib.parse.urlencode({
                    "chat_id": self.tg_chat_id,
                    "text": msg,
                    "parse_mode": "Markdown"
                }).encode("utf-8")
                
                req = urllib.request.Request(tg_url, data=data)
                with urllib.request.urlopen(req, timeout=5) as response:
                    if response.status == 200:
                        print("[TSADS Engine] Telegram alert sent successfully.")
            except Exception as e:
                print(f"[TSADS Engine] Failed to send Telegram alert: {e}")

if __name__ == "__main__":
    # Test script in action
    engine = AlertAlignmentEngine(db_path="tsads_test.db")
    
    mock_post = {
        "id": "test_post_999",
        "text": "Cars are bad!",
        "timestamp": datetime.now().isoformat(),
        "has_impact": True,
        "sectors": ["Automotive"],
        "sentiment": "NEGATIVE",
        "trading_direction": "PUT",
        "confidence": 0.9
    }
    mock_option = {
        "ticker": "SPY",
        "contract": "SPY 260615P00500000",
        "premium": 4800000.0,
        "vol_oi_ratio": 4.5,
        "dte": 1,
        "direction": "PUT",
        "anomaly_score": 10.5,
        "is_anomaly": True
    }
    
    engine.process_new_post(mock_post)
    engine.process_new_option_anomaly(mock_option)
    
    if os.path.exists("tsads_test.db"):
        os.remove("tsads_test.db")
