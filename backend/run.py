"""
TraceBack 溯·源 Backend 启动入口
"""

import os
import sys
import io

# ═══════════════════════════════════════════════════════════════
# 强制设置UTF-8编码（Windows中文环境必需）
# 必须在任何其他导入之前执行
# ═══════════════════════════════════════════════════════════════

# 设置环境变量
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'

# Windows 平台特殊处理
if sys.platform == 'win32':
    # 设置标准输入输出编码
    try:
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, 
            encoding='utf-8', 
            errors='replace'
        )
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer, 
            encoding='utf-8', 
            errors='replace'
        )
    except Exception:
        pass
    
    # 尝试重新配置
    if hasattr(sys.stdout, 'reconfigure'):
        try:
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


def main():
    """主函数"""
    # 暂时跳过配置验证，以便在没有API密钥的情况下测试邀请码系统
    # errors = Config.validate()
    # if errors:
    #     print("配置错误:")
    #     for err in errors:
    #         print(f"  - {err}")
    #     print("\n请检查 .env 文件中的配置")
    #     sys.exit(1)

    app = create_app()

    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_PORT', 5001))
    debug = False

    print(f"\n  TraceBack 溯·源 Backend")
    print(f"  http://localhost:{port}")
    print(f"  API: http://localhost:{port}/api/\n")

    app.run(host=host, port=port, debug=debug, threaded=True)


if __name__ == '__main__':
    main()
