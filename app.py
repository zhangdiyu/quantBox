# -*- coding: utf-8 -*-
"""
QuantBox Streamlit Web App
A股量化研究框架 - Web版本
"""
import os
import sys
import json
import random
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import streamlit as st
import indicators as ind_registry

def read_csv(filepath):
    """通用CSV读取函数，支持多种格式"""
    df = pd.read_csv(filepath)
    
    col_map = {}
    for c in df.columns:
        cl = c.lower().strip()
        if cl in ('trade_date', '日期', 'date'):
            col_map[c] = 'date'
        elif cl in ('open', '开盘'):
            col_map[c] = 'open'
        elif cl in ('high', '最高'):
            col_map[c] = 'high'
        elif cl in ('low', '最低'):
            col_map[c] = 'low'
        elif cl in ('close', '收盘'):
            col_map[c] = 'close'
        elif cl in ('vol', 'volume', '成交量'):
            col_map[c] = 'volume'
        elif cl in ('amount', '成交额'):
            col_map[c] = 'amount'
    
    df.rename(columns=col_map, inplace=True)
    
    required = {'date', 'open', 'high', 'low', 'close'}
    if not required.issubset(df.columns):
        return None
    
    date_raw = df['date'].astype(str).str.strip()
    df['date'] = pd.to_datetime(date_raw, format='%Y%m%d', errors='coerce')
    mask = df['date'].isna()
    if mask.any():
        df.loc[mask, 'date'] = pd.to_datetime(date_raw[mask], errors='coerce')
    df.dropna(subset=['date'], inplace=True)
    df.sort_values('date', inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df

# 添加项目路径
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

# 导入核心模块
try:
    from src.data_reader import StockDataReader, TechnicalIndicators
    from src.backtest_engine import BaseStrategy, BacktestEngine, BacktestResult
    from src.visualization import QuantPlotter
    STREAMLIT_AVAILABLE = True
except ImportError as e:
    st.error(f"导入模块失败: {e}")
    STREAMLIT_AVAILABLE = False

# 页面配置
st.set_page_config(
    page_title="QuantBox - 量化研究",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== 策略定义 ====================

class MovingAverageCrossStrategy(BaseStrategy):
    """均线交叉策略"""
    
    def __init__(self):
        super().__init__()
        self.set_params(fast=5, slow=20)
    
    def init(self, data):
        self.fast = self.params.get('fast', 5)
        self.slow = self.params.get('slow', 20)
    
    def on_bar(self, data, portfolio):
        signals = {}
        for code, df in data.items():
            if len(df) < self.slow:
                continue
            
            ma_fast = df['收盘'].rolling(self.fast).mean().iloc[-1]
            ma_slow = df['收盘'].rolling(self.slow).mean().iloc[-1]
            
            if ma_fast > ma_slow:
                signals[code] = 1
            elif ma_fast < ma_slow:
                signals[code] = -1
            else:
                signals[code] = 0
        
        return signals

# ==================== 辅助函数 ====================

@st.cache_data(ttl=3600)
def get_available_stocks():
    """获取可用股票列表，返回 (code, name, filepath) 元组列表"""
    stocks = []
    
    # 检查两个可能的 data 目录
    data_dirs = [
        SCRIPT_DIR / "data",
        SCRIPT_DIR / "src" / "data"
    ]
    
    for data_dir in data_dirs:
        if data_dir.exists():
            for f in data_dir.glob("*.csv"):
                parts = f.stem.split("_", 1)
                code = parts[0]
                name = parts[1] if len(parts) > 1 else ""
                filepath = str(f)
                # 去重
                if not any(s[0] == code for s in stocks):
                    stocks.append((code, name, filepath))
    
    return sorted(stocks, key=lambda x: x[0])

def load_stock_data(stock_code, start_date=None, end_date=None):
    """加载股票数据 - 支持多种格式"""
    try:
        # 先通过 StockDataReader 尝试
        for data_dir_path in [SCRIPT_DIR / "data", SCRIPT_DIR / "src" / "data"]:
            if data_dir_path.exists():
                # 直接寻找文件
                for f in data_dir_path.glob("*.csv"):
                    if f.stem.startswith(stock_code):
                        # 直接读取并标准化
                        df = pd.read_csv(f)
                        
                        # 标准化列名
                        col_map = {}
                        for c in df.columns:
                            cl = c.lower().strip()
                            if cl in ('trade_date', '日期', 'date'):
                                col_map[c] = 'date'
                            elif cl in ('open', '开盘'):
                                col_map[c] = 'open'
                            elif cl in ('high', '最高'):
                                col_map[c] = 'high'
                            elif cl in ('low', '最低'):
                                col_map[c] = 'low'
                            elif cl in ('close', '收盘'):
                                col_map[c] = 'close'
                            elif cl in ('vol', 'volume', '成交量'):
                                col_map[c] = 'volume'
                            elif cl in ('amount', '成交额'):
                                col_map[c] = 'amount'
                        
                        df.rename(columns=col_map, inplace=True)
                        
                        # 标准化日期
                        if 'date' in df.columns:
                            date_raw = df['date'].astype(str).str.strip()
                            df['date'] = pd.to_datetime(date_raw, format='%Y%m%d', errors='coerce')
                            mask = df['date'].isna()
                            if mask.any():
                                df.loc[mask, 'date'] = pd.to_datetime(date_raw[mask], errors='coerce')
                            df.dropna(subset=['date'], inplace=True)
                            df.sort_values('date', inplace=True)
                            df.reset_index(drop=True, inplace=True)
                        
                        # 日期过滤
                        if start_date:
                            df = df[df['date'] >= start_date]
                        if end_date:
                            df = df[df['date'] <= end_date]
                        
                        return df
        st.error(f"未找到股票 {stock_code} 的数据文件")
        return None
    except Exception as e:
        st.error(f"加载数据失败: {e}")
        return None

def calculate_indicators(df):
    """计算技术指标"""
    try:
        df = TechnicalIndicators.ma(df, periods=[5, 10, 20, 60])
        df = TechnicalIndicators.ema(df, periods=[12, 26])
        df = TechnicalIndicators.macd(df)
        df = TechnicalIndicators.rsi(df, period=14)
        df = TechnicalIndicators.bollinger_bands(df)
        return df
    except Exception as e:
        st.error(f"计算指标失败: {e}")
        return df

def run_backtest(strategy, stock_codes, initial_capital, commission_rate, slippage):
    """运行回测"""
    try:
        # 尝试两个可能的 data 目录
        reader = None
        for data_dir_path in [SCRIPT_DIR / "data", SCRIPT_DIR / "src" / "data"]:
            if data_dir_path.exists():
                try:
                    reader = StockDataReader(str(data_dir_path))
                    break
                except:
                    continue
        
        if not reader:
            st.error("未找到数据目录")
            return None
        
        data = {}
        for code in stock_codes:
            try:
                df = reader.read_stock(code)
                data[code] = df
            except:
                continue
        
        if not data:
            st.error("没有可用的数据进行回测")
            return None
        
        engine = BacktestEngine(
            initial_capital=initial_capital,
            commission_rate=commission_rate,
            slippage=slippage
        )
        
        result = engine.run(data, strategy)
        return result
    except Exception as e:
        st.error(f"回测失败: {e}")
        return None

# ==================== 页面组件 ====================

def show_home():
    """首页"""
    st.title("📊 QuantBox - A股量化研究框架")
    
    st.markdown("""
    欢迎使用 QuantBox！这是一个完整的A股量化研究解决方案，提供：
    
    - 📈 **数据浏览** - 查看股票K线和技术指标
    - 🎯 **策略回测** - 测试你的交易策略
    - 📊 **可视化报告** - 查看回测结果分析
    
    从左侧菜单选择功能开始使用！
    """)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        stocks = get_available_stocks()
        st.metric("可用股票", len(stocks))
    with col2:
        st.metric("技术指标", len(ind_registry.list_names()))
    with col3:
        st.metric("策略模板", "9+")

def show_data_explorer():
    """数据浏览器"""
    st.title("📈 数据浏览器")
    
    st.sidebar.header("股票选择")
    stocks = get_available_stocks()
    
    if not stocks:
        st.warning("未找到数据文件，请确保 data/ 目录中有股票数据")
        return
    
    stock_options = [f"{code} {name}" for code, name, _ in stocks]
    selected_idx = st.sidebar.selectbox("选择股票", range(len(stocks)), index=0, format_func=lambda i: stock_options[i])
    stock_code = stocks[selected_idx][0]
    
    st.sidebar.header("日期范围")
    col1, col2 = st.sidebar.columns(2)
    with col1:
        start_date = st.date_input("开始日期", datetime.now() - timedelta(days=365))
    with col2:
        end_date = st.date_input("结束日期", datetime.now())
    
    # ── 动态加载技术指标选择 ──
    all_indicators = ind_registry.get_all()
    selected_indicators = []  # list of (info, params_dict)

    for cat_name, ind_list in all_indicators.items():
        st.sidebar.header(cat_name)
        for info in ind_list:
            enabled = st.sidebar.checkbox(info['label'], value=(info['name'] in ('MA',)), key=f"ind_{info['name']}")
            if not enabled:
                continue
            # 收集该指标的参数
            params = {}
            for p in info.get('params', []):
                pk = f"{info['name']}_{p['key']}"
                if p['type'] == 'int':
                    params[p['key']] = st.sidebar.slider(p['label'], p.get('min', 1), p.get('max', 100), p['default'], key=pk)
                elif p['type'] == 'float':
                    params[p['key']] = st.sidebar.slider(p['label'], p.get('min', 0.0), p.get('max', 10.0), p['default'], step=p.get('step', 0.1), key=pk)
                elif p['type'] == 'multi_select':
                    params[p['key']] = st.sidebar.multiselect(p['label'], p['options'], default=p['default'], key=pk)
            selected_indicators.append((info, params))

    df = load_stock_data(stock_code, str(start_date), str(end_date))

    if df is None or len(df) == 0:
        st.error("无法加载数据")
        return

    st.subheader(f"股票: {stock_code}")

    # 列名映射
    close_col = 'close' if 'close' in df.columns else '收盘'
    high_col = 'high' if 'high' in df.columns else '最高'
    low_col = 'low' if 'low' in df.columns else '最低'
    open_col = 'open' if 'open' in df.columns else '开盘'
    vol_col = 'volume' if 'volume' in df.columns else '成交量'
    date_col = 'date' if 'date' in df.columns else '日期'

    # 显示基本信息
    if close_col in df.columns:
        col1, col2, col3, col4 = st.columns(4)
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest

        change = latest[close_col] - prev[close_col]
        change_pct = (change / prev[close_col]) * 100 if prev[close_col] != 0 else 0

        with col1:
            st.metric("收盘价", f"{latest[close_col]:.2f}", f"{change:+.2f} ({change_pct:+.2f}%)")
        with col2:
            st.metric("最高价", f"{latest[high_col]:.2f}")
        with col3:
            st.metric("最低价", f"{latest[low_col]:.2f}")
        with col4:
            if vol_col in df.columns:
                st.metric("成交量", f"{int(latest[vol_col]):,}")

    # ── 计算指标并绘图 ──
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    df_plot = df.copy()
    dates = df_plot[date_col].dt.strftime('%Y-%m-%d').tolist()
    color_up = '#ef5350'
    color_down = '#26a69a'

    # 计算所有选中指标
    calc_results = []
    for info, params in selected_indicators:
        calc_fn = info['calc']
        kw = dict(params)
        # 映射列名
        import inspect
        sig = inspect.signature(calc_fn)
        if 'col' in sig.parameters:
            kw.setdefault('col', close_col)
        if 'close' in sig.parameters:
            kw.setdefault('close', close_col)
        if 'high' in sig.parameters:
            kw.setdefault('high', high_col)
        if 'low' in sig.parameters:
            kw.setdefault('low', low_col)
        if 'volume' in sig.parameters:
            kw.setdefault('volume', vol_col)
        # multi_select 类型需要逐个调用
        multi_key = None
        for p in info.get('params', []):
            if p['type'] == 'multi_select':
                multi_key = p['key']
                break
        if multi_key and isinstance(kw.get(multi_key), list):
            for val in kw[multi_key]:
                single_kw = dict(kw)
                single_kw[multi_key] = val
                df_plot, _ = calc_fn(df_plot, **single_kw)
                calc_results.append((info, single_kw))
        else:
            df_plot, _ = calc_fn(df_plot, **kw)
            calc_results.append((info, kw))

    # 确定子图布局
    has_volume = vol_col in df_plot.columns
    # 独立子图指标（非叠加、非成交量叠加）
    subplot_indicators = [(info, kw) for info, kw in calc_results if not info.get('overlay') and not info.get('on_volume')]
    # 去重（同名指标只占一行）
    seen_names = set()
    unique_subplots = []
    for info, kw in subplot_indicators:
        if info['name'] not in seen_names:
            seen_names.add(info['name'])
            unique_subplots.append((info, kw))

    n_rows = 1  # K线
    row_heights = [4]
    if has_volume:
        n_rows += 1
        row_heights.append(1)
    for _ in unique_subplots:
        n_rows += 1
        row_heights.append(1)

    fig = make_subplots(
        rows=n_rows, cols=1,
        shared_xaxes=True,
        row_heights=row_heights,
        vertical_spacing=0.05
    )

    # K线
    fig.add_trace(
        go.Candlestick(
            x=dates, open=df_plot[open_col], high=df_plot[high_col],
            low=df_plot[low_col], close=df_plot[close_col],
            name='K线', increasing_line_color=color_up, decreasing_line_color=color_down
        ),
        row=1, col=1
    )

    # 叠加指标（画在K线行）
    for info, kw in calc_results:
        if info.get('overlay'):
            info['plot'](fig, df_plot, dates, row=1, **kw)

    current_row = 2

    # 成交量
    if has_volume:
        colors = [color_up if df_plot[close_col].iloc[i] >= df_plot[open_col].iloc[i] else color_down for i in range(len(df_plot))]
        fig.add_trace(
            go.Bar(x=dates, y=df_plot[vol_col], name='成交量', marker_color=colors, opacity=0.8),
            row=current_row, col=1
        )
        # 成交量叠加指标
        for info, kw in calc_results:
            if info.get('on_volume'):
                info['plot'](fig, df_plot, dates, row=current_row, **kw)
        fig.update_yaxes(title_text='成交量', row=current_row, col=1)
        current_row += 1

    # 独立子图指标
    subplot_row_map = {}
    for info, kw in unique_subplots:
        subplot_row_map[info['name']] = current_row
        current_row += 1
    for info, kw in calc_results:
        if not info.get('overlay') and not info.get('on_volume') and info['name'] in subplot_row_map:
            info['plot'](fig, df_plot, dates, row=subplot_row_map[info['name']], **kw)

    fig.update_layout(
        height=400 + (n_rows - 1) * 150,
        xaxis_rangeslider_visible=False,
        showlegend=True
    )

    st.plotly_chart(fig, use_container_width=True)

    with st.expander("查看原始数据"):
        st.dataframe(df, use_container_width=True)

def show_backtest():
    """策略回测"""
    st.title("🎯 策略回测")
    
    st.sidebar.header("策略选择")

    # 构建策略列表
    base_strategies = ["双均线策略", "MACD策略", "RSI策略", "布林带策略"]
    indicator_strategies = ["KDJ策略", "CCI策略", "Williams %R策略", "ATR突破策略", "OBV策略"]
    saved_factors = _load_saved_factors()
    factor_strategies = [f"因子: {f['name']}" for f in saved_factors]
    all_strategies = base_strategies + indicator_strategies + factor_strategies

    strategy_name = st.sidebar.selectbox("选择策略", all_strategies)

    st.sidebar.subheader("策略参数")

    strategy_kwargs = {}
    
    if strategy_name == "双均线策略":
        fast_period = st.sidebar.slider("短期均线", 1, 60, 5)
        slow_period = st.sidebar.slider("长期均线", 5, 250, 20)
        strategy_kwargs = {'fast_period': fast_period, 'slow_period': slow_period}
        
        def strategy_func(df, **kwargs):
            df = df.copy()
            close_col = 'close' if 'close' in df.columns else '收盘'
            df['ma_fast'] = df[close_col].rolling(window=kwargs['fast_period'], min_periods=1).mean()
            df['ma_slow'] = df[close_col].rolling(window=kwargs['slow_period'], min_periods=1).mean()
            df['signal'] = 0
            cross_up = (df['ma_fast'] > df['ma_slow']) & (df['ma_fast'].shift(1) <= df['ma_slow'].shift(1))
            cross_down = (df['ma_fast'] < df['ma_slow']) & (df['ma_fast'].shift(1) >= df['ma_slow'].shift(1))
            df.loc[cross_up, 'signal'] = 1
            df.loc[cross_down, 'signal'] = -1
            return df
    
    elif strategy_name == "MACD策略":
        macd_fast = st.sidebar.slider("快线周期", 2, 50, 12)
        macd_slow = st.sidebar.slider("慢线周期", 5, 100, 26)
        macd_signal = st.sidebar.slider("信号线", 2, 30, 9)
        strategy_kwargs = {'fast': macd_fast, 'slow': macd_slow, 'signal': macd_signal}
        
        def strategy_func(df, **kwargs):
            df = df.copy()
            close_col = 'close' if 'close' in df.columns else '收盘'
            ema_f = df[close_col].ewm(span=kwargs['fast'], adjust=False).mean()
            ema_s = df[close_col].ewm(span=kwargs['slow'], adjust=False).mean()
            dif = ema_f - ema_s
            dea = dif.ewm(span=kwargs['signal'], adjust=False).mean()
            df['dif'] = dif
            df['dea'] = dea
            df['signal'] = 0
            cross_up = (dif > dea) & (dif.shift(1) <= dea.shift(1))
            cross_down = (dif < dea) & (dif.shift(1) >= dea.shift(1))
            df.loc[cross_up, 'signal'] = 1
            df.loc[cross_down, 'signal'] = -1
            return df
    
    elif strategy_name == "RSI策略":
        rsi_period = st.sidebar.slider("RSI周期", 2, 50, 14)
        rsi_oversold = st.sidebar.slider("超卖阈值", 5, 40, 30)
        rsi_overbought = st.sidebar.slider("超买阈值", 60, 95, 70)
        strategy_kwargs = {'period': rsi_period, 'oversold': rsi_oversold, 'overbought': rsi_overbought}
        
        def strategy_func(df, **kwargs):
            df = df.copy()
            close_col = 'close' if 'close' in df.columns else '收盘'
            delta = df[close_col].diff()
            gain = delta.where(delta > 0, 0.0).rolling(kwargs['period']).mean()
            loss = (-delta.where(delta < 0, 0.0)).rolling(kwargs['period']).mean()
            rs = gain / loss.replace(0, 1e-10)
            rsi = (100 - (100 / (1 + rs))).fillna(50)
            df['rsi'] = rsi
            df['signal'] = 0
            df.loc[rsi < kwargs['oversold'], 'signal'] = 1
            df.loc[rsi > kwargs['overbought'], 'signal'] = -1
            return df
    
    elif strategy_name == "布林带策略":
        boll_period = st.sidebar.slider("周期", 5, 60, 20)
        boll_std = st.sidebar.slider("标准差倍数", 1.0, 3.0, 2.0, step=0.1)
        strategy_kwargs = {'period': boll_period, 'std_dev': boll_std}
        
        def strategy_func(df, **kwargs):
            df = df.copy()
            close_col = 'close' if 'close' in df.columns else '收盘'
            mid = df[close_col].rolling(window=kwargs['period'], min_periods=1).mean()
            std = df[close_col].rolling(window=kwargs['period'], min_periods=1).std()
            upper = mid + kwargs['std_dev'] * std
            lower = mid - kwargs['std_dev'] * std
            df['bb_upper'] = upper
            df['bb_lower'] = lower
            df['signal'] = 0
            df.loc[df['low'] <= lower, 'signal'] = 1
            df.loc[df['high'] >= upper, 'signal'] = -1
            return df

    elif strategy_name == "KDJ策略":
        kdj_n = st.sidebar.slider("KDJ-N周期", 2, 30, 9, key="bt_kdj_n")
        kdj_m1 = st.sidebar.slider("KDJ-M1平滑", 2, 10, 3, key="bt_kdj_m1")
        kdj_m2 = st.sidebar.slider("KDJ-M2平滑", 2, 10, 3, key="bt_kdj_m2")
        kdj_oversold = st.sidebar.slider("超卖阈值 (买入)", 5, 40, 20, key="bt_kdj_os")
        kdj_overbought = st.sidebar.slider("超买阈值 (卖出)", 60, 95, 80, key="bt_kdj_ob")
        strategy_kwargs = {'n': kdj_n, 'm1': kdj_m1, 'm2': kdj_m2,
                           'oversold': kdj_oversold, 'overbought': kdj_overbought}

        def strategy_func(df, **kwargs):
            df = df.copy()
            from indicators.momentum import calc_kdj
            close_col = 'close' if 'close' in df.columns else '收盘'
            high_col = 'high' if 'high' in df.columns else '最高'
            low_col = 'low' if 'low' in df.columns else '最低'
            df, _ = calc_kdj(df, n=kwargs['n'], m1=kwargs['m1'], m2=kwargs['m2'],
                             high=high_col, low=low_col, close=close_col)
            df['signal'] = 0
            # J值超卖金叉买入，超买死叉卖出
            buy = (df['KDJ_J'] < kwargs['oversold']) | \
                  ((df['KDJ_K'] > df['KDJ_D']) & (df['KDJ_K'].shift(1) <= df['KDJ_D'].shift(1)))
            sell = (df['KDJ_J'] > kwargs['overbought']) | \
                   ((df['KDJ_K'] < df['KDJ_D']) & (df['KDJ_K'].shift(1) >= df['KDJ_D'].shift(1)))
            df.loc[buy, 'signal'] = 1
            df.loc[sell, 'signal'] = -1
            return df

    elif strategy_name == "CCI策略":
        cci_period = st.sidebar.slider("CCI周期", 2, 50, 14, key="bt_cci_p")
        cci_upper = st.sidebar.slider("超买阈值 (卖出)", 50, 200, 100, key="bt_cci_up")
        cci_lower = st.sidebar.slider("超卖阈值 (买入)", -200, -50, -100, key="bt_cci_dn")
        strategy_kwargs = {'period': cci_period, 'upper': cci_upper, 'lower': cci_lower}

        def strategy_func(df, **kwargs):
            df = df.copy()
            from indicators.momentum import calc_cci
            close_col = 'close' if 'close' in df.columns else '收盘'
            high_col = 'high' if 'high' in df.columns else '最高'
            low_col = 'low' if 'low' in df.columns else '最低'
            df, _ = calc_cci(df, period=kwargs['period'], high=high_col, low=low_col, close=close_col)
            key = f"CCI{kwargs['period']}"
            df['signal'] = 0
            # CCI从下穿越-100买入，从上穿越+100卖出
            buy = (df[key] > kwargs['lower']) & (df[key].shift(1) <= kwargs['lower'])
            sell = (df[key] < kwargs['upper']) & (df[key].shift(1) >= kwargs['upper'])
            df.loc[buy, 'signal'] = 1
            df.loc[sell, 'signal'] = -1
            return df

    elif strategy_name == "Williams %R策略":
        wr_period = st.sidebar.slider("WR周期", 2, 50, 14, key="bt_wr_p")
        wr_oversold = st.sidebar.slider("超卖阈值 (买入)", -100, -60, -80, key="bt_wr_os")
        wr_overbought = st.sidebar.slider("超买阈值 (卖出)", -40, 0, -20, key="bt_wr_ob")
        strategy_kwargs = {'period': wr_period, 'oversold': wr_oversold, 'overbought': wr_overbought}

        def strategy_func(df, **kwargs):
            df = df.copy()
            from indicators.momentum import calc_williams
            close_col = 'close' if 'close' in df.columns else '收盘'
            high_col = 'high' if 'high' in df.columns else '最高'
            low_col = 'low' if 'low' in df.columns else '最低'
            df, _ = calc_williams(df, period=kwargs['period'], high=high_col, low=low_col, close=close_col)
            key = f"WR{kwargs['period']}"
            df['signal'] = 0
            # WR从超卖区上穿买入，从超买区下穿卖出
            buy = (df[key] > kwargs['oversold']) & (df[key].shift(1) <= kwargs['oversold'])
            sell = (df[key] < kwargs['overbought']) & (df[key].shift(1) >= kwargs['overbought'])
            df.loc[buy, 'signal'] = 1
            df.loc[sell, 'signal'] = -1
            return df

    elif strategy_name == "ATR突破策略":
        atr_period = st.sidebar.slider("ATR周期", 2, 50, 14, key="bt_atr_p")
        atr_mult = st.sidebar.slider("突破倍数", 1.0, 5.0, 2.0, step=0.5, key="bt_atr_m")
        strategy_kwargs = {'period': atr_period, 'mult': atr_mult}

        def strategy_func(df, **kwargs):
            df = df.copy()
            from indicators.volatility import calc_atr
            close_col = 'close' if 'close' in df.columns else '收盘'
            high_col = 'high' if 'high' in df.columns else '最高'
            low_col = 'low' if 'low' in df.columns else '最低'
            df, _ = calc_atr(df, period=kwargs['period'], high=high_col, low=low_col, close=close_col)
            key = f"ATR{kwargs['period']}"
            # 价格突破前日收盘 + N倍ATR 买入，跌破前日收盘 - N倍ATR 卖出
            prev_close = df[close_col].shift(1)
            atr = df[key]
            df['signal'] = 0
            buy = df[close_col] > prev_close + kwargs['mult'] * atr
            sell = df[close_col] < prev_close - kwargs['mult'] * atr
            df.loc[buy, 'signal'] = 1
            df.loc[sell, 'signal'] = -1
            return df

    elif strategy_name == "OBV策略":
        obv_ma_period = st.sidebar.slider("OBV均线周期", 5, 60, 20, key="bt_obv_ma")
        strategy_kwargs = {'ma_period': obv_ma_period}

        def strategy_func(df, **kwargs):
            df = df.copy()
            from indicators.volume_ind import calc_obv
            close_col = 'close' if 'close' in df.columns else '收盘'
            vol_col = 'volume' if 'volume' in df.columns else '成交量'
            df, _ = calc_obv(df, close=close_col, volume=vol_col)
            if 'OBV' not in df.columns:
                df['signal'] = 0
                return df
            obv_ma = df['OBV'].rolling(window=kwargs['ma_period'], min_periods=1).mean()
            df['signal'] = 0
            # OBV上穿均线买入，下穿卖出
            buy = (df['OBV'] > obv_ma) & (df['OBV'].shift(1) <= obv_ma.shift(1))
            sell = (df['OBV'] < obv_ma) & (df['OBV'].shift(1) >= obv_ma.shift(1))
            df.loc[buy, 'signal'] = 1
            df.loc[sell, 'signal'] = -1
            return df

    elif strategy_name.startswith("因子: "):
        factor_name = strategy_name[4:]
        factor_data = next((f for f in saved_factors if f['name'] == factor_name), None)
        if factor_data:
            st.sidebar.code(factor_data['code'], language='python')
            st.sidebar.caption(f"IC: {factor_data.get('ic', 0):.4f} | Rank IC: {factor_data.get('rank_ic', 0):.4f}")
            factor_direction = st.sidebar.radio("因子方向", ["做多（因子值高买入）", "做空（因子值低买入）"], key="factor_dir")
            factor_top_pct = st.sidebar.slider("因子选股百分位", 5, 50, 20, step=5, help="买入因子值排名前/后N%时买入")
            factor_hold_days = st.sidebar.slider("持仓天数", 1, 60, 5)
            strategy_kwargs = {
                'factor_code': factor_data['code'],
                'go_long': factor_direction.startswith("做多"),
                'top_pct': factor_top_pct,
                'hold_days': factor_hold_days
            }

            def strategy_func(df, **kwargs):
                df = df.copy()
                exec(kwargs['factor_code'], {'df': df, 'np': np, 'pd': pd})
                if 'factor' not in df.columns:
                    df['signal'] = 0
                    return df
                factor = df['factor']
                threshold_high = factor.quantile(1 - kwargs['top_pct'] / 100)
                threshold_low = factor.quantile(kwargs['top_pct'] / 100)
                df['signal'] = 0
                if kwargs['go_long']:
                    df.loc[factor >= threshold_high, 'signal'] = 1
                else:
                    df.loc[factor <= threshold_low, 'signal'] = 1
                # 持仓天数后卖出
                hold = kwargs['hold_days']
                buy_signals = df.index[df['signal'] == 1].tolist()
                for idx in buy_signals:
                    sell_idx = idx + hold
                    if sell_idx < len(df):
                        df.iloc[sell_idx, df.columns.get_loc('signal')] = -1
                return df
        else:
            def strategy_func(df, **kwargs):
                df = df.copy()
                df['signal'] = 0
                return df

    st.sidebar.header("回测参数")
    initial_capital = st.sidebar.number_input("初始资金", 10000, 100000000, 100000, step=10000)
    
    st.sidebar.subheader("交易成本")
    commission = st.sidebar.number_input("佣金费率", 0.0, 0.003, 0.0003, format="%.4f")
    stamp_tax = st.sidebar.number_input("印花税(卖)", 0.0, 0.003, 0.001, format="%.4f")
    slippage = st.sidebar.number_input("滑点", 0.0, 0.01, 0.0, format="%.4f")
    
    st.sidebar.subheader("日期范围")
    col1, col2 = st.sidebar.columns(2)
    with col1:
        start_date = st.date_input("开始日期", datetime.now() - timedelta(days=730))
    with col2:
        end_date = st.date_input("结束日期", datetime.now())
    
    stocks = get_available_stocks()
    if not stocks:
        st.warning("未找到数据文件")
        return
    
    stock_options = [f"{code} {name}" for code, name, _ in stocks]
    selected_idx = st.selectbox("选择股票", range(len(stocks)), format_func=lambda i: stock_options[i])
    code, name, filepath = stocks[selected_idx]
    
    if st.button("🚀 运行回测", type="primary"):
        with st.spinner("正在运行回测..."):
            df = read_csv(filepath)
            if df is None or df.empty:
                st.error("无法读取数据")
                return
            
            sd = pd.Timestamp(start_date)
            ed = pd.Timestamp(end_date)
            date_col = 'date' if 'date' in df.columns else '日期'
            df = df[(df[date_col] >= sd) & (df[date_col] <= ed)].copy()
            
            if len(df) < 30:
                st.error("数据太少，无法回测")
                return
            
            df = strategy_func(df, **strategy_kwargs)
            
            # 回测引擎
            close_col = 'close' if 'close' in df.columns else '收盘'
            open_col = 'open' if 'open' in df.columns else '开盘'
            
            n = len(df)
            cash = initial_capital
            shares = 0
            equity_curve = np.zeros(n)
            trade_list = []
            
            for i in range(n):
                price = df[close_col].iloc[i]
                sig = df['signal'].iloc[i]
                
                next_open = df[open_col].iloc[i + 1] if i < n - 1 else price
                
                if sig == 1 and i < n - 1 and shares == 0 and cash > 0:
                    exec_price = next_open * (1 + slippage)
                    max_shares = int(cash / (exec_price * (1 + commission)) / 100) * 100
                    if max_shares > 0:
                        cost = max_shares * exec_price
                        comm = cost * commission
                        cash -= cost + comm
                        shares = max_shares
                        trade_list.append({
                            'buy_date': df[date_col].iloc[i + 1],
                            'buy_price': exec_price,
                            'shares': max_shares,
                        })
                
                elif sig == -1 and i < n - 1 and shares > 0:
                    exec_price = next_open * (1 - slippage)
                    revenue = shares * exec_price
                    comm = revenue * commission
                    tax = revenue * stamp_tax
                    cash += revenue - comm - tax
                    trade_list[-1]['sell_date'] = df[date_col].iloc[i + 1]
                    trade_list[-1]['sell_price'] = exec_price
                    ret = (exec_price - trade_list[-1]['buy_price']) / trade_list[-1]['buy_price']
                    trade_list[-1]['return_pct'] = ret
                    shares = 0
                
                equity_curve[i] = cash + shares * price

            # 回测结束时强制平仓
            if shares > 0:
                last_price = df[close_col].iloc[-1]
                revenue = shares * last_price
                comm = revenue * commission
                tax = revenue * stamp_tax
                cash += revenue - comm - tax
                if trade_list and 'sell_date' not in trade_list[-1]:
                    trade_list[-1]['sell_date'] = df[date_col].iloc[-1]
                    trade_list[-1]['sell_price'] = last_price
                    ret = (last_price - trade_list[-1]['buy_price']) / trade_list[-1]['buy_price']
                    trade_list[-1]['return_pct'] = ret
                    trade_list[-1]['forced_close'] = True
                shares = 0
                equity_curve[-1] = cash

            equity_curve = pd.Series(equity_curve, index=df[date_col])
            
            # 计算基准收益（简单持有）
            first_price = df[close_col].iloc[0]
            benchmark = initial_capital * (df[close_col] / first_price)
            
            # 计算完整指标
            metrics = calculate_metrics(equity_curve, benchmark, trade_list, initial_capital, df)
            
            # 保存结果
            st.session_state['bt_equity'] = equity_curve
            st.session_state['bt_benchmark'] = benchmark
            st.session_state['bt_trades'] = trade_list
            st.session_state['bt_metrics'] = metrics
            st.session_state['bt_df'] = df
            st.session_state['bt_code'] = f"{code} {name}"
            
            st.success("回测完成！")
    
    # 显示结果
    if 'bt_metrics' in st.session_state:
        metrics = st.session_state['bt_metrics']
        equity_curve = st.session_state['bt_equity']
        benchmark = st.session_state['bt_benchmark']
        
        st.subheader(f"📊 回测结果 - {st.session_state.get('bt_code', '')}")
        
        # 基本指标
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("总收益率", f"{metrics['总收益率']:.2%}")
        with col2:
            st.metric("年化收益率", f"{metrics['年化收益率']:.2%}")
        with col3:
            st.metric("最大回撤", f"{metrics['最大回撤']:.2%}", delta_color="inverse")
        with col4:
            st.metric("夏普比率", f"{metrics['夏普比率']:.2f}")
        
        # 高级指标
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Alpha", f"{metrics['Alpha']:.4f}")
        with col2:
            st.metric("Beta", f"{metrics['Beta']:.4f}")
        with col3:
            st.metric("信息比率", f"{metrics['信息比率']:.4f}")
        with col4:
            st.metric("卡玛比率", f"{metrics['卡玛比率']:.4f}")
        
        # 更多指标
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("胜率", f"{metrics['胜率']:.2%}")
        with col2:
            st.metric("盈亏比", f"{metrics['盈亏比']:.2f}")
        with col3:
            st.metric("交易次数", metrics['交易次数'])
        with col4:
            st.metric("波动率", f"{metrics['波动率']:.2%}")
        
        # 图表
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
        
        dates = equity_curve.index.strftime('%Y-%m-%d').tolist()
        
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            row_heights=[3, 1],
            vertical_spacing=0.1
        )
        
        # 策略净值
        fig.add_trace(
            go.Scatter(x=dates, y=equity_curve.values, name='策略净值', 
                      line=dict(color='#00d4ff', width=1.5)),
            row=1, col=1
        )
        
        # 基准净值
        fig.add_trace(
            go.Scatter(x=dates, y=benchmark.values, name='买入持有', 
                      line=dict(color='#888', width=1, dash='dash')),
            row=1, col=1
        )
        
        # 回撤
        cummax = equity_curve.cummax()
        drawdown = (equity_curve - cummax) / cummax * 100
        fig.add_trace(
            go.Scatter(x=dates, y=drawdown.values, name='回撤', 
                      fill='tozeroy', line=dict(color='#ef5350', width=0.5)),
            row=2, col=1
        )
        
        fig.update_layout(
            height=500,
            xaxis_rangeslider_visible=False,
            showlegend=True
        )
        fig.update_yaxes(title_text="净值", row=1, col=1)
        fig.update_yaxes(title_text="回撤(%)", row=2, col=1)
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 交易记录
        trade_list = st.session_state.get('bt_trades', [])
        completed_trades = [t for t in trade_list if 'sell_date' in t and t['sell_date'] is not None]
        if completed_trades:
            st.subheader("📋 交易记录")
            trade_df = pd.DataFrame(completed_trades)
            trade_df['买入日期'] = pd.to_datetime(trade_df['buy_date']).dt.strftime('%Y-%m-%d')
            trade_df['卖出日期'] = pd.to_datetime(trade_df['sell_date']).dt.strftime('%Y-%m-%d')
            trade_df['买入价'] = trade_df['buy_price'].apply(lambda x: f"{x:.2f}")
            trade_df['卖出价'] = trade_df['sell_price'].apply(lambda x: f"{x:.2f}")
            trade_df['收益率'] = trade_df['return_pct'].apply(lambda x: f"{x:.2%}")
            trade_df['备注'] = trade_df.apply(lambda r: '期末平仓' if r.get('forced_close') else '', axis=1)
            st.dataframe(trade_df[['买入日期', '卖出日期', '买入价', '卖出价', '收益率', '备注']], use_container_width=True)


def calculate_metrics(equity_curve, benchmark, trade_list, initial_capital, df):
    """计算完整的回测指标"""
    close_col = 'close' if 'close' in df.columns else '收盘'
    date_col = 'date' if 'date' in df.columns else '日期'
    
    # 基本指标
    final_value = equity_curve.iloc[-1]
    total_return = (final_value / initial_capital - 1) if initial_capital > 0 else 0
    
    days = (df[date_col].iloc[-1] - df[date_col].iloc[0]).days
    years = max(days / 365.0, 1/365)
    annual_return = (final_value / initial_capital) ** (1 / years) - 1 if initial_capital > 0 else 0
    
    cummax = equity_curve.cummax()
    drawdown = (equity_curve - cummax) / cummax
    max_drawdown = drawdown.min() if len(drawdown) > 0 else 0
    
    # 日收益率
    daily_returns = equity_curve.pct_change().dropna()
    benchmark_returns = benchmark.pct_change().dropna()
    
    # 年化波动率
    volatility = daily_returns.std() * np.sqrt(252) if len(daily_returns) > 0 else 0
    
    # 夏普比率 (假设无风险利率3%)
    risk_free = 0.03
    excess_returns = daily_returns - risk_free / 252
    sharpe = (excess_returns.mean() / excess_returns.std() * np.sqrt(252)) if excess_returns.std() > 0 else 0
    
    # Alpha & Beta
    if len(daily_returns) > 0 and len(benchmark_returns) > 0:
        min_len = min(len(daily_returns), len(benchmark_returns))
        strategy_ret = daily_returns.iloc[:min_len].values
        benchmark_ret = benchmark_returns.iloc[:min_len].values
        
        # 计算Beta
        covariance = np.cov(strategy_ret, benchmark_ret)[0][1]
        benchmark_var = np.var(benchmark_ret)
        beta = covariance / benchmark_var if benchmark_var > 0 else 1.0
        
        # 计算Alpha
        alpha = annual_return - risk_free - beta * (benchmark.iloc[-1] / benchmark.iloc[0] - 1 - risk_free)
    else:
        beta = 1.0
        alpha = 0.0
    
    # 信息比率 (相对于基准)
    diff_returns = daily_returns - benchmark_returns.iloc[:len(daily_returns)]
    info_ratio = (diff_returns.mean() / diff_returns.std() * np.sqrt(252)) if diff_returns.std() > 0 else 0
    
    # 卡玛比率 (年化收益/最大回撤)
    calmar = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0
    
    # 胜率
    completed = [t for t in trade_list if 'return_pct' in t and t['return_pct'] is not None]
    wins = [t for t in completed if t['return_pct'] > 0]
    total_trades = len(completed)
    win_rate = len(wins) / total_trades if total_trades > 0 else 0
    
    # 盈亏比
    avg_win = np.mean([t['return_pct'] for t in wins]) if wins else 0
    losses = [t for t in completed if t['return_pct'] <= 0]
    avg_loss = abs(np.mean([t['return_pct'] for t in losses])) if losses else 0
    profit_ratio = avg_win / avg_loss if avg_loss > 0 else 0
    
    return {
        '总收益率': total_return,
        '年化收益率': annual_return,
        '最大回撤': max_drawdown,
        '夏普比率': sharpe,
        'Alpha': alpha,
        'Beta': beta,
        '信息比率': info_ratio,
        '卡玛比率': calmar,
        '波动率': volatility,
        '胜率': win_rate,
        '盈亏比': profit_ratio,
        '交易次数': total_trades,
    }

# ==================== 主入口 ====================

def show_market_sense():
    """盘感锻炼小游戏"""
    st.markdown("随机展示一段季度级别K线（约60个交易日），请判断未来20个交易日的涨跌方向！")
    
    if 'ms_total' not in st.session_state:
        st.session_state.ms_total = 0
        st.session_state.ms_correct = 0
        st.session_state.ms_current_df = None
        st.session_state.ms_future_df = None
        st.session_state.ms_answered = False
        st.session_state.ms_current_code = ""
        st.session_state.ms_current_name = ""
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("总题数", st.session_state.ms_total)
    with col2:
        st.metric("正确", st.session_state.ms_correct)
    with col3:
        accuracy = (st.session_state.ms_correct / st.session_state.ms_total * 100) if st.session_state.ms_total > 0 else 0
        st.metric("正确率", f"{accuracy:.0f}%")
    
    stocks = get_available_stocks()
    if not stocks:
        st.warning("未找到数据文件")
        return
    
    QUARTER_DAYS = 60
    FUTURE_DAYS = 10
    MIN_ROWS = QUARTER_DAYS + FUTURE_DAYS + 30
    
    if st.button("🎲 下一题", type="primary", key="ms_next"):
        random.shuffle(stocks)

        for code, name, filepath in stocks:
            df = read_csv(filepath)
            if df is None or len(df) < MIN_ROWS:
                continue

            max_start = len(df) - QUARTER_DAYS - FUTURE_DAYS
            start_idx = random.randint(0, max_start)
            end_visible = start_idx + QUARTER_DAYS
            end_future = end_visible + FUTURE_DAYS
            
            st.session_state.ms_current_df = df.iloc[start_idx:end_visible].copy().reset_index(drop=True)
            st.session_state.ms_future_df = df.iloc[end_visible:end_future].copy().reset_index(drop=True)
            st.session_state.ms_current_code = code
            st.session_state.ms_current_name = name
            st.session_state.ms_answered = False
            break
    
    if st.session_state.ms_current_df is not None:
        df_vis = st.session_state.ms_current_df
        df_fut = st.session_state.ms_future_df
        
        st.info(f"展示区间: {df_vis['date'].iloc[0].strftime('%Y-%m-%d')} ~ {df_vis['date'].iloc[-1].strftime('%Y-%m-%d')}  |  共 {len(df_vis)} 根K线")
        
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        color_up = '#ef5350'
        color_down = '#26a69a'
        dates_vis = df_vis['date'].dt.strftime('%m-%d').tolist()

        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            row_heights=[3, 1],
            vertical_spacing=0.05
        )
        fig.add_trace(
            go.Candlestick(
                x=dates_vis,
                open=df_vis['open'],
                high=df_vis['high'],
                low=df_vis['low'],
                close=df_vis['close'],
                name='K线',
                increasing_line_color=color_up,
                decreasing_line_color=color_down
            ),
            row=1, col=1
        )

        # 成交量
        vol_col = 'volume' if 'volume' in df_vis.columns else '成交量'
        if vol_col in df_vis.columns:
            colors = [color_up if df_vis['close'].iloc[i] >= df_vis['open'].iloc[i] else color_down for i in range(len(df_vis))]
            fig.add_trace(
                go.Bar(x=dates_vis, y=df_vis[vol_col], name='成交量', marker_color=colors, opacity=0.8),
                row=2, col=1
            )

        fig.update_layout(
            height=450,
            xaxis_rangeslider_visible=False,
            xaxis_type='category',
            xaxis2_type='category',
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)

        if not st.session_state.ms_answered:
            col1, col2, col3 = st.columns([1, 1, 1])
            with col1:
                if st.button("🔺 看涨", type="secondary", use_container_width=True, key="ms_up"):
                    _check_answer(True)
            with col3:
                if st.button("🔻 看跌", type="secondary", use_container_width=True, key="ms_down"):
                    _check_answer(False)
        else:
            _show_result()

