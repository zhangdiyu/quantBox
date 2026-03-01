
"""
持仓管理面板
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QSplitter, QGroupBox, QFormLayout,
    QDoubleSpinBox, QDateEdit, QMessageBox
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QColor, QFont


class PortfolioPanel(QWidget):
    """持仓管理面板"""
    
    def __init__(self):
        super().__init__()
        self._init_ui()
        
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        
        # 顶部汇总信息
        summary_layout = QHBoxLayout()
        
        # 总资产
        total_group = QGroupBox("总资产")
        total_layout = QVBoxLayout(total_group)
        self.total_label = QLabel("¥1,000,000.00")
        self.total_label.setFont(QFont("Arial", 20, QFont.Bold))
        self.total_label.setStyleSheet("color: #2ecc71;")
        total_layout.addWidget(self.total_label)
        summary_layout.addWidget(total_group)
        
        # 总市值
        market_group = QGroupBox("总市值")
        market_layout = QVBoxLayout(market_group)
        self.market_label = QLabel("¥850,000.00")
        self.market_label.setFont(QFont("Arial", 16))
        market_layout.addWidget(self.market_label)
        summary_layout.addWidget(market_group)
        
        # 可用资金
        cash_group = QGroupBox("可用资金")
        cash_layout = QVBoxLayout(cash_group)
        self.cash_label = QLabel("¥150,000.00")
        self.cash_label.setFont(QFont("Arial", 16))
        cash_layout.addWidget(self.cash_label)
        summary_layout.addWidget(cash_group)
        
        # 总盈亏
        pnl_group = QGroupBox("总盈亏")
        pnl_layout = QVBoxLayout(pnl_group)
        self.pnl_label = QLabel("+¥25,000.00 (+2.50%)")
        self.pnl_label.setFont(QFont("Arial", 16))
        self.pnl_label.setStyleSheet("color: #2ecc71;")
        pnl_layout.addWidget(self.pnl_label)
        summary_layout.addWidget(pnl_group)
        
        layout.addLayout(summary_layout)
        
        # 分割器
        splitter = QSplitter(Qt.Vertical)
        
        # 上半部分 - 持仓列表
        holdings_group = QGroupBox("当前持仓")
        holdings_layout = QVBoxLayout(holdings_group)
        
        self.holdings_table = QTableWidget()
        self.holdings_table.setColumnCount(8)
        self.holdings_table.setHorizontalHeaderLabels([
            "代码", "名称", "持仓数量", "持仓市值", 
            "成本价", "现价", "盈亏", "盈亏比例"
        ])
        self.holdings_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.holdings_table.setAlternatingRowColors(True)
        
        # 添加示例持仓
        sample_holdings = [
            ("000001", "平安银行", 1000, 12500, 11.50, 12.50, "+1000", "+8.70%"),
            ("000002", "万科A", 500, 8750, 16.00, 17.50, "+750", "+9.38%"),
            ("600519", "贵州茅台", 10, 18000, 1750.00, 1800.00, "+500", "+2.86%"),
        ]
        
        self.holdings_table.setRowCount(len(sample_holdings))
        for i, (code, name, qty, value, cost, price, pnl, pnl_pct) in enumerate(sample_holdings):
            self.holdings_table.setItem(i, 0, QTableWidgetItem(code))
            self.holdings_table.setItem(i, 1, QTableWidgetItem(name))
            self.holdings_table.setItem(i, 2, QTableWidgetItem(str(qty)))
            self.holdings_table.setItem(i, 3, QTableWidgetItem(f"¥{value:,.2f}"))
            self.holdings_table.setItem(i, 4, QTableWidgetItem(f"¥{cost:.2f}"))
            self.holdings_table.setItem(i, 5, QTableWidgetItem(f"¥{price:.2f}"))
            
            pnl_item = QTableWidgetItem(pnl)
            if pnl.startswith("+"):
                pnl_item.setForeground(QColor("#2ecc71"))
            else:
                pnl_item.setForeground(QColor("#e74c3c"))
            self.holdings_table.setItem(i, 6, pnl_item)
            
            pnl_pct_item = QTableWidgetItem(pnl_pct)
            if pnl_pct.startswith("+"):
                pnl_pct_item.setForeground(QColor("#2ecc71"))
            else:
                pnl_pct_item.setForeground(QColor("#e74c3c"))
            self.holdings_table.setItem(i, 7, pnl_pct_item)
        
        holdings_layout.addWidget(self.holdings_table)
        splitter.addWidget(holdings_group)
        
        # 下半部分 - 交易记录和信号提醒
        bottom_splitter = QSplitter(Qt.Horizontal)
        
        # 交易记录
        trades_group = QGroupBox("交易记录")
        trades_layout = QVBoxLayout(trades_group)
        
        self.trades_table = QTableWidget()
        self.trades_table.setColumnCount(5)
        self.trades_table.setHorizontalHeaderLabels(["日期", "代码", "名称", "操作", "数量"])
        self.trades_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        sample_trades = [
            ("2024-01-15", "000001", "平安银行", "买入", 1000),
            ("2024-01-16", "000002", "万科A", "买入", 500),
            ("2024-01-17", "600519", "贵州茅台", "买入", 10),
        ]
        
        self.trades_table.setRowCount(len(sample_trades))
        for i, (date, code, name, action, qty) in enumerate(sample_trades):
            self.trades_table.setItem(i, 0, QTableWidgetItem(date))
            self.trades_table.setItem(i, 1, QTableWidgetItem(code))
            self.trades_table.setItem(i, 2, QTableWidgetItem(name))
            
            action_item = QTableWidgetItem(action)
            if action == "买入":
                action_item.setForeground(QColor("#2ecc71"))
            else:
                action_item.setForeground(QColor("#e74c3c"))
            self.trades_table.setItem(i, 3, action_item)
            
            self.trades_table.setItem(i, 4, QTableWidgetItem(str(qty)))
        
        trades_layout.addWidget(self.trades_table)
        bottom_splitter.addWidget(trades_group)
        
        # 信号提醒
        signals_group = QGroupBox("今日信号")
        signals_layout = QVBoxLayout(signals_group)
        
        self.signals_table = QTableWidget()
        self.signals_table.setColumnCount(4)
        self.signals_table.setHorizontalHeaderLabels(["时间", "代码", "名称", "信号"])
        self.signals_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        sample_signals = [
            ("09:30:00", "600036", "招商银行", "买入"),
            ("10:15:00", "000858", "五粮液", "持有"),
            ("14:30:00", "601318", "中国平安", "卖出"),
        ]
        
        self.signals_table.setRowCount(len(sample_signals))
        for i, (time, code, name, signal) in enumerate(sample_signals):
            self.signals_table.setItem(i, 0, QTableWidgetItem(time))
            self.signals_table.setItem(i, 1, QTableWidgetItem(code))
            self.signals_table.setItem(i, 2, QTableWidgetItem(name))
            
            signal_item = QTableWidgetItem(signal)
            if signal == "买入":
                signal_item.setForeground(QColor("#2ecc71"))
            elif signal == "卖出":
                signal_item.setForeground(QColor("#e74c3c"))
            self.signals_table.setItem(i, 3, signal_item)
        
        signals_layout.addWidget(self.signals_table)
        bottom_splitter.addWidget(signals_group)
        
        bottom_splitter.setStretchFactor(0, 1)
        bottom_splitter.setStretchFactor(1, 1)
        
        splitter.addWidget(bottom_splitter)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        
        layout.addWidget(splitter)
        
        # 底部操作按钮
        button_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("刷新数据")
        self.refresh_btn.clicked.connect(self._refresh)
        button_layout.addWidget(self.refresh_btn)
        
        self.export_btn = QPushButton("导出持仓")
        self.export_btn.clicked.connect(self._export)
        button_layout.addWidget(self.export_btn)
        
        button_layout.addStretch()
        
        self.signal_check_btn = QPushButton("检查信号")
        self.signal_check_btn.clicked.connect(self._check_signals)
        button_layout.addWidget(self.signal_check_btn)
        
        layout.addLayout(button_layout)
        
    def _refresh(self):
        """刷新数据"""
        QMessageBox.information(self, "提示", "刷新功能需要完善...")
        
    def _export(self):
        """导出持仓"""
        QMessageBox.information(self, "提示", "导出功能需要完善...")
        
    def _check_signals(self):
        """检查信号"""
        QMessageBox.information(self, "提示", "信号检查功能需要完善...")

