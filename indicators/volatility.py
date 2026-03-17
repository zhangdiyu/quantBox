# -*- coding: utf-8 -*-
"""波动指标: ATR, StdDev, Variance"""
import numpy as np
import pandas as pd


# ── ATR ───────────────────────────────────────────
def calc_atr(df, period=14, high='high', low='low', close='close'):
    """平均真实波幅 (Average True Range)"""
    prev_close = df[close].shift(1)
    tr1 = df[high] - df[low]
    tr2 = (df[high] - prev_close).abs()
    tr3 = (df[low] - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['TR'] = tr
    df[f'ATR{period}'] = tr.rolling(window=period, min_periods=1).mean()
    return df, ['TR', f'ATR{period}']


def plot_atr(fig, df, dates, row, period=14, **_kw):
    import plotly.graph_objects as go
    key = f'ATR{period}'
    if key in df.columns:
        fig.add_trace(
            go.Scatter(x=dates, y=df[key], name=key,
                       line=dict(color='#ff5722', width=1)),
            row=row, col=1
        )
        fig.update_yaxes(title_text='ATR', row=row, col=1)


# ── StdDev ────────────────────────────────────────
def calc_stddev(df, period=20, col='close'):
    """标准差"""
    df[f'STDDEV{period}'] = df[col].rolling(window=period, min_periods=1).std()
    return df, [f'STDDEV{period}']


def plot_stddev(fig, df, dates, row, period=20, **_kw):
    import plotly.graph_objects as go
    key = f'STDDEV{period}'
    if key in df.columns:
        fig.add_trace(
            go.Scatter(x=dates, y=df[key], name=key,
                       line=dict(color='#795548', width=1)),
            row=row, col=1
        )
        fig.update_yaxes(title_text='StdDev', row=row, col=1)


# ── Variance ──────────────────────────────────────
def calc_variance(df, period=20, col='close'):
    """方差"""
    df[f'VAR{period}'] = df[col].rolling(window=period, min_periods=1).var()
    return df, [f'VAR{period}']


def plot_variance(fig, df, dates, row, period=20, **_kw):
    import plotly.graph_objects as go
    key = f'VAR{period}'
    if key in df.columns:
        fig.add_trace(
            go.Scatter(x=dates, y=df[key], name=key,
                       line=dict(color='#607d8b', width=1)),
            row=row, col=1
        )
        fig.update_yaxes(title_text='Variance', row=row, col=1)


# ── 注册 ──────────────────────────────────────────
INDICATORS = [
    {
        'name': 'ATR',
        'label': '平均真实波幅 (ATR)',
        'category': '波动指标',
        'overlay': False,
        'calc': calc_atr,
        'plot': plot_atr,
        'params': [
            {'key': 'period', 'label': 'ATR周期', 'type': 'int', 'default': 14, 'min': 2, 'max': 50},
        ],
    },
    {
        'name': 'STDDEV',
        'label': '标准差 (StdDev)',
        'category': '波动指标',
        'overlay': False,
        'calc': calc_stddev,
        'plot': plot_stddev,
        'params': [
            {'key': 'period', 'label': '周期', 'type': 'int', 'default': 20, 'min': 2, 'max': 60},
        ],
    },
    {
        'name': 'VAR',
        'label': '方差 (Variance)',
        'category': '波动指标',
        'overlay': False,
        'calc': calc_variance,
        'plot': plot_variance,
        'params': [
            {'key': 'period', 'label': '周期', 'type': 'int', 'default': 20, 'min': 2, 'max': 60},
        ],
    },
]