def _check_answer(user_says_up):
    """检查答案"""
    st.session_state.ms_answered = True
    st.session_state.ms_total += 1
    
    df_vis = st.session_state.ms_current_df
    df_fut = st.session_state.ms_future_df
    
    last_close = df_vis['close'].iloc[-1]
    future_close = df_fut['close'].iloc[-1]
    change = future_close - last_close
    actual_up = change >= 0
    
    if user_says_up == actual_up:
        st.session_state.ms_correct += 1

def _show_result():
    """显示结果"""
    df_vis = st.session_state.ms_current_df
    df_fut = st.session_state.ms_future_df
    
    last_close = df_vis['close'].iloc[-1]
    future_close = df_fut['close'].iloc[-1]
    change = future_close - last_close
    change_pct = (change / last_close) * 100
    actual_up = change >= 0
    
    direction = "上涨" if actual_up else "下跌"
    direction_emoji = "📈" if actual_up else "📉"
    
    future_high = df_fut['high'].max()
    future_low = df_fut['low'].min()
    max_up_pct = (future_high - last_close) / last_close * 100
    max_down_pct = (future_low - last_close) / last_close * 100
    
    st.success(f"{direction_emoji} 标的: {st.session_state.ms_current_code} {st.session_state.ms_current_name}")
    st.info(f"未来20日收盘价: **{direction} {abs(change_pct):.2f}%**  ({last_close:.2f} → {future_close:.2f})")
    st.caption(f"期间最高涨 {max_up_pct:+.2f}%  |  最大跌 {max_down_pct:+.2f}%")
    
    # 展示完整K线
    import plotly.graph_objects as go
    
    df_all = pd.concat([df_vis, df_fut], ignore_index=True)
    
    color_up = '#ef5350'
    color_down = '#26a69a'
    dates_all = df_all['date'].dt.strftime('%m-%d').tolist()
    
    fig = go.Figure()
    fig.add_trace(
        go.Candlestick(
            x=dates_all,
            open=df_all['open'],
            high=df_all['high'],
            low=df_all['low'],
            close=df_all['close'],
            name='K线',
            increasing_line_color=color_up,
            decreasing_line_color=color_down
        )
    )
    
    # 添加预测分界线（使用竖线）
    split_idx = len(df_vis)
    if split_idx > 0 and split_idx < len(dates_all):
        fig.add_vline(
            x=split_idx - 0.5,
            line_dash='dash',
            line_color='#ffeb3b',
            line_width=2
        )
    
    fig.update_layout(
        height=400,
        xaxis_rangeslider_visible=False,
        xaxis_type='category',
        showlegend=False,
        annotations=[
            dict(
                x=split_idx - 0.5,
                y=1,
                xref='x',
                yref='paper',
                text='预测分界线',
                showarrow=False,
                font=dict(color='#ffeb3b', size=10)
            )
        ]
    )
    st.plotly_chart(fig, use_container_width=True)

