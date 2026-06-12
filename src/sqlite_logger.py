# -*- coding: utf-8 -*-
"""
TSADS - Local SQLite Database Logger
Initializes sqlite3 schema and logs alerts, posts, and anomalies to tsads_history.db.
"""

import sqlite3
import os
import json
from datetime import datetime

class SQLiteLogger:
    def __init__(self, db_path="tsads_history.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """
        Creates SQLite tables if they do not exist.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 1. Posts Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS posts (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT,
                    text TEXT,
                    sectors TEXT,
                    sentiment TEXT,
                    trading_direction TEXT,
                    confidence REAL
                )
            """)
            
            # 2. Option Anomalies Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS option_anomalies (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT,
                    ticker TEXT,
                    contract TEXT,
                    direction TEXT,
                    premium REAL,
                    vol_oi_ratio REAL,
                    dte INTEGER,
                    anomaly_score REAL
                )
            """)
            
            # 3. Alerts Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT,
                    level TEXT,
                    ticker TEXT,
                    action TEXT,
                    vol_oi_ratio REAL,
                    premium REAL,
                    dte INTEGER,
                    source_post TEXT,
                    reason TEXT,
                    allocated_dollars REAL,
                    buy_strike REAL,
                    sell_strike REAL
                )
            """)
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[TSADS DB] Error initializing SQLite: {e}")

    def log_post(self, post):
        """
        Inserts a Truth Social post analysis into the database.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO posts (id, timestamp, text, sectors, sentiment, trading_direction, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                post.get("id", str(hash(post.get("text", "")))),
                post.get("timestamp", datetime.now().isoformat()),
                post.get("text", ""),
                json.dumps(post.get("sectors", [])),
                post.get("sentiment", "NEUTRAL"),
                post.get("trading_direction", "NONE"),
                post.get("confidence", 0.0)
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[TSADS DB] Error logging post to database: {e}")

    def log_option(self, opt):
        """
        Inserts an option anomaly into the database.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO option_anomalies (id, timestamp, ticker, contract, direction, premium, vol_oi_ratio, dte, anomaly_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                opt.get("trade_id", opt.get("contract", str(hash(datetime.now().isoformat())))),
                opt.get("timestamp", datetime.now().isoformat()),
                opt.get("ticker", "UNKNOWN"),
                opt.get("contract", "UNKNOWN"),
                opt.get("direction", "NONE"),
                opt.get("premium", 0.0),
                opt.get("vol_oi_ratio", 0.0),
                opt.get("dte", 0),
                opt.get("anomaly_score", 0.0)
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[TSADS DB] Error logging option anomaly to database: {e}")

    def log_alert(self, alert):
        """
        Inserts a Red/Yellow alert into the database.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO alerts (id, timestamp, level, ticker, action, vol_oi_ratio, premium, dte, source_post, reason, allocated_dollars, buy_strike, sell_strike)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                alert.get("alert_id"),
                alert.get("timestamp", datetime.now().isoformat()),
                alert.get("level", "YELLOW"),
                alert.get("ticker", ""),
                alert.get("action", ""),
                alert.get("vol_oi_ratio", 0.0),
                alert.get("premium", 0.0),
                alert.get("dte", 0),
                alert.get("source_post", ""),
                alert.get("reason", ""),
                alert.get("allocated_dollars", 0.0),
                alert.get("buy_strike", 0.0),
                alert.get("sell_strike", 0.0)
            ))
            conn.commit()
            conn.close()
            print(f"[TSADS DB] Alert successfully written to local database.")
        except Exception as e:
            print(f"[TSADS DB] Error logging alert to database: {e}")

if __name__ == "__main__":
    # Test DB Write
    logger = SQLiteLogger("tsads_test.db")
    mock_post = {
        "id": "test_post_001",
        "timestamp": datetime.now().isoformat(),
        "text": "Tariff time!",
        "sectors": ["Automotive"],
        "sentiment": "NEGATIVE",
        "trading_direction": "PUT",
        "confidence": 0.88
    }
    logger.log_post(mock_post)
    print("Database test run complete. File created: tsads_test.db")
    if os.path.exists("tsads_test.db"):
        os.remove("tsads_test.db") # Cleanup test file
