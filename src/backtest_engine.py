# -*- coding: utf-8 -*-
"""
策略回测引擎
提供完整的回测功能，包括:
- 策略基类
- 回测引擎
- 持仓管理
- 绩效分析
"""
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
import warnings
warnings.filterwarnings('ignore')


@dataclass
class Trade:
    """交易记录"""
    date: datetime
    code: str
    action: str  # 'buy' or 'sell'
    price: float
    volume: int
    amount: float
    commission: float = 0.0
    
@dataclass
class Position:
    """持仓信息"""
    code: str
    volume: int = 0
    avg_cost: float = 0.0
    current_price: float = 0.0
    
    @property
    def market_value(self) -> float:
        return self.volume * self.current_price
    
    @property
    def profit(self) -> float:
        return (self.current_price - self.avg_cost) * self.volume
    
    @property
    def profit_pct(self) -> float:
        if self.avg_cost == 0:
            return 0.0
        return (self.current_price - self.avg_cost) / self.avg_cost

@dataclass
class Portfolio:
    """投资组合"""
    cash: float = 1000000.0  # 初始资金100万
    positions: Dict[str, Position] = field(default_factory=dict)
    trades: List[Trade] = field(default_factory=list)
    
    def update_price(self, prices: Dict[str, float]):
        """更新持仓价格"""
        for code, price in prices.items():
            if code in self.positions:
                self.positions[code].current_price = price
    
    @property
    def total_value(self) -> float:
        """总资产"""
        position_value = sum(p.market_value for p in self.positions.values())
        return self.cash + position_value
    
    @property
    def position_value(self) -> float:
        """持仓市值"""
        return sum(p.market_value for p in self.positions.values())
    
class BaseStrategy:
    """策略基类"""
    
    def __init__(self):
        self.params = {}
        
    def set_params(self, **kwargs):
        """设置参数"""
        self.params.update(kwargs)
        return self
    
    def init(self, data):
        """初始化策略（在回测开始前调用）"""
        pass
    
    def on_bar(self, data, portfolio):
        """
        处理每个bar的数据n        
        Args:
            data: 当前bar的DataFrame数据
            portfolio: 当前投资组合n            
        Returns:
            dict: 交易信号 {'code': action} 
                  action: 1(买入), -1(卖出), 0(持有)
        """
        return {}


@dataclass
class BacktestResult:
    """回测结果"""
    strategy_name: str
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_value: float
    total_return: float
    annual_return: float
    max_drawdown: float
    sharpe_ratio: float
    total_trades: int
    win_rate: float
    
    # 详细数据
    daily_returns: pd.Series = None
    equity_curve: pd.Series = None
    trades: List[Trade] = None
    
    def summary(self) -> str:
        """生成回测摘要"""
        return f"""
{'='*60}
回测结果: {self.strategy_name}
{'='*60}
回测区间: {self.start_date.strftime('%Y-%m-%d')} ~ {self.end_date.strftime('%Y-%m-%d')}
初始资金: {self.initial_capital:,.2f}
最终资金: {self.final_value:,.2f}
{'-'*60}
总收益率: {self.total_return:.2%}
年化收益: {self.annual_return:.2%}
最大回撤: {self.max_drawdown:.2%}
夏普比率: {self.sharpe_ratio:.2f}
{'-'*60}
交易次数: {self.total_trades}
胜率: {self.win_rate:.2%}
{'='*60}
"""


