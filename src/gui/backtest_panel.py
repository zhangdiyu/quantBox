# -*- coding: utf-8 -*-
"""
策略回测面板 - 完整功能实现
支持双均线、MACD、RSI、布林带、自定义策略
"""
from pathlib import Path
import pandas as pd
import numpy as np
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QComboBox, QTextEdit, QSplitter,
    QGroupBox, QFormLayout, QDoubleSpinBox, QSpinBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QDateEdit, QMessageBox, QStackedWidget,
    QSizePolicy
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QFont

import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

DATA_DIR = Path(__file__).parent.parent.parent / "data"


# --------------------------------------------------------------------------- #
#  策略逻辑 (向量化)
# --------------------------------------------------------------------------- #

def strategy_dual_ma(df: pd.DataFrame, fast_period: int, slow_period: int) -> pd.DataFrame:
    """双均线策略: 快线上穿慢线买入, 下穿卖出"""
    df = df.copy()
    df['ma_fast'] = df['close'].rolling(window=fast_period, min_periods=1).mean()
    df['ma_slow'] = df['close'].rolling(window=slow_period, min_periods=1).mean()
    df['signal'] = 0
    cross_up = (df['ma_fast'] > df['ma_slow']) & (df['ma_fast'].shift(1) <= df['ma_slow'].shift(1))
    cross_down = (df['ma_fast'] < df['ma_slow']) & (df['ma_fast'].shift(1) >= df['ma_slow'].shift(1))
    df.loc[cross_up, 'signal'] = 1
    df.loc[cross_down, 'signal'] = -1
    return df


def strategy_macd(df: pd.DataFrame, fast: int, slow: int, signal: int) -> pd.DataFrame:
    """MACD策略: DIF上穿DEA买入, 下穿卖出"""
    df = df.copy()
    ema_f = df['close'].ewm(span=fast, adjust=False).mean()
    ema_s = df['close'].ewm(span=slow, adjust=False).mean()
    dif = ema_f - ema_s
    dea = dif.ewm(span=signal, adjust=False).mean()
    df['dif'] = dif
    df['dea'] = dea
    df['signal'] = 0
    cross_up = (dif > dea) & (dif.shift(1) <= dea.shift(1))
    cross_down = (dif < dea) & (dif.shift(1) >= dea.shift(1))
    df.loc[cross_up, 'signal'] = 1
    df.loc[cross_down, 'signal'] = -1
    return df


def strategy_rsi(df: pd.DataFrame, period: int, oversold: float, overbought: float) -> pd.DataFrame:
    """RSI策略: RSI<oversold买入, RSI>overbought卖出"""
    df = df.copy()
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0.0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(window=period).mean()
    rs = gain / loss.replace(0, 1e-10)
    rsi = (100 - (100 / (1 + rs))).fillna(50)
    df['rsi'] = rsi
    df['signal'] = 0
    df.loc[rsi < oversold, 'signal'] = 1
    df.loc[rsi > overbought, 'signal'] = -1
    return df


def strategy_bollinger(df: pd.DataFrame, period: int, std_dev: float) -> pd.DataFrame:
    """布林带策略: 价格触及下轨买入, 触及上轨卖出"""
    df = df.copy()
    mid = df['close'].rolling(window=period, min_periods=1).mean()
    std = df['close'].rolling(window=period, min_periods=1).std()
    upper = mid + std_dev * std
    lower = mid - std_dev * std
    df['bb_upper'] = upper
    df['bb_lower'] = lower
    df['signal'] = 0
    touch_lower = df['low'] <= lower
    touch_upper = df['high'] >= upper
    df.loc[touch_lower, 'signal'] = 1
    df.loc[touch_upper, 'signal'] = -1
    return df


