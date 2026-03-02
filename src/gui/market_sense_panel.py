# -*- coding: utf-8 -*-
"""
盘感锻炼面板 - 随机展示一段K线，用户预判未来涨跌，揭晓答案
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QSizePolicy, QMessageBox, QFrame,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

import pandas as pd
import numpy as np
from pathlib import Path
import random


DATA_DIR = Path(__file__).parent.parent.parent / "data"
ETF_DIR = DATA_DIR / "etf"
INDICES_DIR = DATA_DIR / "indices"
MARKET_VOL_CACHE = INDICES_DIR / "000001_上证指数.csv"

QUARTER_DAYS = 60
FUTURE_DAYS = 20
MIN_ROWS = QUARTER_DAYS + FUTURE_DAYS + 30


class _MarketVolLoader(QThread):
    """后台下载上证指数数据"""
    finished = pyqtSignal(bool, str)

    def run(self):
        try:
            import akshare as ak
            df = ak.index_zh_a_hist(
                symbol="000001", period="daily",
                start_date="20100101",
                end_date=pd.Timestamp.now().strftime("%Y%m%d"),
            )
            if df is None or df.empty:
                self.finished.emit(False, "akshare 未返回数据")
                return
            INDICES_DIR.mkdir(parents=True, exist_ok=True)
            df.to_csv(MARKET_VOL_CACHE, index=False, encoding='utf-8-sig')
            self.finished.emit(True, "")
        except Exception as e:
            self.finished.emit(False, str(e))


class MarketSensePanel(QWidget):
    """盘感锻炼面板"""

    def __init__(self):
        super().__init__()
        self._all_files: list[Path] = []
        self._current_name = ""
        self._current_code = ""
        self._df_visible = None
        self._df_future = None
        self._market_vol_visible = None
        self._market_vol_future = None
        self._answered = False
        self._market_df: pd.DataFrame | None = None
        self._loader_thread: _MarketVolLoader | None = None
        self._init_ui()
        self._scan_files()
        self._load_market_data()

    # ------------------------------------------------------------------ #
    #  UI
    # ------------------------------------------------------------------ #
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        hint = QLabel("随机展示一段季度级别K线（约60个交易日），请判断未来20个交易日的涨跌方向")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("color: #aaa; font-size: 13px; padding: 4px;")
        layout.addWidget(hint)

        self.figure = Figure(facecolor='#1a1a2e')
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.canvas, stretch=1)

        self.stats_label = QLabel("")
        self.stats_label.setAlignment(Qt.AlignCenter)
        self.stats_label.setStyleSheet("color: #ccc; font-size: 12px; padding: 4px;")
        layout.addWidget(self.stats_label)

        self.result_frame = QFrame()
        self.result_frame.setStyleSheet(
            "QFrame { background: #2a2a3e; border-radius: 8px; padding: 12px; }"
        )
        result_layout = QVBoxLayout(self.result_frame)
        self.result_label = QLabel("")
        self.result_label.setAlignment(Qt.AlignCenter)
        self.result_label.setWordWrap(True)
        self.result_label.setStyleSheet("font-size: 15px; padding: 8px;")
        result_layout.addWidget(self.result_label)
        self.result_frame.setVisible(False)
        layout.addWidget(self.result_frame)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_up = QPushButton("  看涨 ▲  ")
        self.btn_up.setMinimumSize(140, 48)
        self.btn_up.setStyleSheet(
            "QPushButton { background: #c62828; color: white; font-size: 16px; "
            "font-weight: bold; border-radius: 8px; }"
            "QPushButton:hover { background: #e53935; }"
            "QPushButton:disabled { background: #555; color: #888; }"
        )
        self.btn_up.clicked.connect(lambda: self._on_answer(True))
        btn_layout.addWidget(self.btn_up)

        btn_layout.addSpacing(30)

        self.btn_down = QPushButton("  看跌 ▼  ")
        self.btn_down.setMinimumSize(140, 48)
        self.btn_down.setStyleSheet(
            "QPushButton { background: #2e7d32; color: white; font-size: 16px; "
            "font-weight: bold; border-radius: 8px; }"
            "QPushButton:hover { background: #43a047; }"
            "QPushButton:disabled { background: #555; color: #888; }"
        )
        self.btn_down.clicked.connect(lambda: self._on_answer(False))
        btn_layout.addWidget(self.btn_down)

        btn_layout.addSpacing(50)

        self.btn_next = QPushButton("  下一题 →  ")
        self.btn_next.setMinimumSize(140, 48)
        self.btn_next.setStyleSheet(
            "QPushButton { background: #1565c0; color: white; font-size: 16px; "
            "font-weight: bold; border-radius: 8px; }"
            "QPushButton:hover { background: #1e88e5; }"
        )
        self.btn_next.clicked.connect(self._next_question)
        btn_layout.addWidget(self.btn_next)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self._total = 0
        self._correct = 0
        self.score_label = QLabel("得分: 0 / 0")
        self.score_label.setAlignment(Qt.AlignCenter)
        self.score_label.setStyleSheet("color: #aaa; font-size: 12px; padding: 4px;")
        layout.addWidget(self.score_label)

    # ------------------------------------------------------------------ #
    #  数据扫描
    # ------------------------------------------------------------------ #
    def _scan_files(self):
        self._all_files = []
        for d in [DATA_DIR, ETF_DIR]:
            if d.exists():
                self._all_files.extend(sorted(d.glob("*.csv")))

    def _parse_name(self, filepath: Path):
        parts = filepath.stem.split("_", 1)
        code = parts[0]
        name = parts[1] if len(parts) > 1 else ""
        return code, name

    def _read_csv(self, filepath: Path) -> pd.DataFrame | None:
        try:
            df = pd.read_csv(filepath)
        except Exception:
            return None

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
        if not required.issubset(df.columns):
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

    # ------------------------------------------------------------------ #
    #  全A（上证指数）成交量数据
    # ------------------------------------------------------------------ #
    def _load_market_data(self):
        """尝试从缓存加载上证指数数据，不存在则后台下载"""
        if MARKET_VOL_CACHE.exists():
            self._parse_market_cache()
        else:
            self._download_market_data()

    def _parse_market_cache(self):
        try:
            df = pd.read_csv(MARKET_VOL_CACHE)
            col_map = {}
            for c in df.columns:
                cl = c.lower().strip()
                if cl in ('trade_date', '日期', 'date'):
                    col_map[c] = 'date'
                elif cl in ('vol', 'volume', '成交量'):
                    col_map[c] = 'volume'
                elif cl in ('amount', '成交额'):
                    col_map[c] = 'amount'
                elif cl in ('close', '收盘'):
                    col_map[c] = 'close'
            df.rename(columns=col_map, inplace=True)

            date_raw = df['date'].astype(str).str.strip()
            df['date'] = pd.to_datetime(date_raw, format='%Y%m%d', errors='coerce')
            mask = df['date'].isna()
            if mask.any():
                df.loc[mask, 'date'] = pd.to_datetime(date_raw[mask], errors='coerce')
            df.dropna(subset=['date'], inplace=True)
            df.sort_values('date', inplace=True)
            df.reset_index(drop=True, inplace=True)
            self._market_df = df
        except Exception:
            self._market_df = None

    def _download_market_data(self):
        self._loader_thread = _MarketVolLoader()
        self._loader_thread.finished.connect(self._on_market_download_done)
        self._loader_thread.start()

    def _on_market_download_done(self, ok: bool, err: str):
        if ok:
            self._parse_market_cache()
        self._loader_thread = None

    def _get_market_vol_slice(self, date_start, date_end):
        """根据日期范围获取上证指数成交量切片，按日期对齐"""
        if self._market_df is None:
            return None
        mask = (self._market_df['date'] >= date_start) & (self._market_df['date'] <= date_end)
        sub = self._market_df.loc[mask].copy().reset_index(drop=True)
        if sub.empty:
            return None
        return sub

    # ------------------------------------------------------------------ #
    #  出题
    # ------------------------------------------------------------------ #
    def _next_question(self):
        if not self._all_files:
            self._scan_files()
        if not self._all_files:
            QMessageBox.warning(self, "提示", "未找到任何数据文件，请先下载股票/ETF数据")
            return

        candidates = list(self._all_files)
        random.shuffle(candidates)

        for filepath in candidates:
            df = self._read_csv(filepath)
            if df is None or len(df) < MIN_ROWS:
                continue

            max_start = len(df) - QUARTER_DAYS - FUTURE_DAYS
            start_idx = random.randint(0, max_start)
            end_visible = start_idx + QUARTER_DAYS
            end_future = end_visible + FUTURE_DAYS

            self._df_visible = df.iloc[start_idx:end_visible].copy().reset_index(drop=True)
            self._df_future = df.iloc[end_visible:end_future].copy().reset_index(drop=True)
            self._current_code, self._current_name = self._parse_name(filepath)
            self._answered = False

            d_start = self._df_visible['date'].iloc[0]
            d_end_visible = self._df_visible['date'].iloc[-1]
            d_end_future = self._df_future['date'].iloc[-1]
            self._market_vol_visible = self._get_market_vol_slice(d_start, d_end_visible)
            self._market_vol_future = self._get_market_vol_slice(
                d_end_visible + pd.Timedelta(days=1), d_end_future
            )

            self.btn_up.setEnabled(True)
            self.btn_down.setEnabled(True)
            self.result_frame.setVisible(False)
            self.result_label.setText("")

            self.stats_label.setText(
                f"展示区间: {d_start.strftime('%Y-%m-%d')} ~ "
                f"{d_end_visible.strftime('%Y-%m-%d')}  |  "
                f"共 {len(self._df_visible)} 根K线"
            )

            self._draw_question()
            return

        QMessageBox.warning(self, "提示", "没有找到足够数据量的标的，请先下载更多数据")

    # ------------------------------------------------------------------ #
    #  回答
    # ------------------------------------------------------------------ #
    def _on_answer(self, user_says_up: bool):
        if self._answered or self._df_future is None:
            return
        self._answered = True
        self.btn_up.setEnabled(False)
        self.btn_down.setEnabled(False)

        last_close = self._df_visible['close'].iloc[-1]
        future_close = self._df_future['close'].iloc[-1]
        change = future_close - last_close
        pct = change / last_close * 100
        actual_up = change >= 0

        future_high = self._df_future['high'].max()
        future_low = self._df_future['low'].min()
        max_up_pct = (future_high - last_close) / last_close * 100
        max_down_pct = (future_low - last_close) / last_close * 100

        self._total += 1
        is_correct = user_says_up == actual_up
        if is_correct:
            self._correct += 1

        direction = "上涨" if actual_up else "下跌"
        color = "#ef5350" if actual_up else "#26a69a"
        judge = "正确 ✓" if is_correct else "错误 ✗"
        judge_color = "#4caf50" if is_correct else "#f44336"

        self.result_label.setText(
            f'<span style="color:{judge_color}; font-size:18px; font-weight:bold;">{judge}</span>'
            f'<br><br>'
            f'<span style="color:white;">标的: </span>'
            f'<span style="color:#ffeb3b; font-weight:bold;">{self._current_code} {self._current_name}</span>'
            f'<br>'
            f'<span style="color:white;">未来20日收盘价: </span>'
            f'<span style="color:{color}; font-weight:bold;">{direction} {abs(pct):.2f}%</span>'
            f'<span style="color:#aaa;">  ({last_close:.2f} → {future_close:.2f})</span>'
            f'<br>'
            f'<span style="color:#aaa;">期间最高涨 {max_up_pct:+.2f}%  |  最大跌 {max_down_pct:+.2f}%</span>'
        )
        self.result_frame.setVisible(True)

        accuracy = self._correct / self._total * 100 if self._total > 0 else 0
        self.score_label.setText(
            f"得分: {self._correct} / {self._total}  "
            f"(正确率 {accuracy:.0f}%)"
        )

        self._draw_answer()

    # ------------------------------------------------------------------ #
    #  绘图 - 构建子图布局
    # ------------------------------------------------------------------ #
    def _make_axes(self, has_market_vol: bool):
        """返回 (ax_candle, ax_vol, ax_market | None)"""
        if has_market_vol:
            axes = self.figure.subplots(
                3, 1, sharex=True,
                gridspec_kw={'height_ratios': [4, 1, 1], 'hspace': 0.06},
            )
            return axes[0], axes[1], axes[2]
        else:
            axes = self.figure.subplots(
                2, 1, sharex=True,
                gridspec_kw={'height_ratios': [4, 1], 'hspace': 0.06},
            )
            return axes[0], axes[1], None

    # ------------------------------------------------------------------ #
    #  绘图 - 出题阶段
    # ------------------------------------------------------------------ #
    def _draw_question(self):
        self.figure.clear()
        df = self._df_visible
        has_vol = 'volume' in df.columns
        has_market = self._market_vol_visible is not None

        if not has_vol and not has_market:
            ax = self.figure.add_subplot(111)
            self._draw_candles(ax, df)
            ax.set_title("请判断未来20个交易日的涨跌方向", color='#ffeb3b',
                          fontsize=13, pad=10, fontfamily='Microsoft YaHei')
            self._style_axis(ax, df)
        else:
            ax_candle, ax_vol, ax_market = self._make_axes(has_market)
            self._draw_candles(ax_candle, df)
            ax_candle.set_title("请判断未来20个交易日的涨跌方向", color='#ffeb3b',
                                fontsize=13, pad=10, fontfamily='Microsoft YaHei')
            self._style_axis(ax_candle, df, show_x=False)

            if has_vol:
                self._draw_volume(ax_vol, df, label="成交量")
                self._style_axis(ax_vol, df, show_x=(ax_market is None))

            if ax_market is not None and has_market:
                self._draw_market_volume(ax_market, self._market_vol_visible, len(df))
                self._style_axis(ax_market, df, show_x=True)

        self.figure.subplots_adjust(left=0.07, right=0.97, top=0.92, bottom=0.10)
        self.canvas.draw_idle()

    # ------------------------------------------------------------------ #
    #  绘图 - 揭晓答案
    # ------------------------------------------------------------------ #
    def _draw_answer(self):
        self.figure.clear()
        df_all = pd.concat([self._df_visible, self._df_future], ignore_index=True)
        split = len(self._df_visible)
        has_vol = 'volume' in df_all.columns

        mv_all = None
        has_market = False
        if self._market_vol_visible is not None:
            parts = [self._market_vol_visible]
            if self._market_vol_future is not None:
                parts.append(self._market_vol_future)
            mv_all = pd.concat(parts, ignore_index=True)
            has_market = True

        if not has_vol and not has_market:
            ax = self.figure.add_subplot(111)
            self._draw_candles(ax, df_all)
            self._draw_split_line(ax, split, len(df_all))
            ax.set_title(f"{self._current_code} {self._current_name}",
                         color='white', fontsize=13, pad=10, fontfamily='Microsoft YaHei')
            self._style_axis(ax, df_all)
        else:
            ax_candle, ax_vol, ax_market = self._make_axes(has_market)
            self._draw_candles(ax_candle, df_all)
            self._draw_split_line(ax_candle, split, len(df_all))
            ax_candle.set_title(f"{self._current_code} {self._current_name}",
                                color='white', fontsize=13, pad=10, fontfamily='Microsoft YaHei')
            self._style_axis(ax_candle, df_all, show_x=False)

            if has_vol:
                self._draw_volume(ax_vol, df_all, label="成交量")
                ax_vol.axvline(x=split - 0.5, color='#ffeb3b', linewidth=1,
                               linestyle='--', alpha=0.6)
                self._style_axis(ax_vol, df_all, show_x=(ax_market is None))

            if ax_market is not None and has_market:
                self._draw_market_volume(ax_market, mv_all, len(df_all))
                ax_market.axvline(x=split - 0.5, color='#ffeb3b', linewidth=1,
                                  linestyle='--', alpha=0.6)
                self._style_axis(ax_market, df_all, show_x=True)

        self.figure.subplots_adjust(left=0.07, right=0.97, top=0.92, bottom=0.10)
        self.canvas.draw_idle()

    def _draw_split_line(self, ax, split, total):
        ax.axvline(x=split - 0.5, color='#ffeb3b', linewidth=1.5,
                   linestyle='--', alpha=0.8)
        ax.text(split - 0.5, ax.get_ylim()[1], '  ← 预测分界线',
                color='#ffeb3b', fontsize=9, va='top',
                fontfamily='Microsoft YaHei')
        ax.axvspan(split - 0.5, total - 0.5, alpha=0.08, color='#ffeb3b')

    # ------------------------------------------------------------------ #
    #  蜡烛图绘制
    # ------------------------------------------------------------------ #
    def _draw_candles(self, ax, df):
        x = np.arange(len(df))
        opens = df['open'].values
        highs = df['high'].values
        lows = df['low'].values
        closes = df['close'].values

        up = closes >= opens
        down = ~up
        body_w = 0.6
        shadow_w = 0.15
        c_up = '#ef5350'
        c_down = '#26a69a'

        ax.bar(x[up], closes[up] - opens[up], body_w,
               bottom=opens[up], color=c_up, edgecolor=c_up, linewidth=0.5)
        ax.bar(x[up], highs[up] - closes[up], shadow_w,
               bottom=closes[up], color=c_up, edgecolor=c_up, linewidth=0.5)
        ax.bar(x[up], opens[up] - lows[up], shadow_w,
               bottom=lows[up], color=c_up, edgecolor=c_up, linewidth=0.5)

        ax.bar(x[down], opens[down] - closes[down], body_w,
               bottom=closes[down], color=c_down, edgecolor=c_down, linewidth=0.5)
        ax.bar(x[down], highs[down] - opens[down], shadow_w,
               bottom=opens[down], color=c_down, edgecolor=c_down, linewidth=0.5)
        ax.bar(x[down], closes[down] - lows[down], shadow_w,
               bottom=lows[down], color=c_down, edgecolor=c_down, linewidth=0.5)

    # ------------------------------------------------------------------ #
    #  成交量绘制
    # ------------------------------------------------------------------ #
    def _draw_volume(self, ax, df, label="成交量"):
        if 'volume' not in df.columns:
            return
        x = np.arange(len(df))
        vol = df['volume'].values
        opens = df['open'].values
        closes = df['close'].values
        up = closes >= opens
        c_up = '#ef5350'
        c_down = '#26a69a'
        colors = [c_up if u else c_down for u in up]
        ax.bar(x, vol, 0.6, color=colors, alpha=0.8)
        ax.set_ylabel(label, color='white', fontsize=8, fontfamily='Microsoft YaHei')

    def _draw_market_volume(self, ax, mv_df, n_bars):
        """绘制全A（上证指数）成交量，按位置对齐到 n_bars 长度"""
        if mv_df is None or mv_df.empty:
            return
        vol_col = 'volume' if 'volume' in mv_df.columns else None
        if vol_col is None and 'amount' in mv_df.columns:
            vol_col = 'amount'
        if vol_col is None:
            return

        vol = mv_df[vol_col].values
        n = min(len(vol), n_bars)
        x = np.arange(n)
        ax.bar(x, vol[:n], 0.6, color='#5c6bc0', alpha=0.7)
        ax.set_ylabel("全A成交量", color='white', fontsize=8, fontfamily='Microsoft YaHei')

    # ------------------------------------------------------------------ #
    #  坐标轴样式
    # ------------------------------------------------------------------ #
    def _style_axis(self, ax, df, show_x=True):
        ax.set_facecolor('#1a1a2e')
        ax.tick_params(colors='#ccc', labelsize=7)
        for spine in ax.spines.values():
            spine.set_color('#444')
        ax.yaxis.label.set_color('white')
        ax.grid(True, color='#333', linewidth=0.3, alpha=0.5)
        ax.set_xlim(-1, len(df))

        if show_x:
            dates = df['date'].values
            step = max(1, len(df) // 10)
            tick_pos = list(range(0, len(df), step))
            tick_labels = [pd.Timestamp(dates[i]).strftime('%m-%d') for i in tick_pos]
            ax.set_xticks(tick_pos)
            ax.set_xticklabels(tick_labels, rotation=30, fontsize=7, color='#ccc')
        else:
            ax.tick_params(axis='x', labelbottom=False)
