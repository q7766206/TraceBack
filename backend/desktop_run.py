"""
TraceBack 溯·源 桌面应用启动入口
"""

import os
import sys
import io
import time
import threading
import webview
import requests

# ═══════════════════════════════════════════════════════════════
# 强制设置UTF-8编码（Windows中文环境必需）
# ═══════════════════════════════════════════════════════════════

# 设置环境变量
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'

# Windows 平台特殊处理
if sys.platform == 'win32':
    # 设置标准输入输出编码（仅在非打包环境下）
    if not getattr(sys, 'frozen', False):
        try:
            if hasattr(sys.stdout, 'reconfigure'):
                sys.stdout.reconfigure(encoding='utf-8', errors='replace')
                sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
    
    # 设置Windows控制台代码页
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleCP(65001)  # UTF-8
        kernel32.SetConsoleOutputCP(65001)  # UTF-8
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.config import Config

def run_flask():
    """运行Flask应用"""
    app = create_app()
    host = '127.0.0.1'
    port = 5001
    app.run(host=host, port=port, debug=False, threaded=True)

def wait_for_flask(url, timeout=30):
    """等待Flask服务启动"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False

def main():
    """主函数"""
    host = '127.0.0.1'
    port = 5001
    url = f'http://{host}:{port}'
    
    # 启动Flask应用在后台线程（不使用daemon）
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # 等待Flask服务启动
    print(f'等待Flask服务启动: {url}')
    if wait_for_flask(url, timeout=30):
        print('Flask服务已启动，准备打开WebView')
    else:
        print('警告：Flask服务可能未完全启动，但仍尝试打开WebView')
    
    # 创建WebView窗口
    window = webview.create_window(
        'TraceBack 溯·源',
        url,
        width=1200,
        height=800,
        resizable=True,
        min_size=(800, 600)
    )
    
    # 启动WebView
    webview.start()

if __name__ == '__main__':
    main()