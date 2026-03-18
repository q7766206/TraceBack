"""
TraceBack API 蓝图注册
"""

from flask import Blueprint

graph_bp = Blueprint('graph', __name__)
analysis_bp = Blueprint('analysis', __name__)
report_bp = Blueprint('report', __name__)
simulation_bp = Blueprint('simulation', __name__)
config_bp = Blueprint('config', __name__)

# 导入模块
from . import graph
from . import analysis
from . import report
from . import simulation
from . import config_api
from . import license

# 从license模块导入license_bp
license_bp = license.license_bp
