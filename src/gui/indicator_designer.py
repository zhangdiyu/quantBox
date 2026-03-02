# -*- coding: utf-8 -*-
"""
量化指标设计器
支持可视化和编程方式设计自定义技术指标
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QComboBox, QTextEdit, QSplitter,
    QGroupBox, QFormLayout, QLineEdit,
    QMessageBox, QListWidget, QListWidgetItem, QDateEdit,
    QSizePolicy, QFileDialog
)
from PyQt5.QtCore import Qt, pyqtSignal, QDate
from PyQt5.QtGui import QFont, QColor, QSyntaxHighlighter, QTextCharFormat

import re
from pathlib import Path
import json

import pandas as pd
import numpy as np

import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

DATA_DIR = Path(__file__).parent.parent.parent / "data"


class PythonHighlighter(QSyntaxHighlighter):
    """Python语法高亮器"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_highlighting()

    def _init_highlighting(self):
        """初始化高亮规则"""
        self.highlighting_rules = []

        # 关键字
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#569CD6"))
        keyword_format.setFontWeight(QFont.Bold)
        keywords = [
            "def", "class", "if", "else", "elif", "for", "while",
            "try", "except", "finally", "return", "import", "from",
            "as", "True", "False", "None", "and", "or", "not", "in",
            "is", "global", "nonlocal", "lambda", "pass", "break",
            "continue", "raise", "assert", "with", "yield"
        ]
        for word in keywords:
            pattern = rf"\b{word}\b"
            self.highlighting_rules.append((re.compile(pattern), keyword_format))

        # 字符串
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#CE9178"))
        self.highlighting_rules.append((re.compile(r'"[^"\\]*(\\.[^"\\]*)*"'), string_format))
        self.highlighting_rules.append((re.compile(r"'[^'\\]*(\\.[^'\\]*)*'"), string_format))

        # 注释
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6A9955"))
        self.highlighting_rules.append((re.compile(r"#.*$"), comment_format))

        # 数字
        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#B5CEA8"))
        self.highlighting_rules.append((re.compile(r"\b[0-9]+\.?[0-9]*\b"), number_format))

        # 函数名
        function_format = QTextCharFormat()
        function_format.setForeground(QColor("#DCDCAA"))
        self.highlighting_rules.append((re.compile(r"\b[A-Za-z0-9_]+(?=\()"), function_format))

    def highlightBlock(self, text):
        """高亮代码块"""
        for pattern, format in self.highlighting_rules:
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), format)


