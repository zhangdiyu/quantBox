# -*- coding: utf-8 -*-
"""成交量指标: OBV, Volume MA, Volume RSI"""
import numpy as np
import pandas as pd


# ── OBV ───────────────────────────────────────────
def calc_obv(df, close='close', volume='volume'):
    """能量潮 (On-Balance Volume)"""
    if volume not in df.columns:
        return df, []
    sign = np.sign(df[close].diff()).fillna(0)
    df['OBV'] = (sign * df[volume]).cumsum()
    return df, ['OBV']


def plot_obv(fig, df, dates, row, **_kw):
    import plotly.graph_objects as go
    if 'OBV' in df.columns:
        fig.add_trace(
            go.Scatter(x=dates, y=df['OBV'], name='OBV',
                       line=dict(color='#4caf50', width=1)),
            row=row, col=1
        )
        fig.update_yaxes(title_text='OBV', row=row, col=1)


# ── Volume MA ─────────────────────────────────────
def calc_vol_ma(df, period=20, volume='volume'):
    """成交量移动平均"""
    if volume not in df.columns:
        return df, []
    df[f'VOL_MA{period}'] = df[volume].rolling(window=period, min_periods=1).mean()
    return df, [f'VOL_MA{period}']


def plot_vol_ma(fig, df, dates, row, period=20, **_kw):
    import plotly.graph_objects as go
    key = f'VOL_MA{period}'
    if key in df.columns:
        fig.add_trace(
            go.Scatter(x=dates, y=df[key], name=key,
                       line=dict(color='#ff9800', width=1.5, dash='dash')),
            row=row, col=1
        )
        fig.update_yaxes(title_text='Vol MA', row=row, col=1)


# ── Volume RSI ────────────────────────────────────
def calc_vol_rsi(df, period=14, volume='volume'):
    """成交量RSI"""
    if volume not in df.columns:
        return df, []
    delta = df[volume].diff()
    gain = delta.where(delta > 0, 0.0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
    rs = gain / loss.replace(0, 1e-10)
    df[f'VOL_RSI{period}'] = (100 - (100 / (1 + rs))).fillna(50)
    return df, [f'VOL_RSI{period}']


def plot_vol_rsi(fig, df, dates, row, period=14, **_kw):
    import plotly.graph_objects as go
    key = f'VOL_RSI{period}'
    if key in df.columns:
        fig.add_trace(
            go.Scatter(x=dates, y=df[key], name=key,
                       line=dict(color='#9c27b0', width=1)),
            row=row, col=1
        )
        fig.add_hline(y=70, line_dash='dash', line_color='#ef5350', row=row, col=1)
        fig.add_hline(y=30, line_dash='dash', line_color='#26a69a', row=row, col=1)
        fig.update_yaxes(title_text='Vol RSI', row=row, col=1, range=[0, 100])


# ── 注册 ──────────────────────────────────────────
INDICATORS = [
    {
        'name': 'OBV',
        'label': '能量潮 (OBV)',
        'category': '成交量指标',
        'overlay': False,
        'calc': calc_obv,
        'plot': plot_obv,
        'params': [],
    },
    {
        'name': 'VOL_MA',
        'label': '成交量均线 (Vol MA)',
        'category': '成交量指标',
        'overlay': False,     # 绘制在成交量子图上
        'on_volume': True,    # 标记：叠加到成交量行
        'calc': calc_vol_ma,
        'plot': plot_vol_ma,
        'params': [
            {'key': 'period', 'label': '周期', 'type': 'int', 'default': 20, 'min': 2, 'max': 60},
        ],
    },
    {
        'name': 'VOL_RSI',
        'label': '成交量RSI (Vol RSI)',
        'category': '成交量指标',
        'overlay': False,
        'calc': calc_vol_rsi,
        'plot': plot_vol_rsi,
        'params': [
            {'key': 'period', 'label': '周期', 'type': 'int', 'default': 14, 'min': 2, 'max': 50},
        ],
    },
]
