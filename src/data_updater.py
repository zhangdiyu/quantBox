# -*- coding: utf-8 -*-
"""
A股数据增量更新工具
- 自动检测已有数据
- 只下载缺失的最新数据
- 支持断点续传
"""
import akshare as ak
import pandas as pd
import os
import time
from datetime import datetime, timedelta
from tqdm import tqdm
import json

# 配置
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "data")
PROGRESS_FILE = os.path.join(SCRIPT_DIR, "update_progress.json")

# 确保数据目录存在
os.makedirs(DATA_DIR, exist_ok=True)


def get_last_update_date():
    """获取上次更新日期"""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            progress = json.load(f)
            return progress.get('last_update_date')
    return None


def save_progress(last_date, stats):
    """保存更新进度"""
    progress = {
        'last_update_date': last_date,
        'last_update_time': datetime.now().isoformat(),
        'stats': stats
    }
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def get_stock_last_date(stock_code):
    """获取某只股票已有数据的最后日期"""
    filename = os.path.join(DATA_DIR, f"{stock_code}.csv")
    if os.path.exists(filename):
        try:
            df = pd.read_csv(filename)
            if '日期' in df.columns and not df.empty:
                return df['日期'].iloc[-1]
        except Exception as e:
            print(f"[WARN] 读取 {stock_code} 历史数据失败: {e}")
    return None


def fetch_stock_data(stock_code, start_date, end_date):
    """获取单只股票的K线数据"""
    try:
        # 使用akshare获取数据
        df = ak.stock_zh_a_hist(
            symbol=stock_code,
            start_date=start_date,
            end_date=end_date,
            adjust="qfq"  # 前复权
        )
        return df
    except Exception as e:
        print(f"[ERROR] 获取 {stock_code} 数据失败: {e}")
        return None


def merge_and_save(stock_code, new_df):
    """合并新数据并保存"""
    if new_df is None or new_df.empty:
        return False
    
    filename = os.path.join(DATA_DIR, f"{stock_code}.csv")
    
    try:
        if os.path.exists(filename):
            # 读取已有数据
            old_df = pd.read_csv(filename)
            # 合并数据
            combined = pd.concat([old_df, new_df], ignore_index=True)
            # 去重（按日期）
            combined = combined.drop_duplicates(subset=['日期'], keep='first')
            # 排序
            combined = combined.sort_values('日期').reset_index(drop=True)
        else:
            combined = new_df
        
        # 保存
        combined.to_csv(filename, index=False, encoding='utf-8-sig')
        return True
    except Exception as e:
        print(f"[ERROR] 保存 {stock_code} 数据失败: {e}")
        return False


def update_stocks(stock_codes, start_date=None, end_date=None):
    """批量更新股票数据"""
    if end_date is None:
        end_date = datetime.now().strftime('%Y%m%d')
    
    if start_date is None:
        # 默认从30天前开始
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')
    
    print(f"[INFO] 数据更新范围: {start_date} - {end_date}")
    print(f"[INFO] 待更新股票数: {len(stock_codes)}")
    
    success = 0
    fail = 0
    
    for i, code in enumerate(tqdm(stock_codes, desc="更新进度")):
        # 检查该股票的最后更新日期
        last_date = get_stock_last_date(code)
        
        if last_date:
            # 从最后日期的下一天开始
            next_date = (pd.to_datetime(last_date) + timedelta(days=1)).strftime('%Y%m%d')
            if next_date > end_date:
                print(f"[SKIP] {code} 数据已是最新 ({last_date})")
                continue
            fetch_start = next_date
        else:
            fetch_start = start_date
        
        print(f"\n[{i+1}/{len(stock_codes)}] {code}: {fetch_start} - {end_date}")
        
        # 获取数据
        new_df = fetch_stock_data(code, fetch_start, end_date)
        
        # 合并保存
        if new_df is not None and not new_df.empty:
            if merge_and_save(code, new_df):
                success += 1
            else:
                fail += 1
        else:
            print(f"[WARN] {code} 无新数据")
            fail += 1
        
        # 避免请求过快
        time.sleep(0.5)
    
    return success, fail


def main():
    """主函数"""
    print("=" * 60)
    print("A股数据增量更新工具")
    print("=" * 60)
    
    # 获取上次更新日期
    last_update = get_last_update_date()
    if last_update:
        print(f"[INFO] 上次更新日期: {last_update}")
    else:
        print("[INFO] 首次运行，将下载历史数据")
    
    # 获取股票列表
    print("\n[INFO] 正在获取股票列表...")
    stock_df = ak.stock_zh_a_spot_em()
    stock_codes = stock_df['代码'].tolist()[:100]  # 先测试前100只
    print(f"[INFO] 获取到 {len(stock_codes)} 只股票")
    
    # 执行更新
    print("\n[INFO] 开始更新数据...")
    success, fail = update_stocks(stock_codes)
    
    # 保存进度
    end_date = datetime.now().strftime('%Y%m%d')
    stats = {
        'total': len(stock_codes),
        'success': success,
        'fail': fail
    }
    save_progress(end_date, stats)
    
    # 输出结果
    print("\n" + "=" * 60)
    print("更新完成!")
    print(f"- 总股票数: {len(stock_codes)}")
    print(f"- 成功: {success}")
    print(f"- 失败: {fail}")
    print(f"- 数据保存路径: {DATA_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
