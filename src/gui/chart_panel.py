# -*- coding: utf-8 -*-
"""
K线图表面板 - 基于 matplotlib 的蜡烛图、成交量、技术指标
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QComboBox, QDateEdit, QCheckBox, QSizePolicy,
    QMessageBox
)
from PyQt5.QtCore import Qt, QDate, pyqtSignal

import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
import matplotlib.dates as mdates
import matplotlib.ticker as mticker

import pandas as pd
import numpy as np
from pathlib import Path


DATA_DIR = Path(__file__).parent.parent.parent / "data"


class ChartPanel(QWidget):
    """K线图表面板"""

    stock_list_updated = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self._stock_items = []
        self._df = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # --- 顶部控制栏 ---
        control = QHBoxLayout()

        control.addWidget(QLabel("股票:"))
        self.stock_combo = QComboBox()
        self.stock_combo.setMinimumWidth(180)
        self.stock_combo.setEditable(True)
        self.stock_combo.setInsertPolicy(QComboBox.NoInsert)
        control.addWidget(self.stock_combo)

        control.addWidget(QLabel("开始:"))
        self.start_date = QDateEdit()
        self.start_date.setDate(QDate.currentDate().addYears(-1))
        self.start_date.setCalendarPopup(True)
        self.start_date.setDisplayFormat("yyyy-MM-dd")
        control.addWidget(self.start_date)

        control.addWidget(QLabel("结束:"))
        self.end_date = QDateEdit()
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setCalendarPopup(True)
        self.end_date.setDisplayFormat("yyyy-MM-dd")
        control.addWidget(self.end_date)

        self.refresh_btn = QPushButton("刷新图表")
        self.refresh_btn.clicked.connect(self._refresh_chart)
        control.addWidget(self.refresh_btn)

        control.addStretch()

        self.ma_check = QCheckBox("MA均线")
        self.ma_check.setChecked(True)
        control.addWidget(self.ma_check)

        self.vol_check = QCheckBox("成交量")
        self.vol_check.setChecked(True)
        control.addWidget(self.vol_check)

        self.macd_check = QCheckBox("MACD")
        self.macd_check.setChecked(False)
        control.addWidget(self.macd_check)

        self.rsi_check = QCheckBox("RSI")
        self.rsi_check.setChecked(False)
        control.addWidget(self.rsi_check)

        layout.addLayout(control)

        # --- 图表画布 ---
        self.figure = Figure(facecolor='#1a1a2e')
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.toolbar = NavigationToolbar(self.canvas, self)
        self.toolbar.setStyleSheet("background: #2d2d44; color: white;")

        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas, stretch=1)

        # 首次扫描股票列表
        self.reload_stock_list()

    # ------------------------------------------------------------------ #
    #  股票列表管理
    # ------------------------------------------------------------------ #
    def reload_stock_list(self):
        """扫描 data/ 目录，动态构建股票列表"""
        self._stock_items = []
        if DATA_DIR.exists():
            for f in sorted(DATA_DIR.glob("*.csv")):
                parts = f.stem.split("_", 1)
                code = parts[0]
                name = parts[1] if len(parts) > 1 else ""
                self._stock_items.append((code, name, str(f)))

        self.stock_combo.blockSignals(True)
        self.stock_combo.clear()
        for code, name, _ in self._stock_items:
            self.stock_combo.addItem(f"{code} {name}")
        self.stock_combo.blockSignals(False)

        self.stock_list_updated.emit(self._stock_items)

    def get_stock_items(self):
        return list(self._stock_items)

    def set_stock_by_code(self, code: str):
        """从外部（如股票池点击）设定当前股票并刷新图表"""
        for i, (c, _, _) in enumerate(self._stock_items):
            if c == code:
                self.stock_combo.setCurrentIndex(i)
                self._refresh_chart()
                return

    def load_file(self, filepath: str):
        """从外部加载任意 CSV 文件并绘图"""
        p = Path(filepath)
        if not p.exists():
            QMessageBox.warning(self, "错误", f"文件不存在:\n{filepath}")
            return
        try:
            df = self._read_csv(p)
            if df is None:
                return
            self._df = df
            name = p.stem
            self._draw(name)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"加载失败:\n{e}")

    # ------------------------------------------------------------------ #
    #  数据读取
    # ------------------------------------------------------------------ #
    def _read_csv(self, filepath: Path) -> pd.DataFrame:
        df = pd.read_csv(filepath)

        # 统一列名：支持 tushare 和 akshare 两种格式
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
        missing = required - set(df.columns)
        if missing:
            QMessageBox.warning(self, "格式错误",
                                f"CSV 缺少必要列: {', '.join(missing)}")
            return None

        date_raw = df['date'].astype(str).str.strip()
        df['date'] = pd.to_datetime(date_raw, format='%Y%m%d', errors='coerce')
        # 回退：兼容 YYYY-MM-DD 等其他日期格式
        mask = df['date'].isna()
        if mask.any():
            df.loc[mask, 'date'] = pd.to_datetime(date_raw[mask], errors='coerce')
        df.dropna(subset=['date'], inplace=True)
        df.sort_values('date', inplace=True)
        df.reset_index(drop=True, inplace=True)
        return df

    # ------------------------------------------------------------------ #
    #  刷新图表
    # ------------------------------------------------------------------ #
    def _refresh_chart(self):
        idx = self.stock_combo.currentIndex()
        if idx < 0 or idx >= len(self._stock_items):
            QMessageBox.information(self, "提示", "请先选择一只股票")
            return

        code, name, filepath = self._stock_items[idx]
        df = self._read_csv(Path(filepath))
        if df is None:
            return

        # 日期范围过滤
        sd = pd.Timestamp(self.start_date.date().toPyDate())
        ed = pd.Timestamp(self.end_date.date().toPyDate())
        df = df[(df['date'] >= sd) & (df['date'] <= ed)]

        if df.empty:
            QMessageBox.information(self, "提示", "所选日期范围内没有数据")
            return

        self._df = df
        self._draw(f"{code} {name}")

    # ------------------------------------------------------------------ #
    #  技术指标计算
    # ------------------------------------------------------------------ #
    @staticmethod
    def _calc_ma(series, period):
        return series.rolling(window=period, min_periods=1).mean()

    @staticmethod
    def _calc_macd(close, fast=12, slow=26, signal=9):
        ema_f = close.ewm(span=fast, adjust=False).mean()
        ema_s = close.ewm(span=slow, adjust=False).mean()
        dif = ema_f - ema_s
        dea = dif.ewm(span=signal, adjust=False).mean()
        hist = (dif - dea) * 2
        return dif, dea, hist

    @staticmethod
    def _calc_rsi(close, period=14):
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
        rs = gain / loss
        return 100 - 100 / (1 + rs)

    # ------------------------------------------------------------------ #
    #  绘图
    # ------------------------------------------------------------------ #
    def _draw(self, title: str):
        df = self._df.copy()
        self.figure.clear()

        show_vol = self.vol_check.isChecked() and 'volume' in df.columns
        show_macd = self.macd_check.isChecked()
        show_rsi = self.rsi_check.isChecked()

        n_panels = 1 + int(show_vol) + int(show_macd) + int(show_rsi)
        ratios = [4]
        if show_vol:
            ratios.append(1)
        if show_macd:
            ratios.append(1)
        if show_rsi:
            ratios.append(1)

        axes = self.figure.subplots(n_panels, 1, sharex=True,
                                     gridspec_kw={'height_ratios': ratios,
                                                  'hspace': 0.05})
        if n_panels == 1:
            axes = [axes]

        ax_main = axes[0]
        ax_idx = 1

        # ---- 蜡烛图 ----
        dates = df['date'].values
        x = np.arange(len(df))
        opens = df['open'].values
        highs = df['high'].values
        lows = df['low'].values
        closes = df['close'].values

        up = closes >= opens
        down = ~up

        body_width = 0.6
        shadow_width = 0.15

        color_up = '#ef5350'
        color_down = '#26a69a'

        # 上涨蜡烛
        ax_main.bar(x[up], closes[up] - opens[up], body_width,
                    bottom=opens[up], color=color_up, edgecolor=color_up, linewidth=0.5)
        ax_main.bar(x[up], highs[up] - closes[up], shadow_width,
                    bottom=closes[up], color=color_up, edgecolor=color_up, linewidth=0.5)
        ax_main.bar(x[up], opens[up] - lows[up], shadow_width,
                    bottom=lows[up], color=color_up, edgecolor=color_up, linewidth=0.5)

        # 下跌蜡烛
        ax_main.bar(x[down], opens[down] - closes[down], body_width,
                    bottom=closes[down], color=color_down, edgecolor=color_down, linewidth=0.5)
        ax_main.bar(x[down], highs[down] - opens[down], shadow_width,
                    bottom=opens[down], color=color_down, edgecolor=color_down, linewidth=0.5)
        ax_main.bar(x[down], closes[down] - lows[down], shadow_width,
                    bottom=lows[down], color=color_down, edgecolor=color_down, linewidth=0.5)

        # ---- MA 均线 ----
        if self.ma_check.isChecked():
            ma_config = [(5, '#ffeb3b'), (10, '#ff9800'), (20, '#e91e63'), (60, '#2196f3')]
            for period, color in ma_config:
                if len(df) >= period:
                    ma = self._calc_ma(df['close'], period)
                    ax_main.plot(x, ma.values, color=color, linewidth=0.8,
                                label=f'MA{period}', alpha=0.9)
            ax_main.legend(loc='upper left', fontsize=7, facecolor='#1a1a2e',
                           edgecolor='#444', labelcolor='white')

        ax_main.set_title(title, color='white', fontsize=12, pad=8,
                          fontfamily='Microsoft YaHei')
        ax_main.set_ylabel('价格', color='white', fontsize=9,
                           fontfamily='Microsoft YaHei')

        # ---- 成交量 ----
        if show_vol:
            ax_vol = axes[ax_idx]
            ax_idx += 1
            vol = df['volume'].values
            vol_colors = [color_up if u else color_down for u in up]
            ax_vol.bar(x, vol, body_width, color=vol_colors, alpha=0.8)
            ax_vol.set_ylabel('成交量', color='white', fontsize=9,
                              fontfamily='Microsoft YaHei')
            self._style_axis(ax_vol)

        # ---- MACD ----
        if show_macd:
            ax_macd = axes[ax_idx]
            ax_idx += 1
            dif, dea, hist = self._calc_macd(df['close'])
            ax_macd.bar(x, hist.values, body_width,
                        color=[color_up if v >= 0 else color_down for v in hist.values],
                        alpha=0.7)
            ax_macd.plot(x, dif.values, color='#ffeb3b', linewidth=0.8, label='DIF')
            ax_macd.plot(x, dea.values, color='#2196f3', linewidth=0.8, label='DEA')
            ax_macd.axhline(0, color='#555', linewidth=0.5)
            ax_macd.legend(loc='upper left', fontsize=7, facecolor='#1a1a2e',
                           edgecolor='#444', labelcolor='white')
            ax_macd.set_ylabel('MACD', color='white', fontsize=9)
            self._style_axis(ax_macd)

        # ---- RSI ----
        if show_rsi:
            ax_rsi = axes[ax_idx]
            ax_idx += 1
            rsi = self._calc_rsi(df['close'])
            ax_rsi.plot(x, rsi.values, color='#ab47bc', linewidth=1, label='RSI14')
            ax_rsi.axhline(70, color='#ef5350', linewidth=0.5, linestyle='--')
            ax_rsi.axhline(30, color='#26a69a', linewidth=0.5, linestyle='--')
            ax_rsi.set_ylim(0, 100)
            ax_rsi.legend(loc='upper left', fontsize=7, facecolor='#1a1a2e',
                          edgecolor='#444', labelcolor='white')
            ax_rsi.set_ylabel('RSI', color='white', fontsize=9)
            self._style_axis(ax_rsi)

        # ---- X 轴日期标签 ----
        ax_bottom = axes[-1]
        step = max(1, len(df) // 12)
        tick_pos = list(range(0, len(df), step))
        tick_labels = [pd.Timestamp(dates[i]).strftime('%Y-%m-%d') for i in tick_pos]
        ax_bottom.set_xticks(tick_pos)
        ax_bottom.set_xticklabels(tick_labels, rotation=30, fontsize=7, color='#ccc')

        # ---- 统一样式 ----
        self._style_axis(ax_main)
        ax_main.set_xlim(-1, len(df))

        self.figure.subplots_adjust(left=0.06, right=0.97, top=0.95, bottom=0.08)
        self.canvas.draw_idle()

    def _style_axis(self, ax):
        ax.set_facecolor('#1a1a2e')
        ax.tick_params(colors='#ccc', labelsize=7)
        ax.spines['top'].set_color('#444')
        ax.spines['bottom'].set_color('#444')
        ax.spines['left'].set_color('#444')
        ax.spines['right'].set_color('#444')
        ax.yaxis.label.set_color('white')
        ax.grid(True, color='#333', linewidth=0.3, alpha=0.5)
