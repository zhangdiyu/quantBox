
# 主要指数日K数据下载脚本
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

DATA_DIR = os.path.join(SCRIPT_DIR, "data", "indices")
SRC_DIR = SCRIPT_DIR
PROGRESS_FILE = os.path.join(SRC_DIR, "download_progress_indices.json")
START_DATE = "20150101"
END_DATE = datetime.now().strftime("%Y%m%d")
RETRY_TIMES = 5
RETRY_DELAY = 2

# 主要指数列表
MAJOR_INDICES = [
    ("000001", "上证指数", "sh"),
    ("399001", "深证成指", "sz"),
    ("399006", "创业板指", "sz"),
    ("000300", "沪深300", "sh"),
    ("000905", "中证500", "sh"),
    ("000852", "中证1000", "sh"),
    ("000688", "科创50", "sh"),
    ("399106", "深证综指", "sz"),
    ("399005", "中小板指", "sz"),
    ("399300", "沪深300", "sz"),
    ("000016", "上证50", "sh"),
    ("000903", "中证100", "sh"),
]

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

def download_index_kline(symbol, name, market, start_date, end_date):
    """
    下载指数日K数据
    使用 akshare 的指数接口
    """
    for retry in range(RETRY_TIMES):
        try:
            # 尝试使用指数历史行情接口
            df = ak.index_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start_date,
                end_date=end_date
            )
            
            if df is not None and not df.empty:
                # 重命名列以保持一致性
                df = df.rename(columns={
                    '日期': '日期',
                    '开盘': '开盘',
                    '收盘': '收盘',
                    '最高': '最高',
                    '最低': '最低',
                    '成交量': '成交量',
                    '成交额': '成交额',
                    '振幅': '振幅',
                    '涨跌幅': '涨跌幅',
                    '涨跌额': '涨跌额',
                    '换手率': '换手率'
                })
                return df
            
            print(f"[WARN] {symbol} {name}: no data returned")
            return None
            
        except Exception as e:
            if retry < RETRY_TIMES - 1:
                time.sleep(RETRY_DELAY)
            else:
                print(f"[ERROR] {symbol} {name}: {type(e).__name__}: {str(e)[:100]}")
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
            print(f"[OK] {symbol} {name}: {len(df)} rows -> {filepath}")
            return True
        else:
            print(f"[ERROR] {symbol} {name}: file not created!")
            return False
    except Exception as e:
        print(f"[ERROR] {symbol} {name}: {str(e)[:80]}")
        return False

def main():
    print("=" * 60)
    print("主要指数日K数据下载工具")
    print("=" * 60)
    
    progress = load_progress()
    existing = get_existing_files()
    
    # 添加已有文件到进度
    for code in existing:
        if code not in progress["downloaded"]:
            progress["downloaded"].append(code)
    save_progress(progress)
    
    print(f"\n已下载: {len(progress['downloaded'])} 个指数")
    print(f"目标指数: {len(MAJOR_INDICES)} 个")
    
    downloaded = set(progress['downloaded'])
    pending = [(code, name, market) for code, name, market in MAJOR_INDICES if str(code) not in downloaded]
    
    print(f"待下载: {len(pending)} 个指数\n")
    
    if not pending:
        print("所有指数数据已完成下载！")
        return
    
    os.makedirs(DATA_DIR, exist_ok=True)
    success = 0
    fail = 0
    
    for i, (code, name, market) in enumerate(tqdm(pending, desc="下载进度")):
        print(f"\n[{i+1}/{len(pending)}] 正在下载: {code} {name}")
        
        df = download_index_kline(code, name, market, START_DATE, END_DATE)
        
        if save_to_csv(df, code, name):
            success += 1
            progress["downloaded"].append(code)
            save_progress(progress)
        else:
            fail += 1
            progress["failed"].append(code)
            save_progress(progress)
        
        # 避免请求过快
        if (i + 1) % 5 == 0:
            time.sleep(1)
    
    print("\n" + "=" * 60)
    print(f"下载完成！成功: {success}, 失败: {fail}")
    print(f"数据保存位置: {DATA_DIR}")
    print("=" * 60)

if __name__ == "__main__":
    main()

