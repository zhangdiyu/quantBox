
"""
数据管理面板
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QSplitter, QLabel, QComboBox, QDateEdit,
    QGroupBox, QFormLayout, QFileDialog, QMessageBox,
    QProgressBar
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QColor

from pathlib import Path
import pandas as pd
import sys


class DataPanel(QWidget):
    """数据管理面板"""
    
    def __init__(self):
        super().__init__()
        self._init_ui()
        
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        
        # 顶部工具栏
        toolbar_layout = QHBoxLayout()
        
        # 刷新按钮
        self.refresh_btn = QPushButton("刷新数据列表")
        self.refresh_btn.clicked.connect(self._refresh_list)
        toolbar_layout.addWidget(self.refresh_btn)
        
        toolbar_layout.addStretch()
        
        # 数据类型选择
        self.data_type_combo = QComboBox()
        self.data_type_combo.addItems(["股票数据", "指数数据"])
        self.data_type_combo.currentTextChanged.connect(self._on_data_type_changed)
        toolbar_layout.addWidget(QLabel("数据类型:"))
        toolbar_layout.addWidget(self.data_type_combo)
        
        layout.addLayout(toolbar_layout)
        
        # 分割器
        splitter = QSplitter(Qt.Vertical)
        
        # 上半部分 - 数据列表
        self.data_table = QTableWidget()
        self.data_table.setColumnCount(4)
        self.data_table.setHorizontalHeaderLabels(["文件名", "代码", "名称", "数据行数"])
        self.data_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.data_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.data_table.itemSelectionChanged.connect(self._on_selection_changed)
        self.data_table.doubleClicked.connect(self._on_double_click)
        splitter.addWidget(self.data_table)
        
        # 下半部分 - 数据预览
        self.preview_table = QTableWidget()
        self.preview_table.setAlternatingRowColors(True)
        splitter.addWidget(self.preview_table)
        
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        
        layout.addWidget(splitter)
        
        # 初始加载数据列表
        self._refresh_list()
        
    def _refresh_list(self):
        """刷新数据列表"""
        data_type = self.data_type_combo.currentText()
        
        # 与 data_updater / data_reader 保持一致，数据在项目根目录的 data/ 下
        if data_type == "股票数据":
            data_dir = Path(__file__).parent.parent.parent / "data"
        else:
            data_dir = Path(__file__).parent.parent.parent / "data" / "indices"
        
        self.data_table.setRowCount(0)
        
        if data_dir.exists():
            csv_files = list(data_dir.glob("*.csv"))
            
            for i, csv_file in enumerate(csv_files):
                try:
                    # 解析文件名
                    filename = csv_file.name
                    parts = filename.replace(".csv", "").split("_")
                    
                    if len(parts) >= 2:
                        code = parts[0]
                        name = "_".join(parts[1:])
                    else:
                        code = parts[0] if len(parts) > 0 else ""
                        name = parts[1] if len(parts) > 1 else ""
                    
                    # 读取行数
                    try:
                        df = pd.read_csv(csv_file, nrows=0)
                        row_count = len(pd.read_csv(csv_file))
                    except:
                        row_count = "未知"
                    
                    # 添加到表格
                    self.data_table.insertRow(i)
                    self.data_table.setItem(i, 0, QTableWidgetItem(filename))
                    self.data_table.setItem(i, 1, QTableWidgetItem(code))
                    self.data_table.setItem(i, 2, QTableWidgetItem(name))
                    self.data_table.setItem(i, 3, QTableWidgetItem(str(row_count)))
                    
                except Exception as e:
                    continue
                    
    def _on_data_type_changed(self, text):
        """数据类型改变"""
        self._refresh_list()
        
    def _on_selection_changed(self):
        """选择改变"""
        selected_items = self.data_table.selectedItems()
        if selected_items:
            self._load_preview(selected_items[0].text())
            
    def _on_double_click(self, index):
        """双击打开"""
        item = self.data_table.item(index.row(), 0)
        if item:
            self._load_preview(item.text())
            
    def _load_preview(self, filename):
        """加载数据预览"""
        data_type = self.data_type_combo.currentText()
        
        if data_type == "股票数据":
            data_dir = Path(__file__).parent.parent.parent / "data"
        else:
            data_dir = Path(__file__).parent.parent.parent / "data" / "indices"
            
        file_path = data_dir / filename
        
        if file_path.exists():
            try:
                df = pd.read_csv(file_path, nrows=100)  # 只加载前100行
                
                self.preview_table.setRowCount(len(df))
                self.preview_table.setColumnCount(len(df.columns))
                self.preview_table.setHorizontalHeaderLabels(df.columns.tolist())
                
                for i, row in df.iterrows():
                    for j, value in enumerate(row):
                        item = QTableWidgetItem(str(value))
                        self.preview_table.setItem(i, j, item)
                        
            except Exception as e:
                QMessageBox.warning(self, "错误", f"无法加载文件: {str(e)}")

