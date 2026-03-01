# QuantBox 量化研究框架

<p align="center">
  <img src="https://img.shields.io/badge/version-1.0.0-blue.svg" alt="version">
  <img src="https://img.shields.io/badge/python-3.8+-blue.svg" alt="python">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="license">
</p>

<p align="center">
  <b>完整的A股量化研究解决方案</b><br>
  数据获取 → 技术指标 → 策略回测 → 可视化报告
</p>

---

## 📋 目录

- [功能特性](#-功能特性)
- [快速开始](#-快速开始)
- [详细文档](#-详细文档)
  - [数据模块](#数据模块)
  - [技术指标](#技术指标)
  - [策略开发](#策略开发)
  - [回测引擎](#回测引擎)
  - [可视化](#可视化)
- [示例代码](#-示例代码)
- [API参考](#-api参考)
- [常见问题](#-常见问题)
- [更新日志](#-更新日志)

---

## ✨ 功能特性

### 🔄 智能数据管理
- **增量更新**: 自动检测本地数据，只下载最新缺失数据
- **断点续传**: 支持中断后恢复下载，无需重新开始
- **多数据源**: 支持Akshare、Tushare等多种数据源

### 📊 丰富技术指标
- **趋势指标**: MA、EMA、MACD、Bollinger Bands
- **动量指标**: RSI、KDJ、CCI、Williams %R
- **波动指标**: ATR、StdDev、Variance
- **成交量指标**: OBV、Volume MA、Volume RSI

### 🎯 灵活策略开发
- **基类继承**: 简单继承`BaseStrategy`即可开发策略
- **参数优化**: 支持策略参数网格搜索和优化
- **组合策略**: 支持多策略组合和权重配置

### 🏃 高性能回测
- **事件驱动**: 基于事件驱动的回测引擎
- **持仓管理**: 自动处理持仓、资金、交易记录
- **绩效分析**: 自动计算收益率、夏普比率、最大回撤等

### 📈 可视化报告
- **交互式图表**: 使用Plotly生成交互式图表
- **HTML报告**: 自动生成完整的HTML回测报告
- **多维度分析**: 资金曲线、回撤、月度收益、交易分布等

---

## 🚀 快速开始

### 安装依赖

```bash
pip install akshare pandas numpy plotly tqdm
```

### 第一次运行

```python
from src.quant_framework import run_full_workflow

# 运行完整工作流（更新数据 + 回测 + 生成报告）
result = run_full_workflow(
    stock_codes=['000001', '000002', '600000'],  # 股票代码
    strategy=MyStrategy()  # 你的策略
)
```

### 查看报告
运行后会生成HTML报告文件，用浏览器打开即可查看：
- 资金曲线
- 回撤分析
- 月度收益热力图
- 交易分布
- 绩效指标

---

## 📖 详细文档

### 数据模块


#### 1. 增量更新
```python
from src.data_updater import update_stocks

# 更新指定股票列表
update_stocks(['000001', '000002', '600000'])


# 或者使用StockDataUpdater类
from src.quant_framework import StockDataUpdater

updater = StockDataUpdater()
updater.update_stocks(['000001', '000002'])
```

**特点：**
- 自动检测本地已有数据
- 只下载缺失的最新数据
- 自动合并新旧数据，去重
- 支持断点续传

#### 2. 数据读取
```python
from src.data_reader import StockDataReader

reader = StockDataReader()

# 读取单只股票
df = reader.read_stock('000001')
df = reader.read_stock('000001', start_date='2024-01-01', end_date='2024-12-31')

# 读取多只股票
data = reader.read_multiple(['000001', '000002', '600000'])

# 使用缓存（默认开启）
df = reader.read_stock('000001', use_cache=True)
```

**功能：**
- 支持单只/多只股票读取
- 支持日期范围筛选
- 自动缓存加速
- 支持多种文件格式

---

### 技术指标

```python
from src.data_reader import StockDataReader, TechnicalIndicators

reader = StockDataReader()
df = reader.read_stock('000001')

# 计算移动平均线
df = TechnicalIndicators.ma(df, periods=[5, 10, 20, 60])

# 计算指数移动平均
df = TechnicalIndicators.ema(df, periods=[12, 26])

# 计算MACD
df = TechnicalIndicators.macd(df)
# 计算RSI
df = TechnicalIndicators.rsi(df, period=14)

# 计算布林带
df = TechnicalIndicators.bollinger_bands(df, period=20, std=2)

# 一次性计算所有指标
df = TechnicalIndicators.calculate_all(df)

print(df[['日期', '收盘', 'MA5', 'MA20', 'RSI14', 'MACD', 'BB_Upper20'].tail())
```

**支持的指标：**

| 指标 | 方法 | 说明 |
|------|------|------|| MA | `ma(df, periods)` | 简单移动平均线 || EMA | `ema(df, periods)` | 指数移动平均线 || MACD | `macd(df)` | 异同移动平均线 || RSI | `rsi(df, period)` | 相对强弱指数 || Bollinger | `bollinger_bands(df)` | 布林带 |

---

### 策略开发

#### 1. 继承策略基类
```python
from src.backtest_engine import BaseStrategy

class MyStrategy(BaseStrategy):
    def __init__(self):
        super().__init__()
        # 设置默认参数
        self.set_params(fast=5, slow=20)
    
    def on_init(self, data):
        """初始化策略"""
        self.fast = self.params.get('fast', 5)
        self.slow = self.params.get('slow', 20)
    
    def on_bar(self, data, portfolio):
        """
        处理每个bar
        
        Args:
            data: 当前bar的数据 {code: DataFrame}
            portfolio: 当前投资组合
            
        Returns:
            dict: 交易信号 {code: action}
                    action: 1(买入), -1(卖出), 0(持有)
        """
        signals = {}
        
        for code, df in data.items():
            if len(df) < self.slow:
                continue
            
            # 计算均线
            ma_fast = df['收盘'].rolling(self.fast).mean().iloc[-1]
            ma_slow = df['收盘'].rolling(self.slow).mean().iloc[-1]
            
            # 生成信号
            if ma_fast > ma_slow:
                signals[code] = 1  # 买入
            elif ma_fast < ma_slow:
                signals[code] = -1 # 卖出
            else:
                signals[code] = 0  # 持有
        
        return signals
```

#### 2. 参数优化
```python
# 测试不同参数组合
best_result = None
best_params = None
best_return = -float('inf')

for fast in range(3, 21, 2):
    for slow in range(fast+5, 61, 5):
        strategy = MyStrategy()
        strategy.set_params(fast=fast, slow=slow)
        
        result = engine.run(data, strategy)
        
        if result.annual_return > best_return:
            best_return = result.annual_return
            best_result = result
            best_params = {'fast': fast, 'slow': slow}

print(f"最优参数: {best_params}, 年化收益: {best_return:.2%}")
```

#### 3. 多策略组合
```python
class CompositeStrategy(BaseStrategy):
    """组合策略"""
    def __init__(self, strategies, weights=None):
        super().__init__()
        self.strategies = strategies
        self.weights = weights or [1/len(strategies)] * len(strategies)
    
    def on_bar(self, data, portfolio):
        # 收集各策略信号
        all_signals = []
        for strategy in self.strategies:
            signals = strategy.on_bar(data, portfolio)
            all_signals.append(signals)
        
        # 加权合成信号
        final_signals = {}
        for code in set().union(*[s.keys() for s in all_signals]):
            weighted_sum = sum(
                s.get(code, 0) * w 
                for s, w in zip(all_signals, self.weights)
            )
            final_signals[code] = 1 if weighted_sum > 0.3 else (-1 if weighted_sum < -0.3 else 0)
        
        return final_signals
```

---

### 回测引擎

```python
from src.backtest_engine import BacktestEngine

# 创建回测引擎
engine = BacktestEngine(
    initial_capital=1000000,  # 初始资金100万
    commission_rate=0.0003,     # 手续费万3
    slippage=0.001              # 滑点千1
)

# 运行回测
result = engine.run(data, strategy)

# 查看结果
print(result.summary())

# 生成HTML报告
result.to_html('backtest_report.html')
```

**绩效指标：**

| 指标 | 说明 |
|------|------|| 总收益率 | (最终资金 - 初始资金) / 初始资金 || 年化收益率 | 按复利计算的年化收益率 || 最大回撤 | 从高点到低点的最大跌幅 || 夏普比率 | 超额收益与风险的比值 || 胜率 | 盈利交易次数 / 总交易次数 |


---

### 可视化系统

```python
from src.visualization import QuantPlotter

# 创建图表生成器
plotter = QuantPlotter(result)

# 生成资金曲线图
equity_fig = plotter.plot_equity_curve()
equity_fig.show()

# 生成回撤图
drawdown_fig = plotter.plot_drawdown()
drawdown_fig.show()

# 生成月度收益热力图
monthly_fig = plotter.plot_monthly_returns()
monthly_fig.show()

# 生成交易分布图
trade_fig = plotter.plot_trade_distribution()
trade_fig.show()

# 一键生成完整HTML报告
html_path = plotter.generate_report('my_backtest_report.html')
```

**图表类型：**


| 图表 | 说明 |
|------|------|| 资金曲线 | 展示资产总值随时间变化 || 回撤曲线 | 展示从高点回撤的幅度 || 月度收益热力图 | 按年月展示收益率矩阵 || 交易分布 | 展示每笔交易的盈亏分布 |

---

## 🎯 最佳实践

### 1. 数据管理
- **定期更新**: 建议每天收盘后运行数据更新
- **增量下载**: 利用增量更新功能，避免重复下载
- **数据备份**: 定期备份`data/`目录

### 2. 策略开发
- **参数优化**: 使用网格搜索找到最优参数组合
- **过拟合检验**: 区分样本内和样本外测试
- **多策略组合**: 通过组合降低单一策略风险
### 3. 风险管理
- **仓位控制**: 不要全仓单只股票
- **止损设置**: 为每笔交易设置止损点
- **分散投资**: 持有多个行业的股票
### 4. 回测验证
- **样本外测试**: 用未参与优化的数据验证
- **参数稳定性**: 检查参数在小范围变化时的表现
- **交易成本**: 考虑手续费、滑点等成本
---

## 🐛 常见问题

### Q1: 数据下载很慢怎么办？
**A**: 
- 使用增量更新功能，只下载最新数据
- 减少同时下载的股票数量
- 检查网络连接，必要时使用代理
### Q2: 如何添加新的技术指标？
**A**:
在`TechnicalIndicators`类中添加新方法：
```python
@staticmethod
def my_indicator(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    df['MY_IND'] = df['close'].rolling(period).apply(my_calculation)
    return df
```
### Q3: 回测结果和实际交易有差异？
**A**: 
常见原因：
- 滑点设置不合理，实际滑点可能更大
- 没有考虑涨停板、跌停板无法成交的情况
- 回测使用收盘价，实际成交价可能有偏差
- 没有考虑市场冲击成本（大单影响价格）
### Q4: 如何优化策略参数？
**A**:
```python
best_result = None
best_params = None
best_sharpe = -float('inf')

for fast in range(3, 21, 2):
    for slow in range(fast+5, 61, 5):
        strategy = MyStrategy().set_params(fast=fast, slow=slow)
        result = engine.run(data, strategy)
        
        if result.sharpe_ratio > best_sharpe:
            best_sharpe = result.sharpe_ratio
            best_result = result
            best_params = {'fast': fast, 'slow': slow}

print(f"最优参数: {best_params}, 夏普比率: {best_sharpe:.2f}")
```
### Q5: 如何处理停牌股票？
**A**:
在策略中过滤停牌股票：
```python
def on_bar(self, data, portfolio):
    signals = {}
    for code, df in data.items():
        # 跳过停牌股票（成交量为0）
        if df['volume'].iloc[-1] == 0:
            continue
        
        # 正常处理...
        signals[code] = self.calculate_signal(df)
    
    return signals
```
---

## 📞 联系方式

如有问题或建议，欢迎通过以下方式联系：
- **GitHub Issues**: [提交Issue](https://github.com/yourusername/quantbox/issues)
- **Email**: your.email@example.com
---

## 📄 许可证

本项目采用 [MIT License](LICENSE) 开源许可证。
---

<p align="center">
  <b>Happy Quant Trading! 🚀</b>
</p>