def show_history_game():
    """历史事件猜涨跌小游戏"""
    st.markdown("根据历史事件，猜猜当天大盘是涨还是跌！")
    
    # 历史事件数据
    historical_events = [
        {"date": "2020-02-03", "event": "新冠疫情爆发，春节后首个交易日", "up": False},
        {"date": "2020-07-06", "event": "A股大涨，两市成交额破1.5万亿", "up": True},
        {"date": "2021-02-18", "event": "茅台股价突破2600元", "up": True},
        {"date": "2022-04-27", "event": "上证指数跌破2900点", "up": False},
        {"date": "2022-11-01", "event": "防疫政策优化，股市大涨", "up": True},
        {"date": "2023-10-24", "event": "中央金融工作会议召开", "up": True},
        {"date": "2024-02-01", "event": "A股全面实行注册制", "up": False},
        {"date": "2024-09-24", "event": "央行降准0.5个百分点", "up": True},
        {"date": "2015-06-15", "event": "股灾开始，千股跌停", "up": False},
        {"date": "2019-02-25", "event": "A股暴涨，券商股全线涨停", "up": True},
    ]
    
    if 'hg_total' not in st.session_state:
        st.session_state.hg_total = 0
        st.session_state.hg_correct = 0
        st.session_state.hg_current_event = None
        st.session_state.hg_answered = False
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("总题数", st.session_state.hg_total)
    with col2:
        st.metric("正确", st.session_state.hg_correct)
    with col3:
        accuracy = (st.session_state.hg_correct / st.session_state.hg_total * 100) if st.session_state.hg_total > 0 else 0
        st.metric("正确率", f"{accuracy:.0f}%")
    
    if st.button("🎲 下一题", type="primary", key="hg_next"):
        st.session_state.hg_current_event = random.choice(historical_events)
        st.session_state.hg_answered = False
    
    if st.session_state.hg_current_event is not None:
        event = st.session_state.hg_current_event
        
        st.subheader(f"📅 {event['date']}")
        st.info(f"**事件**: {event['event']}")
        
        if not st.session_state.hg_answered:
            col1, col2, col3 = st.columns([1, 1, 1])
            with col1:
                if st.button("📈 看涨", type="secondary", use_container_width=True, key="hg_up"):
                    _check_history_answer(True, event['up'])
            with col3:
                if st.button("📉 看跌", type="secondary", use_container_width=True, key="hg_down"):
                    _check_history_answer(False, event['up'])
        else:
            _show_history_result(event['up'])

