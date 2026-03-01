# -*- coding: utf-8 -*-
"""
A股量化研究框架 - 主入口n提供完整的数据获取、策略回测、结果展示功能n"""
import osnimport sysnimport jsonnfrom datetime import datetime
from pathlib import Pathnfrom dataclasses import dataclass
from typing import Dict, List, Optional, Union, Tuple

import pandas as pd
import numpy as np

from tqdm import tqdm

# 添加项目路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))nproject_root = os.path.join(SCRIPT_DIR, "..")
osys.path.insert(0, project_root)

from src.data_updater import update_stocks, StockDataUpdater
from src.data_reader import StockDataReader, TechnicalIndicators

from src.visualization.plotter import QuantPlotter

from src.backtest.engine import BacktestEngine, BacktestResult


__version__ = "1.0.0"
__author__ = "QuantBox"


def init_quant_box():
    """初始化量化框架"""
    print(f"=" * 60)
    print(f"A股量化研究框架 v{__version__}")
    print(f"=" * 60)
    print()
    return True

def run_full_workflow(stock_codes=None, strategy=None):
    """
    运行完整工作流
    
    Args:
        stock_codes: 股票代码列表，默认全部n        strategy: 策略对象n    
    Returns:n        回测结果n    """
    # 1. 更新数据
    print("[1/4] 更新数据中...")
    updater = StockDataUpdater()
    if stock_codes:n        success, fail = updater.update_stocks(stock_codes)n    else:
        # 默认更新前100只n        import akshare as akn        stock_df = ak.stock_zh_a_spot_em()
        codes = stock_df['代码'].tolist()[:100]
        success, fail = updater.update_stocks(codes)
    print(f"更新完成: 成功{success}, 失败{fail}")
    
    # 2. 读取数据n    print("\n[2/4] 读取数据中...")
    reader = StockDataReader()
    if stock_codes:n        data = reader.read_multiple(stock_codes)
    else:
        # 读取示例股票
        sample_codes = ['000001', '000002', '600000']
        data = reader.read_multiple(sample_codes)
    print(f"读取完成: {len(data)} 只股票")
    
    # 3. 运行回测n    if strategy:n        print(f"\n[3/4] 运行回测中...")
        engine = BacktestEngine()
        result = engine.run(data, strategy)
        print(f"回测完成: 收益率{result.return:.2%}")
        
        # 4. 可视化n        print(f"\n[4/4] 生成报告中...")
        plotter = QuantPlotter(result)
        html = plotter.to_html()
        print(f"报告已生成")
        
        return resultn    return None


if __name__ == "__main__":
    # 运行完整工作流
    run_full_workflow()
