# -*- coding: utf-8 -*-
"""
使用iTick下载港股历史K线数据
免费注册获取token: https://api.itick.org
"""
import requests
import pandas as pd
import os
import time
import json
from datetime import datetime
from tqdm import tqdm

# 强制设置工作目录
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)

# iTick配置 - 需要注册获取免费token
# https://api.itick.org 注册免费账号
ITICK_TOKEN = ""  # 在这里填入你的iTick token

DATA_DIR = os.path.join(SCRIPT_DIR, "..", "hk_data")
PROGRESS_FILE = os.path.join(SCRIPT_DIR, "download_progress_hk.json")
START_DATE = "2005-01-01"
END_DATE = datetime.now().strftime("%Y-%m-%d")
RETRY_TIMES = 3
RETRY_DELAY = 2

print(f"Working directory: {os.getcwd()}")
print(f"Data directory: {DATA_DIR}")


# 港股主要股票列表（按市值排名，top 500简版）
HK_STOCKS = [
    {"code": "700", "name": "腾讯控股"},
    {"code": "9988", "name": "阿里巴巴-SW"},
    {"code": "0001", "name": "长和"},
    {"code": "0011", "name": "恒生银行"},
    {"code": "0012", "name": "恒安国际"},
    {"code": "0016", "name": "新鸿基地产"},
    {"code": "0017", "name": "新鸿基"},
    {"code": "0019", "name": "太古股份公司A"},
    {"code": "0022", "name": "巨涛海洋石油"},
    {"code": "0027", "name": "银河娱乐"},
    {"code": "0045", "name": "香港中华煤气"},
    {"code": "0066", "name": "港铁公司"},
    {"code": "0092", "name": "粤海投资"},
    {"code": "0095", "name": "蒙牛乳业"},
    {"code": "0109", "name": "北京控股"},
    {"code": "0113", "name": "德昌电机控股"},
    {"code": "0119", "name": "中国海外"},
    {"code": "0131", "name": "中国卓银"},
    {"code": "0133", "name": "华润啤酒"},
    {"code": "0144", "name": "中国招商局"},
    {"code": "0156", "name": "中金公司"},
    {"code": "0158", "name": "中国建筑国际"},
    {"code": "0188", "name": "中国燃气"},
    {"code": "0189", "name": "山东黄金"},
    {"code": "0191", "name": "华润水泥"},
    {"code": "0199", "name": "中国交通建设"},
    {"code": "0219", "name": "中国太保"},
    {"code": "0222", "name": "中国飞鹤"},
    {"code": "0238", "name": "中国电子"},
    {"code": "0240", "name": "中国电力"},
    {"code": "0242", "name": "信德集团"},
    {"code": "0247", "name": "中国民生"},
    {"code": "0249", "name": "中国金茂"},
    {"code": "0257", "name": "光大环境"},
    {"code": "0260", "name": "中国北方"},
    {"code": "0267", "name": "中信股份"},
    {"code": "0270", "name": "粤海置地"},
    {"code": "0285", "name": "中国华能"},
    {"code": "0293", "name": "国泰航空"},
    {"code": "0297", "name": "中国中铁"},
    {"code": "0330", "name": "思爱普"},
    {"code": "0348", "name": "中国利郎"},
    {"code": "0358", "name": "江西铜业"},
    {"code": "0366", "name": "中通服"},
    {"code": "0386", "name": "中国石油化工"},
    {"code": "0388", "name": "港交所"},
    {"code": "0390", "name": "中国中铁"},
    {"code": "0408", "name": "中国家居"},
    {"code": "0418", "name": "中国方正"},
    {"code": "0425", "name": "中国民生"},
    {"code": "0433", "name": "中国北方稀土"},
    {"code": "0449", "name": "中国忠旺"},
    {"code": "0452", "name": "中国中铁"},
    {"code": "0489", "name": "中国东风"},
    {"code": "0588", "name": "中国银行"},
    {"code": "0606", "name": "中国金控"},
    {"code": "0607", "name": "中国金融投资"},
    {"code": "0608", "name": "中国远洋"},
    {"code": "0611", "name": "中国核能"},
    {"code": "0618", "name": "中国海洋石油"},
    {"code": "0619", "name": "中国燃气"},
    {"code": "0621", "name": "中国金属"},
    {"code": "0625", "name": "中国投资"},
    {"code": "0628", "name": "中国电力"},
    {"code": "0636", "name": "中国航空"},
    {"code": "0656", "name": "中国光大"},
    {"code": "0669", "name": "中国海泥"},
    {"code": "0688", "name": "中国海外"},
    {"code": "0696", "name": "中国民航"},
    {"code": "0700", "name": "腾讯控股"},
    {"code": "0728", "name": "中国电信"},
    {"code": "0755", "name": "中国华融"},
    {"code": "0762", "name": "中国联通"},
    {"code": "0769", "name": "中国投资"},
    {"code": "0788", "name": "中国铁建"},
    {"code": "0806", "name": "中国惠理"},
    {"code": "0813", "name": "中国中铁"},
    {"code": "0823", "name": "中国水务"},
    {"code": "0828", "name": "中国金手指"},
    {"code": "0831", "name": "中国中铁"},
    {"code": "0836", "name": "中国华润"},
    {"code": "0857", "name": "中国石油"},
    {"code": "0866", "name": "中国中铁"},
    {"code": "0881", "name": "中国升海"},
    {"code": "0883", "name": "中国海洋石油"},
    {"code": "0888", "name": "中国金山"},
    {"code": "0891", "name": "中国网络"},
    {"code": "0895", "name": "中国东江"},
    {"code": "0906", "name": "中国网通"},
    {"code": "0912", "name": "中国金融"},
    {"code": "0914", "name": "中国电力"},
    {"code": "0921", "name": "中国食品"},
    {"code": "0939", "name": "建设银行"},
    {"code": "0941", "name": "中国移动"},
    {"code": "0943", "name": "中国铝业"},
    {"code": "0955", "name": "中国信用"},
    {"code": "0959", "name": "中国奥园"},
    {"code": "0960", "name": "中国龙湖"},
    {"code": "0968", "name": "中国电力"},
    {"code": "0969", "name": "中国环保"},
    {"code": "0981", "name": "中芯国际"},
    {"code": "0988", "name": "工商银行"},
    {"code": "0992", "name": "联想集团"},
    {"code": "0998", "name": "工商银行"},
    {"code": "0999", "name": "招商银行"},
]


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
                code = f.replace('.csv', '')
                existing.add(code)
    return existing