def run_custom_strategy(df: pd.DataFrame, code: str) -> pd.DataFrame:
    """执行自定义策略代码, 必须定义 generate_signals(df) 返回带 signal 列的 DataFrame"""
    if not code.strip():
        raise ValueError("自定义策略代码不能为空")
    safe_builtins = {
        'pd': pd, 'np': np, 'DataFrame': pd.DataFrame, 'Series': pd.Series,
        'len': len, 'range': range, 'min': min, 'max': max, 'abs': abs,
        'sum': sum, 'round': round, 'zip': zip, 'enumerate': enumerate,
        'list': list, 'dict': dict, 'float': float, 'int': int, 'bool': bool,
        'True': True, 'False': False, 'None': None,
    }
    local_ns = {'df': df.copy(), **safe_builtins}
    exec(code, {'__builtins__': safe_builtins}, local_ns)
    if 'generate_signals' not in local_ns:
        raise ValueError("自定义策略必须定义函数 generate_signals(df)")
    result = local_ns['generate_signals'](df)
    if 'signal' not in result.columns:
        raise ValueError("generate_signals(df) 必须返回包含 'signal' 列的 DataFrame")
    return result


# --------------------------------------------------------------------------- #
#  回测引擎
# --------------------------------------------------------------------------- #

def run_backtest(df: pd.DataFrame, initial_capital: float, commission_rate: float):
    """
    简单回测引擎
    - 买入信号: 下一根K线开盘价买入, 尽可能多买
    - 卖出信号: 下一根K线开盘价全部卖出
    - 返回: equity_curve (Series), trade_list, metrics_dict
    """
    df = df.copy()
    if 'signal' not in df.columns:
        raise ValueError("DataFrame 必须包含 signal 列 (1=买, -1=卖, 0=持有)")

    n = len(df)
    cash = initial_capital
    shares = 0
    portfolio_value = np.zeros(n)
    equity_curve = np.zeros(n)
    trade_list = []

    for i in range(n):
        price = df['close'].iloc[i]
        signal = df['signal'].iloc[i]

        if i < n - 1:
            next_open = df['open'].iloc[i + 1]
        else:
            next_open = price

        if signal == 1 and i < n - 1:
            if shares == 0 and cash > 0:
                max_shares = int(cash / (next_open * (1 + commission_rate)) / 100) * 100
                if max_shares > 0:
                    cost = max_shares * next_open
                    commission = cost * commission_rate
                    cash -= cost + commission
                    shares = max_shares
                    trade_list.append({
                        'buy_date': df['date'].iloc[i + 1],
                        'sell_date': None,
                        'buy_price': next_open,
                        'sell_price': None,
                        'return_pct': None,
                        'hold_days': None,
                        'shares': max_shares,
                    })

        elif signal == -1 and i < n - 1:
            if shares > 0:
                revenue = shares * next_open
                commission = revenue * commission_rate
                cash += revenue - commission
                buy_info = trade_list[-1]
                buy_info['sell_date'] = df['date'].iloc[i + 1]
                buy_info['sell_price'] = next_open
                ret = (next_open - buy_info['buy_price']) / buy_info['buy_price']
                buy_info['return_pct'] = ret
                buy_info['hold_days'] = (buy_info['sell_date'] - buy_info['buy_date']).days
                shares = 0

        portfolio_value[i] = cash + shares * price
        equity_curve[i] = portfolio_value[i]

    equity_curve = pd.Series(equity_curve, index=df['date'])

    metrics = _calc_metrics(
        equity_curve, trade_list, initial_capital,
        df['date'].iloc[0], df['date'].iloc[-1]
    )
    return equity_curve, trade_list, metrics