def _check_history_answer(user_says_up, actual_up):
    """检查历史事件答案"""
    st.session_state.hg_answered = True
    st.session_state.hg_total += 1
    if user_says_up == actual_up:
        st.session_state.hg_correct += 1

def _show_history_result(actual_up):
    """显示历史事件结果"""
    direction = "上涨" if actual_up else "下跌"
    direction_emoji = "📈" if actual_up else "📉"
    
    is_correct = False
    if 'hg_current_event' in st.session_state:
        # 这里简化处理，实际应该记录用户的选择
        pass
    
    st.success(f"{direction_emoji} 当天大盘: **{direction}**")

# ==================== 量化因子开发 ====================

def show_factor_development():
    """量化因子开发工具"""
    st.title("🔬 量化因子开发")
    st.markdown("创建、回测自定义因子，验证因子有效性")
    
    # 预定义因子模板
    factor_templates = {
        "自定义": "",
        "ROE因子": "df['factor'] = df['净利润'] / df['股东权益']",
        "毛利率因子": "df['factor'] = df['毛利率']",
        "营收增长率": "df['factor'] = df['营业收入'].pct_change(periods=4)",
        "价格动量": "df['factor'] = df['close'].pct_change(periods=20)",
        "波动率": "df['factor'] = df['close'].rolling(20).std() / df['close'].rolling(20).mean()",
        "成交量动量": "df['factor'] = df['volume'].pct_change(periods=5)",
        "换手率": "df['factor'] = df['volume'].rolling(20).mean() / df['volume'].rolling(60).mean()",
    }
    
    # 已保存因子
    saved = _load_saved_factors()
    if saved:
        st.sidebar.header("已保存因子")
        for sf in saved:
            with st.sidebar.expander(f"📌 {sf['name']}"):
                st.code(sf['code'], language='python')
                st.caption(f"IC: {sf.get('ic', 0):.4f} | Rank IC: {sf.get('rank_ic', 0):.4f}")
                st.caption(f"保存于: {sf.get('created', '未知')}")
                if st.button(f"🗑️ 删除", key=f"del_{sf['name']}"):
                    fpath = os.path.join(FACTOR_DIR, f"{sf['name']}.json")
                    if os.path.exists(fpath):
                        os.remove(fpath)
                        st.rerun()

    st.sidebar.header("因子设置")
    selected_template = st.sidebar.selectbox("选择因子模板", list(factor_templates.keys()))
    
    custom_code = st.sidebar.text_area(
        "因子公式 (Python)",
        value=factor_templates[selected_template],
        height=150,
        help="使用 df['列名'] 访问数据列，创建 df['factor'] 列"
    )
    
    # 数据选择
    stocks = get_available_stocks()
    if not stocks:
        st.warning("未找到数据文件")
        return
    
    stock_options = [f"{code} {name}" for code, name, _ in stocks]
    selected_idx = st.selectbox("选择股票", range(len(stocks)), format_func=lambda i: stock_options[i])
    code, name, filepath = stocks[selected_idx]
    
    # 日期范围
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("开始日期", datetime.now() - timedelta(days=365))
    with col2:
        end_date = st.date_input("结束日期", datetime.now())
    
    if custom_code and st.button("🔬 计算因子", type="primary"):
        with st.spinner("正在计算因子..."):
            df = read_csv(filepath)
            if df is None:
                st.error("无法读取数据")
                return
            
            sd = pd.Timestamp(start_date)
            ed = pd.Timestamp(end_date)
            date_col = 'date' if 'date' in df.columns else '日期'
            df = df[(df[date_col] >= sd) & (df[date_col] <= ed)].copy()
            
            if len(df) < 30:
                st.error("数据太少")
                return
            
            # 执行因子计算
            try:
                close_col = 'close' if 'close' in df.columns else '收盘'
                high_col = 'high' if 'high' in df.columns else '最高'
                low_col = 'low' if 'low' in df.columns else '最低'
                open_col = 'open' if 'open' in df.columns else '开盘'
                volume_col = 'volume' if 'volume' in df.columns else '成交量'
                
                exec(custom_code, {'df': df, 'np': np, 'pd': pd})
                
                if 'factor' not in df.columns:
                    st.error("未创建 df['factor'] 列，请检查公式")
                    return
                
                # 因子分析
                factor = df['factor'].dropna()
                
                # 未来收益
                future_return = df[close_col].shift(-5) / df[close_col] - 1
                future_return = future_return.dropna()
                
                # 因子与未来收益的相关性
                valid_idx = factor.index.intersection(future_return.index)
                if len(valid_idx) > 10:
                    ic = np.corrcoef(factor.loc[valid_idx], future_return.loc[valid_idx])[0][1]
                    rank_ic = spearmanr(factor.loc[valid_idx], future_return.loc[valid_idx])
                else:
                    ic = 0
                    rank_ic = 0
                
                # 分组回测
                n_groups = 5
                df_analysis = pd.DataFrame({
                    'factor': factor,
                    'future_return': future_return.reindex(factor.index)
                }).dropna()
                
                if len(df_analysis) > n_groups:
                    df_analysis['group'] = pd.qcut(df_analysis['factor'], n_groups, labels=False, duplicates='drop')
                    group_returns = df_analysis.groupby('group')['future_return'].mean()
                else:
                    group_returns = pd.Series([0])
                
                # 保存结果
                st.session_state['factor_df'] = df
                st.session_state['factor_ic'] = ic
                st.session_state['factor_rank_ic'] = rank_ic
                st.session_state['factor_name'] = selected_template if selected_template != "自定义" else "自定义因子"
                st.session_state['factor_groups'] = group_returns
                st.session_state['factor_code'] = custom_code

                st.success("因子计算完成！")
                
            except Exception as e:
                st.error(f"因子计算失败: {e}")
    
    # 显示结果
    if 'factor_df' in st.session_state:
        df = st.session_state['factor_df']
        
        st.subheader(f"📊 因子分析结果 - {st.session_state.get('factor_name', '因子')}")
        
        # IC指标
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("IC (线性相关)", f"{st.session_state.get('factor_ic', 0):.4f}")
        with col2:
            st.metric("Rank IC (秩相关)", f"{st.session_state.get('factor_rank_ic', 0):.4f}")
        with col3:
            ic_abs = abs(st.session_state.get('factor_ic', 0))
            quality = "优秀" if ic_abs > 0.05 else "一般" if ic_abs > 0.02 else "较弱"
            st.metric("因子质量", quality)

        # 操作按钮
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            if st.button("📈 生成做多因子、做空因子策略"):
                _generate_factor_strategy(st.session_state.get('factor_groups', pd.Series()))
        with btn_col2:
            factor_save_name = st.text_input("因子名称", value=st.session_state.get('factor_name', '自定义因子'), key="factor_save_name")
            if st.button("💾 保存因子", key="save_factor_btn"):
                _save_factor(factor_save_name, st.session_state.get('factor_code', ''),
                            st.session_state.get('factor_ic', 0),
                            st.session_state.get('factor_rank_ic', 0))
        
        # 因子图表
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
        
        date_col = 'date' if 'date' in df.columns else '日期'
        close_col = 'close' if 'close' in df.columns else '收盘'
        factor = df['factor'].dropna()
        
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            row_heights=[2, 1],
            vertical_spacing=0.1
        )
        
        dates = df[date_col].dt.strftime('%Y-%m-%d').tolist()
        
        # 因子值
        fig.add_trace(
            go.Scatter(
                x=dates, 
                y=df['factor'], 
                name='因子值',
                line=dict(color='yellow', width=1)
            ),
            row=1, col=1
        )
        
        # 归一化因子 (z-score)
        if factor.std() > 0:
            z_score = (factor - factor.mean()) / factor.std()
            fig.add_trace(
                go.Scatter(
                    x=dates[:len(z_score)],
                    y=z_score,
                    name='Z-Score',
                    line=dict(color='purple', width=1)
                ),
                row=1, col=1
            )
        
        # 收盘价
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=df[close_col],
                name='收盘价',
                line=dict(color='gray', width=1),
                opacity=0.5
            ),
            row=2, col=1
        )
        
        fig.update_layout(
            height=500,
            xaxis_rangeslider_visible=False,
            showlegend=True
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 分组收益
        if 'factor_groups' in st.session_state:
            groups = st.session_state['factor_groups']
            if len(groups) > 0:
                st.subheader("📊 分组回测")
                
                fig2 = go.Figure()
                colors = ['#ef5350', '#ff9800', '#ffeb3b', '#4caf50', '#2196f3']
                
                for i, (group, ret) in enumerate(groups.items()):
                    fig2.add_trace(go.Bar(
                        x=[f'第{group+1}组'],
                        y=[ret * 100],
                        name=f'第{group+1}组',
                        marker_color=colors[i % len(colors)]
                    ))
                
                fig2.update_layout(
                    height=300,
                    yaxis_title='平均收益(%)',
                    showlegend=False
                )
                st.plotly_chart(fig2, use_container_width=True)
                
                # 多空组合
                if len(groups) >= 2:
                    long_short = groups.iloc[-1] - groups.iloc[0]
                    st.metric("多空组合收益", f"{long_short*100:.2f}%", 
                             delta_color="normal" if long_short > 0 else "inverse")

def spearmanr(x, y):
    """计算Spearman秩相关系数"""
    from scipy import stats
    return stats.spearmanr(x, y)[0]

FACTOR_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config', 'factors')

def _save_factor(name, code, ic, rank_ic):
    """保存因子到文件"""
    os.makedirs(FACTOR_DIR, exist_ok=True)
    safe_name = name.replace('/', '_').replace('\\', '_').strip()
    if not safe_name:
        st.error("因子名称不能为空")
        return
    filepath = os.path.join(FACTOR_DIR, f"{safe_name}.json")
    data = {
        'name': safe_name,
        'code': code,
        'ic': ic,
        'rank_ic': rank_ic,
        'created': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    st.success(f"因子「{safe_name}」已保存！可在策略回测中使用。")

def _load_saved_factors():
    """加载所有已保存的因子"""
    if not os.path.exists(FACTOR_DIR):
        return []
    factors = []
    for fname in sorted(os.listdir(FACTOR_DIR)):
        if fname.endswith('.json'):
            filepath = os.path.join(FACTOR_DIR, fname)
            with open(filepath, 'r', encoding='utf-8') as f:
                factors.append(json.load(f))
    return factors

def _generate_factor_strategy(groups):
    """生成因子策略"""
    st.info("因子策略已生成！请前往「策略回测」使用。")
    st.markdown("""
    **做多因子策略**: 买入因子值最高的股票
    **做空因子策略**: 买入因子值最低的股票

    提示: 如果 Rank IC > 0，说明因子与未来收益正相关（因子越大越好）
         如果 Rank IC < 0，说明因子与未来收益负相关（因子越小越好）
    """)

def show_mini_games():
    """小游戏合集页面"""
    st.title("🎮 小游戏合集")

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "🎮 盘感锻炼", "📜 历史事件", "📊 成交量异常",
        "🚀 突破新高", "➕ 均线金叉", "⬜ 跳空缺口"
    ])

    with tab1:
        show_market_sense()
    with tab2:
        show_history_game()
    with tab3:
        show_volume_game()
    with tab4:
        show_breakout_game()
    with tab5:
        show_ma_cross_game()
    with tab6:
        show_gap_game()

