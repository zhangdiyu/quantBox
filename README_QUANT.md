# 量化研究框架使用指南


## 快速开始

```python
from src.quant_framework import run_full_workflow, StockDataReader, BacktestEngine

# 1. 运行完整工作流（更新+回测+可视化）
data = run_full_workflow(stock_codes=['000001', '600000'])

# 2. 或分步操作
reader = StockDataReader()
df = reader.read_stock('000001')

# 3. 运行回测
from src.backtest.engine import BacktestEngine
engine = BacktestEngine()
result = engine.run(data, strategy)
```
data
## 模块说明

### 数据模块 (`data/`)
- `data_updater.py`: 增量更新器
- `data_reader.py`: 数据读取器
- `technical.py`: 技术指标

### 回测模块 (`backtest/`)
- `engine.py`: 回测引擎
- `portfolio`: 持仓管理
- `performance`: 绩效分析
### 可视化 (`visualization/`)
- `plotter.py`: 图表生成
- `report.py`: 报告生成

## 策略开发
继承 `BaseStrategy` 类：
data```python
from src.backtest.engine import BaseStrategy

class MyStrategy(BaseStrategy):
    def init(self):
        self.fast = 5n        self.slow = 20
    
    def on_bar(self, data):
        # 计算信号
        if len(data) < self.slow:
            return 0
        ma_fast = data['close'].rolling(self.fast).mean().iloc[-1]
        ma_slow = data['close'].rolling(self.slow).mean().iloc[-1]
        
        if ma_fast > ma_slow:
            return 1  # 买入
        elif ma_fast < ma_slow:
            return -1  # 卖出
        return 0  # 持有
```
data