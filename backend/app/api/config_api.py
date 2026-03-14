# -*- coding: utf-8 -*-
"""
TraceBack 溯·源 - API连接配置接口
支持前端读取和修改 .env 中的 API 配置
"""

import os
from flask import request, jsonify
from . import config_bp

# 项目根目录的 .env 文件路径
ENV_PATH = os.path.join(os.path.dirname(__file__), '../../../.env')

# 允许前端读写的配置键（白名单，防止泄露敏感信息）
ALLOWED_KEYS = [
    'LLM_API_KEY', 'LLM_BASE_URL', 'LLM_MODEL_NAME',
    'LLM_REASONING_API_KEY', 'LLM_REASONING_BASE_URL', 'LLM_REASONING_MODEL_NAME',
    'LLM_FAST_API_KEY', 'LLM_FAST_BASE_URL', 'LLM_FAST_MODEL_NAME',
    'SEARCH_PROVIDER', 'SEARCH_API_KEY', 'SEARCH_MAX_RESULTS',
    'ZEP_API_KEY',
]


def _parse_env_file():
    """解析 .env 文件，返回 (lines, config_dict)"""
    lines = []
    config = {}
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('#') and '=' in stripped:
                key, _, value = stripped.partition('=')
                config[key.strip()] = value.strip()
    return lines, config


def _mask_key(value):
    """对 API Key 做脱敏处理，只显示前6位和后4位"""
    if not value or len(value) <= 10:
        return value
    return value[:6] + '****' + value[-4:]


@config_bp.route('/get', methods=['GET'])
def get_config():
    """获取当前 API 配置（Key 脱敏）"""
    try:
        _, config = _parse_env_file()
        result = {}
        for key in ALLOWED_KEYS:
            val = config.get(key, '')
            if 'KEY' in key and val:
                result[key] = _mask_key(val)
            else:
                result[key] = val
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@config_bp.route('/update', methods=['POST'])
def update_config():
    """更新 API 配置，写入 .env 文件并热更新环境变量"""
    try:
        updates = request.get_json()
        if not updates:
            return jsonify({'success': False, 'error': '请求体为空'}), 400

        # 过滤非白名单的键
        valid_updates = {}
        for key, value in updates.items():
            if key in ALLOWED_KEYS:
                # 跳过脱敏值（用户没有修改的字段）
                if 'KEY' in key and '****' in str(value):
                    continue
                valid_updates[key] = value

        if not valid_updates:
            return jsonify({'success': True, 'message': '无需更新'})

        # 读取现有 .env 文件
        lines, _ = _parse_env_file()

        # 更新已有行
        updated_keys = set()
        new_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('#') and '=' in stripped:
                key, _, _ = stripped.partition('=')
                key = key.strip()
                if key in valid_updates:
                    new_lines.append(f'{key}={valid_updates[key]}\n')
                    updated_keys.add(key)
                    continue
            new_lines.append(line)

        # 追加新增的键
        for key, value in valid_updates.items():
            if key not in updated_keys:
                new_lines.append(f'{key}={value}\n')

        # 写回 .env 文件
        with open(ENV_PATH, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)

        # 热更新环境变量
        for key, value in valid_updates.items():
            os.environ[key] = value

        # 重新加载 Config
        from ..config import Config
        for key, value in valid_updates.items():
            if hasattr(Config, key):
                setattr(Config, key, value)

        return jsonify({
            'success': True,
            'message': f'已更新 {len(valid_updates)} 项配置',
            'updated_keys': list(valid_updates.keys())
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@config_bp.route('/test', methods=['POST'])
def test_connection():
    """测试 LLM API 连接 - 使用 OpenAI SDK（兼容火山引擎）"""
    try:
        data = request.get_json() or {}
        base_url = data.get('base_url', os.environ.get('LLM_BASE_URL', ''))
        api_key = data.get('api_key', os.environ.get('LLM_API_KEY', ''))
        model = data.get('model', os.environ.get('LLM_MODEL_NAME', ''))

        if not base_url or not api_key:
            return jsonify({'success': False, 'error': '缺少 base_url 或 api_key'}), 400

        # 使用 OpenAI SDK 调用（兼容火山引擎等 OpenAI 兼容服务）
        from openai import OpenAI
        
        client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        
        response = client.chat.completions.create(
            model=model,
            messages=[{'role': 'user', 'content': 'Hi'}],
            max_tokens=5
        )
        
        return jsonify({'success': True, 'message': '连接成功', 'model': response.model})
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'连接失败: {str(e)}'}), 500
