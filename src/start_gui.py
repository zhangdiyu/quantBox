
"""
QuantBox GUI 启动脚本
"""
import sys
from pathlib import Path

# 添加项目根目录到Python路径
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR
sys.path.insert(0, str(PROJECT_ROOT))

from gui.app import main

if __name__ == "__main__":
    main()

