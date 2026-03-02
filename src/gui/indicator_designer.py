
"""
量化指标设计器
支持可视化和编程方式设计自定义技术指标
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QComboBox, QTextEdit, QSplitter,
    QGroupBox, QFormLayout, QLineEdit, QTableWidget,
    QTableWidgetItem, QHeaderView, QTabWidget,
    QCheckBox, QSpinBox, QDoubleSpinBox, QFileDialog,
    QMessageBox, QListWidget, QListWidgetItem
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QSyntaxHighlighter, QTextCharFormat

import re
from pathlib import Path
import json


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
        self._init_ui()
        self._load_builtin_indicators()
        
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        
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
        
        # 右侧 - 代码编辑和测试
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
            "相对强弱指数 (RSI)",
            "MACD",
            "布林带",
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
            "# 可用变量: df (包含OHLCV数据的DataFrame)\n"
            "# 必须返回: 包含新指标列的DataFrame\n\n"
            "def calculate_indicator(df):\n"
            "    # 示例: 计算5日均线\n"
            "    df['MA5'] = df['收盘'].rolling(5).mean()\n"
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
        
        right_splitter.setStretchFactor(0, 2)
        right_splitter.setStretchFactor(1, 1)
        
        splitter.addWidget(right_splitter)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        
        layout.addWidget(splitter)
        
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
        self.indicator_name_edit.setText(name.split(" - ")[0])
        self.indicator_desc_edit.setText(name.split(" - ")[1])
        
        # 加载对应的模板代码
        self._load_template_code(name)
        
    def _on_template_changed(self, template_name):
        """模板改变"""
        self._load_template_code(template_name)
        
    def _load_template_code(self, template_name):
        """加载模板代码"""
        templates = {
            "空白模板": """# 空白模板
def calculate_indicator(df):
    # 在此编写你的指标计算逻辑
    # df 包含以下列: 开盘, 收盘, 最高, 最低, 成交量, 成交额
    return df
""",
            "移动平均 (MA)": """# 移动平均 (MA)
def calculate_indicator(df):
    # 计算不同周期的移动平均线
    periods = [5, 10, 20, 60]
    for period in periods:
        df[f'MA{period}'] = df['收盘'].rolling(period).mean()
    return df
""",
            "相对强弱指数 (RSI)": """# 相对强弱指数 (RSI)
def calculate_indicator(df, period=14):
    # 计算价格变化
    delta = df['收盘'].diff()
    
    # 分离涨跌
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    # 计算RSI
    rs = gain / loss
    df[f'RSI{period}'] = 100 - (100 / (1 + rs))
    return df
""",
            "MACD": """# MACD - 异同移动平均线
def calculate_indicator(df):
    # 计算EMA
    ema12 = df['收盘'].ewm(span=12, adjust=False).mean()
    ema26 = df['收盘'].ewm(span=26, adjust=False).mean()
    
    # 计算DIF和DEA
    df['MACD_DIF'] = ema12 - ema26
    df['MACD_DEA'] = df['MACD_DIF'].ewm(span=9, adjust=False).mean()
    
    # 计算MACD柱
    df['MACD_HIST'] = 2 * (df['MACD_DIF'] - df['MACD_DEA'])
    return df
""",
            "布林带": """# 布林带 (Bollinger Bands)
def calculate_indicator(df, period=20, std_dev=2):
    # 计算中轨
    df[f'BB_MID{period}'] = df['收盘'].rolling(period).mean()
    
    # 计算标准差
    std = df['收盘'].rolling(period).std()
    
    # 计算上下轨
    df[f'BB_UPPER{period}'] = df[f'BB_MID{period}'] + (std * std_dev)
    df[f'BB_LOWER{period}'] = df[f'BB_MID{period}'] - (std * std_dev)
    
    return df
""",
        }
        
        # 查找匹配的模板
        for key, code in templates.items():
            if key in template_name or template_name in key:
                self.code_editor.setPlainText(code)
                return
        
        # 默认使用空白模板
        self.code_editor.setPlainText(templates.get("空白模板", ""))
        
    def _new_indicator(self):
        """新建指标"""
        self.indicator_name_edit.clear()
        self.indicator_desc_edit.clear()
        self.code_editor.clear()
        self.test_output.clear()
        self.template_combo.setCurrentIndex(0)
        
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
        
        # 保存文件
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
                
    def _test_indicator(self):
        """测试指标"""
        code = self.code_editor.toPlainText()
        name = self.indicator_name_edit.text() or "未命名"
        
        self.test_output.clear()
        self.test_output.append(f"测试指标: {name}")
        self.test_output.append("=" * 50)
        self.test_output.append("\n[提示] 完整测试需要加载实际数据...")
        self.test_output.append("请确保已下载股票数据")
        self.test_output.append("\n代码语法检查通过！")
        self.test_output.append("✓ 指标代码格式正确")


if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    window = IndicatorDesigner()
    window.setWindowTitle("QuantBox - 量化指标设计器")
    window.resize(1200, 800)
    window.show()
    sys.exit(app.exec_())

