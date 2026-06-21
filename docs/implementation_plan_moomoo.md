# Moomoo Options Scanner Implementation Plan

## 1. Overview
The goal is to integrate the Moomoo API as the primary options anomaly scanner while keeping `YFinanceOptionsScanner` as a fallback. We will build `MoomooOptionsScanner` in `src/moomoo_options_scanner.py`, which implements the same interface as `YFinanceOptionsScanner.scan_ticker()`. It will utilize existing python scripts via `subprocess` to fetch data.

## 2. Architectural Reflection & Considerations
1. **Subprocess Overhead:** Calling multiple python scripts via `subprocess` (one for dates, one for chains, one for snapshots) introduces overhead. To mitigate this, we will batch option codes when calling `get_snapshot.py` (which already supports batches of up to 400).
2. **Missing Field in Snapshot:** The existing `get_snapshot.py` does not output `open_interest`. We will modify `get_snapshot.py` to extract `option_open_interest` and include it in the JSON output.
3. **Error Handling & Fallback:** The Moomoo API might fail (e.g., due to lacking US stock quote permissions). The scanner must distinguish between "no anomalies found" and "API error". On API error (non-zero exit code or explicit JSON error), `MoomooOptionsScanner.scan_ticker()` will raise an exception. `main_monitor.py` will catch this and trigger the fallback `YFinanceOptionsScanner`.
4. **Multiplier & Premium Calculation:** Moomoo returns volume as the number of contracts. The premium will be calculated as `last_price * volume * 100`.
5. **Path Resolution:** The Moomoo scripts are located at `~/.antigravity/skills/moomoo/moomooapi/scripts/quote/`. The code will dynamically resolve this path using `os.path.expanduser`.

## 3. Implementation Steps

### Step 1: Update `get_snapshot.py`
Modify `C:\Users\Aeron\.antigravity\skills\moomoo\moomooapi\scripts\quote\get_snapshot.py` to parse `option_open_interest`.
```python
# In _parse_snapshot_row(row):
"open_interest": safe_int(safe_get(row, "option_open_interest", default=0)),
"strike_price": safe_float(safe_get(row, "strike_price", default=0)), # Optional, helpful for analysis
```

### Step 2: Create `src/moomoo_options_scanner.py`
Create a new class `MoomooOptionsScanner` mirroring the `YFinanceOptionsScanner` constructor and methods.
- **`__init__(self, min_vol_oi=2.0, min_premium=100000.0, max_dte=7)`**
- **`scan_ticker(self, ticker)`**:
  1. Calls `get_option_expiration_date.py <ticker> --json`.
  2. Filters dates to those with `DTE <= max_dte`.
  3. Calls `get_option_chain.py <ticker> --start <date> --end <date> --json` for each valid date.
  4. Collects all option codes.
  5. Calls `get_snapshot.py <codes...> --json` in chunks of 400.
  6. Analyzes the snapshot results:
     - Check `volume >= 10` and `open_interest >= 5`.
     - Check `vol/oi >= min_vol_oi`.
     - Check `premium (last_price * volume * 100) >= min_premium`.
  7. Formats the output dict identically to YFinance scanner.
  8. Raises a `RuntimeError` if any subprocess returns an error or JSON contains `"error"`.

### Step 3: Modify `src/main_monitor.py`
Update the `main_monitor.py` loop to instantiate both scanners and implement the fallback logic.
```python
from moomoo_options_scanner import MoomooOptionsScanner
from yfinance_options_scanner import YFinanceOptionsScanner

# Initialization
moomoo_scanner = MoomooOptionsScanner(min_vol_oi=2.0, min_premium=100000.0, max_dte=7)
yf_scanner = YFinanceOptionsScanner(min_vol_oi=2.0, min_premium=100000.0, max_dte=7)

# Inside the scanning loop:
try:
    anomalies = moomoo_scanner.scan_ticker(ticker)
except Exception as e:
    logger.warning(f"[Scanner] Moomoo API failed for {ticker}: {e}. Falling back to YFinance.")
    anomalies = yf_scanner.scan_ticker(ticker)
```

## 4. Expected Deliverables
- Modified `get_snapshot.py`.
- New `moomoo_options_scanner.py`.
- Modified `main_monitor.py`.
