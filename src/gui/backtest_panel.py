# -*- coding: utf-8 -*-
"""
策略回测面板 - 完整功能实现
支持双均线、MACD、RSI、布林带、自定义策略
支持详细交易成本设置（佣金/印花税/滑点）
支持批量多股回测
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
    QSizePolicy, QDialog, QListWidget, QListWidgetItem,
    QLineEdit, QProgressBar, QCheckBox, QFileDialog,
    QAbstractItemView, QApplication
)
from PyQt5.QtCore import Qt, QDate, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor

import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

DATA_DIR = Path(__file__).parent.parent.parent / "data"
ETF_DIR = DATA_DIR / "etf"


# --------------------------------------------------------------------------- #
#  策略逻辑 (向量化)
# --------------------------------------------------------------------------- #

def strategy_dual_ma(df: pd.DataFrame, fast_period: int, slow_period: int) -> pd.DataFrame:
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
    df = df.copy()
    mid = df['close'].rolling(window=period, min_periods=1).mean()
    std = df['close'].rolling(window=period, min_periods=1).std()
    upper = mid + std_dev * std
    lower = mid - std_dev * std
    df['bb_upper'] = upper
    df['bb_lower'] = lower
    df['signal'] = 0
    df.loc[df['low'] <= lower, 'signal'] = 1
    df.loc[df['high'] >= upper, 'signal'] = -1
    return df


def run_custom_strategy(df: pd.DataFrame, code: str) -> pd.DataFrame:
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

def run_backtest(df: pd.DataFrame, initial_capital: float,
                 commission: float = 0.0003,
                 stamp_tax: float = 0.001,
                 slippage: float = 0.0):
    """
    回测引擎
    - commission: 佣金费率 (买卖均收)
    - stamp_tax: 印花税 (仅卖出收取)
    - slippage: 滑点 (买入价上浮, 卖出价下浮)
    """
    df = df.copy()
    if 'signal' not in df.columns:
        raise ValueError("DataFrame 必须包含 signal 列 (1=买, -1=卖, 0=持有)")

    n = len(df)
    cash = initial_capital
    shares = 0
    equity_curve = np.zeros(n)
    trade_list = []

    for i in range(n):
        price = df['close'].iloc[i]
        sig = df['signal'].iloc[i]

        if i < n - 1:
            next_open = df['open'].iloc[i + 1]
        else:
            next_open = price

        if sig == 1 and i < n - 1 and shares == 0 and cash > 0:
            exec_price = next_open * (1 + slippage)
            buy_cost_rate = 1 + commission
            max_shares = int(cash / (exec_price * buy_cost_rate) / 100) * 100
            if max_shares > 0:
                cost = max_shares * exec_price
                comm = cost * commission
                cash -= cost + comm
                shares = max_shares
                trade_list.append({
                    'buy_date': df['date'].iloc[i + 1],
                    'sell_date': None,
                    'buy_price': exec_price,
                    'sell_price': None,
                    'return_pct': None,
                    'hold_days': None,
                    'shares': max_shares,
                })

        elif sig == -1 and i < n - 1 and shares > 0:
            exec_price = next_open * (1 - slippage)
            revenue = shares * exec_price
            comm = revenue * commission
            tax = revenue * stamp_tax
            cash += revenue - comm - tax
            buy_info = trade_list[-1]
            buy_info['sell_date'] = df['date'].iloc[i + 1]
            buy_info['sell_price'] = exec_price
            ret = (exec_price - buy_info['buy_price']) / buy_info['buy_price']
            buy_info['return_pct'] = ret
            buy_info['hold_days'] = (buy_info['sell_date'] - buy_info['buy_date']).days
            shares = 0

        equity_curve[i] = cash + shares * price

    equity_curve = pd.Series(equity_curve, index=df['date'])
    metrics = _calc_metrics(equity_curve, trade_list, initial_capital,
                            df['date'].iloc[0], df['date'].iloc[-1])
    return equity_curve, trade_list, metrics


def _calc_metrics(equity_curve, trade_list, initial_capital, start_date, end_date):
    final_value = equity_curve.iloc[-1]
    total_return = (final_value / initial_capital - 1) if initial_capital > 0 else 0

    days = (end_date - start_date).days
    years = max(days / 365.0, 1 / 365)
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
#  CSV 读取
# --------------------------------------------------------------------------- #

def read_csv(filepath: Path) -> pd.DataFrame:
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


# --------------------------------------------------------------------------- #
#  批量回测后台线程
# --------------------------------------------------------------------------- #

class BatchBacktestThread(QThread):
    progress = pyqtSignal(int, int, str)   # current, total, stock_label
    finished = pyqtSignal(list)            # list of result dicts
    error = pyqtSignal(str)

    def __init__(self, stock_items, strategy_fn, strategy_kwargs,
                 start_date, end_date, initial_capital,
                 commission, stamp_tax, slippage):
        super().__init__()
        self.stock_items = stock_items
        self.strategy_fn = strategy_fn
        self.strategy_kwargs = strategy_kwargs
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.commission = commission
        self.stamp_tax = stamp_tax
        self.slippage = slippage
        self._abort = False

    def abort(self):
        self._abort = True

    def run(self):
        results = []
        total = len(self.stock_items)
        for idx, (code, name, filepath) in enumerate(self.stock_items):
            if self._abort:
                break
            label = f"{code} {name}"
            self.progress.emit(idx, total, label)

            try:
                df = read_csv(Path(filepath))
                if df is None or df.empty:
                    continue
                df = df[(df['date'] >= self.start_date) & (df['date'] <= self.end_date)].copy()
                if len(df) < 30:
                    continue

                df = self.strategy_fn(df, **self.strategy_kwargs)
                eq, trades, metrics = run_backtest(
                    df, self.initial_capital,
                    self.commission, self.stamp_tax, self.slippage
                )
                results.append({
                    'code': code,
                    'name': name,
                    **metrics,
                })
            except Exception:
                continue

        self.progress.emit(total, total, "完成")
        self.finished.emit(results)


# --------------------------------------------------------------------------- #
#  批量回测结果对话框
# --------------------------------------------------------------------------- #

class BatchResultDialog(QDialog):
    def __init__(self, results: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("批量回测结果")
        self.resize(1000, 600)
        self.results = results
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        info = QLabel(f"共回测 {len(self.results)} 只标的")
        info.setStyleSheet("font-size: 13px; font-weight: bold;")
        layout.addWidget(info)

        cols = ["代码", "名称", "总收益率", "年化收益率", "最大回撤",
                "夏普比率", "胜率", "交易次数"]
        self.table = QTableWidget(len(self.results), len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)

        for i, r in enumerate(self.results):
            self.table.setItem(i, 0, QTableWidgetItem(r['code']))
            self.table.setItem(i, 1, QTableWidgetItem(r['name']))
            self._set_pct_item(i, 2, r['总收益率'])
            self._set_pct_item(i, 3, r['年化收益率'])
            self._set_pct_item(i, 4, r['最大回撤'])
            self._set_num_item(i, 5, r['夏普比率'], fmt="{:.2f}")
            self._set_pct_item(i, 6, r['胜率'])
            self._set_num_item(i, 7, r['交易次数'], fmt="{:.0f}")

        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        export_btn = QPushButton("导出CSV")
        export_btn.clicked.connect(self._export_csv)
        btn_row.addStretch()
        btn_row.addWidget(export_btn)
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _set_pct_item(self, row, col, val):
        item = QTableWidgetItem()
        item.setData(Qt.DisplayRole, f"{val:.2%}")
        item.setData(Qt.UserRole, float(val))
        if val > 0:
            item.setForeground(QColor("#26a69a"))
        elif val < 0:
            item.setForeground(QColor("#ef5350"))
        self.table.setItem(row, col, item)

    def _set_num_item(self, row, col, val, fmt="{:.2f}"):
        item = QTableWidgetItem()
        item.setData(Qt.DisplayRole, fmt.format(val))
        item.setData(Qt.UserRole, float(val))
        self.table.setItem(row, col, item)

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "导出", "batch_result.csv", "CSV (*.csv)")
        if not path:
            return
        rows = []
        for r in self.results:
            rows.append({
                '代码': r['code'], '名称': r['name'],
                '总收益率': f"{r['总收益率']:.4f}",
                '年化收益率': f"{r['年化收益率']:.4f}",
                '最大回撤': f"{r['最大回撤']:.4f}",
                '夏普比率': f"{r['夏普比率']:.2f}",
                '胜率': f"{r['胜率']:.4f}",
                '交易次数': int(r['交易次数']),
                '盈利次数': int(r['盈利次数']),
                '亏损次数': int(r['亏损次数']),
                '盈亏比': f"{r['盈亏比']:.2f}",
                '平均持仓天数': f"{r['平均持仓天数']:.1f}",
            })
        pd.DataFrame(rows).to_csv(path, index=False, encoding='utf-8-sig')
        QMessageBox.information(self, "成功", f"已导出至:\n{path}")


# --------------------------------------------------------------------------- #
#  批量选股对话框
# --------------------------------------------------------------------------- #

class BatchSelectDialog(QDialog):
    def __init__(self, stock_items: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("批量回测 - 选择标的")
        self.resize(400, 550)
        self.stock_items = stock_items
        self.selected = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索代码或名称…")
        self.search_edit.textChanged.connect(self._filter)
        layout.addWidget(self.search_edit)

        btn_row = QHBoxLayout()
        sel_all = QPushButton("全选")
        sel_all.clicked.connect(self._select_all)
        btn_row.addWidget(sel_all)
        desel_all = QPushButton("反选")
        desel_all.clicked.connect(self._invert)
        btn_row.addWidget(desel_all)
        self.count_label = QLabel(f"共 {len(self.stock_items)} 只")
        btn_row.addStretch()
        btn_row.addWidget(self.count_label)
        layout.addLayout(btn_row)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.NoSelection)
        for code, name, fp in self.stock_items:
            item = QListWidgetItem(f"{code} {name}")
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            item.setData(Qt.UserRole, (code, name, fp))
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget)

        bottom = QHBoxLayout()
        bottom.addStretch()
        ok_btn = QPushButton("开始回测")
        ok_btn.clicked.connect(self._accept)
        bottom.addWidget(ok_btn)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        bottom.addWidget(cancel_btn)
        layout.addLayout(bottom)

    def _filter(self, text):
        text = text.strip().lower()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setHidden(text != "" and text not in item.text().lower())

    def _select_all(self):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if not item.isHidden():
                item.setCheckState(Qt.Checked)

    def _invert(self):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if not item.isHidden():
                item.setCheckState(Qt.Unchecked if item.checkState() == Qt.Checked else Qt.Checked)

    def _accept(self):
        self.selected = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.Checked:
                self.selected.append(item.data(Qt.UserRole))
        if not self.selected:
            QMessageBox.warning(self, "提示", "请至少选择一只标的")
            return
        self.accept()


# --------------------------------------------------------------------------- #
#  主面板
# --------------------------------------------------------------------------- #

class BacktestPanel(QWidget):

    def __init__(self):
        super().__init__()
        self._stock_items = []
        self._equity_curve = None
        self._trade_list = []
        self._metrics = {}
        self._df_full = None
        self._batch_thread = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # ----- 顶部控制行 -----
        top_row = QHBoxLayout()

        top_row.addWidget(QLabel("数据:"))
        self.data_type_combo = QComboBox()
        self.data_type_combo.addItems(["股票", "ETF"])
        self.data_type_combo.currentIndexChanged.connect(self._scan_stocks)
        top_row.addWidget(self.data_type_combo)

        top_row.addWidget(QLabel("标的:"))
        self.stock_combo = QComboBox()
        self.stock_combo.setMinimumWidth(160)
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

        top_row.addWidget(QLabel("资金:"))
        self.capital_spin = QDoubleSpinBox()
        self.capital_spin.setRange(10000, 100000000)
        self.capital_spin.setValue(1000000)
        self.capital_spin.setPrefix("¥")
        self.capital_spin.setDecimals(0)
        top_row.addWidget(self.capital_spin)

        self.run_btn = QPushButton("开始回测")
        self.run_btn.setMinimumWidth(80)
        self.run_btn.clicked.connect(self._run_backtest)
        top_row.addWidget(self.run_btn)

        self.batch_btn = QPushButton("批量回测")
        self.batch_btn.setMinimumWidth(80)
        self.batch_btn.clicked.connect(self._run_batch)
        top_row.addWidget(self.batch_btn)

        top_row.addStretch()
        layout.addLayout(top_row)

        # 批量回测进度条
        self.batch_progress = QProgressBar()
        self.batch_progress.setVisible(False)
        self.batch_progress.setMaximumHeight(18)
        self.batch_progress.setTextVisible(True)
        layout.addWidget(self.batch_progress)

        # ----- 主分割器: 左(参数+成本) | 右(日志+图表+结果) -----
        main_splitter = QSplitter(Qt.Horizontal)

        # ===== 左侧 =====
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # 策略参数
        self.params_stack = QStackedWidget()

        # 双均线
        dual_ma_w = QWidget()
        fl = QFormLayout(dual_ma_w)
        self.fast_ma_spin = QSpinBox(); self.fast_ma_spin.setRange(1, 100); self.fast_ma_spin.setValue(5)
        fl.addRow("短期均线:", self.fast_ma_spin)
        self.slow_ma_spin = QSpinBox(); self.slow_ma_spin.setRange(1, 200); self.slow_ma_spin.setValue(20)
        fl.addRow("长期均线:", self.slow_ma_spin)
        self.params_stack.addWidget(dual_ma_w)

        # MACD
        macd_w = QWidget()
        fl2 = QFormLayout(macd_w)
        self.macd_fast_spin = QSpinBox(); self.macd_fast_spin.setRange(2, 50); self.macd_fast_spin.setValue(12)
        fl2.addRow("快线周期:", self.macd_fast_spin)
        self.macd_slow_spin = QSpinBox(); self.macd_slow_spin.setRange(5, 100); self.macd_slow_spin.setValue(26)
        fl2.addRow("慢线周期:", self.macd_slow_spin)
        self.macd_signal_spin = QSpinBox(); self.macd_signal_spin.setRange(2, 30); self.macd_signal_spin.setValue(9)
        fl2.addRow("信号线:", self.macd_signal_spin)
        self.params_stack.addWidget(macd_w)

        # RSI
        rsi_w = QWidget()
        fl3 = QFormLayout(rsi_w)
        self.rsi_period_spin = QSpinBox(); self.rsi_period_spin.setRange(2, 50); self.rsi_period_spin.setValue(14)
        fl3.addRow("RSI周期:", self.rsi_period_spin)
        self.rsi_oversold_spin = QSpinBox(); self.rsi_oversold_spin.setRange(5, 50); self.rsi_oversold_spin.setValue(30)
        fl3.addRow("超卖阈值:", self.rsi_oversold_spin)
        self.rsi_overbought_spin = QSpinBox(); self.rsi_overbought_spin.setRange(50, 95); self.rsi_overbought_spin.setValue(70)
        fl3.addRow("超买阈值:", self.rsi_overbought_spin)
        self.params_stack.addWidget(rsi_w)

        # 布林带
        boll_w = QWidget()
        fl4 = QFormLayout(boll_w)
        self.boll_period_spin = QSpinBox(); self.boll_period_spin.setRange(5, 100); self.boll_period_spin.setValue(20)
        fl4.addRow("周期:", self.boll_period_spin)
        self.boll_std_spin = QDoubleSpinBox(); self.boll_std_spin.setRange(1.0, 5.0); self.boll_std_spin.setValue(2.0); self.boll_std_spin.setSingleStep(0.1)
        fl4.addRow("标准差倍数:", self.boll_std_spin)
        self.params_stack.addWidget(boll_w)

        # 自定义
        custom_w = QWidget()
        cl = QVBoxLayout(custom_w)
        cl.addWidget(QLabel("Python (定义 generate_signals(df)):"))
        self.custom_code_edit = QTextEdit()
        self.custom_code_edit.setPlainText(
            "def generate_signals(df):\n"
            "    df = df.copy()\n"
            "    df['ma5'] = df['close'].rolling(5).mean()\n"
            "    df['ma20'] = df['close'].rolling(20).mean()\n"
            "    df['signal'] = 0\n"
            "    up = (df['ma5'] > df['ma20']) & (df['ma5'].shift(1) <= df['ma20'].shift(1))\n"
            "    dn = (df['ma5'] < df['ma20']) & (df['ma5'].shift(1) >= df['ma20'].shift(1))\n"
            "    df.loc[up, 'signal'] = 1\n"
            "    df.loc[dn, 'signal'] = -1\n"
            "    return df"
        )
        self.custom_code_edit.setFont(QFont("Consolas", 9))
        self.custom_code_edit.setMinimumHeight(100)
        cl.addWidget(self.custom_code_edit)
        self.params_stack.addWidget(custom_w)

        params_group = QGroupBox("策略参数")
        pg_layout = QVBoxLayout(params_group)
        pg_layout.addWidget(self.params_stack)
        left_layout.addWidget(params_group)

        # 交易成本设置
        cost_group = QGroupBox("交易成本")
        cost_layout = QFormLayout(cost_group)

        self.comm_spin = QDoubleSpinBox()
        self.comm_spin.setRange(0, 0.003)
        self.comm_spin.setValue(0.0003)
        self.comm_spin.setSingleStep(0.0001)
        self.comm_spin.setDecimals(4)
        self.comm_spin.setSuffix("  (万三)")
        self.comm_spin.valueChanged.connect(self._update_cost_summary)
        cost_layout.addRow("佣金费率:", self.comm_spin)

        self.stamp_spin = QDoubleSpinBox()
        self.stamp_spin.setRange(0, 0.005)
        self.stamp_spin.setValue(0.001)
        self.stamp_spin.setSingleStep(0.0001)
        self.stamp_spin.setDecimals(4)
        self.stamp_spin.setSuffix("  (千一)")
        self.stamp_spin.valueChanged.connect(self._update_cost_summary)
        cost_layout.addRow("印花税(卖):", self.stamp_spin)

        self.slip_spin = QDoubleSpinBox()
        self.slip_spin.setRange(0, 0.005)
        self.slip_spin.setValue(0.0)
        self.slip_spin.setSingleStep(0.0001)
        self.slip_spin.setDecimals(4)
        self.slip_spin.valueChanged.connect(self._update_cost_summary)
        cost_layout.addRow("滑点:", self.slip_spin)

        self.cost_summary = QLabel()
        self.cost_summary.setStyleSheet("color: #aaa; font-size: 11px;")
        cost_layout.addRow(self.cost_summary)
        self._update_cost_summary()

        left_layout.addWidget(cost_group)
        left_layout.addStretch()

        left_widget.setMinimumWidth(220)
        left_widget.setMaximumWidth(280)
        main_splitter.addWidget(left_widget)

        # ===== 右侧 =====
        right_splitter = QSplitter(Qt.Vertical)

        log_group = QGroupBox("回测日志")
        log_lay = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(100)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.append("等待回测开始...")
        log_lay.addWidget(self.log_text)
        right_splitter.addWidget(log_group)

        chart_group = QGroupBox("净值曲线")
        chart_lay = QVBoxLayout(chart_group)
        self.figure = Figure(facecolor='#1a1a2e')
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.canvas.setMinimumHeight(200)
        chart_lay.addWidget(self.canvas)
        right_splitter.addWidget(chart_group)

        bottom_splitter = QSplitter(Qt.Horizontal)

        metrics_group = QGroupBox("绩效指标")
        mg_layout = QVBoxLayout(metrics_group)
        self.metrics_table = QTableWidget()
        self.metrics_table.setColumnCount(2)
        self.metrics_table.setHorizontalHeaderLabels(["指标", "数值"])
        self.metrics_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        metric_names = [
            "总收益率", "年化收益率", "最大回撤", "夏普比率",
            "胜率", "交易次数", "盈利次数", "亏损次数", "盈亏比", "平均持仓天数"
        ]
        self.metrics_table.setRowCount(len(metric_names))
        for i, nm in enumerate(metric_names):
            self.metrics_table.setItem(i, 0, QTableWidgetItem(nm))
            self.metrics_table.setItem(i, 1, QTableWidgetItem("-"))
        mg_layout.addWidget(self.metrics_table)
        bottom_splitter.addWidget(metrics_group)

        trades_group = QGroupBox("交易记录")
        tg_layout = QVBoxLayout(trades_group)
        self.trades_table = QTableWidget()
        self.trades_table.setColumnCount(6)
        self.trades_table.setHorizontalHeaderLabels(
            ["买入日期", "卖出日期", "买入价", "卖出价", "收益率", "持仓天数"]
        )
        self.trades_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tg_layout.addWidget(self.trades_table)
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

    # ------------------------------------------------------------------ #
    #  交易成本
    # ------------------------------------------------------------------ #
    def _update_cost_summary(self):
        comm = self.comm_spin.value()
        stamp = self.stamp_spin.value()
        slip = self.slip_spin.value()
        buy_cost = comm + slip
        sell_cost = comm + stamp + slip
        total = buy_cost + sell_cost
        self.cost_summary.setText(
            f"买入: {buy_cost*100:.3f}%  卖出: {sell_cost*100:.3f}%\n"
            f"单次往返: {total*100:.3f}%"
        )

    # ------------------------------------------------------------------ #
    #  股票扫描
    # ------------------------------------------------------------------ #
    def _scan_stocks(self, _=None):
        self._stock_items = []
        data_dir = ETF_DIR if self.data_type_combo.currentText() == "ETF" else DATA_DIR
        if data_dir.exists():
            for f in sorted(data_dir.glob("*.csv")):
                parts = f.stem.split("_", 1)
                code = parts[0]
                name = parts[1] if len(parts) > 1 else ""
                self._stock_items.append((code, name, str(f)))
        self.stock_combo.clear()
        for code, name, _ in self._stock_items:
            self.stock_combo.addItem(f"{code} {name}")

    def _on_strategy_changed(self, index):
        self.params_stack.setCurrentIndex(index)

    # ------------------------------------------------------------------ #
    #  获取当前策略函数和参数
    # ------------------------------------------------------------------ #
    def _get_strategy_fn_kwargs(self):
        strategy_name = self.strategy_combo.currentText()
        if strategy_name == "双均线策略":
            return strategy_dual_ma, {'fast_period': self.fast_ma_spin.value(), 'slow_period': self.slow_ma_spin.value()}
        elif strategy_name == "MACD策略":
            return strategy_macd, {'fast': self.macd_fast_spin.value(), 'slow': self.macd_slow_spin.value(), 'signal': self.macd_signal_spin.value()}
        elif strategy_name == "RSI策略":
            return strategy_rsi, {'period': self.rsi_period_spin.value(), 'oversold': self.rsi_oversold_spin.value(), 'overbought': self.rsi_overbought_spin.value()}
        elif strategy_name == "布林带策略":
            return strategy_bollinger, {'period': self.boll_period_spin.value(), 'std_dev': self.boll_std_spin.value()}
        else:
            code_text = self.custom_code_edit.toPlainText()
            return lambda df, _code=code_text: run_custom_strategy(df, _code), {}

    def _apply_strategy(self, df):
        fn, kwargs = self._get_strategy_fn_kwargs()
        return fn(df, **kwargs)

    # ------------------------------------------------------------------ #
    #  单股回测
    # ------------------------------------------------------------------ #
    def _run_backtest(self):
        idx = self.stock_combo.currentIndex()
        if idx < 0 or idx >= len(self._stock_items):
            QMessageBox.warning(self, "提示", "请先选择一只标的")
            return

        code, name, filepath = self._stock_items[idx]
        df = read_csv(Path(filepath))
        if df is None or df.empty:
            QMessageBox.warning(self, "错误", "无法读取数据或数据为空")
            return

        sd = pd.Timestamp(self.start_date_edit.date().toPyDate())
        ed = pd.Timestamp(self.end_date_edit.date().toPyDate())
        df = df[(df['date'] >= sd) & (df['date'] <= ed)].copy()
        if df.empty:
            QMessageBox.warning(self, "错误", "所选日期范围内没有数据")
            return

        initial_capital = self.capital_spin.value()
        comm = self.comm_spin.value()
        stamp = self.stamp_spin.value()
        slip = self.slip_spin.value()

        self.log_text.clear()
        self.log_text.append("=" * 50)
        self.log_text.append(f"股票: {code} {name}")
        self.log_text.append(f"日期: {df['date'].iloc[0].strftime('%Y-%m-%d')} ~ {df['date'].iloc[-1].strftime('%Y-%m-%d')}")
        self.log_text.append(f"策略: {self.strategy_combo.currentText()}")
        self.log_text.append(f"资金: ¥{initial_capital:,.0f}")
        self.log_text.append(f"佣金: {comm*100:.2f}%  印花税: {stamp*100:.2f}%  滑点: {slip*100:.2f}%")
        self.log_text.append("=" * 50)

        try:
            df = self._apply_strategy(df)
        except Exception as e:
            self.log_text.append(f"\n[策略错误] {e}")
            QMessageBox.critical(self, "策略执行错误", str(e))
            return

        try:
            equity_curve, trade_list, metrics = run_backtest(
                df, initial_capital, comm, stamp, slip
            )
        except Exception as e:
            self.log_text.append(f"\n[回测错误] {e}")
            QMessageBox.critical(self, "回测错误", str(e))
            return

        self._equity_curve = equity_curve
        self._trade_list = trade_list
        self._metrics = metrics
        self._df_full = df

        self.log_text.append(f"\n回测完成! 总收益率: {metrics['总收益率']:.2%}  交易: {int(metrics['交易次数'])}次")
        self._update_metrics_table(metrics)
        self._update_trades_table(trade_list)
        self._draw_equity_chart(df, equity_curve, trade_list, initial_capital)

    # ------------------------------------------------------------------ #
    #  批量回测
    # ------------------------------------------------------------------ #
    def _run_batch(self):
        if not self._stock_items:
            QMessageBox.warning(self, "提示", "没有可用的数据文件")
            return

        dlg = BatchSelectDialog(self._stock_items, self)
        if dlg.exec_() != QDialog.Accepted or not dlg.selected:
            return

        fn, kwargs = self._get_strategy_fn_kwargs()
        sd = pd.Timestamp(self.start_date_edit.date().toPyDate())
        ed = pd.Timestamp(self.end_date_edit.date().toPyDate())

        self.batch_progress.setVisible(True)
        self.batch_progress.setMaximum(len(dlg.selected))
        self.batch_progress.setValue(0)
        self.batch_btn.setEnabled(False)
        self.run_btn.setEnabled(False)

        self.log_text.clear()
        self.log_text.append(f"批量回测: {len(dlg.selected)} 只标的")
        self.log_text.append(f"策略: {self.strategy_combo.currentText()}")

        self._batch_thread = BatchBacktestThread(
            dlg.selected, fn, kwargs, sd, ed,
            self.capital_spin.value(),
            self.comm_spin.value(), self.stamp_spin.value(), self.slip_spin.value()
        )
        self._batch_thread.progress.connect(self._on_batch_progress)
        self._batch_thread.finished.connect(self._on_batch_done)
        self._batch_thread.start()

    def _on_batch_progress(self, cur, total, label):
        self.batch_progress.setValue(cur)
        self.batch_progress.setFormat(f"{cur}/{total}  {label}")

    def _on_batch_done(self, results):
        self.batch_progress.setVisible(False)
        self.batch_btn.setEnabled(True)
        self.run_btn.setEnabled(True)
        self._batch_thread = None

        if not results:
            QMessageBox.information(self, "提示", "没有有效的回测结果")
            return

        self.log_text.append(f"\n批量回测完成! 有效结果: {len(results)} 只")
        dlg = BatchResultDialog(results, self)
        dlg.exec_()

    # ------------------------------------------------------------------ #
    #  更新 UI
    # ------------------------------------------------------------------ #
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
            nm = self.metrics_table.item(i, 0).text()
            val = metrics.get(nm, 0)
            self.metrics_table.setItem(i, 1, QTableWidgetItem(fmt_map.get(nm, str)(val)))

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

        x = np.arange(len(df))
        ax1.plot(x, equity_curve.values, color='#00d4ff', linewidth=1.5, label='策略净值')

        first_close = df['close'].iloc[0]
        bh = initial_capital * (df['close'] / first_close)
        ax1.plot(x, bh.values, color='#888', linewidth=1, linestyle='--', label='买入持有')

        date_index = df['date'].reset_index(drop=True)
        buy_x, buy_y, sell_x, sell_y = [], [], [], []
        for t in trade_list:
            bd = t['buy_date']
            matches = date_index[date_index == bd].index
            if len(matches) > 0:
                ix = matches[0]
                buy_x.append(ix)
                buy_y.append(equity_curve.iloc[ix] if ix < len(equity_curve) else equity_curve.iloc[-1])
            sd = t.get('sell_date')
            if sd is not None:
                matches = date_index[date_index == sd].index
                if len(matches) > 0:
                    ix = matches[0]
                    sell_x.append(ix)
                    sell_y.append(equity_curve.iloc[ix])
        if buy_x:
            ax1.scatter(buy_x, buy_y, color='#26a69a', s=30, marker='^', zorder=5, label='买入')
        if sell_x:
            ax1.scatter(sell_x, sell_y, color='#ef5350', s=30, marker='v', zorder=5, label='卖出')

        for ax in (ax1, ax2):
            ax.set_facecolor('#1a1a2e')
            ax.tick_params(colors='#ccc', labelsize=7)
            ax.grid(True, color='#333', alpha=0.5)
            for spine in ax.spines.values():
                spine.set_color('#444')

        ax1.set_ylabel('净值', color='white')
        ax1.legend(loc='upper left', fontsize=7, facecolor='#1a1a2e', labelcolor='white', edgecolor='#444')
        ax1.set_xlim(0, len(x) - 1)

        cummax = equity_curve.cummax()
        drawdown = (equity_curve - cummax) / cummax.replace(0, np.nan)
        ax2.fill_between(x, 0, drawdown.values, color='#ef5350', alpha=0.5)
        ax2.set_ylabel('回撤', color='white')

        self.figure.subplots_adjust(left=0.08, right=0.97, top=0.96, bottom=0.06, hspace=0.08)
        self.canvas.draw_idle()