def main():
    """主函数"""
    page = st.sidebar.radio(
        "导航",
        ["🏠 首页", "📈 数据浏览", "🎯 策略回测", "🔬 因子开发", "🎮 小游戏"]
    )

    if page == "🏠 首页":
        show_home()
    elif page == "📈 数据浏览":
        show_data_explorer()
    elif page == "🎯 策略回测":
        show_backtest()
    elif page == "🔬 因子开发":
        show_factor_development()
    elif page == "🎮 小游戏":
        show_mini_games()

def show_volume_game():
    """成交量异常猜涨跌小游戏"""
    st.markdown("观察某天的成交量异常放大/萎缩，猜猜第二天是涨还是跌！")
    
    if 'vg_total' not in st.session_state:
        st.session_state.vg_total = 0
        st.session_state.vg_correct = 0
        st.session_state.vg_current_data = None
        st.session_state.vg_answered = False
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("总题数", st.session_state.vg_total)
    with col2:
        st.metric("正确", st.session_state.vg_correct)
    with col3:
        accuracy = (st.session_state.vg_correct / st.session_state.vg_total * 100) if st.session_state.vg_total > 0 else 0
        st.metric("正确率", f"{accuracy:.0f}%")
    
    stocks = get_available_stocks()
    if not stocks:
        st.warning("未找到数据文件")
        return
    
    MIN_ROWS = 30
    
    if st.button("🎲 下一题", type="primary", key="vg_next"):
        random.shuffle(stocks)

        for code, name, filepath in stocks:
            df = read_csv(filepath)
            if df is None or len(df) < MIN_ROWS:
                continue

            # 找到成交量异常的日子（比平均高50%以上）
            if 'volume' not in df.columns:
                continue
                
            avg_vol = df['volume'].rolling(20).mean()
            abnormal_idx = []
            for i in range(20, len(df) - 1):
                if df['volume'].iloc[i] > avg_vol.iloc[i] * 1.5:
                    abnormal_idx.append(i)
            
            if not abnormal_idx:
                continue
            
            idx = random.choice(abnormal_idx)
            
            # 展示异常日的K线和前后几天的成交量
            start_idx = max(0, idx - 25)
            end_idx = min(len(df), idx + 5)
            
            st.session_state.vg_current_data = {
                'df': df.iloc[start_idx:end_idx].copy().reset_index(drop=True),
                'abnormal_idx': idx - start_idx,
                'code': code,
                'name': name,
                'actual_up': df['close'].iloc[idx + 1] > df['close'].iloc[idx] if idx + 1 < len(df) else False
            }
            st.session_state.vg_answered = False
            break
    
    if st.session_state.vg_current_data is not None:
        data = st.session_state.vg_current_data
        df = data['df']
        abnormal_idx = data['abnormal_idx']
        
        vol_col = 'volume' if 'volume' in df.columns else '成交量'
        
        st.subheader(f"股票: {data['code']} {data['name']}")
        st.info(f"📊 观察箭头指向的那根K线，成交量明显放大，猜猜第二天走势！")
        
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
        
        dates = df['date'].dt.strftime('%m-%d').tolist()
        
        # 创建K线和成交量子图
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            row_heights=[3, 1],
            vertical_spacing=0.1
        )
        
        color_up = '#ef5350'
        color_down = '#26a69a'
        
        # K线
        fig.add_trace(
            go.Candlestick(
                x=dates,
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                name='K线',
                increasing_line_color=color_up,
                decreasing_line_color=color_down
            ),
            row=1, col=1
        )
        
        # 成交量
        colors = [color_up if df['close'].iloc[i] >= df['open'].iloc[i] else color_down for i in range(len(df))]
        fig.add_trace(
            go.Bar(x=dates, y=df[vol_col], name='成交量', marker_color=colors, opacity=0.8),
            row=2, col=1
        )
        
        # 标记异常K线
        if abnormal_idx < len(dates):
            fig.add_annotation(
                x=dates[abnormal_idx],
                y=df[vol_col].iloc[abnormal_idx] if abnormal_idx < len(df) else 0,
                text="⬆️",
                showarrow=True,
                arrowhead=2,
                arrowsize=1,
                arrowwidth=2,
                ax=0,
                ay=-40
            )
        
        fig.update_layout(
            height=450,
            xaxis_rangeslider_visible=False,
            xaxis_type='category',
            xaxis2_type='category',
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)

        if not st.session_state.vg_answered:
            col1, col2, col3 = st.columns([1, 1, 1])
            with col1:
                if st.button("📈 第二天上涨", type="secondary", use_container_width=True, key="vg_up"):
                    _check_volume_answer(True, data['actual_up'])
            with col3:
                if st.button("📉 第二天下跌", type="secondary", use_container_width=True, key="vg_down"):
                    _check_volume_answer(False, data['actual_up'])
        else:
            _show_volume_result(data['actual_up'])

