
"""
信号提醒系统
处理持仓管理和每日交易信号提醒
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTableWidget, QTableWidgetItem, QHeaderView,
    QGroupBox, QFormLayout, QCheckBox, QSpinBox,
    QDoubleSpinBox, QTimeEdit, QSystemTrayIcon, QMenu,
    QMessageBox, QComboBox
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QTime, QDate
from PyQt5.QtGui import QIcon, QColor, QFont

import json
from pathlib import Path
from datetime import datetime, time


class SignalAlertSystem(QWidget):
    """信号提醒系统"""
    
    signal_triggered = pyqtSignal(str, str, str)  # 时间, 代码, 信号
    
    def __init__(self):
        super().__init__()
        self._init_ui()
        self._init_timer()
        self._load_settings()
        
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        
        # 顶部 - 提醒设置
        settings_group = QGroupBox("提醒设置")
        settings_layout = QFormLayout(settings_group)
        
        # 启用提醒
        self.enable_alerts = QCheckBox("启用信号提醒")
        self.enable_alerts.setChecked(True)
        self.enable_alerts.toggled.connect(self._on_alerts_toggled)
        settings_layout.addRow(self.enable_alerts)
        
        # 检查间隔
        self.check_interval = QSpinBox()
        self.check_interval.setRange(1, 60)
        self.check_interval.setValue(5)
        self.check_interval.setSuffix(" 分钟")
        settings_layout.addRow("检查间隔:", self.check_interval)
        
        # 提醒时间范围
        time_layout = QHBoxLayout()
        self.start_time = QTimeEdit(QTime(9, 0))
        self.end_time = QTimeEdit(QTime(15, 0))
        time_layout.addWidget(self.start_time)
        time_layout.addWidget(QLabel("至"))
        time_layout.addWidget(self.end_time)
        settings_layout.addRow("交易时间:", time_layout)
        
        # 提醒方式
        self.alert_sound = QCheckBox("播放声音")
        self.alert_sound.setChecked(True)
        settings_layout.addRow("声音提醒:", self.alert_sound)
        
        self.alert_popup = QCheckBox("弹窗提醒")
        self.alert_popup.setChecked(True)
        settings_layout.addRow("弹窗提醒:", self.alert_popup)
        
        self.alert_tray = QCheckBox("托盘通知")
        self.alert_tray.setChecked(True)
        settings_layout.addRow("托盘通知:", self.alert_tray)
        
        layout.addWidget(settings_group)
        
        # 中间 - 策略信号配置
        strategy_group = QGroupBox("信号策略")
        strategy_layout = QVBoxLayout(strategy_group)
        
        # 策略列表
        self.strategy_table = QTableWidget()
        self.strategy_table.setColumnCount(4)
        self.strategy_table.setHorizontalHeaderLabels(["策略名称", "股票池", "启用", "参数"])
        self.strategy_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        # 添加示例策略
        sample_strategies = [
            ("双均线策略", "自选股", True, "fast=5, slow=20"),
            ("MACD策略", "沪深300", True, "fast=12, slow=26, signal=9"),
            ("RSI策略", "中证500", False, "period=14, overbought=70, oversold=30"),
            ("布林带策略", "全部A股", True, "period=20, std=2"),
        ]
        
        self.strategy_table.setRowCount(len(sample_strategies))
        for i, (name, pool, enabled, params) in enumerate(sample_strategies):
            self.strategy_table.setItem(i, 0, QTableWidgetItem(name))
            self.strategy_table.setItem(i, 1, QTableWidgetItem(pool))
            
            enabled_item = QTableWidgetItem()
            enabled_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            enabled_item.setCheckState(Qt.Checked if enabled else Qt.Unchecked)
            self.strategy_table.setItem(i, 2, enabled_item)
            
            self.strategy_table.setItem(i, 3, QTableWidgetItem(params))
        
        strategy_layout.addWidget(self.strategy_table)
        
        # 策略按钮
        strategy_btn_layout = QHBoxLayout()
        self.add_strategy_btn = QPushButton("添加策略")
        self.edit_strategy_btn = QPushButton("编辑策略")
        self.delete_strategy_btn = QPushButton("删除策略")
        strategy_btn_layout.addWidget(self.add_strategy_btn)
        strategy_btn_layout.addWidget(self.edit_strategy_btn)
        strategy_btn_layout.addWidget(self.delete_strategy_btn)
        strategy_btn_layout.addStretch()
        strategy_layout.addLayout(strategy_btn_layout)
        
        layout.addWidget(strategy_group)
        
        # 底部 - 信号历史
        history_group = QGroupBox("信号历史")
        history_layout = QVBoxLayout(history_group)
        
        self.signal_history = QTableWidget()
        self.signal_history.setColumnCount(5)
        self.signal_history.setHorizontalHeaderLabels(["时间", "代码", "名称", "信号", "价格"])
        self.signal_history.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.signal_history.setAlternatingRowColors(True)
        
        # 添加示例信号
        sample_signals = [
            ("2024-01-15 09:35:00", "000001", "平安银行", "买入", "12.45"),
            ("2024-01-15 10:15:00", "000002", "万科A", "持有", "18.20"),
            ("2024-01-15 14:30:00", "600519", "贵州茅台", "卖出", "1785.00"),
        ]
        
        self.signal_history.setRowCount(len(sample_signals))
        for i, (time, code, name, signal, price) in enumerate(sample_signals):
            self.signal_history.setItem(i, 0, QTableWidgetItem(time))
            self.signal_history.setItem(i, 1, QTableWidgetItem(code))
            self.signal_history.setItem(i, 2, QTableWidgetItem(name))
            
            signal_item = QTableWidgetItem(signal)
            if signal == "买入":
                signal_item.setForeground(QColor("#2ecc71"))
                signal_item.setFont(QFont("Arial", 9, QFont.Bold))
            elif signal == "卖出":
                signal_item.setForeground(QColor("#e74c3c"))
                signal_item.setFont(QFont("Arial", 9, QFont.Bold))
            self.signal_history.setItem(i, 3, signal_item)
            
            self.signal_history.setItem(i, 4, QTableWidgetItem(f"¥{price}"))
        
        history_layout.addWidget(self.signal_history)
        
        # 历史按钮
        history_btn_layout = QHBoxLayout()
        self.clear_history_btn = QPushButton("清空历史")
        self.export_history_btn = QPushButton("导出历史")
        self.refresh_history_btn = QPushButton("刷新")
        history_btn_layout.addWidget(self.clear_history_btn)
        history_btn_layout.addWidget(self.export_history_btn)
        history_btn_layout.addStretch()
        history_btn_layout.addWidget(self.refresh_history_btn)
        history_layout.addLayout(history_btn_layout)
        
        layout.addWidget(history_group)
        
    def _init_timer(self):
        """初始化定时器"""
        self.check_timer = QTimer()
        self.check_timer.timeout.connect(self._check_signals)
        self.check_timer.start(5 * 60 * 1000)  # 每5分钟检查一次
        
    def _load_settings(self):
        """加载设置"""
        settings_file = Path(__file__).parent / "signal_settings.json"
        if settings_file.exists():
            try:
                with open(settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                # 应用设置...
            except:
                pass
                
    def _save_settings(self):
        """保存设置"""
        settings = {
            "enable_alerts": self.enable_alerts.isChecked(),
            "check_interval": self.check_interval.value(),
            "start_time": self.start_time.time().toString("HH:mm"),
            "end_time": self.end_time.time().toString("HH:mm"),
            "alert_sound": self.alert_sound.isChecked(),
            "alert_popup": self.alert_popup.isChecked(),
            "alert_tray": self.alert_tray.isChecked(),
        }
        
        settings_file = Path(__file__).parent / "signal_settings.json"
        try:
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存设置失败: {e}")
            
    def _on_alerts_toggled(self, enabled):
        """提醒开关切换"""
        if enabled:
            interval = self.check_interval.value() * 60 * 1000
            self.check_timer.start(interval)
        else:
            self.check_timer.stop()
            
    def _check_signals(self):
        """检查交易信号"""
        if not self.enable_alerts.isChecked():
            return
            
        # 检查是否在交易时间内
        current_time = QTime.currentTime()
        start = self.start_time.time()
        end = self.end_time.time()
        
        if not (start &lt;= current_time &lt;= end):
            return
            
        # TODO: 实现真实的信号检查逻辑
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 检查交易信号...")
        
    def add_signal(self, code, name, signal, price):
        """添加信号"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 插入到表格顶部
        self.signal_history.insertRow(0)
        self.signal_history.setItem(0, 0, QTableWidgetItem(timestamp))
        self.signal_history.setItem(0, 1, QTableWidgetItem(code))
        self.signal_history.setItem(0, 2, QTableWidgetItem(name))
        
        signal_item = QTableWidgetItem(signal)
        if signal == "买入":
            signal_item.setForeground(QColor("#2ecc71"))
            signal_item.setFont(QFont("Arial", 9, QFont.Bold))
        elif signal == "卖出":
            signal_item.setForeground(QColor("#e74c3c"))
            signal_item.setFont(QFont("Arial", 9, QFont.Bold))
        self.signal_history.setItem(0, 3, signal_item)
        
        self.signal_history.setItem(0, 4, QTableWidgetItem(f"¥{price}"))
        
        # 发送信号
        self.signal_triggered.emit(timestamp, code, signal)
        
        # 提醒
        if self.alert_popup.isChecked():
            QMessageBox.information(
                self, 
                "交易信号", 
                f"{timestamp}\n{code} {name}\n信号: {signal}\n价格: ¥{price}"
            )


if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    window = SignalAlertSystem()
    window.setWindowTitle("QuantBox - 信号提醒系统")
    window.resize(1000, 800)
    window.show()
    sys.exit(app.exec_())

