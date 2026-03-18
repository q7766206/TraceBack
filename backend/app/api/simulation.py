"""
TraceBack Simulation API 路由
提供模拟环境的创建、准备、运行等功能
"""

import os
import json
import uuid
import threading
import time
from datetime import datetime
from flask import request, jsonify

from . import simulation_bp
from ..config import Config
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger
from ..models.project import ProjectManager
from ..services.local_graph_store import LocalGraphStore

logger = get_logger('traceback.simulation')

# ═══════════════════════════════════════════════════════════════
# 内存存储（模拟实例、准备任务等）
# ═══════════════════════════════════════════════════════════════

_simulations = {}       # simulation_id -> simulation data
_prepare_tasks = {}     # task_id -> task status
_simulation_configs = {}  # simulation_id -> config


def _get_simulation_dir(simulation_id):
    base = os.path.join(Config.UPLOAD_FOLDER, 'simulations')
    d = os.path.join(base, simulation_id)
    os.makedirs(d, exist_ok=True)
    return d


def _save_simulation(simulation_id, data):
    _simulations[simulation_id] = data
    d = _get_simulation_dir(simulation_id)
    with open(os.path.join(d, 'simulation.json'), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load_simulation(simulation_id):
    if simulation_id in _simulations:
        return _simulations[simulation_id]
    d = _get_simulation_dir(simulation_id)
    fp = os.path.join(d, 'simulation.json')
    if os.path.exists(fp):
        with open(fp, 'r', encoding='utf-8') as f:
            data = json.load(f)
            _simulations[simulation_id] = data
            return data
    return None


# ═══════════════════════════════════════════════════════════════
# API: 创建模拟
# ═══════════════════════════════════════════════════════════════

@simulation_bp.route('/create', methods=['POST'])
def create_simulation():
    """创建模拟实例"""
    try:
        data = request.get_json()
        project_id = data.get('project_id')
        graph_id = data.get('graph_id')
        simulation_requirement = data.get('simulation_requirement', '')

        if not project_id or not graph_id:
            return jsonify({"success": False, "error": "缺少 project_id 或 graph_id"}), 400

        simulation_id = f"sim_{uuid.uuid4().hex[:12]}"

        sim_data = {
            "simulation_id": simulation_id,
            "project_id": project_id,
            "graph_id": graph_id,
            "simulation_requirement": simulation_requirement,
            "status": "created",
            "profiles": [],
            "config": {},
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "enable_reddit": data.get('enable_reddit', True),
            "enable_twitter": data.get('enable_twitter', True),
        }

        _save_simulation(simulation_id, sim_data)
        logger.info(f"创建模拟实例: {simulation_id} (project={project_id}, graph={graph_id})")

        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "status": "created"
            }
        })

    except Exception as e:
        logger.error(f"创建模拟失败: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# ═══════════════════════════════════════════════════════════════
# API: 准备模拟（生成 Agent Profiles）
# ═══════════════════════════════════════════════════════════════

@simulation_bp.route('/prepare', methods=['POST'])
def prepare_simulation():
    """准备模拟环境 - 从图谱中提取实体并生成 Agent Profiles"""
    try:
        data = request.get_json()
        simulation_id = data.get('simulation_id')

        if not simulation_id:
            return jsonify({"success": False, "error": "缺少 simulation_id"}), 400

        sim = _load_simulation(simulation_id)
        if not sim:
            return jsonify({"success": False, "error": f"模拟 {simulation_id} 不存在"}), 404

        # 检查是否已经准备完成
        if sim.get('profiles') and len(sim['profiles']) > 0:
            return jsonify({
                "success": True,
                "data": {
                    "already_prepared": True,
                    "simulation_id": simulation_id,
                    "profiles_count": len(sim['profiles'])
                }
            })

        task_id = f"prep_{uuid.uuid4().hex[:8]}"
        graph_id = sim['graph_id']

        # 快速预估实体数量（用于前端显示）
        expected_count = 0
        entity_types = []

        if Config.ZEP_API_KEY:
            try:
                from zep_cloud.client import Zep
                from ..utils.zep_paging import fetch_all_nodes
                zep_client = Zep(api_key=Config.ZEP_API_KEY)
                zep_nodes = fetch_all_nodes(zep_client, graph_id)
                expected_count = len(zep_nodes)
                for node in zep_nodes:
                    labels = getattr(node, 'labels', None) or getattr(node, 'entity_type', None)
                    if isinstance(labels, str):
                        labels = [labels]
                    elif labels is None:
                        labels = []
                    for label in labels:
                        if label and label not in entity_types:
                            entity_types.append(label)
                logger.info(f"Zep 读取到 {expected_count} 个节点")
            except Exception as e:
                logger.warning(f"Zep 预估失败: {e}")

        if expected_count == 0:
            graph_store = LocalGraphStore()
            if graph_store.graph_exists(graph_id):
                all_nodes = graph_store.get_all_nodes(graph_id)
                expected_count = len(all_nodes)
                for node in all_nodes:
                    for label in node.labels:
                        if label not in entity_types:
                            entity_types.append(label)

        # 创建任务
        _prepare_tasks[task_id] = {
            "task_id": task_id,
            "simulation_id": simulation_id,
            "status": "processing",
            "progress": 0,
            "message": "正在准备...",
            "profiles_generated": 0,
        }

        # 启动后台线程
        thread = threading.Thread(
            target=_prepare_worker,
            args=(task_id, simulation_id, graph_id),
            daemon=True
        )
        thread.start()

        logger.info(f"准备任务启动: {task_id} (sim={simulation_id}, entities={expected_count})")

        return jsonify({
            "success": True,
            "data": {
                "task_id": task_id,
                "simulation_id": simulation_id,
                "expected_entities_count": expected_count,
                "entity_types": entity_types,
            }
        })

    except Exception as e:
        logger.error(f"准备模拟失败: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


def _prepare_worker(task_id, simulation_id, graph_id):
    """后台线程：从图谱提取实体并用 LLM 批量生成 Agent Profiles。
    策略：筛选 top-30 关键实体，分批（每批10个）一次 LLM 调用生成。
    总共只需 3-4 次 LLM 调用，不会触发 429。
    """
    try:
        from ..services.graph_builder import get_prebuilt_profiles
        llm = LLMClient()
        sim = _load_simulation(simulation_id)
        profiles = []
        config_agents = []
        need_generate = True

        # ── 1. 优先检查预生成缓存 ──
        prebuilt = get_prebuilt_profiles(graph_id)
        if prebuilt and len(prebuilt.get("profiles", [])) > 0:
            profiles = prebuilt["profiles"]
            config_agents = prebuilt["config_agents"]
            need_generate = False
            logger.info(f"命中预生成缓存！{len(profiles)} 个 Profile (graph={graph_id})")
            _prepare_tasks[task_id].update({
                "progress": 90,
                "message": f"从缓存加载 {len(profiles)} 个 Profile...",
                "profiles_generated": len(profiles),
            })

        # ── 2. 无缓存则从图谱读取节点并批量生成 ──
        if need_generate:
            logger.info(f"无预生成缓存，从图谱批量生成 Profile (graph={graph_id})")
            _prepare_tasks[task_id].update({"progress": 10, "message": "正在读取图谱节点..."})

            # 读取节点：优先 Zep，降级本地
            all_nodes = []
            if Config.ZEP_API_KEY:
                try:
                    from zep_cloud.client import Zep
                    from ..utils.zep_paging import fetch_all_nodes
                    zep_client = Zep(api_key=Config.ZEP_API_KEY)
                    zep_raw = fetch_all_nodes(zep_client, graph_id)
                    for i, zn in enumerate(zep_raw):
                        class _N: pass
                        n = _N()
                        n.name = getattr(zn, 'name', '') or f"entity_{i}"
                        n.summary = getattr(zn, 'summary', '') or ''
                        rl = getattr(zn, 'labels', None) or getattr(zn, 'entity_type', None)
                        n.labels = [rl] if isinstance(rl, str) else (rl if isinstance(rl, list) else ['Entity'])
                        n.node_id = getattr(zn, 'uuid_', None) or getattr(zn, 'uuid', None) or f"node_{i}"
                        all_nodes.append(n)
                    logger.info(f"Zep 读取到 {len(all_nodes)} 个节点")
                except Exception as e:
                    logger.warning(f"Zep 读取失败，降级本地: {e}")

            if not all_nodes:
                gs = LocalGraphStore()
                if gs.graph_exists(graph_id):
                    all_nodes = gs.get_all_nodes(graph_id)
                    logger.info(f"本地读取到 {len(all_nodes)} 个节点")

            if not all_nodes:
                logger.warning(f"图谱 {graph_id} 无节点")
                _prepare_tasks[task_id].update({
                    "status": "completed", "progress": 100,
                    "message": "图谱无节点，跳过 Profile 生成", "profiles_generated": 0,
                })
                sim['profiles'] = []
                sim['config'] = {"agents": [], "total_agents": 0}
                sim['status'] = 'prepared'
                sim['updated_at'] = datetime.now().isoformat()
                _save_simulation(simulation_id, sim)
                return

            # 筛选关键实体（最多 30 个）
            MAX_AGENTS = 30
            BATCH_SIZE = 10

            def _importance(n):
                s = 0
                if getattr(n, 'summary', ''): s += 2
                for lb in (getattr(n, 'labels', []) or []):
                    if lb in ('Person', 'Organization', '人物', '组织', '机构'): s += 3
                    elif lb in ('Event', 'Location', '事件', '地点'): s += 1
                return s

            sorted_nodes = sorted(all_nodes, key=_importance, reverse=True)[:MAX_AGENTS]
            total = len(sorted_nodes)
            total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
            logger.info(f"筛选 {total}/{len(all_nodes)} 个关键实体，分 {total_batches} 批生成")
            _prepare_tasks[task_id].update({
                "progress": 20, "message": f"筛选出 {total} 个关键实体，开始批量生成...",
            })

            # 分批生成
            for batch_start in range(0, total, BATCH_SIZE):
                if _prepare_tasks.get(task_id, {}).get('status') == 'cancelled':
                    break

                batch = sorted_nodes[batch_start:batch_start + BATCH_SIZE]
                batch_num = batch_start // BATCH_SIZE + 1

                # 构造批量 prompt
                entities_desc = ""
                for j, nd in enumerate(batch):
                    nm = nd.name
                    sm = getattr(nd, 'summary', '') or ''
                    lb = (getattr(nd, 'labels', []) or [])
                    et = lb[0] if lb else "Entity"
                    entities_desc += f"\n{j+1}. 名称: {nm}\n   类型: {et}\n   描述: {sm[:150]}\n"

                requirement = sim.get('simulation_requirement', '')
                prompt = f"""你是学术研究助手，为历史事件因果分析系统构建角色档案。
研究课题: {requirement}

请为以下 {len(batch)} 个实体生成角色档案：
{entities_desc}

以JSON数组输出，每个元素包含：
[{{"username":"显示名","real_name":"原名","entity_type":"类型","bio":"80字简介","stance":"neutral/positive/negative/critical","expertise":["领域"],"posts_per_hour":2,"replies_per_hour":3,"active_hours":[9,10,14,15,20,21]}}]

要求：数组长度={len(batch)}，顺序对应，real_name与输入一致。"""

                try:
                    result = llm.chat_json([{"role": "user", "content": prompt}])
                    # 兼容不同返回格式
                    if isinstance(result, dict):
                        result = result.get("profiles") or result.get("agents") or result.get("data") or [result]
                    if not isinstance(result, list):
                        result = [result]

                    for j, prof in enumerate(result):
                        if j >= len(batch):
                            break
                        nd = batch[j]
                        lb = (getattr(nd, 'labels', []) or [])
                        et = lb[0] if lb else "Entity"
                        nid = getattr(nd, 'node_id', f"node_{batch_start+j}")
                        prof['real_name'] = nd.name
                        prof['entity_type'] = et
                        prof['node_id'] = nid
                        profiles.append(prof)
                        config_agents.append({
                            "agent_id": nid, "username": prof.get('username', nd.name),
                            "real_name": nd.name, "entity_type": et,
                            "stance": prof.get('stance', 'neutral'),
                            "posts_per_hour": prof.get('posts_per_hour', 2),
                            "replies_per_hour": prof.get('replies_per_hour', 3),
                            "active_hours": prof.get('active_hours', [9, 10, 14, 15, 20, 21]),
                        })
                    logger.info(f"批次 {batch_num}/{total_batches} OK，累计 {len(profiles)} 个 Profile")

                except Exception as e:
                    logger.warning(f"批次 {batch_num} LLM 失败: {e}，使用默认 Profile")
                    for j, nd in enumerate(batch):
                        lb = (getattr(nd, 'labels', []) or [])
                        et = lb[0] if lb else "Entity"
                        nid = getattr(nd, 'node_id', f"node_{batch_start+j}")
                        profiles.append({
                            "username": nd.name, "real_name": nd.name, "entity_type": et,
                            "bio": (getattr(nd, 'summary', '') or nd.name)[:80],
                            "stance": "neutral", "expertise": [], "personality_traits": [],
                            "posts_per_hour": 2, "replies_per_hour": 3,
                            "active_hours": [9, 10, 14, 15, 20, 21], "node_id": nid,
                        })
                        config_agents.append({
                            "agent_id": nid, "username": nd.name, "real_name": nd.name,
                            "entity_type": et, "stance": "neutral",
                            "posts_per_hour": 2, "replies_per_hour": 3,
                            "active_hours": [9, 10, 14, 15, 20, 21],
                        })

                progress = 20 + int((batch_start + len(batch)) / total * 70)
                _prepare_tasks[task_id].update({
                    "progress": progress,
                    "message": f"批次 {batch_num}/{total_batches} 完成，已生成 {len(profiles)} 个 Profile",
                    "profiles_generated": len(profiles),
                })

        # ── 3. 保存结果 ──
        sim_config = {
            "simulation_id": simulation_id, "graph_id": graph_id,
            "time_config": {
                "peak_hours": [9, 10, 14, 15, 20, 21], "peak_activity_multiplier": 2.0,
                "off_peak_hours": [0, 1, 2, 3, 4, 5], "off_peak_activity_multiplier": 0.3,
            },
            "agents": config_agents, "total_agents": len(config_agents),
            "platforms": {"reddit": sim.get('enable_reddit', True), "twitter": sim.get('enable_twitter', True)},
        }
        sim['profiles'] = profiles
        sim['config'] = sim_config
        sim['status'] = 'prepared'
        sim['updated_at'] = datetime.now().isoformat()
        _save_simulation(simulation_id, sim)
        _simulation_configs[simulation_id] = sim_config

        _prepare_tasks[task_id].update({
            "status": "completed", "progress": 100,
            "message": f"准备完成，共生成 {len(profiles)} 个 Agent Profile",
            "profiles_generated": len(profiles),
        })
        logger.info(f"准备完成: {task_id} (profiles={len(profiles)})")

    except Exception as e:
        logger.error(f"准备任务失败: {task_id}: {e}", exc_info=True)
        _prepare_tasks[task_id].update({"status": "failed", "message": f"准备失败: {str(e)}"})


# ═══════════════════════════════════════════════════════════════
# API: 查询准备进度
# ═══════════════════════════════════════════════════════════════

@simulation_bp.route('/prepare/status', methods=['POST'])
def get_prepare_status():
    """查询准备任务进度"""
    try:
        data = request.get_json()
        task_id = data.get('task_id')
        simulation_id = data.get('simulation_id')

        if task_id and task_id in _prepare_tasks:
            return jsonify({"success": True, "data": _prepare_tasks[task_id]})

        # 通过 simulation_id 查找
        if simulation_id:
            for tid, task in _prepare_tasks.items():
                if task.get('simulation_id') == simulation_id:
                    return jsonify({"success": True, "data": task})

        return jsonify({"success": False, "error": "任务不存在"}), 404

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ═══════════════════════════════════════════════════════════════
# API: 获取模拟信息
# ═══════════════════════════════════════════════════════════════

@simulation_bp.route('/<simulation_id>', methods=['GET'])
def get_simulation(simulation_id):
    """获取模拟状态"""
    try:
        sim = _load_simulation(simulation_id)
        if not sim:
            return jsonify({"success": False, "error": "模拟不存在"}), 404
        return jsonify({"success": True, "data": sim})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@simulation_bp.route('/<simulation_id>/profiles', methods=['GET'])
def get_simulation_profiles(simulation_id):
    """获取模拟的 Agent Profiles"""
    try:
        sim = _load_simulation(simulation_id)
        if not sim:
            return jsonify({"success": False, "error": "模拟不存在"}), 404

        platform = request.args.get('platform', 'reddit')
        profiles = sim.get('profiles', [])

        return jsonify({
            "success": True,
            "data": profiles,
            "count": len(profiles),
            "platform": platform,
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@simulation_bp.route('/<simulation_id>/profiles/realtime', methods=['GET'])
def get_simulation_profiles_realtime(simulation_id):
    """实时获取 Profile 生成进度"""
    try:
        sim = _load_simulation(simulation_id)
        if not sim:
            return jsonify({"success": False, "error": "模拟不存在"}), 404

        profiles = sim.get('profiles', [])
        return jsonify({
            "success": True,
            "data": {
                "profiles": profiles,
                "count": len(profiles),
                "status": sim.get('status', 'unknown'),
            }
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@simulation_bp.route('/<simulation_id>/config', methods=['GET'])
def get_simulation_config(simulation_id):
    """获取模拟配置"""
    try:
        if simulation_id in _simulation_configs:
            return jsonify({"success": True, "data": _simulation_configs[simulation_id]})

        sim = _load_simulation(simulation_id)
        if not sim:
            return jsonify({"success": False, "error": "模拟不存在"}), 404

        return jsonify({"success": True, "data": sim.get('config', {})})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@simulation_bp.route('/<simulation_id>/config/realtime', methods=['GET'])
def get_simulation_config_realtime(simulation_id):
    """实时获取配置"""
    try:
        if simulation_id in _simulation_configs:
            config = _simulation_configs[simulation_id]
        else:
            sim = _load_simulation(simulation_id)
            if not sim:
                return jsonify({"success": False, "error": "模拟不存在"}), 404
            config = sim.get('config', {})

        has_config = bool(config and config.get('agents'))
        agents = config.get('agents', [])

        return jsonify({
            "success": True,
            "data": {
                "config": config,
                "config_generated": has_config,
                "total_agents": config.get('total_agents', len(agents)),
                "status": "ready" if has_config else "pending",
                "summary": {
                    "total_agents": len(agents),
                    "simulation_hours": config.get('time_config', {}).get('total_simulation_hours', 24),
                    "initial_posts_count": 0,
                    "hot_topics_count": 0,
                    "has_twitter_config": config.get('platforms', {}).get('twitter', False),
                    "has_reddit_config": config.get('platforms', {}).get('reddit', False),
                } if has_config else None,
            }
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ═══════════════════════════════════════════════════════════════
# API: 启动/停止模拟
# ═══════════════════════════════════════════════════════════════

@simulation_bp.route('/start', methods=['POST'])
def start_simulation_api():
    """启动模拟"""
    try:
        data = request.get_json()
        simulation_id = data.get('simulation_id')
        max_rounds = data.get('max_rounds', 10)
        force = data.get('force', False)

        if not simulation_id:
            return jsonify({"success": False, "error": "缺少 simulation_id"}), 400

        sim = _load_simulation(simulation_id)
        if not sim:
            return jsonify({"success": False, "error": "模拟不存在"}), 404

        from ..services.simulation_engine import start_simulation as engine_start, get_run_state
        
        # 如果 force=True，清理旧状态
        force_restarted = False
        if force:
            old_state = get_run_state(simulation_id)
            if old_state:
                force_restarted = True

        state = engine_start(simulation_id, sim, max_rounds=max_rounds)

        sim['status'] = 'running'
        sim['updated_at'] = datetime.now().isoformat()
        _save_simulation(simulation_id, sim)

        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "status": "running",
                "process_pid": state.process_pid,
                "total_rounds": state.total_rounds,
                "force_restarted": force_restarted,
            }
        })

    except Exception as e:
        logger.error(f"启动模拟失败: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@simulation_bp.route('/stop', methods=['POST'])
def stop_simulation_api():
    """停止模拟"""
    try:
        data = request.get_json()
        simulation_id = data.get('simulation_id')

        if not simulation_id:
            return jsonify({"success": False, "error": "缺少 simulation_id"}), 400

        from ..services.simulation_engine import stop_simulation as engine_stop
        engine_stop(simulation_id)

        sim = _load_simulation(simulation_id)
        if sim:
            sim['status'] = 'stopped'
            sim['updated_at'] = datetime.now().isoformat()
            _save_simulation(simulation_id, sim)

        return jsonify({"success": True, "data": {"simulation_id": simulation_id, "status": "stopped"}})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@simulation_bp.route('/<simulation_id>/run-status', methods=['GET'])
def get_run_status(simulation_id):
    """获取运行状态"""
    try:
        from ..services.simulation_engine import get_run_state
        state = get_run_state(simulation_id)
        if state:
            return jsonify({"success": True, "data": state.to_dict()})

        # 降级到 sim 数据
        sim = _load_simulation(simulation_id)
        if not sim:
            return jsonify({"success": False, "error": "模拟不存在"}), 404
        return jsonify({"success": True, "data": sim.get('run_status', {})})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@simulation_bp.route('/<simulation_id>/run-status/detail', methods=['GET'])
def get_run_status_detail(simulation_id):
    """获取运行状态详情（含 actions）"""
    try:
        from ..services.simulation_engine import get_run_state
        state = get_run_state(simulation_id)
        if state:
            return jsonify({"success": True, "data": state.detail_dict()})

        sim = _load_simulation(simulation_id)
        if not sim:
            return jsonify({"success": False, "error": "模拟不存在"}), 404
        return jsonify({"success": True, "data": sim.get('run_status', {})})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ═══════════════════════════════════════════════════════════════
# API: 模拟数据查询
# ═══════════════════════════════════════════════════════════════

@simulation_bp.route('/<simulation_id>/posts', methods=['GET'])
def get_simulation_posts(simulation_id):
    """获取模拟帖子"""
    try:
        return jsonify({"success": True, "data": [], "total": 0})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@simulation_bp.route('/<simulation_id>/timeline', methods=['GET'])
def get_simulation_timeline(simulation_id):
    """获取模拟时间线"""
    try:
        return jsonify({"success": True, "data": []})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@simulation_bp.route('/<simulation_id>/agent-stats', methods=['GET'])
def get_agent_stats(simulation_id):
    """获取 Agent 统计"""
    try:
        sim = _load_simulation(simulation_id)
        if not sim:
            return jsonify({"success": False, "error": "模拟不存在"}), 404
        profiles = sim.get('profiles', [])
        stats = {
            "total_agents": len(profiles),
            "active_agents": len(profiles),
            "total_posts": 0,
            "total_comments": 0,
            "agents": [
                {
                    "username": p.get('username', p.get('real_name', '')),
                    "entity_type": p.get('entity_type', ''),
                    "stance": p.get('stance', 'neutral'),
                    "posts": 0,
                    "comments": 0,
                }
                for p in profiles[:50]
            ]
        }
        return jsonify({"success": True, "data": stats})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ═══════════════════════════════════════════════════════════════
# API: 环境状态
# ═══════════════════════════════════════════════════════════════

@simulation_bp.route('/<simulation_id>/env-status', methods=['GET'])
def get_env_status(simulation_id):
    """获取环境状态"""
    try:
        sim = _load_simulation(simulation_id)
        if not sim:
            return jsonify({"success": False, "error": "模拟不存在"}), 404
        return jsonify({
            "success": True,
            "data": {"env_alive": sim.get('env_alive', False)}
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@simulation_bp.route('/interview/batch', methods=['POST'])
def interview_batch():
    """批量采访 Agent"""
    try:
        return jsonify({"success": True, "data": {"responses": []}})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ═══════════════════════════════════════════════════════════════
# API: 历史记录
# ═══════════════════════════════════════════════════════════════

@simulation_bp.route('/list', methods=['GET'])
def list_simulations():
    """列出所有模拟"""
    try:
        sims = list(_simulations.values())
        return jsonify({"success": True, "data": sims, "count": len(sims)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@simulation_bp.route('/history', methods=['GET'])
def get_history():
    """获取历史记录"""
    try:
        limit = request.args.get('limit', 10, type=int)
        sims = sorted(
            _simulations.values(),
            key=lambda x: x.get('created_at', ''),
            reverse=True
        )[:limit]
        return jsonify({"success": True, "data": sims})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