def _check_volume_answer(user_says_up, actual_up):
    """检查成交量游戏答案"""
    st.session_state.vg_answered = True
    st.session_state.vg_total += 1
    if user_says_up == actual_up:
        st.session_state.vg_correct += 1

def _show_volume_result(actual_up):
    """显示成交量游戏结果"""
    direction = "上涨" if actual_up else "下跌"
    direction_emoji = "📈" if actual_up else "📉"
    st.success(f"{direction_emoji} 第二天走势: **{direction}**")

# ==================== 突破新高/新低猜涨跌 ====================

def show_breakout_game():
    """突破新高/新低猜涨跌小游戏"""
    st.markdown("观察突破前期高点或低点的K线，猜猜后续走势！")
    
    if 'bg_total' not in st.session_state:
        st.session_state.bg_total = 0
        st.session_state.bg_correct = 0
        st.session_state.bg_current_data = None
        st.session_state.bg_answered = False
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("总题数", st.session_state.bg_total)
    with col2:
        st.metric("正确", st.session_state.bg_correct)
    with col3:
        accuracy = (st.session_state.bg_correct / st.session_state.bg_total * 100) if st.session_state.bg_total > 0 else 0
        st.metric("正确率", f"{accuracy:.0f}%")
    
    stocks = get_available_stocks()
    if not stocks:
        st.warning("未找到数据文件")
        return
    
    MIN_ROWS = 60
    
    if st.button("🎲 下一题", type="primary", key="bg_next"):
        random.shuffle(stocks)

        for code, name, filepath in stocks:
            df = read_csv(filepath)
            if df is None or len(df) < MIN_ROWS:
                continue

            close_col = 'close' if 'close' in df.columns else '收盘'
            high_col = 'high' if 'high' in df.columns else '最高'
            low_col = 'low' if 'low' in df.columns else '最低'

            # 找突破新高的日子
            for idx in range(20, len(df) - 5):
                prev_high = df[high_col].iloc[:idx].max()
                if df[high_col].iloc[idx] > prev_high * 1.02:  # 突破前高2%以上
                    # 后续5天走势
                    future_close = df[close_col].iloc[idx + 5] if idx + 5 < len(df) else df[close_col].iloc[-1]
                    actual_up = future_close > df[close_col].iloc[idx]
                    
                    bg_start = max(0, idx - 25)
                    st.session_state.bg_current_data = {
                        'df': df.iloc[bg_start:idx + 6].copy().reset_index(drop=True),
                        'breakout_idx': idx - bg_start,
                        'code': code,
                        'name': name,
                        'breakout_type': '新高',
                        'actual_up': actual_up
                    }
                    st.session_state.bg_answered = False
                    break
            else:
                # 找突破新低的日子
                for idx in range(20, len(df) - 5):
                    prev_low = df[low_col].iloc[:idx].min()
                    if df[low_col].iloc[idx] < prev_low * 0.98:  # 突破前低2%以上
                        future_close = df[close_col].iloc[idx + 5] if idx + 5 < len(df) else df[close_col].iloc[-1]
                        actual_up = future_close > df[close_col].iloc[idx]
                        
                        bg_start = max(0, idx - 25)
                        st.session_state.bg_current_data = {
                            'df': df.iloc[bg_start:idx + 6].copy().reset_index(drop=True),
                            'breakout_idx': idx - bg_start,
                            'code': code,
                            'name': name,
                            'breakout_type': '新低',
                            'actual_up': actual_up
                        }
                        st.session_state.bg_answered = False
                        break
            
            if st.session_state.bg_current_data:
                break
    
    if st.session_state.bg_current_data is not None:
        data = st.session_state.bg_current_data
        df = data['df']
        breakout_idx = data['breakout_idx']
        
        st.subheader(f"股票: {data['code']} {data['name']}")
        st.info(f"📈 观察箭头指向的K线，突破了{data['breakout_type']}！猜猜后续走势？")
        
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
        
        dates = df['date'].dt.strftime('%m-%d').tolist()
        
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            row_heights=[3, 1],
            vertical_spacing=0.1
        )
        
        color_up = '#ef5350'
        color_down = '#26a69a'
        
        # K线
        fig.add_trace(
            go.Candlestick(
                x=dates,
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                name='K线',
                increasing_line_color=color_up,
                decreasing_line_color=color_down
            ),
            row=1, col=1
        )
        
        # 成交量
        vol_col = 'volume' if 'volume' in df.columns else '成交量'
        if vol_col in df.columns:
            colors = [color_up if df['close'].iloc[i] >= df['open'].iloc[i] else color_down for i in range(len(df))]
            fig.add_trace(
                go.Bar(x=dates, y=df[vol_col], name='成交量', marker_color=colors, opacity=0.8),
                row=2, col=1
            )
        
        # 标记突破点
        fig.add_annotation(
            x=dates[breakout_idx],
            y=df['high'].iloc[breakout_idx],
            text="🚀",
            showarrow=True,
            arrowhead=2,
            arrowsize=1,
            arrowwidth=2,
            ax=0,
            ay=-40
        )
        
        # 画突破前的最高/最低点
        if data['breakout_type'] == '新高':
            prev_high = df['high'].iloc[:breakout_idx].max()
            fig.add_hline(y=prev_high, line_dash='dash', line_color='yellow', row=1, col=1)
        
        fig.update_layout(
            height=450,
            xaxis_rangeslider_visible=False,
            xaxis_type='category',
            xaxis2_type='category',
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)

        if not st.session_state.bg_answered:
            col1, col2, col3 = st.columns([1, 1, 1])
            with col1:
                if st.button("📈 继续上涨", type="secondary", use_container_width=True, key="bg_up"):
                    _check_breakout_answer(True, data['actual_up'])
            with col3:
                if st.button("📉 开始下跌", type="secondary", use_container_width=True, key="bg_down"):
                    _check_breakout_answer(False, data['actual_up'])
        else:
            _show_breakout_result(data['actual_up'])

