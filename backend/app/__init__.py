"""
TraceBack 溯·源 - Flask应用工厂
"""

import os
import warnings

warnings.filterwarnings("ignore", message=".*resource_tracker.*")

from flask import Flask, request
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
    from .services.retrospection_runner import RetrospectionRunner
    RetrospectionRunner.register_cleanup()
    if should_log_startup:
        logger.info("已注册分析进程清理函数")

    @app.before_request
    def log_request():
        logger = get_logger('traceback.request')
        logger.debug(f"请求: {request.method} {request.path}")

    @app.after_request
    def log_response(response):
        logger = get_logger('traceback.request')
        logger.debug(f"响应: {response.status_code}")
        return response

    # 注册蓝图
    from .api import graph_bp, analysis_bp, report_bp, simulation_bp, config_bp
    app.register_blueprint(graph_bp, url_prefix='/api/graph')
    app.register_blueprint(analysis_bp, url_prefix='/api/analysis')
    app.register_blueprint(report_bp, url_prefix='/api/report')
    app.register_blueprint(simulation_bp, url_prefix='/api/simulation')
    app.register_blueprint(config_bp, url_prefix='/api/config')

    if should_log_startup:
        logger.info("API蓝图注册完成: /api/graph, /api/analysis, /api/report, /api/simulation, /api/config")
        logger.info("TraceBack Backend 启动完成!")

    return app
