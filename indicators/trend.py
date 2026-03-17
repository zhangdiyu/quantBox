# -*- coding: utf-8 -*-
"""趋势指标: MA, EMA, MACD, Bollinger Bands"""
import numpy as np
import pandas as pd


# ── MA ────────────────────────────────────────────
def calc_ma(df, period=20, col='close'):
    """简单移动平均线"""
    key = f'MA{period}'
    df[key] = df[col].rolling(window=period, min_periods=1).mean()
    return df, [key]


def plot_ma(fig, df, dates, row, period=20, **_kw):
    import plotly.graph_objects as go
    colors = {5: '#ffeb3b', 10: '#ff9800', 20: '#e91e63', 60: '#2196f3'}
    key = f'MA{period}'
    if key in df.columns:
        fig.add_trace(
            go.Scatter(x=dates, y=df[key], name=key,
                       line=dict(color=colors.get(period, '#ffffff'), width=1)),
            row=row, col=1
        )


# ── EMA ───────────────────────────────────────────
def calc_ema(df, period=12, col='close'):
    """指数移动平均线"""
    key = f'EMA{period}'
    df[key] = df[col].ewm(span=period, adjust=False).mean()
    return df, [key]


def plot_ema(fig, df, dates, row, period=12, **_kw):
    import plotly.graph_objects as go
    colors = {12: '#9c27b0', 26: '#00bcd4'}
    key = f'EMA{period}'
    if key in df.columns:
        fig.add_trace(
            go.Scatter(x=dates, y=df[key], name=key,
                       line=dict(color=colors.get(period, '#ffffff'), width=1, dash='dash')),
            row=row, col=1
        )


# ── MACD ──────────────────────────────────────────
def calc_macd(df, fast=12, slow=26, signal=9, col='close'):
    """MACD (Moving Average Convergence Divergence)"""
    ema_f = df[col].ewm(span=fast, adjust=False).mean()
    ema_s = df[col].ewm(span=slow, adjust=False).mean()
    df['DIF'] = ema_f - ema_s
    df['DEA'] = df['DIF'].ewm(span=signal, adjust=False).mean()
    df['MACD_HIST'] = (df['DIF'] - df['DEA']) * 2
    return df, ['DIF', 'DEA', 'MACD_HIST']


def plot_macd(fig, df, dates, row, **_kw):
    import plotly.graph_objects as go
    color_up, color_down = '#ef5350', '#26a69a'
    hist_colors = [color_up if v >= 0 else color_down for v in df['MACD_HIST']]
    fig.add_trace(
        go.Bar(x=dates, y=df['MACD_HIST'], name='MACD柱', marker_color=hist_colors, opacity=0.7),
        row=row, col=1
    )
    fig.add_trace(
        go.Scatter(x=dates, y=df['DIF'], name='DIF', line=dict(color='#ffeb3b', width=1)),
        row=row, col=1
    )
    fig.add_trace(
        go.Scatter(x=dates, y=df['DEA'], name='DEA', line=dict(color='#2196f3', width=1)),
        row=row, col=1
    )
    fig.update_yaxes(title_text='MACD', row=row, col=1)


# ── Bollinger Bands ───────────────────────────────
def calc_bollinger(df, period=20, std_dev=2, col='close'):
    """布林带"""
    mid = df[col].rolling(window=period, min_periods=1).mean()
    std = df[col].rolling(window=period, min_periods=1).std()
    df['BOLL_MID'] = mid
    df['BOLL_UP'] = mid + std_dev * std
    df['BOLL_DN'] = mid - std_dev * std
    return df, ['BOLL_MID', 'BOLL_UP', 'BOLL_DN']


def plot_bollinger(fig, df, dates, row, **_kw):
    import plotly.graph_objects as go
    fig.add_trace(
        go.Scatter(x=dates, y=df['BOLL_UP'], name='BOLL上轨',
                   line=dict(color='gray', width=1), opacity=0.5),
        row=row, col=1
    )
    fig.add_trace(
        go.Scatter(x=dates, y=df['BOLL_DN'], name='BOLL下轨',
                   line=dict(color='gray', width=1), fill='tonexty', opacity=0.2),
        row=row, col=1
    )


# ── 注册 ──────────────────────────────────────────
INDICATORS = [
    {
        'name': 'MA',
        'label': '移动平均线 (MA)',
        'category': '趋势指标',
        'overlay': True,       # 叠加在K线上
        'calc': calc_ma,
        'plot': plot_ma,
        'params': [
            {'key': 'period', 'label': 'MA周期', 'type': 'multi_select',
             'options': [5, 10, 20, 60], 'default': [5, 20]},
        ],
    },
    {
        'name': 'EMA',
        'label': '指数移动平均 (EMA)',
        'category': '趋势指标',
        'overlay': True,
        'calc': calc_ema,
        'plot': plot_ema,
        'params': [
            {'key': 'period', 'label': 'EMA周期', 'type': 'multi_select',
             'options': [12, 26, 50], 'default': [12, 26]},
        ],
    },
    {
        'name': 'MACD',
        'label': 'MACD',
        'category': '趋势指标',
        'overlay': False,
        'calc': calc_macd,
        'plot': plot_macd,
        'params': [
            {'key': 'fast', 'label': '快线', 'type': 'int', 'default': 12, 'min': 2, 'max': 50},
            {'key': 'slow', 'label': '慢线', 'type': 'int', 'default': 26, 'min': 5, 'max': 100},
            {'key': 'signal', 'label': '信号线', 'type': 'int', 'default': 9, 'min': 2, 'max': 30},
        ],
    },
    {
        'name': 'BOLL',
        'label': '布林带 (Bollinger Bands)',
        'category': '趋势指标',
        'overlay': True,
        'calc': calc_bollinger,
        'plot': plot_bollinger,
        'params': [
            {'key': 'period', 'label': '周期', 'type': 'int', 'default': 20, 'min': 5, 'max': 60},
            {'key': 'std_dev', 'label': '标准差倍数', 'type': 'float', 'default': 2.0, 'min': 1.0, 'max': 3.0, 'step': 0.1},
        ],
    },
]