def _check_breakout_answer(user_says_up, actual_up):
    st.session_state.bg_answered = True
    st.session_state.bg_total += 1
    if user_says_up == actual_up:
        st.session_state.bg_correct += 1

def _show_breakout_result(actual_up):
    direction = "上涨" if actual_up else "下跌"
    direction_emoji = "📈" if actual_up else "📉"
    st.success(f"{direction_emoji} 后续走势: **{direction}**")

# ==================== 均线金叉死叉猜涨跌 ====================

def show_ma_cross_game():
    """均线金叉/死叉猜涨跌小游戏"""
    st.markdown("观察均线金叉（买入信号）或死叉（卖出信号），猜猜后续走势！")
    
    if 'mg_total' not in st.session_state:
        st.session_state.mg_total = 0
        st.session_state.mg_correct = 0
        st.session_state.mg_current_data = None
        st.session_state.mg_answered = False
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("总题数", st.session_state.mg_total)
    with col2:
        st.metric("正确", st.session_state.mg_correct)
    with col3:
        accuracy = (st.session_state.mg_correct / st.session_state.mg_total * 100) if st.session_state.mg_total > 0 else 0
        st.metric("正确率", f"{accuracy:.0f}%")
    
    stocks = get_available_stocks()
    if not stocks:
        st.warning("未找到数据文件")
        return
    
    MIN_ROWS = 60
    
    if st.button("🎲 下一题", type="primary", key="mg_next"):
        random.shuffle(stocks)

        for code, name, filepath in stocks:
            df = read_csv(filepath)
            if df is None or len(df) < MIN_ROWS:
                continue

            close_col = 'close' if 'close' in df.columns else '收盘'

            # 计算均线
            df['ma5'] = df[close_col].rolling(5).mean()
            df['ma20'] = df[close_col].rolling(20).mean()
            
            # 找金叉/死叉
            for idx in range(25, len(df) - 5):
                prev_ma5 = df['ma5'].iloc[idx - 1]
                prev_ma20 = df['ma20'].iloc[idx - 1]
                curr_ma5 = df['ma5'].iloc[idx]
                curr_ma20 = df['ma20'].iloc[idx]
                
                if prev_ma5 <= prev_ma20 and curr_ma5 > curr_ma20:  # 金叉
                    future_close = df[close_col].iloc[idx + 5] if idx + 5 < len(df) else df[close_col].iloc[-1]
                    actual_up = future_close > df[close_col].iloc[idx]
                    
                    mg_start = max(0, idx - 25)
                    st.session_state.mg_current_data = {
                        'df': df.iloc[mg_start:idx + 6].copy().reset_index(drop=True),
                        'cross_idx': idx - mg_start,
                        'code': code,
                        'name': name,
                        'cross_type': '金叉',
                        'actual_up': actual_up
                    }
                    st.session_state.mg_answered = False
                    break
                elif prev_ma5 >= prev_ma20 and curr_ma5 < curr_ma20:  # 死叉
                    future_close = df[close_col].iloc[idx + 5] if idx + 5 < len(df) else df[close_col].iloc[-1]
                    actual_up = future_close > df[close_col].iloc[idx]
                    
                    mg_start = max(0, idx - 25)
                    st.session_state.mg_current_data = {
                        'df': df.iloc[mg_start:idx + 6].copy().reset_index(drop=True),
                        'cross_idx': idx - mg_start,
                        'code': code,
                        'name': name,
                        'cross_type': '死叉',
                        'actual_up': actual_up
                    }
                    st.session_state.mg_answered = False
                    break
            
            if st.session_state.mg_current_data:
                break
    
    if st.session_state.mg_current_data is not None:
        data = st.session_state.mg_current_data
        df = data['df']
        cross_idx = data['cross_idx']
        
        close_col = 'close' if 'close' in df.columns else '收盘'
        
        st.subheader(f"股票: {data['code']} {data['name']}")
        st.info(f"🔔 均线出现{data['cross_type']}(MA5上穿/下穿MA20)！猜猜后续走势？")
        
        import plotly.graph_objects as go
        
        dates = df['date'].dt.strftime('%m-%d').tolist()
        
        fig = go.Figure()
        
        # K线
        color_up = '#ef5350'
        color_down = '#26a69a'
        fig.add_trace(
            go.Candlestick(
                x=dates,
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                name='K线',
                increasing_line_color=color_up,
                decreasing_line_color=color_down
            )
        )
        
        # 均线
        fig.add_trace(
            go.Scatter(x=dates, y=df['ma5'], name='MA5', line=dict(color='yellow', width=1))
        )
        fig.add_trace(
            go.Scatter(x=dates, y=df['ma20'], name='MA20', line=dict(color='blue', width=1))
        )
        
        # 标记金叉/死叉点
        emoji = "🟢" if data['cross_type'] == '金叉' else "🔴"
        fig.add_annotation(
            x=dates[cross_idx],
            y=df[close_col].iloc[cross_idx],
            text=emoji,
            showarrow=True,
            arrowhead=2,
            arrowsize=1,
            arrowwidth=2,
            ax=0,
            ay=-40
        )
        
        fig.update_layout(
            height=450,
            xaxis_rangeslider_visible=False,
            xaxis_type='category'
        )
        st.plotly_chart(fig, use_container_width=True)

        if not st.session_state.mg_answered:
            col1, col2, col3 = st.columns([1, 1, 1])
            with col1:
                if st.button("📈 上涨", type="secondary", use_container_width=True, key="mg_up"):
                    _check_ma_answer(True, data['actual_up'])
            with col3:
                if st.button("📉 下跌", type="secondary", use_container_width=True, key="mg_down"):
                    _check_ma_answer(False, data['actual_up'])
        else:
            _show_ma_result(data['actual_up'])