class BacktestEngine:
    """回测引擎"""
    
    def __init__(self, 
                 initial_capital: float = 1000000.0,
                 commission_rate: float = 0.0003,  # 手续费万3
                 slippage: float = 0.001):       # 滑点千1
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.slippage = slippage
        self.portfolio = None
        
    def run(self, 
            data: Dict[str, pd.DataFrame], 
            strategy: BaseStrategy,
            start_date: str = None,
            end_date: str = None) -> BacktestResult:
        """
        运行回测n        
        Args:
            data: 股票数据字典 {code: DataFrame}
            strategy: 策略对象
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            BacktestResult: 回测结果n        """
        # 初始化投资组合
        self.portfolio = Portfolio(cash=self.initial_capital)
        
        # 合并所有股票的日期
        all_dates = set()
        for code, df in data.items():
            if '日期' in df.columns:
                all_dates.update(df['日期'].tolist())
        
        all_dates = sorted(all_dates)
        
        # 过滤日期范围
        if start_date:
            all_dates = [d for d in all_dates if d >= start_date]
        if end_date:
            all_dates = [d for d in all_dates if d <= end_date]
        
        if not all_dates:
            raise ValueError("没有可回测的数据")
        
        # 策略初始化
        strategy.init(data)
        
        # 记录每日净值
        equity_curve = []
        daily_returns = []
        
        print(f"开始回测: {len(all_dates)} 个交易日")
        
        # 遍历每个交易日
        for i, date in enumerate(all_dates):
            # 获取当前日期的数据
            current_data = {}
            current_prices = {}
            
            for code, df in data.items():
                day_data = df[df['日期'] == date]
                if not day_data.empty:
                    current_data[code] = day_data
                    current_prices[code] = day_data['close'].iloc[0]
            
            # 更新持仓价格
            self.portfolio.update_price(current_prices)
            
            # 生成交易信号
            signals = strategy.on_bar(current_data, self.portfolio)
            
            # 执行交易
            for code, action in signals.items():
                if code in current_prices:
                    self._execute_trade(date, code, action, current_prices[code])
            
            # 记录净值
            equity = self.portfolio.total_value
            equity_curve.append(equity)
            
            if i > 0:
                daily_return = (equity - equity_curve[i-1]) / equity_curve[i-1]
                daily_returns.append(daily_return)
        
        print(f"回测完成: {len(all_dates)} 个交易日")
        
        # 计算绩效指标
        result = self._calculate_performance(
            strategy=strategy.__class__.__name__,
            start_date=all_dates[0],
            end_date=all_dates[-1],
            initial_capital=self.initial_capital,
            final_value=equity_curve[-1],
            daily_returns=pd.Series(daily_returns),
            equity_curve=pd.Series(equity_curve),
            trades=self.portfolio.trades
        )
        
        print(result.summary())
        
        return result
    
    def _execute_trade(self, date, code, action, price):
        """执行交易"""
        # 考虑滑点
        if action == 1:  # 买入
            adjusted_price = price * (1 + self.slippage)
        else:  # 卖出
            adjusted_price = price * (1 - self.slippage)
        
        # 计算可买入数量（假设全仓买入）
        if action == 1:
            # 计算手续费
            max_amount = self.portfolio.cash / (1 + self.commission_rate)
            volume = int(max_amount / adjusted_price / 100) * 100  # 整手
            
            if volume > 0:
                amount = volume * adjusted_price
                commission = amount * self.commission_rate
                
                # 更新持仓
                if code in self.portfolio.positions:
                    pos = self.portfolio.positions[code]
                    total_cost = pos.avg_cost * pos.volume + amount
                    pos.volume += volume
                    pos.avg_cost = total_cost / pos.volume
                else:
                    self.portfolio.positions[code] = Position(
                        code=code, volume=volume, avg_cost=adjusted_price
                    )
                
                # 更新现金
                self.portfolio.cash -= (amount + commission)
                
                # 记录交易
                trade = Trade(
                    date=date, code=code, action='buy',
                    price=adjusted_price, volume=volume,
                    amount=amount, commission=commission
                )
                self.portfolio.trades.append(trade)
                
        elif action == -1:  # 卖出
            if code in self.portfolio.positions:
                pos = self.portfolio.positions[code]
                if pos.volume > 0:
                    volume = pos.volume  # 全仓卖出
                    amount = volume * adjusted_price
                    commission = amount * self.commission_rate
                    
                    # 更新现金
                    self.portfolio.cash += (amount - commission)
                    
                    # 清空持仓
                    del self.portfolio.positions[code]
                    
                    # 记录交易
                    trade = Trade(
                        date=date, code=code, action='sell',
                        price=adjusted_price, volume=volume,
                        amount=amount, commission=commission
                    )
                    self.portfolio.trades.append(trade)
    
    def _calculate_performance(self, **kwargs) -> 'BacktestResult':
        """计算回测绩效"""
        from src.backtest.engine import BacktestResult
        
        # 计算年化收益率
        total_days = (kwargs['end_date'] - kwargs['start_date']).days
        years = total_days / 365
        annual_return = (kwargs['final_value'] / kwargs['initial_capital']) ** (1/years) - 1 if years > 0 else 0
        
        # 计算最大回撤
        equity_curve = kwargs['equity_curve']
        cummax = equity_curve.cummax()
        drawdown = (equity_curve - cummax) / cummax
        max_drawdown = drawdown.min()
        
        # 计算夏普比率
        daily_returns = kwargs['daily_returns']
        if len(daily_returns) > 0 and daily_returns.std() != 0:
            sharpe_ratio = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)
        else:
            sharpe_ratio = 0
        
        # 计算胜率
        trades = kwargs['trades']
        if trades:
            profit_trades = [t for t in trades if t.action == 'sell']
            win_rate = len([t for t in profit_trades if t.amount > 0]) / len(profit_trades) if profit_trades else 0
        else:
            win_rate = 0
        
        return BacktestResult(
            strategy_name=kwargs['strategy'],
            start_date=kwargs['start_date'],
            end_date=kwargs['end_date'],
            initial_capital=kwargs['initial_capital'],
            final_value=kwargs['final_value'],
            total_return=kwargs['final_value'] / kwargs['initial_capital'] - 1,
            annual_return=annual_return,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            total_trades=len(trades),
            win_rate=win_rate,
            daily_returns=daily_returns,
            equity_curve=equity_curve,
            trades=trades
        )


if __name__ == "__main__":
    # Run full workflow
    run_full_workflow()