class IndicatorDesigner(QWidget):
    """指标设计器主窗口"""

    def __init__(self):
        super().__init__()
        self._stock_items = []
        self._last_test_df = None
        self._init_ui()
        self._load_builtin_indicators()
        self._reload_stock_list()

    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # --- 顶部：股票选择 + 日期范围 ---
        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("股票:"))
        self.stock_combo = QComboBox()
        self.stock_combo.setMinimumWidth(200)
        self.stock_combo.setEditable(True)
        self.stock_combo.setInsertPolicy(QComboBox.NoInsert)
        selector_layout.addWidget(self.stock_combo)

        selector_layout.addWidget(QLabel("开始:"))
        self.start_date = QDateEdit()
        self.start_date.setDate(QDate.currentDate().addYears(-1))
        self.start_date.setCalendarPopup(True)
        self.start_date.setDisplayFormat("yyyy-MM-dd")
        selector_layout.addWidget(self.start_date)

        selector_layout.addWidget(QLabel("结束:"))
        self.end_date = QDateEdit()
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setCalendarPopup(True)
        self.end_date.setDisplayFormat("yyyy-MM-dd")
        selector_layout.addWidget(self.end_date)

        layout.addLayout(selector_layout)

        # 顶部工具栏
        toolbar_layout = QHBoxLayout()

        self.new_btn = QPushButton("新建指标")
        self.new_btn.clicked.connect(self._new_indicator)
        toolbar_layout.addWidget(self.new_btn)

        self.save_btn = QPushButton("保存指标")
        self.save_btn.clicked.connect(self._save_indicator)
        toolbar_layout.addWidget(self.save_btn)

        self.load_btn = QPushButton("加载指标")
        self.load_btn.clicked.connect(self._load_indicator)
        toolbar_layout.addWidget(self.load_btn)

        toolbar_layout.addStretch()

        self.test_btn = QPushButton("测试指标")
        self.test_btn.clicked.connect(self._test_indicator)
        toolbar_layout.addWidget(self.test_btn)

        layout.addLayout(toolbar_layout)

        # 分割器
        splitter = QSplitter(Qt.Horizontal)

        # 左侧 - 内置指标和参数
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        # 内置指标列表
        builtin_group = QGroupBox("内置指标")
        builtin_layout = QVBoxLayout(builtin_group)

        self.indicator_list = QListWidget()
        self.indicator_list.itemClicked.connect(self._on_indicator_selected)
        builtin_layout.addWidget(self.indicator_list)

        left_layout.addWidget(builtin_group)

        # 参数设置
        params_group = QGroupBox("参数设置")
        params_layout = QFormLayout(params_group)

        self.indicator_name_edit = QLineEdit()
        self.indicator_name_edit.setPlaceholderText("指标名称")
        params_layout.addRow("名称:", self.indicator_name_edit)

        self.indicator_desc_edit = QLineEdit()
        self.indicator_desc_edit.setPlaceholderText("指标描述")
        params_layout.addRow("描述:", self.indicator_desc_edit)

        left_layout.addWidget(params_group)

        left_layout.addStretch()

        splitter.addWidget(left_panel)

        # 右侧 - 代码编辑、测试结果、图表
        right_splitter = QSplitter(Qt.Vertical)

        # 代码编辑
        code_group = QGroupBox("代码编辑 (Vibe Coding)")
        code_layout = QVBoxLayout(code_group)

        # 代码模板选择
        template_layout = QHBoxLayout()
        template_layout.addWidget(QLabel("模板:"))
        self.template_combo = QComboBox()
        self.template_combo.addItems([
            "空白模板",
            "移动平均 (MA)",
            "EMA - 指数移动平均",
            "相对强弱指数 (RSI)",
            "MACD",
            "布林带",
            "KDJ - 随机指标",
            "ATR - 平均真实波幅",
            "OBV - 能量潮",
            "CCI - 顺势指标",
            "WR - 威廉指标",
            "自定义指标"
        ])
        self.template_combo.currentTextChanged.connect(self._on_template_changed)
        template_layout.addWidget(self.template_combo)
        code_layout.addLayout(template_layout)

        # 代码编辑器
        self.code_editor = QTextEdit()
        self.code_editor.setFont(QFont("Consolas", 10))
        self.code_editor.setPlaceholderText(
            "# 在此编写你的指标代码\n"
            "# df columns: date, open, high, low, close, vol, amount\n"
            "# 必须返回: 包含新指标列的DataFrame\n\n"
            "def calculate_indicator(df):\n"
            "    # 示例: 计算5日均线\n"
            "    df['MA5'] = df['close'].rolling(5).mean()\n"
            "    return df"
        )
        self.highlighter = PythonHighlighter(self.code_editor.document())
        code_layout.addWidget(self.code_editor)

        right_splitter.addWidget(code_group)

        # 测试结果
        test_group = QGroupBox("测试结果")
        test_layout = QVBoxLayout(test_group)

        self.test_output = QTextEdit()
        self.test_output.setReadOnly(True)
        self.test_output.setFont(QFont("Consolas", 9))
        test_layout.addWidget(self.test_output)

        right_splitter.addWidget(test_group)

        # 结果图表
        chart_group = QGroupBox("结果图表")
        chart_layout = QVBoxLayout(chart_group)
        self.chart_figure = Figure(facecolor='#1a1a2e')
        self.chart_canvas = FigureCanvas(self.chart_figure)
        self.chart_canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.chart_canvas.setMinimumHeight(200)
        chart_layout.addWidget(self.chart_canvas)
        right_splitter.addWidget(chart_group)

        right_splitter.setStretchFactor(0, 2)
        right_splitter.setStretchFactor(1, 1)
        right_splitter.setStretchFactor(2, 1)

        splitter.addWidget(right_splitter)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        layout.addWidget(splitter)

    def _reload_stock_list(self):
        """扫描 data/ 目录，构建股票列表"""
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

    def _load_builtin_indicators(self):
        """加载内置指标"""
        builtin_indicators = [
            "MA - 移动平均线",
            "EMA - 指数移动平均",
            "MACD - 异同移动平均线",
            "RSI - 相对强弱指数",
            "KDJ - 随机指标",
            "BOLL - 布林带",
            "ATR - 平均真实波幅",
            "OBV - 能量潮",
            "CCI - 顺势指标",
            "WR - 威廉指标",
        ]

        for indicator in builtin_indicators:
            item = QListWidgetItem(indicator)
            self.indicator_list.addItem(item)

    def _on_indicator_selected(self, item):
        """选择内置指标"""
        name = item.text()
        parts = name.split(" - ", 1)
        self.indicator_name_edit.setText(parts[0])
        self.indicator_desc_edit.setText(parts[1] if len(parts) > 1 else "")

        # 加载对应的模板代码
        self._load_template_code(name)

    def _on_template_changed(self, template_name):
        """模板改变"""
        self._load_template_code(template_name)

    def _get_templates(self):
        """返回所有模板（使用英文列名）"""
        return {
            "空白模板": """# 空白模板
def calculate_indicator(df):
    # 在此编写你的指标计算逻辑
    # df columns: date, open, high, low, close, vol, amount
    return df
""",
            "移动平均 (MA)": """# 移动平均 (MA)
def calculate_indicator(df):
    periods = [5, 10, 20, 60]
    for period in periods:
        df[f'MA{period}'] = df['close'].rolling(period).mean()
    return df
""",
            "EMA - 指数移动平均": """# EMA - 指数移动平均
def calculate_indicator(df):
    periods = [5, 10, 20, 60]
    for period in periods:
        df[f'EMA{period}'] = df['close'].ewm(span=period, adjust=False).mean()
    return df
""",
            "相对强弱指数 (RSI)": """# 相对强弱指数 (RSI)
def calculate_indicator(df, period=14):
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = np.where(loss != 0, gain / loss, np.inf)
    df[f'RSI{period}'] = 100 - (100 / (1 + rs))
    return df
""",
            "MACD": """# MACD - 异同移动平均线
def calculate_indicator(df):
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD_DIF'] = ema12 - ema26
    df['MACD_DEA'] = df['MACD_DIF'].ewm(span=9, adjust=False).mean()
    df['MACD_HIST'] = 2 * (df['MACD_DIF'] - df['MACD_DEA'])
    return df
""",
            "布林带": """# 布林带 (Bollinger Bands)
def calculate_indicator(df, period=20, std_dev=2):
    df[f'BB_MID{period}'] = df['close'].rolling(period).mean()
    std = df['close'].rolling(period).std()
    df[f'BB_UPPER{period}'] = df[f'BB_MID{period}'] + (std * std_dev)
    df[f'BB_LOWER{period}'] = df[f'BB_MID{period}'] - (std * std_dev)
    return df
""",
            "KDJ - 随机指标": """# KDJ - 随机指标
def calculate_indicator(df, n=9, m1=3, m2=3):
    low_min = df['low'].rolling(n).min()
    high_max = df['high'].rolling(n).max()
    rsv = (df['close'] - low_min) / (high_max - low_min) * 100
    df['K'] = rsv.ewm(com=m1-1, adjust=False).mean()
    df['D'] = df['K'].ewm(com=m2-1, adjust=False).mean()
    df['J'] = 3 * df['K'] - 2 * df['D']
    return df
""",
            "ATR - 平均真实波幅": """# ATR - 平均真实波幅
def calculate_indicator(df, period=14):
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift(1))
    low_close = np.abs(df['low'] - df['close'].shift(1))
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df[f'ATR{period}'] = tr.rolling(period).mean()
    return df
""",
            "OBV - 能量潮": """# OBV - 能量潮
def calculate_indicator(df):
    obv = (np.sign(df['close'].diff()) * df['vol']).fillna(0).cumsum()
    df['OBV'] = obv
    return df
""",
            "CCI - 顺势指标": """# CCI - 顺势指标
def calculate_indicator(df, period=20):
    tp = (df['high'] + df['low'] + df['close']) / 3
    ma = tp.rolling(period).mean()
    md = tp.rolling(period).apply(lambda x: np.abs(x - x.mean()).mean())
    df[f'CCI{period}'] = (tp - ma) / (0.015 * md)
    return df
""",
            "WR - 威廉指标": """# WR - 威廉指标
def calculate_indicator(df, period=14):
    high_max = df['high'].rolling(period).max()
    low_min = df['low'].rolling(period).min()
    df[f'WR{period}'] = -100 * (high_max - df['close']) / (high_max - low_min)
    return df
""",
        }

    def _load_template_code(self, template_name):
        """加载模板代码"""
        templates = self._get_templates()

        # 映射：内置指标列表项 -> 模板键
        indicator_to_template = {
            "MA - 移动平均线": "移动平均 (MA)",
            "EMA - 指数移动平均": "EMA - 指数移动平均",
            "MACD - 异同移动平均线": "MACD",
            "RSI - 相对强弱指数": "相对强弱指数 (RSI)",
            "KDJ - 随机指标": "KDJ - 随机指标",
            "BOLL - 布林带": "布林带",
            "ATR - 平均真实波幅": "ATR - 平均真实波幅",
            "OBV - 能量潮": "OBV - 能量潮",
            "CCI - 顺势指标": "CCI - 顺势指标",
            "WR - 威廉指标": "WR - 威廉指标",
        }

        # 先尝试从内置指标名匹配
        if template_name in indicator_to_template:
            key = indicator_to_template[template_name]
            if key in templates:
                self.code_editor.setPlainText(templates[key])
                self.template_combo.blockSignals(True)
                idx = self.template_combo.findText(key)
                if idx >= 0:
                    self.template_combo.setCurrentIndex(idx)
                self.template_combo.blockSignals(False)
                return

        # 再尝试直接匹配模板名
        for key, code in templates.items():
            if key in template_name or template_name in key:
                self.code_editor.setPlainText(code)
                self.template_combo.blockSignals(True)
                idx = self.template_combo.findText(key)
                if idx >= 0:
                    self.template_combo.setCurrentIndex(idx)
                self.template_combo.blockSignals(False)
                return

        # 默认使用空白模板
        self.code_editor.setPlainText(templates.get("空白模板", ""))

    def _read_csv(self, filepath: Path) -> pd.DataFrame:
        """读取CSV并标准化列名、日期"""
        df = pd.read_csv(filepath)

        # 标准化列名
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
                col_map[c] = 'vol'
            elif cl in ('amount', '成交额'):
                col_map[c] = 'amount'
        df.rename(columns=col_map, inplace=True)

        # 解析 trade_date -> date (若原始列为 trade_date)
        if 'date' not in df.columns and 'trade_date' in df.columns:
            df['date'] = pd.to_datetime(df['trade_date'].astype(str), format='%Y%m%d')
        elif 'date' in df.columns:
            date_raw = df['date'].astype(str).str.strip()
            df['date'] = pd.to_datetime(date_raw, format='%Y%m%d', errors='coerce')
            mask = df['date'].isna()
            if mask.any():
                df.loc[mask, 'date'] = pd.to_datetime(date_raw[mask], errors='coerce')

        df.dropna(subset=['date'], inplace=True)
        df.sort_values('date', inplace=True)
        df.reset_index(drop=True, inplace=True)
        return df

    def _test_indicator(self):
        """测试指标"""
        code = self.code_editor.toPlainText()
        name = self.indicator_name_edit.text() or "未命名"

        self.test_output.clear()
        self.test_output.append(f"测试指标: {name}")
        self.test_output.append("=" * 50)

        # 1. 选择股票
        idx = self.stock_combo.currentIndex()
        if idx < 0 or idx >= len(self._stock_items):
            self.test_output.append("\n[错误] 请先选择一只股票")
            self._draw_empty_chart()
            return

        code_str, name_str, filepath = self._stock_items[idx]

        # 2. 加载数据
        try:
            df = self._read_csv(Path(filepath))
        except Exception as e:
            self.test_output.append(f"\n[错误] 加载数据失败: {e}")
            self._draw_empty_chart()
            return

        # 3. 日期范围过滤
        sd = pd.Timestamp(self.start_date.date().toPyDate())
        ed = pd.Timestamp(self.end_date.date().toPyDate())
        df = df[(df['date'] >= sd) & (df['date'] <= ed)].copy()

        if df.empty:
            self.test_output.append("\n[错误] 所选日期范围内没有数据")
            self._draw_empty_chart()
            return

        # 4. 执行用户代码
        restricted = {
            'pd': pd,
            'np': np,
            'df': df,
        }
        try:
            exec(code, restricted)
        except Exception as e:
            self.test_output.append(f"\n[错误] 执行失败:\n{e}")
            self._draw_empty_chart()
            return

        # 5. 获取 calculate_indicator 并调用
        if 'calculate_indicator' not in restricted:
            self.test_output.append("\n[错误] 代码中未定义 calculate_indicator(df) 函数")
            self._draw_empty_chart()
            return

        try:
            result = restricted['calculate_indicator'](df)
        except Exception as e:
            self.test_output.append(f"\n[错误] 指标计算失败:\n{e}")
            self._draw_empty_chart()
            return

        if not isinstance(result, pd.DataFrame):
            self.test_output.append("\n[错误] calculate_indicator 必须返回 DataFrame")
            self._draw_empty_chart()
            return

        # 6. 找出新增列（原始列以外的）
        orig_cols = set(df.columns)
        new_cols = [c for c in result.columns if c not in orig_cols]

        if not new_cols:
            self.test_output.append("\n[提示] 未检测到新增列，请确保在 df 上添加新列并返回 df")
        else:
            self.test_output.append(f"\n新增列: {', '.join(new_cols)}")
            self.test_output.append("\n最后 20 行 (新增列):")
            self.test_output.append("-" * 50)
            display_df = result[['date'] + new_cols].tail(20)
            self.test_output.append(display_df.to_string())

        self._last_test_df = result
        self._draw_result_chart(result, new_cols if new_cols else [])

    def _draw_empty_chart(self):
        """绘制空图表"""
        self.chart_figure.clear()
        ax = self.chart_figure.add_subplot(111)
        ax.set_facecolor('#1a1a2e')
        ax.text(0.5, 0.5, "运行测试后显示图表", ha='center', va='center',
                fontsize=12, color='#888')
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis('off')
        self.chart_canvas.draw_idle()

    def _draw_result_chart(self, df: pd.DataFrame, indicator_cols: list):
        """绘制价格 + 指标叠加图"""
        self.chart_figure.clear()

        if df.empty:
            self._draw_empty_chart()
            return

        # 价格同量纲指标（叠加在主图）
        price_like = [c for c in indicator_cols if any(x in c for x in ('MA', 'EMA', 'BB_', 'ATR'))]
        # 独立量纲指标（副图）
        other_like = [c for c in indicator_cols if c not in price_like]
        has_sub = len(other_like) > 0

        n_plots = 1 + (1 if has_sub else 0)
        axes = self.chart_figure.subplots(n_plots, 1, sharex=True,
                                         gridspec_kw={'height_ratios': [2, 1] if has_sub else [1],
                                                      'hspace': 0.08})
        if n_plots == 1:
            axes = [axes]
        else:
            axes = list(axes)

        x = np.arange(len(df))
        color_up = '#ef5350'
        color_down = '#26a69a'

        # 主图：价格
        ax_main = axes[0]
        ax_main.set_facecolor('#1a1a2e')
        closes = df['close'].values
        opens = df['open'].values
        highs = df['high'].values
        lows = df['low'].values
        up = closes >= opens
        down = ~up

        body_width = 0.6
        shadow_width = 0.15
        ax_main.bar(x[up], closes[up] - opens[up], body_width,
                    bottom=opens[up], color=color_up, edgecolor=color_up, linewidth=0.5)
        ax_main.bar(x[up], highs[up] - closes[up], shadow_width,
                    bottom=closes[up], color=color_up, edgecolor=color_up, linewidth=0.5)
        ax_main.bar(x[up], opens[up] - lows[up], shadow_width,
                    bottom=lows[up], color=color_up, edgecolor=color_up, linewidth=0.5)
        ax_main.bar(x[down], opens[down] - closes[down], body_width,
                    bottom=closes[down], color=color_down, edgecolor=color_down, linewidth=0.5)
        ax_main.bar(x[down], highs[down] - opens[down], shadow_width,
                    bottom=opens[down], color=color_down, edgecolor=color_down, linewidth=0.5)
        ax_main.bar(x[down], closes[down] - lows[down], shadow_width,
                    bottom=lows[down], color=color_down, edgecolor=color_down, linewidth=0.5)

        # 叠加价格类指标（MA、EMA、BB、ATR）
        colors = ['#ffeb3b', '#ff9800', '#e91e63', '#2196f3', '#ab47bc']
        for i, col in enumerate(price_like[:5]):
            if col in df.columns:
                s = df[col].dropna()
                if len(s) > 0:
                    ax_main.plot(x[s.index], s.values, color=colors[i % len(colors)],
                                linewidth=0.8, label=col, alpha=0.9)
        if price_like:
            ax_main.legend(loc='upper left', fontsize=7, facecolor='#1a1a2e',
                          edgecolor='#444', labelcolor='white')

        ax_main.set_ylabel('价格', color='white', fontsize=9)
        ax_main.tick_params(colors='#ccc', labelsize=7)
        ax_main.spines['top'].set_color('#444')
        ax_main.spines['bottom'].set_color('#444')
        ax_main.spines['left'].set_color('#444')
        ax_main.spines['right'].set_color('#444')
        ax_main.yaxis.label.set_color('white')
        ax_main.grid(True, color='#333', linewidth=0.3, alpha=0.5)
        ax_main.set_xlim(-1, len(df))

        # 副图：RSI、KDJ、MACD、OBV、CCI、WR 等
        if has_sub:
            ax_sub = axes[1]
            ax_sub.set_facecolor('#1a1a2e')
            for i, col in enumerate(other_like[:5]):
                if col in df.columns:
                    s = df[col].dropna()
                    if len(s) > 0:
                        ax_sub.plot(x[s.index], s.values, color=colors[i % len(colors)],
                                    linewidth=0.8, label=col, alpha=0.9)
            ax_sub.legend(loc='upper left', fontsize=7, facecolor='#1a1a2e',
                         edgecolor='#444', labelcolor='white')
            ax_sub.set_ylabel('指标', color='white', fontsize=9)
            ax_sub.tick_params(colors='#ccc', labelsize=7)
            ax_sub.spines['top'].set_color('#444')
            ax_sub.spines['bottom'].set_color('#444')
            ax_sub.spines['left'].set_color('#444')
            ax_sub.spines['right'].set_color('#444')
            ax_sub.yaxis.label.set_color('white')
            ax_sub.grid(True, color='#333', linewidth=0.3, alpha=0.5)
            ax_sub.set_xlim(-1, len(df))

        # X 轴日期
        step = max(1, len(df) // 12)
        tick_pos = list(range(0, len(df), step))
        dates = df['date'].values
        tick_labels = [pd.Timestamp(dates[i]).strftime('%Y-%m-%d') for i in tick_pos]
        ax_bottom = axes[-1]
        ax_bottom.set_xticks(tick_pos)
        ax_bottom.set_xticklabels(tick_labels, rotation=30, fontsize=7, color='#ccc')

        self.chart_figure.subplots_adjust(left=0.06, right=0.97, top=0.95, bottom=0.12)
        self.chart_canvas.draw_idle()

    def _new_indicator(self):
        """新建指标"""
        self.indicator_name_edit.clear()
        self.indicator_desc_edit.clear()
        self.code_editor.clear()
        self.test_output.clear()
        self.template_combo.setCurrentIndex(0)
        self._draw_empty_chart()

    def _save_indicator(self):
        """保存指标"""
        name = self.indicator_name_edit.text()
        if not name:
            QMessageBox.warning(self, "提示", "请输入指标名称")
            return

        code = self.code_editor.toPlainText()
        desc = self.indicator_desc_edit.text()

        indicator_data = {
            "name": name,
            "description": desc,
            "code": code,
            "created_at": __import__('datetime').datetime.now().isoformat()
        }

        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存指标", "", "JSON Files (*.json)"
        )

        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(indicator_data, f, ensure_ascii=False, indent=2)
                QMessageBox.information(self, "成功", "指标保存成功！")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"保存失败: {str(e)}")

    def _load_indicator(self):
        """加载指标"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "加载指标", "", "JSON Files (*.json)"
        )

        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                self.indicator_name_edit.setText(data.get("name", ""))
                self.indicator_desc_edit.setText(data.get("description", ""))
                self.code_editor.setPlainText(data.get("code", ""))

                QMessageBox.information(self, "成功", "指标加载成功！")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"加载失败: {str(e)}")


if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication, QFileDialog

    app = QApplication(sys.argv)
    window = IndicatorDesigner()
    window.setWindowTitle("QuantBox - 量化指标设计器")
    window.resize(1200, 800)
    window.show()
    sys.exit(app.exec_())
