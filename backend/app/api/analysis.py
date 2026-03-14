"""
TraceBack 回溯分析 API 路由
"""

import traceback
from flask import request, jsonify

from . import analysis_bp
from ..config import Config
from ..services.retrospection_manager import RetrospectionManager
from ..services.retrospection_runner import RetrospectionRunner
from ..services.agent_profiles import get_agent_summary
from ..utils.logger import get_logger

logger = get_logger('traceback.api.analysis')


# ============== Agent信息接口 ==============

@analysis_bp.route('/agents', methods=['GET'])
def get_agents():
    """获取所有Agent角色信息"""
    return jsonify({
        "success": True,
        "data": get_agent_summary()
    })


# ============== 分析管理接口 ==============

@analysis_bp.route('/create', methods=['POST'])
def create_analysis():
    """
    创建回溯分析任务

    请求（JSON）：
        {
            "project_id": "proj_xxxx",
            "graph_id": "graph_xxxx",
            "task_description": "分析XXX事件的根本原因",
            "time_range_start": "2024-01-01",  // 可选
            "time_range_end": "2024-12-31",    // 可选
            "max_debate_rounds": 3             // 可选
        }
    """
    try:
        data = request.get_json() or {}

        project_id = data.get('project_id')
        graph_id = data.get('graph_id')
        task_description = data.get('task_description')

        if not all([project_id, graph_id, task_description]):
            return jsonify({
                "success": False,
                "error": "请提供 project_id, graph_id, task_description"
            }), 400

        manager = RetrospectionManager()
        state = manager.create_analysis(
            project_id=project_id,
            graph_id=graph_id,
            task_description=task_description,
            time_range_start=data.get('time_range_start', ''),
            time_range_end=data.get('time_range_end', ''),
            max_debate_rounds=data.get('max_debate_rounds'),
        )

        return jsonify({
            "success": True,
            "data": state.to_dict()
        })

    except Exception as e:
        logger.error(f"创建分析失败: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@analysis_bp.route('/start', methods=['POST'])
def start_analysis():
    """
    启动回溯分析

    请求（JSON）：
        {"analysis_id": "analysis_xxxx"}
    """
    try:
        data = request.get_json() or {}
        analysis_id = data.get('analysis_id')

        if not analysis_id:
            return jsonify({"success": False, "error": "请提供 analysis_id"}), 400

        manager = RetrospectionManager()
        state = manager.get_analysis(analysis_id)
        if not state:
            return jsonify({"success": False, "error": f"分析不存在: {analysis_id}"}), 404

        # 检查是否已在运行
        existing = RetrospectionRunner.get_runner(analysis_id)
        if existing and existing.is_running():
            return jsonify({"success": False, "error": "分析已在运行中"}), 409

        # 启动分析
        runner = RetrospectionRunner(analysis_id, state.graph_id)
        runner.start()

        return jsonify({
            "success": True,
            "data": {"analysis_id": analysis_id, "status": "running"}
        })

    except Exception as e:
        logger.error(f"启动分析失败: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@analysis_bp.route('/stop', methods=['POST'])
def stop_analysis():
    """停止回溯分析"""
    try:
        data = request.get_json() or {}
        analysis_id = data.get('analysis_id')

        runner = RetrospectionRunner.get_runner(analysis_id)
        if runner:
            runner.stop()

        return jsonify({"success": True, "data": {"analysis_id": analysis_id, "status": "stopped"}})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@analysis_bp.route('/status/<analysis_id>', methods=['GET'])
def get_analysis_status(analysis_id: str):
    """获取分析状态"""
    try:
        manager = RetrospectionManager()
        state = manager.get_analysis(analysis_id)
        if not state:
            return jsonify({"success": False, "error": f"分析不存在: {analysis_id}"}), 404

        return jsonify({"success": True, "data": state.to_dict()})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@analysis_bp.route('/list', methods=['GET'])
def list_analyses():
    """列出分析任务"""
    try:
        project_id = request.args.get('project_id')
        limit = request.args.get('limit', 50, type=int)

        manager = RetrospectionManager()
        analyses = manager.list_analyses(project_id=project_id, limit=limit)

        return jsonify({"success": True, "data": analyses, "count": len(analyses)})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ============== 可视化数据接口 ==============

@analysis_bp.route('/causal-graph/<analysis_id>', methods=['GET'])
def get_causal_graph(analysis_id: str):
    """获取因果网络图数据（供前端可视化）"""
    try:
        manager = RetrospectionManager()
        data = manager.get_causal_graph_data(analysis_id)
        if data is None:
            return jsonify({"success": False, "error": "分析不存在"}), 404

        return jsonify({"success": True, "data": data})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@analysis_bp.route('/timeline/<analysis_id>', methods=['GET'])
def get_timeline(analysis_id: str):
    """获取时间线数据"""
    try:
        manager = RetrospectionManager()
        data = manager.get_timeline_data(analysis_id)
        if data is None:
            return jsonify({"success": False, "error": "分析不存在"}), 404

        return jsonify({"success": True, "data": data})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@analysis_bp.route('/debate/<analysis_id>', methods=['GET'])
def get_debate_messages(analysis_id: str):
    """获取质证辩论消息（支持增量获取）"""
    try:
        since_index = request.args.get('since', 0, type=int)

        manager = RetrospectionManager()
        messages = manager.get_debate_messages(analysis_id, since_index=since_index)
        if messages is None:
            return jsonify({"success": False, "error": "分析不存在"}), 404

        return jsonify({
            "success": True,
            "data": messages,
            "count": len(messages),
            "next_index": since_index + len(messages)
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@analysis_bp.route('/evidence/<analysis_id>', methods=['GET'])
def get_evidence_chain(analysis_id: str):
    """获取证据链数据"""
    try:
        manager = RetrospectionManager()
        data = manager.get_evidence_chain(analysis_id)
        if data is None:
            return jsonify({"success": False, "error": "分析不存在"}), 404

        return jsonify({"success": True, "data": data})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