def _calc_metrics(equity_curve, trade_list, initial_capital, start_date, end_date):
    """计算绩效指标"""
    final_value = equity_curve.iloc[-1]
    total_return = (final_value / initial_capital - 1) if initial_capital > 0 else 0

    days = (end_date - start_date).days
    years = max(days / 365.0, 1/365)
    annual_return = (final_value / initial_capital) ** (1 / years) - 1 if initial_capital > 0 else 0

    cummax = equity_curve.cummax()
    drawdown = (equity_curve - cummax) / cummax.replace(0, np.nan)
    max_drawdown = drawdown.min() if not drawdown.isna().all() else 0

    daily_returns = equity_curve.pct_change().dropna()
    risk_free = 0.03
    excess = daily_returns - risk_free / 252
    sharpe = (excess.mean() / excess.std() * np.sqrt(252)) if len(excess) > 0 and excess.std() > 0 else 0

    completed = [t for t in trade_list if t['sell_date'] is not None]
    total_trades = len(completed)
    wins = [t for t in completed if t['return_pct'] and t['return_pct'] > 0]
    losses = [t for t in completed if t['return_pct'] and t['return_pct'] <= 0]
    win_count = len(wins)
    loss_count = len(losses)
    win_rate = win_count / total_trades if total_trades > 0 else 0

    avg_win = np.mean([t['return_pct'] for t in wins]) if wins else 0
    avg_loss = abs(np.mean([t['return_pct'] for t in losses])) if losses else 0
    profit_ratio = (avg_win / avg_loss) if avg_loss > 0 else (avg_win if avg_win > 0 else 0)

    avg_hold_days = np.mean([t['hold_days'] for t in completed if t['hold_days']]) if completed else 0

    return {
        '总收益率': total_return,
        '年化收益率': annual_return,
        '最大回撤': max_drawdown,
        '夏普比率': sharpe,
        '胜率': win_rate,
        '交易次数': total_trades,
        '盈利次数': win_count,
        '亏损次数': loss_count,
        '盈亏比': profit_ratio,
        '平均持仓天数': avg_hold_days,
    }


# --------------------------------------------------------------------------- #
#  主面板
# --------------------------------------------------------------------------- #

