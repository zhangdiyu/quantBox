
"""
测试指数下载
"""
import akshare as ak
import pandas as pd
import os
from datetime import datetime
from pathlib import Path

# 设置工作目录
SCRIPT_DIR = Path(__file__).parent
os.chdir(SCRIPT_DIR)

DATA_DIR = SCRIPT_DIR / "data" / "indices"
DATA_DIR.mkdir(parents=True, exist_ok=True)

START_DATE = "20150101"
END_DATE = datetime.now().strftime("%Y%m%d")

print("=" * 60)
print("测试指数下载")
print("=" * 60)

# 先测试一个指数
test_indices = [
    ("000001", "上证指数"),
    ("399001", "深证成指"),
]

for code, name in test_indices:
    print(f"\n正在下载: {code} {name}")
    try:
        df = ak.index_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=START_DATE,
            end_date=END_DATE
        )
        
        if df is not None and not df.empty:
            print(f"  ✓ 成功获取 {len(df)} 条数据")
            print(f"  列名: {df.columns.tolist()}")
            print(f"  前5行:")
            print(df.head())
            
            # 保存文件
            filename = f"{code}_{name}.csv"
            filepath = DATA_DIR / filename
            df.to_csv(filepath, index=False, encoding='utf-8-sig')
            print(f"  ✓ 已保存到: {filepath}")
        else:
            print(f"  ✗ 无数据返回")
            
    except Exception as e:
        print(f"  ✗ 下载失败: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)

