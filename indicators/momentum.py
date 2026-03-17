# -*- coding: utf-8 -*-
"""动量指标: RSI, KDJ, CCI, Williams %R"""
import numpy as np
import pandas as pd


# ── RSI ───────────────────────────────────────────
def calc_rsi(df, period=14, col='close'):
    """相对强弱指数"""
    delta = df[col].diff()
    gain = delta.where(delta > 0, 0.0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
    rs = gain / loss.replace(0, 1e-10)
    df[f'RSI{period}'] = (100 - (100 / (1 + rs))).fillna(50)
    return df, [f'RSI{period}']


def plot_rsi(fig, df, dates, row, period=14, **_kw):
    import plotly.graph_objects as go
    key = f'RSI{period}'
    if key in df.columns:
        fig.add_trace(
            go.Scatter(x=dates, y=df[key], name=key, line=dict(color='#ab47bc', width=1)),
            row=row, col=1
        )
        fig.add_hline(y=70, line_dash='dash', line_color='#ef5350', row=row, col=1)
        fig.add_hline(y=30, line_dash='dash', line_color='#26a69a', row=row, col=1)
        fig.update_yaxes(title_text='RSI', row=row, col=1, range=[0, 100])


# ── KDJ ───────────────────────────────────────────
def calc_kdj(df, n=9, m1=3, m2=3, high='high', low='low', close='close'):
    """KDJ随机指标"""
    low_n = df[low].rolling(window=n, min_periods=1).min()
    high_n = df[high].rolling(window=n, min_periods=1).max()
    rsv = (df[close] - low_n) / (high_n - low_n).replace(0, 1e-10) * 100
    df['KDJ_K'] = rsv.ewm(com=m1 - 1, adjust=False).mean()
    df['KDJ_D'] = df['KDJ_K'].ewm(com=m2 - 1, adjust=False).mean()
    df['KDJ_J'] = 3 * df['KDJ_K'] - 2 * df['KDJ_D']
    return df, ['KDJ_K', 'KDJ_D', 'KDJ_J']


def plot_kdj(fig, df, dates, row, **_kw):
    import plotly.graph_objects as go
    fig.add_trace(
        go.Scatter(x=dates, y=df['KDJ_K'], name='K', line=dict(color='#ffeb3b', width=1)),
        row=row, col=1
    )
    fig.add_trace(
        go.Scatter(x=dates, y=df['KDJ_D'], name='D', line=dict(color='#2196f3', width=1)),
        row=row, col=1
    )
    fig.add_trace(
        go.Scatter(x=dates, y=df['KDJ_J'], name='J', line=dict(color='#e91e63', width=1)),
        row=row, col=1
    )
    fig.add_hline(y=80, line_dash='dash', line_color='#ef5350', row=row, col=1)
    fig.add_hline(y=20, line_dash='dash', line_color='#26a69a', row=row, col=1)
    fig.update_yaxes(title_text='KDJ', row=row, col=1)


# ── CCI ───────────────────────────────────────────
def calc_cci(df, period=14, high='high', low='low', close='close'):
    """顺势指标 (Commodity Channel Index)"""
    tp = (df[high] + df[low] + df[close]) / 3
    ma_tp = tp.rolling(window=period, min_periods=1).mean()
    md = tp.rolling(window=period, min_periods=1).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    df[f'CCI{period}'] = (tp - ma_tp) / (0.015 * md).replace(0, 1e-10)
    return df, [f'CCI{period}']


def plot_cci(fig, df, dates, row, period=14, **_kw):
    import plotly.graph_objects as go
    key = f'CCI{period}'
    if key in df.columns:
        fig.add_trace(
            go.Scatter(x=dates, y=df[key], name=key, line=dict(color='#ff9800', width=1)),
            row=row, col=1
        )
        fig.add_hline(y=100, line_dash='dash', line_color='#ef5350', row=row, col=1)
        fig.add_hline(y=-100, line_dash='dash', line_color='#26a69a', row=row, col=1)
        fig.update_yaxes(title_text='CCI', row=row, col=1)


# ── Williams %R ───────────────────────────────────
def calc_williams(df, period=14, high='high', low='low', close='close'):
    """威廉指标 (Williams %R)"""
    high_n = df[high].rolling(window=period, min_periods=1).max()
    low_n = df[low].rolling(window=period, min_periods=1).min()
    df[f'WR{period}'] = (high_n - df[close]) / (high_n - low_n).replace(0, 1e-10) * -100
    return df, [f'WR{period}']


def plot_williams(fig, df, dates, row, period=14, **_kw):
    import plotly.graph_objects as go
    key = f'WR{period}'
    if key in df.columns:
        fig.add_trace(
            go.Scatter(x=dates, y=df[key], name=key, line=dict(color='#00bcd4', width=1)),
            row=row, col=1
        )
        fig.add_hline(y=-20, line_dash='dash', line_color='#ef5350', row=row, col=1)
        fig.add_hline(y=-80, line_dash='dash', line_color='#26a69a', row=row, col=1)
        fig.update_yaxes(title_text='Williams %R', row=row, col=1, range=[-100, 0])


# ── 注册 ──────────────────────────────────────────
INDICATORS = [
    {
        'name': 'RSI',
        'label': '相对强弱指数 (RSI)',
        'category': '动量指标',
        'overlay': False,
        'calc': calc_rsi,
        'plot': plot_rsi,
        'params': [
            {'key': 'period', 'label': 'RSI周期', 'type': 'int', 'default': 14, 'min': 2, 'max': 50},
        ],
    },
    {
        'name': 'KDJ',
        'label': '随机指标 (KDJ)',
        'category': '动量指标',
        'overlay': False,
        'calc': calc_kdj,
        'plot': plot_kdj,
        'params': [
            {'key': 'n', 'label': 'N周期', 'type': 'int', 'default': 9, 'min': 2, 'max': 30},
            {'key': 'm1', 'label': 'M1平滑', 'type': 'int', 'default': 3, 'min': 2, 'max': 10},
            {'key': 'm2', 'label': 'M2平滑', 'type': 'int', 'default': 3, 'min': 2, 'max': 10},
        ],
    },
    {
        'name': 'CCI',
        'label': '顺势指标 (CCI)',
        'category': '动量指标',
        'overlay': False,
        'calc': calc_cci,
        'plot': plot_cci,
        'params': [
            {'key': 'period', 'label': 'CCI周期', 'type': 'int', 'default': 14, 'min': 2, 'max': 50},
        ],
    },
    {
        'name': 'WR',
        'label': '威廉指标 (Williams %R)',
        'category': '动量指标',
        'overlay': False,
        'calc': calc_williams,
        'plot': plot_williams,
        'params': [
            {'key': 'period', 'label': 'WR周期', 'type': 'int', 'default': 14, 'min': 2, 'max': 50},
        ],
    },
]
