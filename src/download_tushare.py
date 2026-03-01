# -*- coding: utf-8 -*-
"""
使用Tushare下载A股历史K线数据
参考文档：https://tushare.pro/document/2?doc_id=27
每分钟限制50次请求
"""
import tushare as ts
import pandas as pd
import os
import time
import json
from datetime import datetime
from tqdm import tqdm
import sys
import io
import threading

# 强制设置工作目录
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)

if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    except:
        pass

# Tushare配置
TS_TOKEN = "9b7ca75714b459b9f4b9895039e27902d834e622c6cb0e5d188860bd"

# 初始化tushare
ts.set_token(TS_TOKEN)
pro = ts.pro_api()

DATA_DIR = os.path.join(SCRIPT_DIR, "data_tushare")
PROGRESS_FILE = os.path.join(SCRIPT_DIR, "download_progress_tushare.json")
START_DATE = "20150101"
END_DATE = datetime.now().strftime("%Y%m%d")
RETRY_TIMES = 5
RETRY_DELAY = 2

# 限速配置：每分钟50次
MAX_REQUESTS_PER_MINUTE = 50
request_timestamps = []
request_lock = threading.Lock()

print(f"Working directory: {os.getcwd()}")
print(f"Data directory: {DATA_DIR}")


def rate_limit():
    """限速器：确保每分钟不超过50次请求"""
    global request_timestamps
    
    with request_lock:
        now = time.time()
        # 清除1分钟前的请求记录
        request_timestamps = [ts for ts in request_timestamps if now - ts < 60]
        
        if len(request_timestamps) >= MAX_REQUESTS_PER_MINUTE:
            # 需要等待
            earliest = request_timestamps[0]
            wait_time = 60 - (now - earliest) + 0.1
            if wait_time > 0:
                print(f"[RATE LIMIT] 等待 {wait_time:.1f} 秒...")
                time.sleep(wait_time)
                now = time.time()
                request_timestamps = [ts for ts in request_timestamps if now - ts < 60]
        
        request_timestamps.append(time.time())


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


def get_stock_list():
    """从本地文件获取A股股票列表"""
    print("[INFO] 从本地文件读取股票列表...")
    stock_list = []
    
    # 使用项目自带的stock_list.txt
    stock_list_file = os.path.join(SCRIPT_DIR, "..", "stock_list.txt")
    # 也尝试当前目录
    if not os.path.exists(stock_list_file):
        stock_list_file = os.path.join(SCRIPT_DIR, "stock_list.txt")
    
    if os.path.exists(stock_list_file):
        with open(stock_list_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    parts = line.split(',')
                    if len(parts) >= 2:
                        symbol = parts[0].strip()
                        name = parts[1].strip()
                        # 转换symbol为ts_code格式
                        if symbol.startswith('6'):
                            ts_code = f"{symbol}.SH"
                        else:
                            ts_code = f"{symbol}.SZ"
                        stock_list.append({
                            'ts_code': ts_code,
                            'symbol': symbol,
                            'name': name
                        })
        print(f"[SUCCESS] 从本地文件成功读取 {len(stock_list)} 只股票")
        return stock_list
    else:
        print("[ERROR] 股票列表文件不存在!")
        return []


def download_stock_kline(ts_code, name, start_date, end_date):
    """下载单只股票K线数据 - 使用daily接口"""
    print(f"[INFO] 正在下载 {ts_code} ({name}) {start_date} 至 {end_date}...")
    
    for retry in range(RETRY_TIMES):
        try:
            # 每次请求前限速
            rate_limit()
            
            df = pro.daily(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date
            )
            
            if df is not None and not df.empty:
                df = df.sort_values('trade_date').reset_index(drop=True)
                print(f"[SUCCESS] {ts_code} ({name}) 拉取成功，共 {len(df)} 条数据")
                return df
            else:
                print(f"[WARN] {ts_code} ({name}) 无数据返回")
                return None
                
        except Exception as e:
            if retry < RETRY_TIMES - 1:
                print(f"[WARN] {ts_code} ({name}) 下载失败 (尝试 {retry + 1}/{RETRY_TIMES}): {e}")
                time.sleep(RETRY_DELAY)
            else:
                print(f"[ERROR] {ts_code} ({name}) 下载失败: {type(e).__name__}")
    return None


def save_to_csv(df, ts_code, symbol, name):
    """保存数据到CSV"""
    if df is None or df.empty:
        return False
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        safe_name = "".join([c for c in str(name) if c.isalnum() or c in ('_', '-')])
        filename = f"{symbol}_{safe_name}.csv"
        filepath = os.path.join(DATA_DIR, filename)
        df.to_csv(filepath, index=False, encoding='utf-8-sig')
        
        if os.path.exists(filepath):
            print(f"[SUCCESS] {ts_code} ({name}) 保存成功: {len(df)} 条 -> {filepath}")
            return True
        else:
            print(f"[ERROR] {ts_code} ({name}) 文件未创建!")
            return False
    except Exception as e:
        print(f"[ERROR] {ts_code} ({name}) 保存失败: {str(e)[:80]}")
        return False


def main():
    print("=" * 60)
    print("Tushare A股K线数据下载工具 (使用daily接口)")
    print(f"限速: 每分钟 {MAX_REQUESTS_PER_MINUTE} 次请求")
    print("=" * 60)
    
    progress = load_progress()
    existing = get_existing_files()
    
    for code in existing:
        if code not in progress["downloaded"]:
            progress["downloaded"].append(code)
    save_progress(progress)
    
    print(f"[INFO] 已下载: {len(progress['downloaded'])} 只股票")
    
    stock_list = get_stock_list()
    if not stock_list:
        print("[ERROR] 无法获取股票列表!")
        return
    
    downloaded = set(progress['downloaded'])
    pending = [s for s in stock_list if s['symbol'] not in downloaded]
    print(f"[INFO] 待下载: {len(pending)} 只股票")
    
    if not pending:
        print("[INFO] 全部下载完成!")
        return
    
    os.makedirs(DATA_DIR, exist_ok=True)
    success = 0
    fail = 0
    
    for i, stock in enumerate(tqdm(pending, desc="下载进度")):
        ts_code = stock['ts_code']
        symbol = stock['symbol']
        name = stock['name']
        
        print(f"\n--- [{i+1}/{len(pending)}] {ts_code} ({name}) ---")
        
        df = download_stock_kline(ts_code, name, START_DATE, END_DATE)
        
        if save_to_csv(df, ts_code, symbol, name):
            success += 1
            progress["downloaded"].append(symbol)
            save_progress(progress)
        else:
            fail += 1
    
    print("\n" + "=" * 60)
    print(f"下载完成! 成功: {success}, 失败: {fail}")
    print("=" * 60)


if __name__ == "__main__":
    main()
