# -*- coding: utf-8 -*-
"""
可视化与报告生成模块
提供HTML报告、图表展示等功能
"""
import pandas as pd
import numpy as np
import json
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px


class QuantPlotter:
    """量化图表生成器"""
    
    def __init__(self, result=None):
        """
        初始化
        
        Args:
            result: BacktestResult对象
        """
        self.result = result
        self.figures = []
        
    def plot_equity_curve(self, height: int = 500) -> go.Figure:
        """绘制资金曲线"""
        if self.result is None or self.result.equity_curve is None:
            return go.Figure()
        
        equity = self.result.equity_curve
        
        fig = go.Figure()
        
        # 资金曲线
        fig.add_trace(go.Scatter(
            x=equity.index,
            y=equity.values,
            mode='lines',
            name='资金曲线',
            line=dict(color='#1f77b4', width=2)
        ))
        
        # 初始资金线
        fig.add_hline(
            y=self.result.initial_capital,
            line_dash="dash",
            line_color="gray",
            annotation_text="初始资金"
        )
        
        fig.update_layout(
            title='资金曲线',
            xaxis_title='日期',
            yaxis_title='资金',
            height=height,
            hovermode='x unified'
        )
        
        return fig
    
    def plot_drawdown(self, height: int = 300) -> go.Figure:
        """绘制回撤曲线"""
        if self.result is None or self.result.equity_curve is None:
            return go.Figure()
        
        equity = self.result.equity_curve
        cummax = equity.cummax()
        drawdown = (equity - cummax) / cummax
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=drawdown.index,
            y=drawdown.values,
            mode='lines',
            name='回撤',
            fill='tozeroy',
            line=dict(color='red', width=1),
            fillcolor='rgba(255,0,0,0.2)'
        ))
        
        fig.add_hline(
            y=self.result.max_drawdown,
            line_dash="dash",
            line_color="darkred",
            annotation_text=f"最大回撤: {self.result.max_drawdown:.2%}"
        )
        
        fig.update_layout(
            title='回撤曲线',
            xaxis_title='日期',
            yaxis_title='回撤',
            height=height,
            yaxis_tickformat='.1%'
        )
        
        return fig
    
    def plot_monthly_returns(self, height: int = 400) -> go.Figure:
        """绘制月度收益热力图"""
        if self.result is None or self.result.daily_returns is None:
            return go.Figure()
        
        daily_returns = self.result.daily_returns
        
        # 计算月度收益
        monthly_returns = daily_returns.resample('M').apply(
            lambda x: (1 + x).prod() - 1
        )
        
        # 构建透视表
        monthly_returns.index = pd.to_datetime(monthly_returns.index)
        df = pd.DataFrame({
            'year': monthly_returns.index.year,
            'month': monthly_returns.index.month,
            'return': monthly_returns.values
        })
        
        pivot = df.pivot(index='year', columns='month', values='return')
        pivot.columns = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                         'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        # 创建热力图
        fig = go.Figure(data=go.Heatmap(
            z=pivot.values,
            x=pivot.columns,
            y=pivot.index,
            colorscale='RdYlGn',
            zmid=0,
            text=[[f'{v:.1%}' if not pd.isna(v) else '' 
                   for v in row] for row in pivot.values],
            texttemplate='%{text}',
            hovertemplate='Year: %{y}<br>Month: %{x}<br>Return: %{z:.2%}<extra></extra>'
        ))
        
        fig.update_layout(
            title='月度收益热力图',
            height=height,
            xaxis_title='月份',
            yaxis_title='年份'
        )
        
        return fig
    
    def plot_trade_distribution(self, height: int = 400) -> go.Figure:
        """绘制交易分布"""
        if self.result is None or not self.result.trades:
            return go.Figure()
        
        trades = self.result.trades
        
        # 计算每笔交易的盈亏
        trade_profits = []
        for i, trade in enumerate(trades):
            if trade.action == 'sell' and i > 0:
                # 找到对应的买入交易
                buy_trade = None
                for j in range(i-1, -1, -1):
                    if trades[j].action == 'buy' and trades[j].code == trade.code:
                        buy_trade = trades[j]
                        break
                
                if buy_trade:
                    profit = (trade.price - buy_trade.price) * trade.volume
                    profit -= (trade.commission + buy_trade.commission)
                    trade_profits.append(profit)
        
        if not trade_profits:
            return go.Figure()
        
        # 创建盈亏分布图
        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=('交易盈亏分布', '累计盈亏'),
            specs=[[{}, {}]]
        )
        
        # 盈亏分布直方图
        colors = ['red' if p < 0 else 'green' for p in trade_profits]
        fig.add_trace(
            go.Bar(
                x=list(range(len(trade_profits))),
                y=trade_profits,
                marker_color=colors,
                name='单笔盈亏'
            ),
            row=1, col=1
        )
        
        # 累计盈亏曲线
        cumulative = np.cumsum(trade_profits)
        fig.add_trace(
            go.Scatter(
                x=list(range(len(cumulative))),
                y=cumulative,
                mode='lines',
                line=dict(color='blue', width=2),
                name='累计盈亏'
            ),
            row=1, col=2
        )
        
        fig.update_layout(
            title='交易分析',
            height=height,
            showlegend=False
        )
        
        return fig
    
    def generate_report(self, output_path: str = None) -> str:
        """生成HTML报告"""
        if self.result is None:
            return "<p>无回测结果</p>"
        
        # 生成各图表
        equity_fig = self.plot_equity_curve()
        drawdown_fig = self.plot_drawdown()
        monthly_fig = self.plot_monthly_returns()
        trade_fig = self.plot_trade_distribution()
        
        # 转换为HTML
        equity_html = equity_fig.to_html(full_html=False, include_plotlyjs=False)
        drawdown_html = drawdown_fig.to_html(full_html=False, include_plotlyjs=False)
        monthly_html = monthly_fig.to_html(full_html=False, include_plotlyjs=False)
        trade_html = trade_fig.to_html(full_html=False, include_plotlyjs=False)
        
        # 构建完整HTML报告
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>回测报告 - {self.result.strategy_name}</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            border-bottom: 2px solid #007bff;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #555;
            margin-top: 30px;
        }}
        .summary {{
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
        }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }}
        .metric {{
            background-color: white;
            padding: 10px;
            border-radius: 5px;
            text-align: center;
        }}
        .metric-label {{
            font-size: 12px;
            color: #666;
        }}
        .metric-value {{
            font-size: 20px;
            font-weight: bold;
            color: #007bff;
        }}
        .positive {{
            color: #28a745;
        }}
        .negative {{
            color: #dc3545;
        }}
        .chart-container {{
            margin: 30px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 回测报告</h1>
        
        <div class="summary">
            <h2>基本信息</h2>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                <div><strong>策略名称:</strong> {self.result.strategy_name}</div>
                <div><strong>回测周期:</strong> {self.result.start_date.strftime('%Y-%m-%d')} ~ {self.result.end_date.strftime('%Y-%m-%d')}</div>
                <div><strong>初始资金:</strong> {self.result.initial_capital:,.2f}</div>
                <div><strong>最终资金:</strong> {self.result.final_value:,.2f}</div>
            </div>
        </div>
        
        <div class="summary">
            <h2>绩效指标</h2>
            <div class="summary-grid">
                <div class="metric">
                    <div class="metric-label">总收益率</div>
                    <div class="metric-value {'positive' if self.result.total_return > 0 else 'negative'}">{self.result.total_return:.2%}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">年化收益率</div>
                    <div class="metric-value {'positive' if self.result.annual_return > 0 else 'negative'}">{self.result.annual_return:.2%}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">最大回撤</div>
                    <div class="metric-value negative">{self.result.max_drawdown:.2%}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">夏普比率</div>
                    <div class="metric-value">{self.result.sharpe_ratio:.2f}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">交易次数</div>
                    <div class="metric-value">{self.result.total_trades}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">胜率</div>
                    <div class="metric-value">{self.result.win_rate:.2%}</div>
                </div>
            </div>
        </div>
        
        <div class="chart-container">
            <h2>资金曲线</h2>
            {equity_html}
        </div>
        
        <div class="chart-container">
            <h2>回撤曲线</h2>
            {drawdown_html}
        </div>
        
        <div class="chart-container">
            <h2>月度收益热力图</h2>
            {monthly_html}
        </div>
        
        <div class="chart-container">
            <h2>交易分析</h2>
            {trade_html}
        </div>
        
        <div style="margin-top: 50px; padding-top: 20px; border-top: 1px solid #ddd; text-align: center; color: #666; font-size: 12px;">
            生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | QuantBox Framework v1.0
        </div>
    </div>
</body>
</html>
        """
        
        # 保存报告
        if output_path is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = f"backtest_report_{timestamp}.html"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"报告已保存: {output_path}")
        return output_path


class StockDataUpdater:
    """数据更新器包装类"""
    
    def __init__(self):
        pass
    
    def update_stocks(self, stock_codes, start_date=None, end_date=None):
        """更新股票数据"""
        from src.data_updater import update_stocks
        return update_stocks(stock_codes, start_date, end_date)
