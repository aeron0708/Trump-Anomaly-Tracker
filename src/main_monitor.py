# -*- coding: utf-8 -*-
"""
TSADS - Main Real-time Anomaly Tracking Program
Performs infinite loop monitoring of Truth Social posts and SPY/QQQ/DJT/TLT option chains.
Dispatches live alerts to Telegram and saves history to SQLite.
"""

import os
import sys
import time
from datetime import datetime

# Reconfigure stdout to UTF-8 on Windows
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Import TSADS v2.1 components
from truth_social_monitor import TruthSocialMonitor
from yfinance_options_scanner import YFinanceOptionsScanner
from alert_alignment_engine import AlertAlignmentEngine

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
                print(f"[TSADS] Loaded environment config from: {os.path.abspath(path)}")
                return
            except Exception:
                pass

def start_monitoring():
    load_dotenv()
    
    print("=========================================================")
    print("       TSADS v2.1 - REAL-TIME ANOMALY TRACKING SYSTEM    ")
    print("=========================================================")
    print(f"啟動時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Initialize components
    monitor = TruthSocialMonitor(use_llm=True)
    # Scan SPY, QQQ, DJT, TLT with Vol/OI >= 2.0 and Premium >= $100k
    scanner = YFinanceOptionsScanner(min_vol_oi=2.0, min_premium=100000.0, max_dte=7)
    engine = AlertAlignmentEngine(db_path="tsads_history.db")
    
    # Track processed items to avoid double alerts
    processed_post_ids = set()
    processed_option_ids = set()
    
    # Warmup / Initial load to populate history without spamming old alerts
    print("[TSADS] 系統初始化中，載入基線歷史數據...")
    try:
        initial_posts = monitor.fetch_latest_posts(mock=False)
        for post in initial_posts:
            processed_post_ids.add(post["id"])
            # Load into engine history quietly
            post_an = monitor.analyze_post(post["text"])
            engine.post_history.append(post_an)
            
        for ticker in ["SPY", "QQQ", "DJT", "TLT", "GLD", "USO"]:
            initial_options = scanner.scan_ticker(ticker)
            for opt in initial_options:
                processed_option_ids.add(opt["id"])
                # Load into engine history quietly
                engine.option_history.append(opt)
                
        print(f"[TSADS] 基線載入完成。已緩存 {len(processed_post_ids)} 則推文與 {len(processed_option_ids)} 筆期權數據。")
    except Exception as e:
        print(f"[TSADS] 初始化警告 (可能因網絡離線): {e}")

    loop_count = 0
    scan_interval = 60 # 60 seconds interval
    
    print(f"\n[TSADS] 監控中... (掃描間隔: {scan_interval}秒). 按 Ctrl+C 可停止程序。")
    print("="*57)
    
    while True:
        try:
            loop_count += 1
            current_time = datetime.now().strftime("%H:%M:%S")
            print(f"\r[{current_time}] 執行第 {loop_count} 次掃描中...", end="", flush=True)
            
            # 1. Fetch & Process Truth Social
            posts = monitor.fetch_latest_posts(username="realdonaldtrump", mock=False)
            for post in posts:
                if post["id"] not in processed_post_ids:
                    print(f"\n[{current_time}] 偵測到新貼文! ID: {post['id']}")
                    print(f"貼文內容: {post['text'][:100]}...")
                    post_an = monitor.analyze_post(post["text"])
                    engine.process_new_post(post_an)
                    processed_post_ids.add(post["id"])
            
            # 2. Fetch & Process Options Chain
            for ticker in ["SPY", "QQQ", "DJT", "TLT", "GLD", "USO"]:
                anomalies = scanner.scan_ticker(ticker)
                for opt in anomalies:
                    if opt["id"] not in processed_option_ids:
                        print(f"\n[{current_time}] 偵測到 {ticker} 期權異常交易! Contract: {opt['contract']}")
                        engine.process_new_option_anomaly(opt)
                        processed_option_ids.add(opt["id"])
            
            # Prevent history memory leak
            engine._clean_expired_history()
            
            # If running in once_mode (e.g. GitHub Actions Cron), exit after one full scan
            if os.environ.get("TSADS_ONCE_MODE") == "true":
                print("\n[TSADS] 偵測到單次運行模式 (Once Mode)。掃描結束，安全退出。")
                break
            
            # Sleep until next scan
            time.sleep(scan_interval)
            
        except KeyboardInterrupt:
            print("\n[TSADS] 監控程序已由用戶停止。安全退出。")
            break
        except Exception as e:
            print(f"\n[TSADS] 運行時異常: {e}. 5秒後重新嘗試...")
            time.sleep(5)

if __name__ == "__main__":
    start_monitoring()
