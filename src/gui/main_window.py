# -*- coding: utf-8 -*-
"""
QuantBox 主窗口
"""

from PyQt5.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QStatusBar,
    QMenuBar,
    QToolBar,
    QSplitter,
    QDockWidget,
    QListWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QLabel,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QProgressBar,
    QAction,
    QLineEdit,
)
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QThread
from PyQt5.QtGui import QIcon

from pathlib import Path
import sys
import os
import subprocess

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

        self._init_ui()
        self._init_menu()
        self._init_toolbar()
        self._init_statusbar()
        self._connect_signals()

        # reload_stock_list 在 ChartPanel.__init__ 中已执行过，
        # 但当时信号尚未连接，所以手动填充侧边栏股票树
        self._populate_stock_tree(self.chart_panel.get_stock_items())

    # ------------------------------------------------------------------ #
    #  初始化
    # ------------------------------------------------------------------ #
    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.North)

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

        self._create_stock_dock()

    def _create_stock_dock(self):
        self.stock_dock = QDockWidget("股票池", self)
        self.stock_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        dock_widget = QWidget()
        dock_layout = QVBoxLayout(dock_widget)
        dock_layout.setContentsMargins(4, 4, 4, 4)

        # 搜索框
        self.stock_search = QLineEdit()
        self.stock_search.setPlaceholderText("搜索代码或名称…")
        self.stock_search.textChanged.connect(self._filter_stock_tree)
        dock_layout.addWidget(self.stock_search)

        self.stock_list = QTreeWidget()
        self.stock_list.setHeaderLabels(["代码", "名称"])
        self.stock_list.setColumnWidth(0, 80)
        self.stock_list.setColumnWidth(1, 120)
        self.stock_list.itemDoubleClicked.connect(self._on_stock_double_click)
        dock_layout.addWidget(self.stock_list)

        self.stock_count_label = QLabel("共 0 只")
        self.stock_count_label.setAlignment(Qt.AlignRight)
        self.stock_count_label.setStyleSheet("color: gray; font-size: 11px;")
        dock_layout.addWidget(self.stock_count_label)

        self.stock_dock.setWidget(dock_widget)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.stock_dock)

    def _connect_signals(self):
        self.chart_panel.stock_list_updated.connect(self._populate_stock_tree)

    # ------------------------------------------------------------------ #
    #  菜单 & 工具栏
    # ------------------------------------------------------------------ #
    def _init_menu(self):
        menubar = self.menuBar()

        # ---- 文件 ----
        file_menu = menubar.addMenu("文件(&F)")

        open_file_action = QAction("打开CSV文件…", self)
        open_file_action.setShortcut("Ctrl+O")
        open_file_action.triggered.connect(self._open_csv_file)
        file_menu.addAction(open_file_action)

        open_folder_action = QAction("打开数据文件夹", self)
        open_folder_action.triggered.connect(self._open_data_folder)
        file_menu.addAction(open_folder_action)

        file_menu.addSeparator()

        exit_action = QAction("退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # ---- 视图 ----
        view_menu = menubar.addMenu("视图(&V)")
        toggle_stock_dock = self.stock_dock.toggleViewAction()
        toggle_stock_dock.setText("股票池")
        view_menu.addAction(toggle_stock_dock)

        # ---- 工具 ----
        tools_menu = menubar.addMenu("工具(&T)")

        download_action = QAction("下载股票数据", self)
        download_action.triggered.connect(self._download_data)
        tools_menu.addAction(download_action)

        download_indices_action = QAction("下载指数数据", self)
        download_indices_action.triggered.connect(self._download_indices)
        tools_menu.addAction(download_indices_action)

        download_etf_action = QAction("下载ETF数据", self)
        download_etf_action.triggered.connect(self._download_etf)
        tools_menu.addAction(download_etf_action)

        # ---- 帮助 ----
        help_menu = menubar.addMenu("帮助(&H)")
        about_action = QAction("关于", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _init_toolbar(self):
        toolbar = QToolBar("主工具栏")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        refresh_action = QAction("刷新", self)
        refresh_action.triggered.connect(self._refresh)
        toolbar.addAction(refresh_action)

        toolbar.addSeparator()

        download_action = QAction("下载数据", self)
        download_action.triggered.connect(self._download_data)
        toolbar.addAction(download_action)

    def _init_statusbar(self):
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)

        self.status_label = QLabel("就绪")
        self.statusbar.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumWidth(200)
        self.statusbar.addPermanentWidget(self.progress_bar)

    # ------------------------------------------------------------------ #
    #  股票池
    # ------------------------------------------------------------------ #
    def _populate_stock_tree(self, stock_items):
        """chart_panel 扫描完数据目录后，填充侧边栏股票树"""
        self.stock_list.clear()
        self._all_stock_items_for_tree = []

        for code, name, *_ in stock_items:
            item = QTreeWidgetItem([code, name])
            self.stock_list.addTopLevelItem(item)
            self._all_stock_items_for_tree.append((code, name))

        self.stock_count_label.setText(f"共 {len(stock_items)} 只")
        self.status_label.setText(f"已加载 {len(stock_items)} 只股票数据")

    def _filter_stock_tree(self, text):
        text = text.strip().lower()
        for i in range(self.stock_list.topLevelItemCount()):
            item = self.stock_list.topLevelItem(i)
            code = item.text(0).lower()
            name = item.text(1).lower()
            item.setHidden(text != "" and text not in code and text not in name)

    def _on_stock_double_click(self, item, column):
        code = item.text(0)
        self.tab_widget.setCurrentWidget(self.chart_panel)
        self.chart_panel.set_stock_by_code(code)

    # ------------------------------------------------------------------ #
    #  菜单动作
    # ------------------------------------------------------------------ #
    def _open_csv_file(self):
        project_root = Path(__file__).parent.parent.parent
        data_path = project_root / "data"
        start_dir = str(data_path) if data_path.exists() else ""

        filepath, _ = QFileDialog.getOpenFileName(
            self, "打开股票数据文件", start_dir,
            "CSV 文件 (*.csv);;所有文件 (*)"
        )
        if filepath:
            self.tab_widget.setCurrentWidget(self.chart_panel)
            self.chart_panel.load_file(filepath)
            self.status_label.setText(f"已加载: {Path(filepath).name}")

    def _open_data_folder(self):
        project_root = Path(__file__).parent.parent.parent
        data_path = project_root / "data"

        if data_path.exists():
            if sys.platform == "win32":
                os.startfile(str(data_path))
            elif sys.platform == "darwin":
                subprocess.call(["open", str(data_path)])
            else:
                subprocess.call(["xdg-open", str(data_path)])
        else:
            QMessageBox.warning(self, "提示", f"数据文件夹不存在:\n{data_path}")

    def _download_data(self):
        self.status_label.setText("正在启动数据下载...")
        QMessageBox.information(
            self, "提示", "请在终端运行:\npython src/download_kline.py"
        )

    def _download_indices(self):
        self.status_label.setText("正在启动指数下载...")
        QMessageBox.information(
            self, "提示", "请在终端运行:\npython src/download_indices.py"
        )

    def _download_etf(self):
        self.status_label.setText("正在启动ETF数据下载...")
        QMessageBox.information(
            self, "提示", "请在终端运行:\npython src/download_etf.py\n\n"
            "ETF数据将保存到 data/etf/ 目录"
        )

    def _refresh(self):
        self.status_label.setText("正在刷新...")
        self.chart_panel.reload_stock_list()
        self.data_panel._refresh_list()
        self.status_label.setText("刷新完成")

    def _show_about(self):
        QMessageBox.about(
            self,
            "关于 QuantBox",
            "<h3>QuantBox 量化研究平台</h3>"
            "<p>版本: 1.0.0</p>"
            "<p>完整的A股量化研究解决方案</p>"
            "<p>数据获取 → 技术指标 → 策略回测 → 可视化报告</p>",
        )
