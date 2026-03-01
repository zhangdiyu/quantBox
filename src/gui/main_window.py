
"""
QuantBox 主窗口
"""
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QStatusBar, QMenuBar, QToolBar,
    QSplitter, QDockWidget, QListWidget, QTreeWidget,
    QTreeWidgetItem, QLabel, QPushButton, QFileDialog,
    QMessageBox, QProgressBar
)
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QThread
from PyQt5.QtGui import QIcon, QAction

from pathlib import Path
import sys

# 导入各个模块
from gui.data_panel import DataPanel
from gui.chart_panel import ChartPanel
from gui.backtest_panel import BacktestPanel
from gui.portfolio_panel import PortfolioPanel
from gui.indicator_designer import IndicatorDesigner

class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("QuantBox - 量化研究平台")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)
        
        # 初始化UI
        self._init_ui()
        self._init_menu()
        self._init_toolbar()
        self._init_statusbar()
        
    def _init_ui(self):
        """初始化UI布局"""
        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 创建选项卡窗口
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.North)
        
        # 添加各个面板
        self.data_panel = DataPanel()
        self.chart_panel = ChartPanel()
        self.backtest_panel = BacktestPanel()
        self.portfolio_panel = PortfolioPanel()
        self.indicator_designer = IndicatorDesigner()

        self.tab_widget.addTab(self.data_panel, "数据管理")
        self.tab_widget.addTab(self.chart_panel, "K线图表")
        self.tab_widget.addTab(self.backtest_panel, "策略回测")
        self.tab_widget.addTab(self.portfolio_panel, "持仓管理")
        self.tab_widget.addTab(self.indicator_designer, "指标设计器")
        main_layout.addWidget(self.tab_widget)
        
        # 创建左侧停靠窗口 - 股票列表
        self._create_stock_dock()
        
    def _create_stock_dock(self):
        """创建股票列表停靠窗口"""
        self.stock_dock = QDockWidget("股票池", self)
        self.stock_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        
        # 股票列表
        self.stock_list = QTreeWidget()
        self.stock_list.setHeaderLabels(["代码", "名称"])
        self.stock_list.setColumnWidth(0, 100)
        self.stock_list.setColumnWidth(1, 150)
        
        # 添加示例数据
        sample_stocks = [
            ("000001", "平安银行"),
            ("000002", "万科A"),
            ("600000", "浦发银行"),
            ("600519", "贵州茅台"),
        ]
        
        for code, name in sample_stocks:
            item = QTreeWidgetItem([code, name])
            self.stock_list.addTopLevelItem(item)
        
        self.stock_dock.setWidget(self.stock_list)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.stock_dock)
        
    def _init_menu(self):
        """初始化菜单栏"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu("文件(&amp;F)")
        
        # 打开数据文件夹
        open_action = QAction("打开数据文件夹", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._open_data_folder)
        file_menu.addAction(open_action)
        
        file_menu.addSeparator()
        
        # 退出
        exit_action = QAction("退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 视图菜单
        view_menu = menubar.addMenu("视图(&amp;V)")
        
        # 显示/隐藏股票池
        toggle_stock_dock = QAction("股票池", self)
        toggle_stock_dock.setCheckable(True)
        toggle_stock_dock.setChecked(True)
        toggle_stock_dock.triggered.connect(self.stock_dock.toggleViewAction().trigger)
        view_menu.addAction(toggle_stock_dock)
        
        # 工具菜单
        tools_menu = menubar.addMenu("工具(&amp;T)")
        
        # 下载数据
        download_action = QAction("下载股票数据", self)
        download_action.triggered.connect(self._download_data)
        tools_menu.addAction(download_action)
        
        # 下载指数
        download_indices_action = QAction("下载指数数据", self)
        download_indices_action.triggered.connect(self._download_indices)
        tools_menu.addAction(download_indices_action)
        
        # 帮助菜单
        help_menu = menubar.addMenu("帮助(&amp;H)")
        
        # 关于
        about_action = QAction("关于", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
        
    def _init_toolbar(self):
        """初始化工具栏"""
        toolbar = QToolBar("主工具栏")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        
        # 刷新按钮
        refresh_action = QAction("刷新", self)
        refresh_action.triggered.connect(self._refresh)
        toolbar.addAction(refresh_action)
        
        toolbar.addSeparator()
        
        # 下载按钮
        download_action = QAction("下载数据", self)
        download_action.triggered.connect(self._download_data)
        toolbar.addAction(download_action)
        
    def _init_statusbar(self):
        """初始化状态栏"""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        
        # 状态标签
        self.status_label = QLabel("就绪")
        self.statusbar.addWidget(self.status_label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumWidth(200)
        self.statusbar.addPermanentWidget(self.progress_bar)
        
    def _open_data_folder(self):
        """打开数据文件夹"""
        data_path = Path(__file__).parent.parent / "data"
        if data_path.exists():
            import subprocess
            import os
            if sys.platform == 'win32':
                os.startfile(str(data_path))
            elif sys.platform == 'darwin':
                subprocess.call(['open', str(data_path)])
            else:
                subprocess.call(['xdg-open', str(data_path)])
        else:
            QMessageBox.warning(self, "提示", "数据文件夹不存在")
            
    def _download_data(self):
        """下载股票数据"""
        self.status_label.setText("正在启动数据下载...")
        QMessageBox.information(self, "提示", "请在终端运行: python src/download_kline.py")
        
    def _download_indices(self):
        """下载指数数据"""
        self.status_label.setText("正在启动指数下载...")
        QMessageBox.information(self, "提示", "请在终端运行: python src/download_indices.py")
        
    def _refresh(self):
        """刷新"""
        self.status_label.setText("正在刷新...")
        # TODO: 实现刷新逻辑
        self.status_label.setText("刷新完成")
        
    def _show_about(self):
        """显示关于对话框"""
        QMessageBox.about(
            self,
            "关于 QuantBox",
            "&lt;h3&gt;QuantBox 量化研究平台&lt;/h3&gt;"
            "&lt;p&gt;版本: 1.0.0&lt;/p&gt;"
            "&lt;p&gt;完整的A股量化研究解决方案&lt;/p&gt;"
            "&lt;p&gt;数据获取 → 技术指标 → 策略回测 → 可视化报告&lt;/p&gt;"
        )

