# A股历史K线数据下载脚本
import akshare as ak
import pandas as pd
import os
import time
from datetime import datetime
from tqdm import tqdm
import sys
import io
import json

# 强制设置工作目录
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)

if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    except:
        pass

DATA_DIR = os.path.join(SCRIPT_DIR, "data")
SRC_DIR = SCRIPT_DIR
PROGRESS_FILE = os.path.join(SRC_DIR, "download_progress.json")
STOCK_LIST_FILE = os.path.join(SRC_DIR, "stock_list.txt")
START_DATE = "20150101"
END_DATE = datetime.now().strftime("%Y%m%d")
RETRY_TIMES = 5
RETRY_DELAY = 2

print(f"Working directory: {os.getcwd()}")
print(f"Data directory: {DATA_DIR}")

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {"downloaded": [], "failed": [], "last_update": None}

def save_progress(progress):
    progress["last_update"] = datetime.now().isoformat()
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)

def get_existing_files():
    existing = set()
    if os.path.exists(DATA_DIR):
        for f in os.listdir(DATA_DIR):
            if f.endswith('.csv'):
                code = f.split('_')[0]
                existing.add(code)
    return existing

def load_stock_list_from_file():
    stock_list = []
    if os.path.exists(STOCK_LIST_FILE):
        with open(STOCK_LIST_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    parts = line.split(',')
                    if len(parts) >= 2:
                        stock_list.append((parts[0].strip(), parts[1].strip()))
    return stock_list

def download_stock_kline(symbol, name, start_date, end_date):
    for retry in range(RETRY_TIMES):
        try:
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust=""
            )
            if df is not None and not df.empty:
                return df
            print(f"[WARN] {symbol}: no data returned")
            return None
        except Exception as e:
            if retry < RETRY_TIMES - 1:
                time.sleep(RETRY_DELAY)
            else:
                print(f"[ERROR] {symbol}: {type(e).__name__}")
    return None

def save_to_csv(df, symbol, name):
    if df is None or df.empty:
        return False
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        safe_name = "".join([c for c in str(name) if c.isalnum() or c in ('_', '-')])
        filename = f"{symbol}_{safe_name}.csv"
        filepath = os.path.join(DATA_DIR, filename)
        df.to_csv(filepath, index=False, encoding='utf-8-sig')
        
        # Verify file was created
        if os.path.exists(filepath):
            print(f"[OK] {symbol}: {len(df)} rows -> {filepath}")
            return True
        else:
            print(f"[ERROR] {symbol}: file not created!")
            return False
    except Exception as e:
        print(f"[ERROR] {symbol}: {str(e)[:80]}")
        return False

def main():
    print("=" * 50)
    print("A-Share K-Line Data Download Tool v2")
    print("=" * 50)
    
    progress = load_progress()
    existing = get_existing_files()
    for code in existing:
        if code not in progress["downloaded"]:
            progress["downloaded"].append(code)
    save_progress(progress)
    
    print(f"Already: {len(progress['downloaded'])}")
    
    stock_list = load_stock_list_from_file()
    if not stock_list:
        print("No stock list!")
        return
    
    downloaded = set(progress['downloaded'])
    pending = [(c, n) for c, n in stock_list if str(c) not in downloaded]
    print(f"To download: {len(pending)}")
    
    if not pending:
        print("All done!")
        return
    
    os.makedirs(DATA_DIR, exist_ok=True)
    success = 0
    fail = 0
    
    for i, (code, name) in enumerate(tqdm(pending, desc="Download")):
        code = str(code).zfill(6)
        name = str(name) if name else code
        
        df = download_stock_kline(code, name, START_DATE, END_DATE)
        
        if save_to_csv(df, code, name):
            success += 1
            progress["downloaded"].append(code)
            save_progress(progress)
        else:
            fail += 1
        
        if (i + 1) % 50 == 0:
            time.sleep(1)
    
    print(f"Done! Success: {success}, Failed: {fail}")

if __name__ == "__main__":
    main()
