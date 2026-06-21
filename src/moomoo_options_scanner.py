# -*- coding: utf-8 -*-
"""
Moomoo Options Scanner Implementation
Wraps existing Moomoo quote scripts to scan for options anomalies.
"""

import sys
import os
import json
import subprocess
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)

class MoomooOptionsScanner:
    def __init__(self, min_vol_oi=2.0, min_premium=100000.0, max_dte=7):
        self.min_vol_oi = min_vol_oi
        self.min_premium = min_premium
        self.max_dte = max_dte
        self.scripts_dir = os.path.expanduser("~/.antigravity/skills/moomoo/moomooapi/scripts/quote")
        
    def get_dte(self, expiration_str):
        try:
            exp_date = datetime.strptime(expiration_str, "%Y-%m-%d").date()
            today = date.today()
            return (exp_date - today).days
        except Exception:
            return 999
            
    def _run_script(self, script_name, *args):
        script_path = os.path.join(self.scripts_dir, script_name)
        cmd = ["python", script_path] + list(args)
        
        try:
            # Reconfigure stdout to UTF-8 on Windows
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=True, encoding='utf-8', env=env
            )
            # Parse JSON
            try:
                data = json.loads(result.stdout)
                if "error" in data:
                    raise RuntimeError(f"API Error in {script_name}: {data['error']}")
                return data.get("data", [])
            except json.JSONDecodeError:
                raise RuntimeError(f"Failed to parse JSON from {script_name}. Output: {result.stdout[:200]}")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Script {script_name} failed with exit code {e.returncode}. stderr: {e.stderr}")
            
    def scan_ticker(self, ticker):
        logger.info(f"[Moomoo Scanner] Scanning {ticker} option chains...")
        
        # 1. Calls get_option_expiration_date.py <ticker> --json
        try:
            dates = self._run_script("get_option_expiration_date.py", ticker, "--json")
        except Exception as e:
            raise RuntimeError(f"Failed to get expiration dates for {ticker}: {e}")
            
        # 2. Filters dates to those with DTE <= max_dte
        valid_dates = []
        for d in dates:
            exp = d.get("strike_time")
            if not exp:
                continue
            dte = self.get_dte(exp)
            if 0 <= dte <= self.max_dte:
                valid_dates.append((exp, dte))
                
        logger.info(f"[Moomoo Scanner] Found {len(valid_dates)} expiration dates within {self.max_dte} days.")
        
        all_codes = []
        code_to_exp = {} # code -> (exp, dte, direction, strike)
        
        # 3. Calls get_option_chain.py
        for exp, dte in valid_dates:
            try:
                chain = self._run_script("get_option_chain.py", ticker, "--start", exp, "--end", exp, "--json")
            except Exception as e:
                logger.warning(f"Failed to get option chain for {ticker} at {exp}: {e}")
                continue
                
            # Collect codes
            for row in chain:
                call_code = row.get("call", {}).get("code")
                put_code = row.get("put", {}).get("code")
                strike_price = row.get("strike_price")
                
                if call_code:
                    all_codes.append(call_code)
                    code_to_exp[call_code] = (exp, dte, "CALL", strike_price)
                if put_code:
                    all_codes.append(put_code)
                    code_to_exp[put_code] = (exp, dte, "PUT", strike_price)
                    
        # 5. Calls get_snapshot.py in chunks
        anomalies = []
        if not all_codes:
            return anomalies
            
        chunk_size = 400
        for i in range(0, len(all_codes), chunk_size):
            chunk = all_codes[i:i+chunk_size]
            try:
                snapshots = self._run_script("get_snapshot.py", *chunk, "--json")
            except Exception as e:
                raise RuntimeError(f"Failed to get snapshots: {e}")
                
            for snap in snapshots:
                code = snap.get("code")
                vol = snap.get("volume", 0)
                oi = snap.get("open_interest", 0)
                last_price = snap.get("last_price", 0.0)
                
                # Check vol >= 10 and oi >= 5
                if vol < 10 or oi < 5:
                    continue
                    
                vol_oi_ratio = vol / oi
                premium = last_price * vol * 100
                
                if vol_oi_ratio >= self.min_vol_oi and premium >= self.min_premium:
                    exp, dte, direction, strike = code_to_exp.get(code, ("N/A", 999, "UNKNOWN", snap.get("strike_price", 0)))
                    
                    anomalies.append({
                        "id": code,
                        "ticker": ticker,
                        "contract": code,
                        "expiration": exp,
                        "dte": dte,
                        "strike": strike,
                        "last_price": last_price,
                        "volume": int(vol),
                        "open_interest": int(oi),
                        "vol_oi_ratio": round(vol_oi_ratio, 2),
                        "premium": round(premium, 2),
                        "direction": direction,
                        "is_sweep": True if vol > 100 else False,
                        "timestamp": datetime.now().isoformat()
                    })
                    
        return anomalies
