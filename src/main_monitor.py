# -*- coding: utf-8 -*-
"""
TSADS - Main Real-time Anomaly Tracking Program
Performs infinite loop monitoring of Truth Social posts and SPY/QQQ/DJT/TLT option chains.
Dispatches live alerts to Telegram and saves history to SQLite.
"""

import os
import sys
import time
import json
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
from options_anomaly_detector import OptionsAnomalyDetector

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
    detector = OptionsAnomalyDetector(threshold=7.0)
    engine = AlertAlignmentEngine(db_path="tsads_history.db")
    
    # Track processed items to avoid double alerts
    processed_post_ids = set()
    processed_option_ids = set()
    state_path = "processed_state.json"
    
    # Load state from file if exists
    has_state = False
    if os.path.exists(state_path):
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
                processed_post_ids = set(state.get("post_ids", []))
                processed_option_ids = set(state.get("option_ids", []))
            print(f"[TSADS] 成功從狀態檔載入 {len(processed_post_ids)} 個已處理貼文與 {len(processed_option_ids)} 個已處理期權。")
            has_state = True
        except Exception as e:
            print(f"[TSADS] 載入狀態檔失敗，將重新執行 Warmup: {e}")
    
    # Warmup / Initial load to populate history without spamming old alerts
    print("[TSADS] 系統初始化中，載入基線歷史數據...")
    try:
        initial_posts = monitor.fetch_latest_posts(mock=False)
        for post in initial_posts:
            if not has_state:
                processed_post_ids.add(post["id"])
            # Load into engine history quietly for alignment engine context
            post_an = monitor.analyze_post(post["text"])
            engine.post_history.append(post_an)
            
        for ticker in ["SPY", "QQQ", "DJT", "TLT", "GLD", "USO"]:
            initial_options = scanner.scan_ticker(ticker)
            for opt in initial_options:
                # Calculate and attach anomaly score
                score_res = detector.calculate_anomaly_score(opt)
                opt["anomaly_score"] = score_res["anomaly_score"]
                opt["is_anomaly"] = score_res["is_anomaly"]
                opt["score_details"] = score_res["score_details"]
                
                if not has_state:
                    processed_option_ids.add(opt["id"])
                # Load into engine history quietly for alignment engine context
                engine.option_history.append(opt)
                
        # Save baseline or send test alert if test mode is enabled
        is_test_mode = os.environ.get("TSADS_TEST_MODE") == "true"
        if not has_state or is_test_mode:
            try:
                if not has_state:
                    with open(state_path, "w", encoding="utf-8") as f:
                        json.dump({
                            "post_ids": list(processed_post_ids),
                            "option_ids": list(processed_option_ids)
                        }, f, ensure_ascii=False, indent=2)
                    print(f"[TSADS] 首次 Warmup 狀態已儲存至 {state_path}")
                
                # Send test notification
                run_env = "GitHub Actions (手動測試)" if is_test_mode else "GitHub Actions (首次啟動)"
                test_msg = f"📢 [TSADS] 雲端監控程序連線測試成功！\n\n■ 運行環境: {run_env}\n■ 追蹤標的: SPY, QQQ, DJT, TLT, GLD, USO\n■ 目前狀態: 正常運行中（共緩存 {len(engine.post_history)} 貼文與 {len(engine.option_history)} 筆期權數據）。\n\n系統已成功與您的 Telegram 頻道對接，後續若偵測到川普發言與期權異常共振，將在此即時警報！"
                
                if engine.tg_token and engine.tg_chat_id:
                    import urllib.request
                    import urllib.parse
                    tg_url = f"https://api.telegram.org/bot{engine.tg_token}/sendMessage"
                    data = urllib.parse.urlencode({
                        "chat_id": engine.tg_chat_id,
                        "text": test_msg
                    }).encode("utf-8")
                    req = urllib.request.Request(tg_url, data=data)
                    with urllib.request.urlopen(req, timeout=5) as response:
                        if response.status == 200:
                            print("[TSADS] 成功發送 Telegram 連線測試通知。")
            except Exception as se:
                print(f"[TSADS] 儲存 Warmup 狀態檔或發送測試通知失敗: {se}")
                
        print(f"[TSADS] 基線載入完成。已緩存 {len(engine.post_history)} 則推文與 {len(engine.option_history)} 筆期權數據於分析引擎中。")
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
            new_post_detected = False
            for post in posts:
                if post["id"] not in processed_post_ids:
                    print(f"\n[{current_time}] 偵測到新貼文! ID: {post['id']}")
                    print(f"貼文內容: {post['text'][:100]}...")
                    post_an = monitor.analyze_post(post["text"])
                    engine.process_new_post(post_an)
                    processed_post_ids.add(post["id"])
                    new_post_detected = True
            
            # 2. Fetch & Process Options Chain
            new_option_detected = False
            for ticker in ["SPY", "QQQ", "DJT", "TLT", "GLD", "USO"]:
                anomalies = scanner.scan_ticker(ticker)
                for opt in anomalies:
                    if opt["id"] not in processed_option_ids:
                        print(f"\n[{current_time}] 偵測到 {ticker} 期權異常交易! Contract: {opt['contract']}")
                        
                        # Calculate and attach anomaly score
                        score_res = detector.calculate_anomaly_score(opt)
                        opt["anomaly_score"] = score_res["anomaly_score"]
                        opt["is_anomaly"] = score_res["is_anomaly"]
                        opt["score_details"] = score_res["score_details"]
                        
                        engine.process_new_option_anomaly(opt)
                        processed_option_ids.add(opt["id"])
                        new_option_detected = True
            
            # Save state if any new items were processed
            if new_post_detected or new_option_detected:
                try:
                    with open(state_path, "w", encoding="utf-8") as f:
                        json.dump({
                            "post_ids": list(processed_post_ids),
                            "option_ids": list(processed_option_ids)
                        }, f, ensure_ascii=False, indent=2)
                    print(f"\n[{current_time}] 偵測到新數據，狀態已更新儲存至 {state_path}")
                except Exception as se:
                    print(f"\n[{current_time}] 儲存更新狀態檔失敗: {se}")
            
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
            if os.environ.get("TSADS_ONCE_MODE") == "true":
                print("[TSADS] 偵測到單次運行模式 (Once Mode) 發生異常。安全退出以避免無限重試。")
                sys.exit(1)
            time.sleep(5)

if __name__ == "__main__":
    start_monitoring()
