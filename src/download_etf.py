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
from collections import deque
from datetime import datetime
from tqdm import tqdm

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "data", "etf")
PROGRESS_FILE = os.path.join(SCRIPT_DIR, "download_progress_etf.json")
START_DATE = "20150101"
END_DATE = datetime.now().strftime("%Y%m%d")
RETRY_TIMES = 3
RETRY_DELAY = 2
RATE_LIMIT_COUNT = 5
RATE_LIMIT_WINDOW_SECONDS = 60

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


ETF_LIST_CACHE = os.path.join(SCRIPT_DIR, "etf_list_cache.csv")


def get_etf_list():
    """获取全部 ETF 列表，带重试 + 本地缓存回退"""
    print("[INFO] 正在获取 ETF 列表...")

    # 多种接口按优先级尝试
    fetch_methods = [
        ("fund_etf_spot_em", lambda: ak.fund_etf_spot_em()),
        ("fund_etf_category_sina", lambda: ak.fund_etf_category_sina(symbol="ETF基金")),
    ]

    for method_name, fetcher in fetch_methods:
        for attempt in range(RETRY_TIMES):
            try:
                print(f"  尝试 {method_name} (第{attempt+1}次)...")
                df = fetcher()
                if df is not None and not df.empty:
                    etf_list = _parse_etf_df(df)
                    if etf_list:
                        print(f"[INFO] 通过 {method_name} 获取到 {len(etf_list)} 只 ETF")
                        _save_etf_list_cache(etf_list)
                        return etf_list
            except Exception as e:
                print(f"  [{method_name}] 第{attempt+1}次失败: {type(e).__name__}: {str(e)[:80]}")
                time.sleep(RETRY_DELAY * (attempt + 1))

    # 所有在线方式失败，尝试本地缓存
    cached = _load_etf_list_cache()
    if cached:
        print(f"[WARN] 在线获取失败，使用本地缓存 ({len(cached)} 只 ETF)")
        return cached

    print("[ERROR] 无法获取 ETF 列表!")
    return []


def _parse_etf_df(df):
    """从不同来源的 DataFrame 中提取 (code, name) 列表"""
    etf_list = []
    # 尝试多种可能的列名
    code_col = None
    name_col = None
    for c in df.columns:
        cl = str(c).lower()
        if cl in ('代码', 'symbol', 'code', '基金代码'):
            code_col = c
        if cl in ('名称', 'name', '基金简称'):
            name_col = c

    if code_col is None:
        code_col = df.columns[0]
    if name_col is None:
        name_col = df.columns[1] if len(df.columns) > 1 else code_col

    for _, row in df.iterrows():
        code = str(row[code_col]).strip().replace('sh', '').replace('sz', '')
        name = str(row[name_col]).strip()
        # 只保留6位数字代码
        if len(code) == 6 and code.isdigit():
            etf_list.append((code, name))
    return etf_list


def _save_etf_list_cache(etf_list):
    try:
        pd.DataFrame(etf_list, columns=['code', 'name']).to_csv(
            ETF_LIST_CACHE, index=False, encoding='utf-8-sig')
    except Exception:
        pass


def _load_etf_list_cache():
    if os.path.exists(ETF_LIST_CACHE):
        try:
            df = pd.read_csv(ETF_LIST_CACHE, dtype=str)
            return [(r['code'], r['name']) for _, r in df.iterrows()]
        except Exception:
            pass
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
        except (ConnectionError, ConnectionResetError, ConnectionAbortedError) as e:
            wait = RETRY_DELAY * (retry + 1) * 2
            if retry < RETRY_TIMES - 1:
                print(f"  [RETRY] {symbol} 连接断开, {wait}s 后重试...")
                time.sleep(wait)
            else:
                print(f"[ERROR] {symbol} {name}: 连接失败")
        except Exception as e:
            if retry < RETRY_TIMES - 1:
                time.sleep(RETRY_DELAY * (retry + 1))
            else:
                print(f"[ERROR] {symbol} {name}: {type(e).__name__}: {str(e)[:60]}")
    return None


def apply_rate_limit(request_timestamps):
    """限制下载频率：在 60 秒窗口内最多 5 次请求"""
    now = time.time()
    while request_timestamps and now - request_timestamps[0] >= RATE_LIMIT_WINDOW_SECONDS:
        request_timestamps.popleft()

    if len(request_timestamps) >= RATE_LIMIT_COUNT:
        wait_seconds = RATE_LIMIT_WINDOW_SECONDS - (now - request_timestamps[0])
        if wait_seconds > 0:
            print(f"[RATE] 达到频率限制，等待 {wait_seconds:.1f}s ...")
            time.sleep(wait_seconds)

        now = time.time()
        while request_timestamps and now - request_timestamps[0] >= RATE_LIMIT_WINDOW_SECONDS:
            request_timestamps.popleft()

    request_timestamps.append(time.time())


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
    request_timestamps = deque()

    for i, (code, name) in enumerate(tqdm(pending, desc="下载ETF")):
        apply_rate_limit(request_timestamps)
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

    save_progress(progress)

    print("\n" + "=" * 60)
    print(f"下载完成! 成功: {success}, 失败: {fail}")
    print(f"数据保存路径: {DATA_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
