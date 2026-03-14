"""
TraceBack 溯·源 - 配置管理
统一从项目根目录的 .env 文件加载配置
"""

import os
from dotenv import load_dotenv

# 加载项目根目录的 .env 文件
project_root_env = os.path.join(os.path.dirname(__file__), '../../.env')

if os.path.exists(project_root_env):
    load_dotenv(project_root_env, override=True)
else:
    load_dotenv(override=True)


class Config:
    """Flask配置类"""
    
    # Flask配置
    SECRET_KEY = os.environ.get('SECRET_KEY', 'traceback-secret-key')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    # JSON配置
    JSON_AS_ASCII = False
    
    # LLM配置 — 主力模型（DeepSeek-V3.2）
    LLM_API_KEY = os.environ.get('LLM_API_KEY')
    LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
    LLM_MODEL_NAME = os.environ.get('LLM_MODEL_NAME', 'gpt-4o-mini')
    
    # LLM配置 — 推理模型（Doubao-Seed-1.6-thinking）
    LLM_REASONING_API_KEY = os.environ.get('LLM_REASONING_API_KEY', os.environ.get('LLM_API_KEY'))
    LLM_REASONING_BASE_URL = os.environ.get('LLM_REASONING_BASE_URL', os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1'))
    LLM_REASONING_MODEL_NAME = os.environ.get('LLM_REASONING_MODEL_NAME', os.environ.get('LLM_MODEL_NAME', 'gpt-4o-mini'))
    
    # LLM配置 — 轻量模型（Doubao-Seed-2.0-mini）
    LLM_FAST_API_KEY = os.environ.get('LLM_FAST_API_KEY', os.environ.get('LLM_API_KEY'))
    LLM_FAST_BASE_URL = os.environ.get('LLM_FAST_BASE_URL', os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1'))
    LLM_FAST_MODEL_NAME = os.environ.get('LLM_FAST_MODEL_NAME', os.environ.get('LLM_MODEL_NAME', 'gpt-4o-mini'))
    
    # 图谱存储（本地JSON，无需外部服务）
    GRAPH_STORAGE_DIR = os.path.join(os.path.dirname(__file__), '../uploads/graphs')
    
    # Zep Cloud 图谱服务（加速图谱构建）
    ZEP_API_KEY = os.environ.get('ZEP_API_KEY', '')
    
    # 搜索配置（默认使用DuckDuckGo，免费无需API Key）
    SEARCH_PROVIDER = os.environ.get('SEARCH_PROVIDER', 'bocha')  # bocha/tavily/duckduckgo/serper
    SEARCH_API_KEY = os.environ.get('SEARCH_API_KEY', '')  # Serper/Bocha需要，DuckDuckGo不需要
    SEARCH_MAX_RESULTS = int(os.environ.get('SEARCH_MAX_RESULTS', '10'))
    
    # 文件上传配置
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'md', 'txt', 'markdown', 'docx', 'html'}
    
    # 文本处理配置
    DEFAULT_CHUNK_SIZE = 800  # 历史文献段落通常更长
    DEFAULT_CHUNK_OVERLAP = 100
    
    # ===== TraceBack 回溯分析配置 =====
    
    # 质证辩论配置
    TRACEBACK_MAX_DEBATE_ROUNDS = int(os.environ.get('TRACEBACK_MAX_DEBATE_ROUNDS', '3'))
    TRACEBACK_MIN_EVIDENCE_CONFIDENCE = float(os.environ.get('TRACEBACK_MIN_EVIDENCE_CONFIDENCE', '0.3'))
    
    # 分析数据目录
    TRACEBACK_ANALYSIS_DATA_DIR = os.path.join(os.path.dirname(__file__), '../uploads/analyses')
    
    # Agent分析行动类型
    TRACEBACK_AGENT_ACTIONS = [
        'SEARCH_DATA', 'BUILD_TIMELINE', 'PROPOSE_HYPOTHESIS',
        'FIND_EVIDENCE', 'CHALLENGE_CONCLUSION', 'VERIFY_CHAIN',
        'UPDATE_CONFIDENCE', 'SYNTHESIZE', 'DO_NOTHING'
    ]
    
    # 可信度等级定义
    CONFIDENCE_LEVELS = {
        'A': {'min': 0.8, 'label': '高度可信', 'color': '#059669'},
        'B': {'min': 0.6, 'label': '中等可信', 'color': '#D97706'},
        'C': {'min': 0.3, 'label': '低可信度', 'color': '#EA580C'},
        'D': {'min': 0.0, 'label': '待验证',   'color': '#DC2626'},
    }
    
    # Report Agent配置
    REPORT_AGENT_MAX_TOOL_CALLS = int(os.environ.get('REPORT_AGENT_MAX_TOOL_CALLS', '5'))
    REPORT_AGENT_MAX_REFLECTION_ROUNDS = int(os.environ.get('REPORT_AGENT_MAX_REFLECTION_ROUNDS', '2'))
    REPORT_AGENT_TEMPERATURE = float(os.environ.get('REPORT_AGENT_TEMPERATURE', '0.5'))
    
    @classmethod
    def validate(cls):
        """验证必要配置"""
        errors = []
        if not cls.LLM_API_KEY:
            errors.append("LLM_API_KEY 未配置")
        return errors

