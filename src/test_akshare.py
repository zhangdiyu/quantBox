# -*- coding: utf-8 -*-
import akshare as ak
import pandas as pd
import time
import sys
import io

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

print("Testing akshare data fetch...")
print("=" * 50)

# Test 1: Get historical data for one stock
print("\n[Test 1] Get stock 600519 historical data...")
try:
    df = ak.stock_zh_a_hist(
        symbol="600519",
        period="daily",
        start_date="20150101",
        end_date="20251231",
        adjust="",
    )
    print(f"Success! Got {len(df)} records")
    print(df.head())
except Exception as e:
    print(f"Failed: {e}")

# Test 2: Get stock list
print("\n[Test 2] Get A-share stock list...")
time.sleep(2)
try:
    stocks = ak.stock_zh_a_spot_em()
    print(f"Success! Got {len(stocks)} stocks")
    print(stocks[["code", "name"]].head(10))
except Exception as e:
    print(f"Failed: {e}")

print("\nTest completed")
