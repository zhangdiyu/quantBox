# -*- coding: utf-8 -*-
"""
股票数据读取与解析模块
提供便捷的数据读取、技术指标计算、数据筛选等功能
方便量化研究使用
"""
import pandas as pd
import numpy as np
import os
from typing import List, Union, Optional, Dict
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# 配置
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "data")



class StockDataReader:
    """股票数据读取器"""
    
    def __init__(self, data_dir: str = None):
        """
        初始化数据读取器
        
        Args:
            data_dir: 数据目录路径，默认使用标准路径
        """
        self.data_dir = data_dir or DATA_DIR
        if not os.path.exists(self.data_dir):
            raise FileNotFoundError(f"数据目录不存在: {self.data_dir}")
        
        self._cache = {}  # 数据缓存
        
    def _get_stock_file(self, stock_code: str) -> str:
        """获取股票数据文件路径"""
        # 尝试多种格式
        candidates = [
            os.path.join(self.data_dir, f"{stock_code}.csv"),
            os.path.join(self.data_dir, f"{stock_code}.sz.csv"),
            os.path.join(self.data_dir, f"{stock_code}.sh.csv"),
        ]
        for candidate in candidates:
            if os.path.exists(candidate):
                return candidate
        return None
    
    def read_stock(self, stock_code: str, 
                   start_date: str = None,
                   end_date: str = None,
                   use_cache: bool = True) -> pd.DataFrame:
        """
        读取单只股票数据
        
        Args:
            stock_code: 股票代码，如 '000001', '600000'
            start_date: 开始日期 'YYYY-MM-DD'，默认全部
            end_date: 结束日期 'YYYY-MM-DD'，默认全部
            use_cache: 是否使用缓存
            
        Returns:
            DataFrame with columns: 日期, 开盘, 最高, 最低, 收盘, 成交量, 成交额...
        """
        cache_key = f"{stock_code}_{start_date}_{end_date}"
        
        if use_cache and cache_key in self._cache:
            return self._cache[cache_key].copy()
        
        file_path = self._get_stock_file(stock_code)
        if not file_path:
            raise FileNotFoundError(f"未找到股票 {stock_code} 的数据文件")
        
        df = pd.read_csv(file_path)
        
        # 确保日期列存在
        if '日期' in df.columns:
            df['日期'] = pd.to_datetime(df['日期'])
            df = df.sort_values('日期').reset_index(drop=True)
        elif 'date' in df.columns:
            df['日期'] = pd.to_datetime(df['date'])
            df = df.sort_values('日期').reset_index(drop=True)
        
        # 日期过滤
        if start_date:
            df = df[df['日期'] >= start_date]
        if end_date:
            df = df[df['日期'] <= end_date]
        
        # 缓存
        if use_cache:
            self._cache[cache_key] = df.copy()
        
        return df.copy()
    
    def read_multiple(self, stock_codes: List[str],
                      start_date: str = None,
                      end_date: str = None) -> Dict[str, pd.DataFrame]:
        """
        批量读取多只股票数据
        
        Args:
            stock_codes: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            Dict[股票代码, DataFrame]
        """
        result = {}
        for code in tqdm(stock_codes, desc="读取股票数据"):
            try:
                df = self.read_stock(code, start_date, end_date)
                result[code] = df
            except Exception as e:
                print(f"[ERROR] 读取 {code} 失败: {e}")
        return result


class TechnicalIndicators:
    """技术指标计算类"""
    
    @staticmethod
    def ma(df: pd.DataFrame, periods: List[int] = [5, 10, 20, 60]) -> pd.DataFrame:
        """
        计算移动平均线 (MA)
        
        Args:
            df: DataFrame with '收盘' column
            periods: 移动平均周期列表
            
        Returns:
            添加了MA列的DataFrame
        """
        for period in periods:
            df[f'MA{period}'] = df['收盘'].rolling(window=period).mean()
        return df
    
    @staticmethod
    def ema(df: pd.DataFrame, periods: List[int] = [12, 26]) -> pd.DataFrame:
        """
        计算指数移动平均线 (EMA)
        
        Args:
            df: DataFrame with '收盘' column
            periods: EMA周期列表
            
        Returns:
            添加了EMA列的DataFrame
        """
        for period in periods:
            df[f'EMA{period}'] = df['收盘'].ewm(span=period, adjust=False).mean()
        return df
    
    @staticmethod
    def macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
        """
        计算MACD指标
        
        Args:
            df: DataFrame with '收盘' column
            fast: 快线周期
            slow: 慢线周期
            signal: 信号线周期
            
        Returns:
            添加了MACD列的DataFrame
        """
        ema_fast = df['收盘'].ewm(span=fast, adjust=False).mean()
        ema_slow = df['收盘'].ewm(span=slow, adjust=False).mean()
        
        df['MACD'] = ema_fast - ema_slow
        df['MACD_Signal'] = df['MACD'].ewm(span=signal, adjust=False).mean()
        df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
        
        return df
    
    @staticmethod
    def rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """
        计算RSI指标
        
        Args:
            df: DataFrame with '收盘' column
            period: RSI周期
            
        Returns:
            添加了RSI列的DataFrame
        """
        delta = df['收盘'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        df[f'RSI{period}'] = 100 - (100 / (1 + rs))
        return df
    
    @staticmethod
    def bollinger_bands(df: pd.DataFrame, period: int = 20, std: int = 2) -> pd.DataFrame:
        """
        计算布林带
        
        Args:
            df: DataFrame with '收盘' column
            period: 移动平均周期
            std: 标准差倍数
            
        Returns:
            添加了布林带列的DataFrame
        """
        df[f'BB_Middle{period}'] = df['收盘'].rolling(window=period).mean()
        rolling_std = df['收盘'].rolling(window=period).std()
        df[f'BB_Upper{period}'] = df[f'BB_Middle{period}'] + (rolling_std * std)
        df[f'BB_Lower{period}'] = df[f'BB_Middle{period}'] - (rolling_std * std)
        return df
    
    @staticmethod
    def calculate_all(df: pd.DataFrame) -> pd.DataFrame:
        """
        计算所有技术指标
        
        Args:
            df: DataFrame with '收盘', '开盘', '最高', '最低', '成交量' columns
            
        Returns:
            添加了所有技术指标的DataFrame
        """
        # 移动平均线
        df = TechnicalIndicators.ma(df)
        
        # 指数移动平均
        df = TechnicalIndicators.ema(df)
        
        # MACD
        df = TechnicalIndicators.macd(df)
        
        # RSI
        df = TechnicalIndicators.rsi(df)
        
        # 布林带
        df = TechnicalIndicators.bollinger_bands(df)
        
        return df


# ==================== 使用示例 ====================

if __name__ == "__main__":
    print("=" * 60)
    print("数据读取和技术指标计算示例")
    print("=" * 60)
    
    # 1. 创建数据读取器
    reader = StockDataReader()
    
    # 2. 读取单只股票
    print("\n[示例1] 读取单只股票数据")
    try:
        df = reader.read_stock('000001', start_date='2024-01-01')
        print(f"成功读取 000001，共 {len(df)} 条记录")
        print(df.head())
    except Exception as e:
        print(f"读取失败: {e}")
    
    # 3. 计算技术指标
    print("\n[示例2] 计算技术指标")
    try:
        df = TechnicalIndicators.calculate_all(df)
        print("技术指标计算完成")
        print(df[['日期', '收盘', 'MA5', 'MA20', 'RSI14', 'MACD']].tail())
    except Exception as e:
        print(f"计算失败: {e}")
    
    print("\n" + "=" * 60)
    print("示例运行完成！")
    print("=" * 60)
