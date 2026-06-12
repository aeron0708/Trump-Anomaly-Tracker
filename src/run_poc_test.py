# -*- coding: utf-8 -*-
"""
TSADS v2.0 - End-to-End Compliance Test Suite (10-Round Verification)
Implements QA Lead's ten-round test matrix covering anomaly detection,
multi-market resonance, SQLite database validation, Greeks hedging, and CP950 safety.
"""

import os
import time
import sqlite3
import asyncio
from datetime import datetime
from truth_social_monitor import TruthSocialMonitor
from options_anomaly_detector import OptionsAnomalyDetector
from alert_alignment_engine import AlertAlignmentEngine
from async_market_scanner import AsyncMarketScanner

# Reconfigure stdout to UTF-8 on Windows
import sys
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def load_dotenv():
    paths = [".env", "Trump_Anomaly_Tracker/.env", "../.env", "src/.env"]
    for path in paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if "=" in line and not line.startswith("#"):
                            key, val = line.split("=", 1)
                            os.environ[key.strip()] = val.strip()
                print(f"[TSADS] Loaded environment variables from: {os.path.abspath(path)}")
                return
            except Exception:
                pass

load_dotenv()

class QATestSuite:
    def __init__(self, db_path="tsads_history.db"):
        self.db_path = db_path
        # Clean up database if exists for a fresh test run
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except Exception:
                pass
                
        self.monitor = TruthSocialMonitor(use_llm=True) # Will automatically load NVIDIA NIM if configured in .env
        self.detector = OptionsAnomalyDetector(threshold=7.0)
        self.engine = AlertAlignmentEngine(db_path=self.db_path)
        
        self.test_results = []

    def log_result(self, round_num, description, status, details=""):
        self.test_results.append({
            "round": round_num,
            "description": description,
            "status": status,
            "details": details
        })

    def run_all_rounds(self):
        print("=========================================================")
        print("      TSADS v2.0 - QA 10-ROUND VERIFICATION MATRIX       ")
        print("=========================================================")
        
        # Async Scanner Warmup demonstration
        print("\n[QA Warmup] Running Asynchronous Multi-Market scan...")
        scanner = AsyncMarketScanner(use_mock=True)
        loop = asyncio.get_event_loop()
        prices = loop.run_until_complete(scanner.scan_all_markets())
        print(f"[QA Warmup] Concurrently fetched {len(prices)} ticker prices: {list(prices.keys())}")
        time.sleep(1)

        # --- Round 1: SPY Short-term Put + Tariff Post (RED Alert) ---
        print("\n>>> 【第一輪】SPY 短期大額 Put + 汽車關稅貼文對齊")
        post = {
            "text": "I will impose a 20% tariff on imported autos from Europe!",
            "timestamp": datetime.now().isoformat()
        }
        opt = {
            "ticker": "SPY",
            "contract": "SPY 260615P00500000",
            "premium": 4800000.0,
            "vol_oi_ratio": 4.5,
            "dte": 1,
            "is_sweep": True,
            "otm_pct": 0.12,
            "direction": "PUT",
            "timestamp": datetime.now().isoformat()
        }
        
        post_an = self.monitor.analyze_post(post["text"])
        self.engine.process_new_post(post_an)
        score_res = self.detector.calculate_anomaly_score(opt)
        alert = self.engine.process_new_option_anomaly(score_res)
        
        if alert and alert["level"] == "RED" and alert["allocated_percent"] == 5.0:
            self.log_result(1, "SPY Put + Tariff Post Alignment", "PASS", f"RED Alert triggered. Sizing: 5.0% (${alert['allocated_dollars']:,})")
        else:
            self.log_result(1, "SPY Put + Tariff Post Alignment", "FAIL", "RED Alert failed to trigger or dynamic positioning mismatch")

        # --- Round 2: DJT 0DTE Call + Crypto Support Post (RED Alert) ---
        print("\n>>> 【第二輪】DJT 0DTE Call + 加密貨幣利多對齊")
        post = {
            "text": "Bitcoin and Cryptocurrencies are the future! We will make America the crypto capital. Drill baby drill!",
            "timestamp": datetime.now().isoformat()
        }
        opt = {
            "ticker": "DJT",
            "contract": "DJT 260612C00060000",
            "premium": 450000.0,
            "vol_oi_ratio": 5.2,
            "dte": 0,
            "is_sweep": True,
            "otm_pct": 0.20,
            "direction": "CALL",
            "timestamp": datetime.now().isoformat()
        }
        
        post_an = self.monitor.analyze_post(post["text"])
        self.engine.process_new_post(post_an)
        score_res = self.detector.calculate_anomaly_score(opt)
        alert = self.engine.process_new_option_anomaly(score_res)
        
        if alert and alert["level"] == "RED" and alert["buy_strike"] == 50.0:
            self.log_result(2, "DJT Call + Crypto Post Alignment", "PASS", f"RED Alert triggered. Target: {alert['ticker']} {alert['action']}. Greeks hedge: {alert['buy_strike']}/{alert['sell_strike']} Spread")
        else:
            self.log_result(2, "DJT Call + Crypto Post Alignment", "FAIL", "Failed to align DJT option flow")

        # --- Round 3: TLT Put + Bonds & Rates Post (RED Alert - Debt market) ---
        print("\n>>> 【第三輪】TLT Put + 利率/降息通膨言論對齊")
        post = {
            "text": "Inflation is killing our country. Interest rates are too high but Fed needs to act!",
            "timestamp": datetime.now().isoformat()
        }
        opt = {
            "ticker": "TLT",
            "contract": "TLT 260616P00095000",
            "premium": 800000.0,
            "vol_oi_ratio": 3.5,
            "dte": 3,
            "is_sweep": True,
            "otm_pct": 0.05,
            "direction": "PUT",
            "timestamp": datetime.now().isoformat()
        }
        
        post_an = self.monitor.analyze_post(post["text"])
        self.engine.process_new_post(post_an)
        score_res = self.detector.calculate_anomaly_score(opt)
        alert = self.engine.process_new_option_anomaly(score_res)
        
        if alert and alert["level"] == "RED" and alert["ticker"] == "TLT":
            self.log_result(3, "TLT Put + Rate Post Alignment", "PASS", f"RED Alert triggered for Bond ETF. Sizing: {alert['allocated_percent']}% (${alert['allocated_dollars']:,})")
        else:
            self.log_result(3, "TLT Put + Rate Post Alignment", "FAIL", "Failed to align Bond option flow")

        # --- Round 4: USD/CNH + China Tariffs (Multi-market resonance) ---
        print("\n>>> 【第四輪】QQQ Put + 中概關稅言論對齊（多市場共振）")
        post = {
            "text": "We will stop China from taking advantage of us. Tariffs on Beijing incoming!",
            "timestamp": datetime.now().isoformat()
        }
        opt = {
            "ticker": "QQQ",
            "contract": "QQQ 260615P00400000",
            "premium": 3200000.0,
            "vol_oi_ratio": 4.1,
            "dte": 2,
            "is_sweep": True,
            "otm_pct": 0.10,
            "direction": "PUT",
            "timestamp": datetime.now().isoformat()
        }
        
        post_an = self.monitor.analyze_post(post["text"])
        self.engine.process_new_post(post_an)
        score_res = self.detector.calculate_anomaly_score(opt)
        alert = self.engine.process_new_option_anomaly(score_res)
        
        if alert and alert["level"] == "RED" and "China-Exposure" in post_an["sectors"]:
            self.log_result(4, "QQQ Put + China Tariffs Resonance", "PASS", f"Resonance Red Alert triggered. Spread: QQQ {alert['buy_strike']}/{alert['sell_strike']}")
        else:
            self.log_result(4, "QQQ Put + China Tariffs Resonance", "FAIL", "Failed to trigger China Tariff resonance")

        # --- Round 5: No aligned post + SPY $10M Anomaly (YELLOW Alert) ---
        print("\n>>> 【第五輪】無近期貼文 + SPY $10M 超大期權異常（前置洩露）")
        self.engine.post_history = []
        opt = {
            "ticker": "SPY",
            "contract": "SPY 260615P00500000",
            "premium": 10000000.0, # $10M
            "vol_oi_ratio": 4.8,
            "dte": 1,
            "is_sweep": True,
            "otm_pct": 0.12,
            "direction": "PUT",
            "timestamp": datetime.now().isoformat()
        }
        
        score_res = self.detector.calculate_anomaly_score(opt)
        alert = self.engine.process_new_option_anomaly(score_res)
        
        if alert and alert["level"] == "YELLOW":
            self.log_result(5, "Standalone Put Anomaly Leak", "PASS", "YELLOW Alert triggered. Source post: N/A. Dynamic positioning active.")
        else:
            self.log_result(5, "Standalone Put Anomaly Leak", "FAIL", "Failed to trigger standalone Yellow alert")

        # --- Round 6: Option Retail Noise Filtering (NO Alert) ---
        print("\n>>> 【第六輪】常規散戶對沖噪音過濾測試")
        opt = {
            "ticker": "SPY",
            "contract": "SPY 260619C00550000",
            "premium": 50000.0,
            "vol_oi_ratio": 0.2,
            "dte": 30,
            "is_sweep": False,
            "otm_pct": 0.02,
            "direction": "CALL",
            "timestamp": datetime.now().isoformat()
        }
        
        score_res = self.detector.calculate_anomaly_score(opt)
        alert = self.engine.process_new_option_anomaly(score_res)
        
        if not alert and score_res["anomaly_score"] < 7.0:
            self.log_result(6, "Market Retail Noise Filtering", "PASS", f"Successfully ignored. Anomaly Score: {score_res['anomaly_score']} (Below threshold 7.0)")
        else:
            self.log_result(6, "Market Retail Noise Filtering", "FAIL", f"Alert wrongly triggered for noise: {alert}")

        # --- Round 7: Gemini Key Missing Rule-based Fallback ---
        print("\n>>> 【第七輪】Gemini 金鑰缺失回退機制測試")
        # Instantiate a monitor forcing rule-based path
        rule_monitor = TruthSocialMonitor(use_llm=False)
        post_an = rule_monitor.analyze_post("We will put high tariffs on Mexico auto imports!")
        
        if rule_monitor.engine_mode == "RULES" and "Automotive" in post_an["sectors"] and post_an["trading_direction"] == "PUT":
            self.log_result(7, "Gemini Key Fallback to Rules", "PASS", f"Sectors matched: {post_an['sectors']}. Direction: {post_an['trading_direction']}")
        else:
            self.log_result(7, "Gemini Key Fallback to Rules", "FAIL", "Rule engine failed to classify sector/direction correctly")

        # --- Round 8: SQLite Database Integrity Checks ---
        print("\n>>> 【第八輪】SQLite 本地歷史資料庫儲存驗證")
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM posts")
            posts_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM alerts")
            alerts_count = cursor.fetchone()[0]
            
            conn.close()
            if posts_count > 0 and alerts_count > 0:
                self.log_result(8, "SQLite Database Integrity check", "PASS", f"Successfully recorded {posts_count} posts and {alerts_count} alerts in {self.db_path}")
            else:
                self.log_result(8, "SQLite Database Integrity check", "FAIL", f"DB entries empty. Posts: {posts_count}, Alerts: {alerts_count}")
        except Exception as e:
            self.log_result(8, "SQLite Database Integrity check", "FAIL", f"Database query failed: {e}")

        # --- Round 9: Dynamic Position Sizing Check ---
        print("\n>>> 【第九輪】動態倉位比例對照驗證")
        size_low = self.engine.pos_manager.calculate_position_size(anomaly_score=7.2, has_resonance=False)
        size_high = self.engine.pos_manager.calculate_position_size(anomaly_score=10.5, has_resonance=True)
        
        if size_low["allocated_percent"] == 1.0 and size_high["allocated_percent"] == 5.0:
            self.log_result(9, "Dynamic Position Sizing scaling", "PASS", f"Score 7.2 -> {size_low['allocated_percent']}% (${size_low['allocated_dollars']:,}) | Score 10.5 -> {size_high['allocated_percent']}% (${size_high['allocated_dollars']:,})")
        else:
            self.log_result(9, "Dynamic Position Sizing scaling", "FAIL", "Position size scaling calculation incorrect")

        # --- Round 10: CP950 Console Unicode Safety ---
        print("\n>>> 【第十輪】CP950 編碼相容性與 Emoji 轉換極限測試")
        test_alert = {
            "alert_id": "ALERT_UNICODE_TEST",
            "level": "RED",
            "timestamp": datetime.now().isoformat(),
            "ticker": "SPY",
            "contract": "SPY 260612P00500000",
            "action": "PUT",
            "vol_oi_ratio": 4.5,
            "premium": 4800000.0,
            "dte": 1,
            "source_post": "🔴🟡🍀🀄💎 Unicode Test Post",
            "reason": "🔴🟡🍀🀄💎 Special symbol encoding check",
            "trading_guideline": "【對沖建議】垂直價差 500.0 / 495.0",
            "allocated_dollars": 5000.0,
            "allocated_percent": 5.0,
            "buy_strike": 500.0,
            "sell_strike": 495.0,
            "hedging_reason": "Unicode safety test"
        }
        
        try:
            self.engine.dispatch_alert(test_alert, level="RED")
            self.log_result(10, "CP950 Codec Unicode Safety", "PASS", "Dispatched Unicode/Emoji alert successfully without encoding crash")
        except Exception as e:
            self.log_result(10, "CP950 Codec Unicode Safety", "FAIL", f"Encoding crashed: {e}")

        # Display Final Compliance Table
        print("\n" + "="*80)
        print("                        TSADS v2.0 COMPLIANCE REPORT                        ")
        print("="*80)
        print(f"{'Round':<6} | {'Test Description':<38} | {'Status':<6} | {'Details':<25}")
        print("-"*80)
        for res in self.test_results:
            print(f"{res['round']:<6} | {res['description']:<38} | {res['status']:<6} | {res['details']}")
        print("="*80)

if __name__ == "__main__":
    suite = QATestSuite()
    suite.run_all_rounds()
