
"""
策略回测面板
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QComboBox, QTextEdit, QSplitter,
    QGroupBox, QFormLayout, QDoubleSpinBox, QSpinBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor


class BacktestPanel(QWidget):
    """策略回测面板"""
    
    def __init__(self):
        super().__init__()
        self._init_ui()
        
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        
        # 顶部控制区
        control_layout = QHBoxLayout()
        
        # 策略选择
        self.strategy_combo = QComboBox()
        self.strategy_combo.addItems([
            "双均线策略",
            "MACD策略",
            "RSI策略",
            "布林带策略",
            "自定义策略"
        ])
        control_layout.addWidget(QLabel("策略:"))
        control_layout.addWidget(self.strategy_combo)
        
        control_layout.addSpacing(20)
        
        # 初始资金
        self.capital_spin = QDoubleSpinBox()
        self.capital_spin.setRange(10000, 10000000)
        self.capital_spin.setValue(1000000)
        self.capital_spin.setPrefix("¥")
        control_layout.addWidget(QLabel("初始资金:"))
        control_layout.addWidget(self.capital_spin)
        
        control_layout.addSpacing(20)
        
        # 手续费
        self.commission_spin = QDoubleSpinBox()
        self.commission_spin.setRange(0, 0.01)
        self.commission_spin.setValue(0.0003)
        self.commission_spin.setSingleStep(0.0001)
        control_layout.addWidget(QLabel("手续费:"))
        control_layout.addWidget(self.commission_spin)
        
        control_layout.addStretch()
        
        # 开始回测按钮
        self.run_btn = QPushButton("开始回测")
        self.run_btn.setMinimumWidth(120)
        self.run_btn.clicked.connect(self._run_backtest)
        control_layout.addWidget(self.run_btn)
        
        layout.addLayout(control_layout)
        
        # 分割器
        splitter = QSplitter(Qt.Vertical)
        
        # 上半部分 - 参数设置和日志
        top_splitter = QSplitter(Qt.Horizontal)
        
        # 参数设置
        params_group = QGroupBox("策略参数")
        params_layout = QFormLayout(params_group)
        
        self.fast_ma_spin = QSpinBox()
        self.fast_ma_spin.setRange(1, 100)
        self.fast_ma_spin.setValue(5)
        params_layout.addRow("短期均线:", self.fast_ma_spin)
        
        self.slow_ma_spin = QSpinBox()
        self.slow_ma_spin.setRange(1, 200)
        self.slow_ma_spin.setValue(20)
        params_layout.addRow("长期均线:", self.slow_ma_spin)
        
        self.stop_loss_spin = QDoubleSpinBox()
        self.stop_loss_spin.setRange(0, 0.5)
        self.stop_loss_spin.setValue(0.05)
        self.stop_loss_spin.setSingleStep(0.01)
        params_layout.addRow("止损比例:", self.stop_loss_spin)
        
        self.take_profit_spin = QDoubleSpinBox()
        self.take_profit_spin.setRange(0, 1)
        self.take_profit_spin.setValue(0.1)
        self.take_profit_spin.setSingleStep(0.01)
        params_layout.addRow("止盈比例:", self.take_profit_spin)
        
        top_splitter.addWidget(params_group)
        
        # 日志输出
        log_group = QGroupBox("回测日志")
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.append("等待回测开始...")
        log_layout.addWidget(self.log_text)
        
        top_splitter.addWidget(log_group)
        top_splitter.setStretchFactor(0, 1)
        top_splitter.setStretchFactor(1, 2)
        
        splitter.addWidget(top_splitter)
        
        # 下半部分 - 回测结果
        result_group = QGroupBox("回测结果")
        result_layout = QVBoxLayout(result_group)
        
        # 绩效指标表格
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(2)
        self.result_table.setHorizontalHeaderLabels(["指标", "数值"])
        self.result_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        # 添加示例指标
        metrics = [
            ("总收益率", "-"),
            ("年化收益率", "-"),
            ("最大回撤", "-"),
            ("夏普比率", "-"),
            ("胜率", "-"),
            ("交易次数", "-"),
            ("盈利次数", "-"),
            ("亏损次数", "-"),
        ]
        
        self.result_table.setRowCount(len(metrics))
        for i, (name, value) in enumerate(metrics):
            self.result_table.setItem(i, 0, QTableWidgetItem(name))
            self.result_table.setItem(i, 1, QTableWidgetItem(value))
        
        result_layout.addWidget(self.result_table)
        
        splitter.addWidget(result_group)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        
        layout.addWidget(splitter)
        
    def _run_backtest(self):
        """运行回测"""
        self.log_text.append("=" * 50)
        self.log_text.append("开始回测...")
        self.log_text.append(f"策略: {self.strategy_combo.currentText()}")
        self.log_text.append(f"初始资金: ¥{self.capital_spin.value():,.0f}")
        self.log_text.append(f"手续费: {self.commission_spin.value()*100:.2f}%")
        self.log_text.append("=" * 50)
        
        # TODO: 实际的回测逻辑
        self.log_text.append("\n[提示] 回测功能需要完善...")
        self.log_text.append("请实现完整的回测引擎集成")
        
        # 更新结果表格（示例）
        self.result_table.setItem(0, 1, QTableWidgetItem("15.23%"))
        self.result_table.setItem(1, 1, QTableWidgetItem("12.58%"))
        self.result_table.setItem(2, 1, QTableWidgetItem("-8.45%"))
        self.result_table.setItem(3, 1, QTableWidgetItem("1.25"))
        self.result_table.setItem(4, 1, QTableWidgetItem("56.78%"))
        self.result_table.setItem(5, 1, QTableWidgetItem("124"))
        self.result_table.setItem(6, 1, QTableWidgetItem("70"))
        self.result_table.setItem(7, 1, QTableWidgetItem("54"))