class BacktestPanel(QWidget):
    """策略回测面板"""

    def __init__(self):
        super().__init__()
        self._stock_items = []
        self._equity_curve = None
        self._trade_list = []
        self._metrics = {}
        self._df_full = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # ----- 顶部控制行 -----
        top_row = QHBoxLayout()

        top_row.addWidget(QLabel("股票:"))
        self.stock_combo = QComboBox()
        self.stock_combo.setMinimumWidth(180)
        self.stock_combo.setEditable(True)
        top_row.addWidget(self.stock_combo)

        top_row.addWidget(QLabel("开始:"))
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setDate(QDate.currentDate().addYears(-2))
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDisplayFormat("yyyy-MM-dd")
        top_row.addWidget(self.start_date_edit)

        top_row.addWidget(QLabel("结束:"))
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setDate(QDate.currentDate())
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDisplayFormat("yyyy-MM-dd")
        top_row.addWidget(self.end_date_edit)

        top_row.addWidget(QLabel("策略:"))
        self.strategy_combo = QComboBox()
        self.strategy_combo.addItems([
            "双均线策略", "MACD策略", "RSI策略", "布林带策略", "自定义策略"
        ])
        self.strategy_combo.currentIndexChanged.connect(self._on_strategy_changed)
        top_row.addWidget(self.strategy_combo)

        top_row.addWidget(QLabel("初始资金:"))
        self.capital_spin = QDoubleSpinBox()
        self.capital_spin.setRange(10000, 100000000)
        self.capital_spin.setValue(1000000)
        self.capital_spin.setPrefix("¥")
        self.capital_spin.setDecimals(0)
        top_row.addWidget(self.capital_spin)

        top_row.addWidget(QLabel("手续费:"))
        self.commission_spin = QDoubleSpinBox()
        self.commission_spin.setRange(0, 0.01)
        self.commission_spin.setValue(0.0003)
        self.commission_spin.setSingleStep(0.0001)
        self.commission_spin.setDecimals(4)
        top_row.addWidget(self.commission_spin)

        self.run_btn = QPushButton("开始回测")
        self.run_btn.setMinimumWidth(100)
        self.run_btn.clicked.connect(self._run_backtest)
        top_row.addWidget(self.run_btn)

        top_row.addStretch()
        layout.addLayout(top_row)

        # ----- 主分割器: 左(参数) | 右(日志+图表+结果) -----
        main_splitter = QSplitter(Qt.Horizontal)

        # 左侧: 策略参数 (动态切换)
        self.params_stack = QStackedWidget()
        self.params_stack.setMinimumWidth(220)
        self.params_stack.setMaximumWidth(280)

        # 双均线参数
        dual_ma_widget = QWidget()
        dual_ma_layout = QFormLayout(dual_ma_widget)
        self.fast_ma_spin = QSpinBox()
        self.fast_ma_spin.setRange(1, 100)
        self.fast_ma_spin.setValue(5)
        dual_ma_layout.addRow("短期均线:", self.fast_ma_spin)
        self.slow_ma_spin = QSpinBox()
        self.slow_ma_spin.setRange(1, 200)
        self.slow_ma_spin.setValue(20)
        dual_ma_layout.addRow("长期均线:", self.slow_ma_spin)
        self.params_stack.addWidget(dual_ma_widget)

        # MACD参数
        macd_widget = QWidget()
        macd_layout = QFormLayout(macd_widget)
        self.macd_fast_spin = QSpinBox()
        self.macd_fast_spin.setRange(2, 50)
        self.macd_fast_spin.setValue(12)
        macd_layout.addRow("快线周期:", self.macd_fast_spin)
        self.macd_slow_spin = QSpinBox()
        self.macd_slow_spin.setRange(5, 100)
        self.macd_slow_spin.setValue(26)
        macd_layout.addRow("慢线周期:", self.macd_slow_spin)
        self.macd_signal_spin = QSpinBox()
        self.macd_signal_spin.setRange(2, 30)
        self.macd_signal_spin.setValue(9)
        macd_layout.addRow("信号线:", self.macd_signal_spin)
        self.params_stack.addWidget(macd_widget)

        # RSI参数
        rsi_widget = QWidget()
        rsi_layout = QFormLayout(rsi_widget)
        self.rsi_period_spin = QSpinBox()
        self.rsi_period_spin.setRange(2, 50)
        self.rsi_period_spin.setValue(14)
        rsi_layout.addRow("RSI周期:", self.rsi_period_spin)
        self.rsi_oversold_spin = QSpinBox()
        self.rsi_oversold_spin.setRange(5, 50)
        self.rsi_oversold_spin.setValue(30)
        rsi_layout.addRow("超卖阈值:", self.rsi_oversold_spin)
        self.rsi_overbought_spin = QSpinBox()
        self.rsi_overbought_spin.setRange(50, 95)
        self.rsi_overbought_spin.setValue(70)
        rsi_layout.addRow("超买阈值:", self.rsi_overbought_spin)
        self.params_stack.addWidget(rsi_widget)

        # 布林带参数
        boll_widget = QWidget()
        boll_layout = QFormLayout(boll_widget)
        self.boll_period_spin = QSpinBox()
        self.boll_period_spin.setRange(5, 100)
        self.boll_period_spin.setValue(20)
        boll_layout.addRow("周期:", self.boll_period_spin)
        self.boll_std_spin = QDoubleSpinBox()
        self.boll_std_spin.setRange(1.0, 5.0)
        self.boll_std_spin.setValue(2.0)
        self.boll_std_spin.setSingleStep(0.1)
        boll_layout.addRow("标准差倍数:", self.boll_std_spin)
        self.params_stack.addWidget(boll_widget)

        # 自定义策略代码
        custom_widget = QWidget()
        custom_layout = QVBoxLayout(custom_widget)
        custom_layout.addWidget(QLabel("Python 代码 (定义 generate_signals(df)):"))
        self.custom_code_edit = QTextEdit()
        default_code = (
            "def generate_signals(df):\n"
            "    df = df.copy()\n"
            "    df['ma5'] = df['close'].rolling(5).mean()\n"
            "    df['ma20'] = df['close'].rolling(20).mean()\n"
            "    df['signal'] = 0\n"
            "    cross_up = (df['ma5'] > df['ma20']) & (df['ma5'].shift(1) <= df['ma20'].shift(1))\n"
            "    cross_down = (df['ma5'] < df['ma20']) & (df['ma5'].shift(1) >= df['ma20'].shift(1))\n"
            "    df.loc[cross_up, 'signal'] = 1\n"
            "    df.loc[cross_down, 'signal'] = -1\n"
            "    return df"
        )
        self.custom_code_edit.setPlainText(default_code)
        self.custom_code_edit.setFont(QFont("Consolas", 9))
        self.custom_code_edit.setMinimumHeight(120)
        custom_layout.addWidget(self.custom_code_edit)
        self.params_stack.addWidget(custom_widget)

        params_group = QGroupBox("策略参数")
        params_group_layout = QVBoxLayout(params_group)
        params_group_layout.addWidget(self.params_stack)
        main_splitter.addWidget(params_group)

        # 右侧: 垂直分割 日志 | 图表 | 指标+交易
        right_splitter = QSplitter(Qt.Vertical)

        # 日志
        log_group = QGroupBox("回测日志")
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(100)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.append("等待回测开始...")
        log_layout.addWidget(self.log_text)
        right_splitter.addWidget(log_group)

        # 图表
        chart_group = QGroupBox("净值曲线")
        chart_layout = QVBoxLayout(chart_group)
        self.figure = Figure(facecolor='#1a1a2e')
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.canvas.setMinimumHeight(200)
        chart_layout.addWidget(self.canvas)
        right_splitter.addWidget(chart_group)

        # 底部: 指标表格 + 交易列表
        bottom_splitter = QSplitter(Qt.Horizontal)

        metrics_group = QGroupBox("绩效指标")
        metrics_layout = QVBoxLayout(metrics_group)
        self.metrics_table = QTableWidget()
        self.metrics_table.setColumnCount(2)
        self.metrics_table.setHorizontalHeaderLabels(["指标", "数值"])
        self.metrics_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        metric_names = [
            "总收益率", "年化收益率", "最大回撤", "夏普比率",
            "胜率", "交易次数", "盈利次数", "亏损次数", "盈亏比", "平均持仓天数"
        ]
        self.metrics_table.setRowCount(len(metric_names))
        for i, name in enumerate(metric_names):
            self.metrics_table.setItem(i, 0, QTableWidgetItem(name))
            self.metrics_table.setItem(i, 1, QTableWidgetItem("-"))
        metrics_layout.addWidget(self.metrics_table)
        bottom_splitter.addWidget(metrics_group)

        trades_group = QGroupBox("交易记录")
        trades_layout = QVBoxLayout(trades_group)
        self.trades_table = QTableWidget()
        self.trades_table.setColumnCount(6)
        self.trades_table.setHorizontalHeaderLabels(
            ["买入日期", "卖出日期", "买入价", "卖出价", "收益率", "持仓天数"]
        )
        self.trades_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        trades_layout.addWidget(self.trades_table)
        bottom_splitter.addWidget(trades_group)

        right_splitter.addWidget(bottom_splitter)
        right_splitter.setStretchFactor(1, 2)
        right_splitter.setStretchFactor(2, 1)

        main_splitter.addWidget(right_splitter)
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)

        layout.addWidget(main_splitter)

        self._scan_stocks()
        self._on_strategy_changed(0)

    def _scan_stocks(self):
        """扫描 DATA_DIR 下的 CSV 文件"""
        self._stock_items = []
        if DATA_DIR.exists():
            for f in sorted(DATA_DIR.glob("*.csv")):
                parts = f.stem.split("_", 1)
                code = parts[0]
                name = parts[1] if len(parts) > 1 else ""
                self._stock_items.append((code, name, str(f)))
        self.stock_combo.clear()
        for code, name, _ in self._stock_items:
            self.stock_combo.addItem(f"{code} {name}")

    def _on_strategy_changed(self, index):
        self.params_stack.setCurrentIndex(index)

    def _read_csv(self, filepath: Path) -> pd.DataFrame:
        """读取 CSV, 统一列名"""
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
        if required - set(df.columns):
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

    def _run_backtest(self):
        idx = self.stock_combo.currentIndex()
        if idx < 0 or idx >= len(self._stock_items):
            QMessageBox.warning(self, "提示", "请先选择一只股票")
            return

        code, name, filepath = self._stock_items[idx]
        df = self._read_csv(Path(filepath))
        if df is None or df.empty:
            QMessageBox.warning(self, "错误", "无法读取数据或数据为空")
            return

        sd = pd.Timestamp(self.start_date_edit.date().toPyDate())
        ed = pd.Timestamp(self.end_date_edit.date().toPyDate())
        df = df[(df['date'] >= sd) & (df['date'] <= ed)].copy()
        if df.empty:
            QMessageBox.warning(self, "错误", "所选日期范围内没有数据")
            return

        strategy_name = self.strategy_combo.currentText()
        initial_capital = self.capital_spin.value()
        commission = self.commission_spin.value()

        self.log_text.clear()
        self.log_text.append("=" * 50)
        self.log_text.append("开始回测...")
        self.log_text.append(f"股票: {code} {name}")
        self.log_text.append(f"日期: {df['date'].iloc[0].strftime('%Y-%m-%d')} ~ {df['date'].iloc[-1].strftime('%Y-%m-%d')}")
        self.log_text.append(f"策略: {strategy_name}")
        self.log_text.append(f"初始资金: ¥{initial_capital:,.0f}, 手续费: {commission*100:.2f}%")
        self.log_text.append("=" * 50)

        try:
            if strategy_name == "双均线策略":
                df = strategy_dual_ma(df, self.fast_ma_spin.value(), self.slow_ma_spin.value())
            elif strategy_name == "MACD策略":
                df = strategy_macd(
                    df, self.macd_fast_spin.value(),
                    self.macd_slow_spin.value(), self.macd_signal_spin.value()
                )
            elif strategy_name == "RSI策略":
                df = strategy_rsi(
                    df, self.rsi_period_spin.value(),
                    self.rsi_oversold_spin.value(), self.rsi_overbought_spin.value()
                )
            elif strategy_name == "布林带策略":
                df = strategy_bollinger(
                    df, self.boll_period_spin.value(), self.boll_std_spin.value()
                )
            elif strategy_name == "自定义策略":
                df = run_custom_strategy(df, self.custom_code_edit.toPlainText())
        except Exception as e:
            self.log_text.append(f"\n[错误] {str(e)}")
            QMessageBox.critical(self, "策略执行错误", str(e))
            return

        try:
            equity_curve, trade_list, metrics = run_backtest(df, initial_capital, commission)
        except Exception as e:
            self.log_text.append(f"\n[回测错误] {str(e)}")
            QMessageBox.critical(self, "回测错误", str(e))
            return

        self._equity_curve = equity_curve
        self._trade_list = trade_list
        self._metrics = metrics
        self._df_full = df

        self.log_text.append(f"\n回测完成!")
        self.log_text.append(f"总收益率: {metrics['总收益率']:.2%}")
        self.log_text.append(f"交易次数: {metrics['交易次数']}")

        self._update_metrics_table(metrics)
        self._update_trades_table(trade_list)
        self._draw_equity_chart(df, equity_curve, trade_list, initial_capital)

    def _update_metrics_table(self, metrics):
        fmt_map = {
            '总收益率': lambda x: f"{x:.2%}",
            '年化收益率': lambda x: f"{x:.2%}",
            '最大回撤': lambda x: f"{x:.2%}",
            '夏普比率': lambda x: f"{x:.2f}",
            '胜率': lambda x: f"{x:.2%}",
            '交易次数': lambda x: f"{int(x)}",
            '盈利次数': lambda x: f"{int(x)}",
            '亏损次数': lambda x: f"{int(x)}",
            '盈亏比': lambda x: f"{x:.2f}",
            '平均持仓天数': lambda x: f"{x:.1f}",
        }
        for i in range(self.metrics_table.rowCount()):
            name = self.metrics_table.item(i, 0).text()
            val = metrics.get(name, 0)
            self.metrics_table.setItem(i, 1, QTableWidgetItem(fmt_map.get(name, str)(val)))

    def _update_trades_table(self, trade_list):
        completed = [t for t in trade_list if t['sell_date'] is not None]
        self.trades_table.setRowCount(len(completed))
        for i, t in enumerate(completed):
            buy_d = t['buy_date'].strftime('%Y-%m-%d') if hasattr(t['buy_date'], 'strftime') else str(t['buy_date'])
            sell_d = t['sell_date'].strftime('%Y-%m-%d') if hasattr(t['sell_date'], 'strftime') else str(t['sell_date'])
            self.trades_table.setItem(i, 0, QTableWidgetItem(buy_d))
            self.trades_table.setItem(i, 1, QTableWidgetItem(sell_d))
            self.trades_table.setItem(i, 2, QTableWidgetItem(f"{t['buy_price']:.2f}"))
            self.trades_table.setItem(i, 3, QTableWidgetItem(f"{t['sell_price']:.2f}"))
            ret_str = f"{t['return_pct']:.2%}" if t['return_pct'] is not None else "-"
            self.trades_table.setItem(i, 4, QTableWidgetItem(ret_str))
            self.trades_table.setItem(i, 5, QTableWidgetItem(str(t.get('hold_days', '-'))))

    def _draw_equity_chart(self, df, equity_curve, trade_list, initial_capital):
        self.figure.clear()
        ax1 = self.figure.add_subplot(211)
        ax2 = self.figure.add_subplot(212, sharex=ax1)

        dates = df['date'].values
        x = np.arange(len(dates))

        # 策略净值
        ax1.plot(x, equity_curve.values, color='#00d4ff', linewidth=1.5, label='策略净值')

        # 买入持有
        first_close = df['close'].iloc[0]
        bh = initial_capital * (df['close'] / first_close)
        ax1.plot(x, bh.values, color='#888', linewidth=1, linestyle='--', label='买入持有')

        # 买卖标记
        buy_x, buy_y = [], []
        sell_x, sell_y = [], []
        for t in trade_list:
            bd = t['buy_date']
            for i, d in enumerate(df['date']):
                if d == bd:
                    buy_x.append(i)
                    buy_y.append(equity_curve.iloc[i] if i < len(equity_curve) else equity_curve.iloc[-1])
                    break
            sd = t.get('sell_date')
            if sd is not None:
                for i, d in enumerate(df['date']):
                    if d == sd and i < len(equity_curve):
                        sell_x.append(i)
                        sell_y.append(equity_curve.iloc[i])
                        break
        if buy_x:
            ax1.scatter(buy_x, buy_y, color='#26a69a', s=40, marker='^', zorder=5, label='买入')
        if sell_x:
            ax1.scatter(sell_x, sell_y, color='#ef5350', s=40, marker='v', zorder=5, label='卖出')

        ax1.set_facecolor('#1a1a2e')
        ax1.tick_params(colors='white')
        ax1.set_ylabel('净值', color='white')
        ax1.legend(loc='upper left', fontsize=8, facecolor='#1a1a2e', labelcolor='white')
        ax1.grid(True, color='#333', alpha=0.5)
        ax1.set_xlim(0, len(x) - 1)

        # 回撤子图
        cummax = equity_curve.cummax()
        drawdown = (equity_curve - cummax) / cummax.replace(0, np.nan)
        ax2.fill_between(x, 0, drawdown.values, color='#ef5350', alpha=0.5)
        ax2.set_facecolor('#1a1a2e')
        ax2.tick_params(colors='white')
        ax2.set_ylabel('回撤', color='white')
        ax2.grid(True, color='#333', alpha=0.5)
        ax2.set_xlabel('日期', color='white')

        self.figure.tight_layout()
        self.canvas.draw()
