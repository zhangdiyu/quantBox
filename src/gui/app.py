
"""
QuantBox GUI 主程序入口
"""
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QPalette, QColor

from gui.main_window import MainWindow


def set_dark_theme(app):
    """设置深色主题"""
    app.setStyle("Fusion")
    
    dark_palette = QPalette()
    
    dark_palette.setColor(QPalette.Window, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.WindowText, Qt.white)
    dark_palette.setColor(QPalette.Base, QColor(25, 25, 25))
    dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ToolTipBase, Qt.white)
    dark_palette.setColor(QPalette.ToolTipText, Qt.white)
    dark_palette.setColor(QPalette.Text, Qt.white)
    dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ButtonText, Qt.white)
    dark_palette.setColor(QPalette.BrightText, Qt.red)
    dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.HighlightedText, Qt.black)
    
    app.setPalette(dark_palette)


def main():
    """主函数"""
    # 抑制 Windows 上 "Unable to open default EUDC font" 警告
    os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = os.environ.get("QT_QPA_PLATFORM_PLUGIN_PATH", "")
    os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.fonts.warning=false")

    app = QApplication(sys.argv)
    app.setApplicationName("QuantBox - 量化研究平台")
    app.setOrganizationName("QuantBox")
    
    # 设置默认字体
    font = QFont("Microsoft YaHei", 9)
    app.setFont(font)
    
    # 设置深色主题
    set_dark_theme(app)
    
    # 创建主窗口
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