def download_stock_kline_itick(code, name, start_date, end_date):
    """使用iTick API下载港股K线数据"""
    if not ITICK_TOKEN:
        print("[ERROR] 请先在 https://api.itick.org 注册获取token")
        return None
    
    url = "https://api.itick.org/stock/kline"
    params = {
        "code": code,
        "region": "HK",
        "start": start_date,
        "end": end_date,
        "fields": "date,open,high,low,close,volume"
    }
    headers = {
        "accept": "application/json",
        "token": ITICK_TOKEN
    }
    
    for retry in range(RETRY_TIMES):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == 200 and data.get('data'):
                    df = pd.DataFrame(data['data'])
                    return df
            return None
        except Exception as e:
            if retry < RETRY_TIMES - 1:
                time.sleep(RETRY_DELAY)
    return None


def save_to_csv(df, code, name):
    """保存数据到CSV"""
    if df is None or df.empty:
        return False
    
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        filename = f"{code}.csv"
        filepath = os.path.join(DATA_DIR, filename)
        df.to_csv(filepath, index=False, encoding='utf-8-sig')
        
        if os.path.exists(filepath):
            print(f"[SUCCESS] {code} ({name}) 保存成功: {len(df)} 条")
            return True
        return False
    except Exception as e:
        print(f"[ERROR] {code} 保存失败: {str(e)[:80]}")
        return False


def main():
    print("=" * 60)
    print("港股K线数据下载工具 (使用iTick)")
    print("=" * 60)
    
    if not ITICK_TOKEN:
        print("\n请先注册iTick账号获取token:")
        print("1. 访问 https://api.itick.org 注册账号")
        print("2. 登录后在个人中心获取token")
        print("3. 填入到脚本中的 ITICK_TOKEN 变量")
        return
    
    progress = load_progress()
    existing = get_existing_files()
    
    for code in existing:
        if code not in progress["downloaded"]:
            progress["downloaded"].append(code)
    save_progress(progress)
    
    print(f"[INFO] 已下载: {len(progress['downloaded'])} 只股票")
    
    downloaded = set(progress['downloaded'])
    pending = [s for s in HK_STOCKS if s['code'] not in downloaded]
    print(f"[INFO] 待下载: {len(pending)} 只股票")
    
    if not pending:
        print("[INFO] 全部下载完成!")
        return
    
    os.makedirs(DATA_DIR, exist_ok=True)
    success = 0
    fail = 0
    
    for i, stock in enumerate(tqdm(pending, desc="下载进度")):
        code = stock['code']
        name = stock['name']
        
        print(f"\n--- [{i+1}/{len(pending)}] {code} ({name}) ---")
        
        df = download_stock_kline_itick(code, name, START_DATE, END_DATE)
        
        if save_to_csv(df, code, name):
            success += 1
            progress["downloaded"].append(code)
            save_progress(progress)
        else:
            fail += 1
        
        if (i + 1) % 10 == 0:
            time.sleep(1)
    
    print("\n" + "=" * 60)
    print(f"下载完成! 成功: {success}, 失败: {fail}")
    print("=" * 60)


if __name__ == "__main__":
    main()
