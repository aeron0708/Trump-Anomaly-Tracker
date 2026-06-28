# -*- coding: utf-8 -*-
"""
TSADS - Alert Alignment Engine (v2.3)
Aligns options anomalies with social media posts, executing cross-validation,
calculating Greeks-hedged option spreads, logging to SQLite, and sending Telegram alerts.
Supports HTML formatting, keyword tagging (war, trade war, tariffs, inflation, rates, etc.),
consolidation of alerts, and removal of DJT.
"""

from datetime import datetime, timedelta
import urllib.request
import urllib.parse
import json
import sys
import os
import html

# Reconfigure stdout to UTF-8 on Windows if possible
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
        
        self.db_logger = SQLiteLogger(db_path)
        self.pos_manager = PositionManager(account_value=100000.0)

    def map_ticker_to_sectors(self, ticker):
        """
        Maps trading tickers/ETFs to system defined sectors.
        """
        mapping = {
            "SPY": ["General Market", "Automotive", "Semiconductors", "Steel & Metals", "China-Exposure"],
            "QQQ": ["General Market", "Semiconductors", "China-Exposure"],
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
        Consolidates alerts by ticker and direction.
        """
        self.post_history.append(post_analysis)
        self._clean_expired_history()
        
        self.db_logger.log_post(post_analysis)
        
        print(f"[TSADS Engine] Processed Truth Social Post. Sectors: {post_analysis['sectors']} | Direction: {post_analysis['trading_direction']}")
        
        if not post_analysis.get("has_impact", False):
            return None
            
        # Group matching options in history by (ticker, direction)
        matched_opts = {}
        for opt in self.option_history:
            if self._are_aligned(post_analysis, opt):
                key = (opt["ticker"].upper(), opt["direction"].upper())
                if key not in matched_opts:
                    matched_opts[key] = []
                matched_opts[key].append(opt)
                
        alignments = []
        for (ticker, direction), opt_list in matched_opts.items():
            alert = self._create_aligned_alert_grouped(post_analysis, ticker, direction, opt_list)
            alignments.append(alert)
            self.dispatch_alert(alert, level="RED")
            
        return alignments

    def process_new_anomalies_grouped(self, new_anomalies):
        """
        Processes a list of new option anomalies, groups them by (ticker, direction),
        and aligns them with post history to send consolidated alerts.
        """
        for opt in new_anomalies:
            self.option_history.append(opt)
        self._clean_expired_history()
        
        # Log all to DB
        for opt in new_anomalies:
            self.db_logger.log_option(opt)
            
        # Group by (ticker, direction)
        groups = {}
        for opt in new_anomalies:
            key = (opt["ticker"].upper(), opt["direction"].upper())
            if key not in groups:
                groups[key] = []
            groups[key].append(opt)
            
        alerts = []
        for (ticker, direction), opt_list in groups.items():
            matched = False
            for post in self.post_history:
                if self._are_aligned(post, opt_list[0]):
                    alert = self._create_aligned_alert_grouped(post, ticker, direction, opt_list)
                    self.dispatch_alert(alert, level="RED")
                    alerts.append(alert)
                    matched = True
                    break
            
            if not matched:
                # Check if any option in the list has score >= 9.0
                high_score_opts = [o for o in opt_list if o["anomaly_score"] >= 9.0]
                if high_score_opts:
                    alert = self._create_standalone_alert_grouped(ticker, direction, high_score_opts)
                    self.dispatch_alert(alert, level="YELLOW")
                    alerts.append(alert)
        return alerts

    def _are_aligned(self, post, opt):
        """
        Core alignment logic: Check if option flow direction and ticker sectors
        align with the LLM/Rule semantic analysis of the post.
        """
        # Time check
        post_time = datetime.fromisoformat(post["timestamp"])
        opt_time = datetime.fromisoformat(opt["timestamp"])
        
        time_diff = abs((opt_time - post_time).total_seconds()) / 60.0
        if time_diff > self.alignment_window_minutes:
            return False

        # Direction check
        post_dir = post.get("trading_direction", "NONE")
        opt_dir = opt.get("direction", "NONE")
        if post_dir != opt_dir:
            return False
            
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

    def _create_aligned_alert_grouped(self, post, ticker, direction, opt_list):
        """
        Combines post metadata and option metadata into a structured RED Alert with Greeks hedging.
        """
        max_score = max(o["anomaly_score"] for o in opt_list)
        total_premium = sum(o["premium"] for o in opt_list)
        avg_vol_oi = sum(o["vol_oi_ratio"] for o in opt_list) / len(opt_list)
        avg_dte = sum(o["dte"] for o in opt_list) / len(opt_list)
        
        has_tlt_resonance = False
        tlt_msg = ""
        if ticker in ["SPY", "QQQ"]:
            for hist_opt in self.option_history:
                if hist_opt["ticker"].upper() == "TLT" and hist_opt["direction"] == direction:
                    has_tlt_resonance = True
                    tlt_msg = f"【美債共振提醒】偵測到美債 TLT 期權同步出現 {direction} 異常流，債市同步押注政策預期，訊號可信度加分！"
                    break
        
        pos_info = self.pos_manager.calculate_position_size(max_score, has_resonance=has_tlt_resonance)
        
        spot_prices = {"SPY": 500.0, "QQQ": 400.0, "TLT": 95.0, "GLD": 220.0, "USO": 75.0}
        spot = spot_prices.get(ticker, 100.0)
        spread_info = self.pos_manager.generate_spread_recommendation(ticker, direction, current_price=spot)
        
        reason = f"川普發言提及板塊 {post['sectors']}，與 {ticker} 短期 {direction} 掃單方向高度一致。"
        if has_tlt_resonance:
            reason += " 且觀測到美債 TLT 同步共振！"
            
        contracts_desc = []
        for o in opt_list:
            contracts_desc.append(f"• {o['contract']} (Vol/OI: {o['vol_oi_ratio']}x, 規模: ${o['premium']:,}, DTE: {o['dte']})")
        contracts_text = "\n".join(contracts_desc)
        
        alert = {
            "alert_id": f"ALERT_RED_{int(datetime.now().timestamp())}_{ticker}_{direction}",
            "level": "RED",
            "timestamp": datetime.now().isoformat(),
            "ticker": ticker,
            "contract": ", ".join(o["contract"] for o in opt_list),
            "contracts_detail": contracts_text,
            "action": direction,
            "vol_oi_ratio": round(avg_vol_oi, 2),
            "premium": total_premium,
            "dte": int(round(avg_dte)),
            "source_post": post["text"],
            "source_link": post.get("link", ""),
            "confidence": post.get("confidence", 0.0),
            "sentiment": post.get("sentiment", "NEUTRAL"),
            "sectors": post.get("sectors", []),
            "reason": reason,
            "trading_guideline": f"【跟單建議】買入 {spread_info['strategy']}。買入 Strike {spread_info['buy_strike']} / 賣出 Strike {spread_info['sell_strike']}。執行限價單，且進場後 45-60 分鐘內不論盈虧強制平倉。",
            "allocated_dollars": pos_info["allocated_dollars"],
            "allocated_percent": pos_info["allocated_percent"],
            "buy_strike": float(spread_info["buy_strike"]),
            "sell_strike": float(spread_info["sell_strike"]),
            "hedging_reason": spread_info["greeks_hedging_reason"],
            "tlt_resonance_msg": tlt_msg
        }
        
        self.db_logger.log_alert(alert)
        return alert

    def _create_standalone_alert_grouped(self, ticker, direction, opt_list):
        """
        Creates a structured YELLOW Alert for standalone high-score anomalies.
        """
        max_score = max(o["anomaly_score"] for o in opt_list)
        total_premium = sum(o["premium"] for o in opt_list)
        avg_vol_oi = sum(o["vol_oi_ratio"] for o in opt_list) / len(opt_list)
        avg_dte = sum(o["dte"] for o in opt_list) / len(opt_list)
        
        pos_info = self.pos_manager.calculate_position_size(max_score, has_resonance=False)
        spot_prices = {"SPY": 500.0, "QQQ": 400.0, "TLT": 95.0, "GLD": 220.0, "USO": 75.0}
        spot = spot_prices.get(ticker, 100.0)
        spread_info = self.pos_manager.generate_spread_recommendation(ticker, direction, current_price=spot)
        
        contracts_desc = []
        for o in opt_list:
            contracts_desc.append(f"• {o['contract']} (Vol/OI: {o['vol_oi_ratio']}x, 規模: ${o['premium']:,}, DTE: {o['dte']})")
        contracts_text = "\n".join(contracts_desc)
        
        alert = {
            "alert_id": f"ALERT_YELLOW_{int(datetime.now().timestamp())}_{ticker}_{direction}",
            "level": "YELLOW",
            "timestamp": datetime.now().isoformat(),
            "ticker": ticker,
            "contract": ", ".join(o["contract"] for o in opt_list),
            "contracts_detail": contracts_text,
            "action": direction,
            "vol_oi_ratio": round(avg_vol_oi, 2),
            "premium": total_premium,
            "dte": int(round(avg_dte)),
            "source_post": "N/A (無近期對齊貼文，可能是提前洩露或市場噪音)",
            "source_link": "",
            "confidence": 0.0,
            "sentiment": "N/A",
            "sectors": [],
            "reason": f"市場期權流在 {ticker} 出現非典型 {direction} 掃單，異常分數高達 {max_score}，尚未觀測到發言對齊。",
            "trading_guideline": f"【觀望建議】建立防守型 {spread_info['strategy']}。買入 Strike {spread_info['buy_strike']} / 賣出 Strike {spread_info['sell_strike']}。控制總倉位在 {pos_info['allocated_percent']}% 內，設好嚴格停損。",
            "allocated_dollars": pos_info["allocated_dollars"],
            "allocated_percent": pos_info["allocated_percent"],
            "buy_strike": float(spread_info["buy_strike"]),
            "sell_strike": float(spread_info["sell_strike"]),
            "hedging_reason": spread_info["greeks_hedging_reason"],
            "tlt_resonance_msg": ""
        }
        
        self.db_logger.log_alert(alert)
        return alert

    def dispatch_alert(self, alert, level="RED"):
        """
        Dispatches alert to Telegram using HTML parsing.
        """
        emoji = "🔴 <b>[TSADS RED ALERT] 雙重對齊警報</b>" if level == "RED" else "🟡 <b>[TSADS YELLOW ALERT] 前置期權異常</b>"
        
        # Check for macro tags in the source post
        post_text = alert.get("source_post", "").lower()
        tags = []
        if any(w in post_text for w in ["war", "conflict", "military", "defense", "forces", "strike", "hit", "伊朗", "戰爭", "軍事", "國防", "打擊"]):
            tags.append("🚨 戰爭地緣")
        if any(w in post_text for w in ["tariff", "tariffs", "trade war", "sanctions", "china", "chinese", "關稅", "貿易戰", "制裁", "中國"]):
            tags.append("⚠️ 貿易戰/關稅")
        if any(w in post_text for w in ["rate", "rates", "interest", "inflation", "fed", "yield", "cpi", "利率", "通膨", "美聯儲", "降息", "升息"]):
            tags.append("📊 利率/通膨/Fed")
        if any(w in post_text for w in ["invest", "equity", "stake", "merger", "acquisition", "buy", "入股", "投資", "併購", "股權"]):
            tags.append("💰 入股/投資/併購")

        tags_part = ""
        if tags:
            tags_part = f"\n<b>■ 宏觀標籤</b>: " + " | ".join(f"<code>{t}</code>" for t in tags) + "\n"
            
        tlt_part = ""
        if alert.get("tlt_resonance_msg"):
            tlt_part = f"\n<b>■ 債市指標</b>: {alert['tlt_resonance_msg']}\n"
            
        link_part = ""
        if alert.get("source_link"):
            link_part = f'\n<b>■ 貼文連結</b>: <a href="{alert["source_link"]}">點擊查看 Truth Social 原文</a>'
            
        escaped_post = html.escape(alert.get("source_post", "N/A"))
        
        msg = f"""
{emoji}
━━━━━━━━━━━━━━━━━━{tags_part}
<b>■ 交易標的</b>: {alert['ticker']} ({alert['action']})
<b>■ 異常合約</b>:
{alert.get('contracts_detail', alert['contract'])}

<b>■ 合計規模</b>: 均 Vol/OI {alert['vol_oi_ratio']}x | 總額: ${alert['premium']:,} (均 DTE: {alert['dte']}){tlt_part}
<b>■ 建議倉位</b>: {alert['allocated_percent']}% (${alert['allocated_dollars']:,} USD)
<b>■ 對沖策略</b>: 建立 {alert['buy_strike']} / {alert['sell_strike']} 垂直價差
<b>■ 避險理由</b>: {alert.get('hedging_reason', '')}
<b>■ 警報原因</b>: {alert['reason']}
<b>■ 川普發言</b>: <i>"{escaped_post}"</i>{link_part}
<b>■ 實戰建議</b>: {alert['trading_guideline']}
━━━━━━━━━━━━━━━━━━
"""
        
        try:
            print(msg)
        except Exception:
            print(f"[{level} ALERT] {alert['ticker']} {alert['action']} - Premium: ${alert['premium']:,}")
        
        # Send via Telegram API
        if self.tg_token and self.tg_chat_id:
            try:
                tg_url = f"https://api.telegram.org/bot{self.tg_token}/sendMessage"
                data = urllib.parse.urlencode({
                    "chat_id": self.tg_chat_id,
                    "text": msg,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": "true"
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
        "text": "Trade war with China will happen! New tariffs of 50%!",
        "timestamp": datetime.now().isoformat(),
        "has_impact": True,
        "sectors": ["China-Exposure"],
        "sentiment": "NEGATIVE",
        "trading_direction": "PUT",
        "confidence": 0.9,
        "link": "https://truthsocial.com/realDonaldTrump/12345"
    }
    
    mock_anomalies = [
        {
            "ticker": "SPY",
            "contract": "SPY 260615P00500000",
            "premium": 4800000.0,
            "vol_oi_ratio": 4.5,
            "dte": 1,
            "direction": "PUT",
            "anomaly_score": 10.5,
            "timestamp": datetime.now().isoformat()
        },
        {
            "ticker": "SPY",
            "contract": "SPY 260615P00510000",
            "premium": 2500000.0,
            "vol_oi_ratio": 3.2,
            "dte": 1,
            "direction": "PUT",
            "anomaly_score": 9.5,
            "timestamp": datetime.now().isoformat()
        }
    ]
    
    engine.process_new_post(mock_post)
    engine.process_new_anomalies_grouped(mock_anomalies)
    
    if os.path.exists("tsads_test.db"):
        os.remove("tsads_test.db")
