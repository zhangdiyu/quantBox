# -*- coding: utf-8 -*-
"""
全A股ETF日线数据下载工具
- 使用 akshare 获取 ETF 列表和历史日线数据
- 保存到 data/etf/ 目录
- 支持断点续传
"""
import akshare as ak
import pandas as pd
import os
import sys
import io
import time
import json
from datetime import datetime
from tqdm import tqdm

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "data", "etf")
PROGRESS_FILE = os.path.join(SCRIPT_DIR, "download_progress_etf.json")
START_DATE = "20150101"
END_DATE = datetime.now().strftime("%Y%m%d")
RETRY_TIMES = 3
RETRY_DELAY = 2

os.makedirs(DATA_DIR, exist_ok=True)

if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    except Exception:
        pass


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
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


def get_etf_list():
    """获取全部 ETF 列表 (东方财富)"""
    print("[INFO] 正在获取 ETF 列表...")
    try:
        df = ak.fund_etf_spot_em()
        etf_list = []
        for _, row in df.iterrows():
            code = str(row.get('代码', '')).strip()
            name = str(row.get('名称', '')).strip()
            if code and len(code) == 6:
                etf_list.append((code, name))
        print(f"[INFO] 获取到 {len(etf_list)} 只 ETF")
        return etf_list
    except Exception as e:
        print(f"[ERROR] 获取 ETF 列表失败: {e}")
        return []


def download_etf_hist(symbol, name):
    """下载单只 ETF 的日线数据"""
    for retry in range(RETRY_TIMES):
        try:
            df = ak.fund_etf_hist_em(
                symbol=symbol,
                period="daily",
                start_date=START_DATE,
                end_date=END_DATE,
                adjust=""
            )
            if df is not None and not df.empty:
                return df
            return None
        except Exception as e:
            if retry < RETRY_TIMES - 1:
                time.sleep(RETRY_DELAY)
            else:
                print(f"[ERROR] {symbol} {name}: {type(e).__name__}: {str(e)[:60]}")
    return None


def save_to_csv(df, symbol, name):
    if df is None or df.empty:
        return False
    try:
        safe_name = "".join([c for c in name if c.isalnum() or c in ('_', '-')])
        filename = f"{symbol}_{safe_name}.csv"
        filepath = os.path.join(DATA_DIR, filename)
        df.to_csv(filepath, index=False, encoding='utf-8-sig')
        return os.path.exists(filepath)
    except Exception as e:
        print(f"[ERROR] 保存 {symbol} 失败: {e}")
        return False


def main():
    print("=" * 60)
    print("A股 ETF 日线数据下载工具")
    print(f"数据目录: {DATA_DIR}")
    print(f"日期范围: {START_DATE} ~ {END_DATE}")
    print("=" * 60)

    progress = load_progress()
    existing = get_existing_files()
    for code in existing:
        if code not in progress["downloaded"]:
            progress["downloaded"].append(code)
    save_progress(progress)
    print(f"[INFO] 已下载: {len(progress['downloaded'])} 只 ETF")

    etf_list = get_etf_list()
    if not etf_list:
        print("[ERROR] 无法获取 ETF 列表!")
        return

    downloaded = set(progress['downloaded'])
    pending = [(c, n) for c, n in etf_list if c not in downloaded]
    print(f"[INFO] 待下载: {len(pending)} 只 ETF")

    if not pending:
        print("[INFO] 全部下载完成!")
        return

    success = 0
    fail = 0

    for i, (code, name) in enumerate(tqdm(pending, desc="下载ETF")):
        df = download_etf_hist(code, name)

        if save_to_csv(df, code, name):
            success += 1
            progress["downloaded"].append(code)
            if (i + 1) % 10 == 0:
                save_progress(progress)
        else:
            fail += 1
            if code not in progress["failed"]:
                progress["failed"].append(code)

        time.sleep(0.5)

    save_progress(progress)

    print("\n" + "=" * 60)
    print(f"下载完成! 成功: {success}, 失败: {fail}")
    print(f"数据保存路径: {DATA_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