def _check_ma_answer(user_says_up, actual_up):
    st.session_state.mg_answered = True
    st.session_state.mg_total += 1
    if user_says_up == actual_up:
        st.session_state.mg_correct += 1

def _show_ma_result(actual_up):
    direction = "上涨" if actual_up else "下跌"
    direction_emoji = "📈" if actual_up else "📉"
    st.success(f"{direction_emoji} 后续走势: **{direction}**")

# ==================== 跳空缺口猜涨跌 ====================

def show_gap_game():
    """跳空缺口猜涨跌小游戏"""
    st.markdown("观察跳空缺口（向上或向下），猜猜是否回补缺口！")
    
    if 'gap_total' not in st.session_state:
        st.session_state.gap_total = 0
        st.session_state.gap_correct = 0
        st.session_state.gap_current_data = None
        st.session_state.gap_answered = False
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("总题数", st.session_state.gap_total)
    with col2:
        st.metric("正确", st.session_state.gap_correct)
    with col3:
        accuracy = (st.session_state.gap_correct / st.session_state.gap_total * 100) if st.session_state.gap_total > 0 else 0
        st.metric("正确率", f"{accuracy:.0f}%")
    
    stocks = get_available_stocks()
    if not stocks:
        st.warning("未找到数据文件")
        return
    
    MIN_ROWS = 30
    
    if st.button("🎲 下一题", type="primary", key="gap_next"):
        random.shuffle(stocks)

        for code, name, filepath in stocks:
            df = read_csv(filepath)
            if df is None or len(df) < MIN_ROWS:
                continue

            close_col = 'close' if 'close' in df.columns else '收盘'
            open_col = 'open' if 'open' in df.columns else '开盘'

            # 找跳空缺口
            for idx in range(1, len(df) - 5):
                prev_close = df[close_col].iloc[idx - 1]
                curr_open = df[open_col].iloc[idx]
                
                # 向上跳空 > 2%
                if curr_open > prev_close * 1.02:
                    future_low = df[close_col].iloc[idx:idx + 5].min()
                    filled = future_low <= prev_close  # 是否回补缺口
                    
                    gap_start = max(0, idx - 25)
                    st.session_state.gap_current_data = {
                        'df': df.iloc[gap_start:idx + 6].copy().reset_index(drop=True),
                        'gap_idx': idx - gap_start,
                        'code': code,
                        'name': name,
                        'gap_type': '向上',
                        'filled': filled
                    }
                    st.session_state.gap_answered = False
                    break
                # 向下跳空 > 2%
                elif curr_open < prev_close * 0.98:
                    future_high = df[close_col].iloc[idx:idx + 5].max()
                    filled = future_high >= prev_close  # 是否回补缺口
                    
                    gap_start = max(0, idx - 25)
                    st.session_state.gap_current_data = {
                        'df': df.iloc[gap_start:idx + 6].copy().reset_index(drop=True),
                        'gap_idx': idx - gap_start,
                        'code': code,
                        'name': name,
                        'gap_type': '向下',
                        'filled': filled
                    }
                    st.session_state.gap_answered = False
                    break
            
            if st.session_state.gap_current_data:
                break
    
    if st.session_state.gap_current_data is not None:
        data = st.session_state.gap_current_data
        df = data['df']
        gap_idx = data['gap_idx']
        
        close_col = 'close' if 'close' in df.columns else '收盘'
        
        st.subheader(f"股票: {data['code']} {data['name']}")
        st.info(f"⬜ 出现{data['gap_type']}跳空缺口！猜猜5天内是否回补缺口？")
        
        import plotly.graph_objects as go
        
        dates = df['date'].dt.strftime('%m-%d').tolist()
        
        fig = go.Figure()
        
        color_up = '#ef5350'
        color_down = '#26a69a'
        
        fig.add_trace(
            go.Candlestick(
                x=dates,
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                name='K线',
                increasing_line_color=color_up,
                decreasing_line_color=color_down
            )
        )
        
        # 标记缺口
        prev_close = df[close_col].iloc[gap_idx - 1]
        fig.add_hline(y=prev_close, line_dash='dash', line_color='yellow', 
                      annotation_text='缺口支撑/压力位')
        
        emoji = "⬆️" if data['gap_type'] == '向上' else "⬇️"
        fig.add_annotation(
            x=dates[gap_idx],
            y=df['high'].iloc[gap_idx],
            text=emoji,
            showarrow=True,
            arrowhead=2,
            arrowsize=1,
            arrowwidth=2,
            ax=0,
            ay=-40
        )
        
        fig.update_layout(
            height=400,
            xaxis_rangeslider_visible=False,
            xaxis_type='category'
        )
        st.plotly_chart(fig, use_container_width=True)

        if not st.session_state.gap_answered:
            col1, col2, col3 = st.columns([1, 1, 1])
            with col1:
                if st.button("✅ 会回补", type="secondary", use_container_width=True, key="gap_yes"):
                    _check_gap_answer(True, data['filled'])
            with col3:
                if st.button("❌ 不会回补", type="secondary", use_container_width=True, key="gap_no"):
                    _check_gap_answer(False, data['filled'])
        else:
            _show_gap_result(data['filled'])

def _check_gap_answer(user_says_filled, actual_filled):
    st.session_state.gap_answered = True
    st.session_state.gap_total += 1
    if user_says_filled == actual_filled:
        st.session_state.gap_correct += 1

def _show_gap_result(filled):
    result = "回补了缺口" if filled else "没有回补"
    emoji = "✅" if filled else "❌"
    st.success(f"{emoji} 结果: **{result}**")

if __name__ == "__main__":
    main()
