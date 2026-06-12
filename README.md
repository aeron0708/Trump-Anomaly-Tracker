# TSADS - 川普開口前異常交易即時追蹤系統
*Trump Speech Ahead Anomaly Detection System (TSADS) v2.1*

本系統是一套無縫串接川普社交媒體 (Truth Social)、期權異常流量 (Yahoo Finance)、動態倉位控制與期權 Greeks 垂直價差避險的即時事件監控程序，並能在異常對齊時自動發送精美警報至您的 Telegram 頻道。

---

## 📂 專案結構說明

* `src/main_monitor.py`：實時監控主程序（生產級進入點）。
* `src/truth_social_monitor.py`：川普社交媒體監控與 NVIDIA NIM 語意分析。
* `src/yfinance_options_scanner.py`：開源免費的短期異常期權掃描器。
* `src/alert_alignment_engine.py`：對齊驗證、多市場共振、Greeks 價差建議與 Telegram 發送引擎。
* `src/position_manager.py`：動態倉位比例與價差結構計算。
* `src/sqlite_logger.py`：SQLite 歷史數據庫寫入與持久化。
* `src/run_poc_test.py`：合規測試與十輪驗證腳本。
* `.env`：Telegram 與 NVIDIA NIM 金鑰環境設定檔。

---

## 💻 一、本地端配置與啟動指引 (Local Windows)

本地端適合**秒級/分鐘級的高頻實時監控**，能將延遲降到最低。

### 1. 安裝環境與依賴
在命令提示字元 (CMD) 或 PowerShell 中，進入專案目錄並安裝必要 Python 庫（僅需 `yfinance`）：
```bash
pip install yfinance
```
*(本系統的其餘模組，如 SQLite、NIM API、Telegram 推送等，皆已使用 Python 原生網絡庫實作，無須安裝額外依賴。)*

### 2. 設定環境變數
打開 [.env](file:///C:/Antigravity專案/自動交易/Trump%20Anomaly%20Tracker/.env) 檔案，填入您的金鑰：
```ini
TELEGRAM_BOT_TOKEN=8290913387:AAGmcSYd4eu2K9WW...
TELEGRAM_CHAT_ID=7922669146
NVIDIA_API_KEY=您的NVIDIA_NIM金鑰
```

### 3. 啟動與關閉監控程序
我們在根目錄為您配置了三個一鍵運行的指令/腳本：
*   **前台可見模式**：雙擊 [start_visible.bat](file:///C:/Antigravity專案/自動交易/Trump%20Anomaly%20Tracker/start_visible.bat) 可以啟動一個有命令列視窗的監控程序。若要關閉，直接在該 CMD 視窗按下 `Ctrl + C`，然後輸入 `Y` 或關閉該視窗即可。
*   **後台隱形模式**：雙擊 [run_stealth.vbs](file:///C:/Antigravity專案/自動交易/Trump%20Anomaly%20Tracker/run_stealth.vbs) 或使用開機自啟動，程序會在 Windows 背景安靜運行（無視窗）。
*   **一鍵關閉背景程序**：當您使用後台隱形模式，或者不確定是否有程序在背景重複執行時，雙擊 [stop_monitor.bat](file:///C:/Antigravity專案/自動交易/Trump%20Anomaly%20Tracker/stop_monitor.bat)，系統會精準結束所有正在運行的 `main_monitor.py` 進程，安全且不影響其他無關的 Python 程式。


---

## ☁️ 二、雲端配置與啟動指引 (GitHub Actions & Secrets)

由於 GitHub Actions 的單次 Job 運行有 6 小時上限，且不適合無窮 `while True` 循環，我們提供**排程掃描（Cron Job）**與 **VPS 虛擬主機常駐** 兩種雲端方案：

### 方案 A：使用 GitHub Actions 排程掃描 (完全免費)
您可以將系統配置為「每 5 分鐘自動啟動掃描一次，執行完畢即關閉」。
> [!TIP]
> **額度說明**：當您將此 GitHub 倉庫設定為 **Public (公開)** 時，GitHub Actions 定時任務的執行時間為**完全免費且無上限**！若設定為 Private，則每月有 2,000 分鐘的免費額度上限。

#### 1. 設定 GitHub Secrets (安全保護金鑰)
不要將 `.env` 檔案上傳到 GitHub！請在您的 GitHub 項目倉庫中：
1. 進入 `Settings -> Secrets and variables -> Actions`。
2. 點擊 `New repository secret`，依次新增以下三個 Secret：
   * `TELEGRAM_BOT_TOKEN` = (填入您的 Bot Token)
   * `TELEGRAM_CHAT_ID` = (填入您的 Chat ID)
   * `NVIDIA_API_KEY` = (填入您的 NVIDIA NIM 金鑰)

#### 2. 建立 GitHub Actions 工作流檔案
在項目中建立路徑為 `.github/workflows/tsads_monitor.yml` 的檔案，寫入以下內容：
```yaml
name: TSADS Live Anomaly Monitor

on:
  schedule:
    # 全天候 24 小時監控：每 5 分鐘自動掃描一次。
    # 因為專案已設為 Public (公開) 倉庫，GitHub Actions 的執行時間為完全免費且無上限！
    - cron: '*/5 * * * *'
  workflow_dispatch: # 支持手動點擊觸發

permissions:
  contents: write

jobs:
  monitor:
    runs-on: ubuntu-latest

    steps:
    - name: Checkout repository
      uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'

    - name: Install dependencies
      run: |
        pip install yfinance

    - name: Run Scan Job
      env:
        TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
        TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        NVIDIA_API_KEY: ${{ secrets.NVIDIA_API_KEY }}
        TSADS_ONCE_MODE: "true"
        # 手動點擊觸發時會強制發送一則 Telegram 測試通知確認連通
        TSADS_TEST_MODE: ${{ github.event_name == 'workflow_dispatch' && 'true' || 'false' }}
      run: |
        python src/main_monitor.py

    - name: Commit and Push state changes
      run: |
        git config --global user.name "github-actions[bot]"
        git config --global user.email "41898282+github-actions[bot]@users.noreply.github.com"
        if [ -f processed_state.json ]; then
          git add processed_state.json
          git commit -m "Update processed state data [skip ci]" || echo "No changes to commit"
          git push
        fi
```
*(注意：我們的主程序 `main_monitor.py` 在偵測到 `TSADS_ONCE_MODE="true"` 環境變數時，會自動只掃描一輪後便結束退出，且最後的 Commit step 會自動將 `processed_state.json` 的已處理 ID 回傳儲存到 GitHub，保證在無狀態雲端環境下也不會重複警報。)*

### 方案 B：使用 Linux 雲端主機 (VPS) 常駐運行
如果您有阿里雲、AWS 或 GCP 等 Linux 虛擬主機：
1. 將專案複製上傳，並在主機上建立相同的 `.env`。
2. 使用 `nohup` 或 `screen` 讓主循環在背景永久運行，即使關閉終端也不中斷：
   ```bash
   nohup python3 src/main_monitor.py > tsads_run.log 2>&1 &
   ```
3. 您可以使用 `tail -f tsads_run.log` 來隨時查看即時監控日誌。
