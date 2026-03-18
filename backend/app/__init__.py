"""
TraceBack 溯·源 - Flask应用工厂
"""

import os
import sys
import warnings

warnings.filterwarnings("ignore", message=".*resource_tracker.*")

from flask import Flask, request, send_from_directory, jsonify
from flask_cors import CORS

from .config import Config
from .utils.logger import setup_logger, get_logger


def create_app(config_class=Config):
    """Flask应用工厂函数"""
    app = Flask(__name__)
    app.config.from_object(config_class)

    if hasattr(app, 'json') and hasattr(app.json, 'ensure_ascii'):
        app.json.ensure_ascii = False

    logger = setup_logger('traceback')

    is_reloader_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    debug_mode = app.config.get('DEBUG', False)
    should_log_startup = not debug_mode or is_reloader_process

    if should_log_startup:
        logger.info("=" * 50)
        logger.info("TraceBack 溯·源 Backend 启动中...")
        logger.info("=" * 50)

    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # 注册分析进程清理函数
    try:
        from .services.retrospection_runner import RetrospectionRunner
        RetrospectionRunner.register_cleanup()
        if should_log_startup:
            logger.info("已注册分析进程清理函数")
    except Exception as e:
        if should_log_startup:
            logger.warning(f"分析进程清理函数注册失败（无 LLM 模式）: {e}")

    @app.before_request
    def log_request():
        logger = get_logger('traceback.request')
        logger.info(f"请求: {request.method} {request.path}")
        logger.info(f"请求头: {dict(request.headers)}")
        if request.method in ['POST', 'PUT', 'PATCH']:
            logger.info(f"请求体: {request.get_json(silent=True)}")

    @app.after_request
    def log_response(response):
        logger = get_logger('traceback.request')
        logger.info(f"响应: {response.status_code}")
        return response

    # 注册蓝图
    from .api import graph_bp, analysis_bp, report_bp, simulation_bp, config_bp, license_bp
    app.register_blueprint(graph_bp, url_prefix='/api/graph')
    app.register_blueprint(analysis_bp, url_prefix='/api/analysis')
    app.register_blueprint(report_bp, url_prefix='/api/report')
    app.register_blueprint(simulation_bp, url_prefix='/api/simulation')
    app.register_blueprint(config_bp, url_prefix='/api/config')
    app.register_blueprint(license_bp, url_prefix='/api/license')

    # 提供静态文件服务
    # 处理 PyInstaller 打包的情况
    if getattr(sys, 'frozen', False):
        # 运行在打包环境中 - 使用 PyInstaller 的临时目录
        base_dir = sys._MEIPASS
        if should_log_startup:
            logger.info(f"运行在打包环境中，base_dir: {base_dir}")
    else:
        # 运行在开发环境中
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        if should_log_startup:
            logger.info(f"运行在开发环境中，base_dir: {base_dir}")
    
    # 构建静态文件目录路径
    static_dir = os.path.join(base_dir, 'frontend', 'dist')
    # 检查是否存在，如果不存在，尝试查找内部目录
    if not os.path.exists(static_dir):
        static_dir = os.path.join(base_dir, '_internal', 'frontend', 'dist')
    
    if should_log_startup:
        logger.info(f"静态文件目录: {static_dir}")
        logger.info(f"静态文件目录是否存在: {os.path.exists(static_dir)}")
        if os.path.exists(static_dir):
            logger.info(f"静态文件目录内容: {os.listdir(static_dir)}")
    
    if os.path.exists(static_dir):
        # 静态文件服务 - 只处理根路径和静态资源
        @app.route('/')
        def serve_root():
            logger.debug("返回 index.html (根路径)")
            return send_from_directory(static_dir, 'index.html')
        
        # 处理静态资源文件
        @app.route('/assets/<path:path>')
        def serve_assets(path):
            logger.debug(f"返回静态资源: assets/{path}")
            return send_from_directory(os.path.join(static_dir, 'assets'), path)
        
        # 处理图标文件
        @app.route('/icon.png')
        def serve_icon_png():
            logger.debug("返回图标: icon.png")
            return send_from_directory(static_dir, 'icon.png')
        
        @app.route('/icon.svg')
        def serve_icon_svg():
            logger.debug("返回图标: icon.svg")
            return send_from_directory(static_dir, 'icon.svg')
        
        if should_log_startup:
            logger.info(f"静态文件服务已配置: {static_dir}")
    else:
        if should_log_startup:
            logger.warning(f"静态文件目录不存在: {static_dir}")

    # 添加测试路由
    @app.route('/test', methods=['POST'])
    def test_route():
        return jsonify({'message': '测试路由工作正常'})

    if should_log_startup:
        logger.info("API蓝图注册完成: /api/graph, /api/analysis, /api/report, /api/simulation, /api/config, /api/license")
        logger.info("TraceBack Backend 启动完成!")

    return app
