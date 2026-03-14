"""
TraceBack 模拟运行引擎
纯 LLM 驱动的多 Agent 社交平台模拟，无需 OASIS 框架
每轮让 LLM 为每个 Agent 生成动作（发帖/评论/点赞等），记录到 actions 列表
"""

import os
import json
import time
import threading
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum

from ..config import Config
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger

logger = get_logger('traceback.simulation_engine')


class RunnerStatus(str, Enum):
    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    COMPLETED = "completed"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass
class SimulationRunState:
    simulation_id: str
    runner_status: RunnerStatus = RunnerStatus.IDLE
    total_rounds: int = 10
    # Twitter (Info Plaza)
    twitter_current_round: int = 0
    twitter_running: bool = False
    twitter_completed: bool = False
    twitter_actions_count: int = 0
    twitter_simulated_hours: float = 0
    # Reddit (Community)
    reddit_current_round: int = 0
    reddit_running: bool = False
    reddit_completed: bool = False
    reddit_actions_count: int = 0
    reddit_simulated_hours: float = 0
    # General
    process_pid: int = 0
    started_at: str = ""
    all_actions: List[Dict] = field(default_factory=list)
    posts: Dict[str, List[Dict]] = field(default_factory=lambda: {"twitter": [], "reddit": []})
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "simulation_id": self.simulation_id,
            "runner_status": self.runner_status.value,
            "total_rounds": self.total_rounds,
            "twitter_current_round": self.twitter_current_round,
            "twitter_running": self.twitter_running,
            "twitter_completed": self.twitter_completed,
            "twitter_actions_count": self.twitter_actions_count,
            "twitter_simulated_hours": self.twitter_simulated_hours,
            "reddit_current_round": self.reddit_current_round,
            "reddit_running": self.reddit_running,
            "reddit_completed": self.reddit_completed,
            "reddit_actions_count": self.reddit_actions_count,
            "reddit_simulated_hours": self.reddit_simulated_hours,
            "process_pid": self.process_pid,
            "started_at": self.started_at,
            "error": self.error,
        }

    def detail_dict(self) -> Dict[str, Any]:
        d = self.to_dict()
        d["all_actions"] = self.all_actions[-200:]  # 最近 200 条
        return d


# 全局运行状态
_run_states: Dict[str, SimulationRunState] = {}
_run_threads: Dict[str, threading.Thread] = {}
_stop_flags: Dict[str, bool] = {}


def get_run_state(simulation_id: str) -> Optional[SimulationRunState]:
    return _run_states.get(simulation_id)


def start_simulation(simulation_id: str, sim_data: Dict, max_rounds: int = 10) -> SimulationRunState:
    """启动模拟"""
    # 如果已经在运行，先停止
    if simulation_id in _run_states:
        old = _run_states[simulation_id]
        if old.runner_status == RunnerStatus.RUNNING:
            _stop_flags[simulation_id] = True
            time.sleep(1)

    state = SimulationRunState(
        simulation_id=simulation_id,
        total_rounds=max_rounds,
        runner_status=RunnerStatus.STARTING,
        twitter_running=True,
        reddit_running=True,
        started_at=datetime.now().isoformat(),
        process_pid=os.getpid(),
    )
    _run_states[simulation_id] = state
    _stop_flags[simulation_id] = False

    thread = threading.Thread(
        target=_simulation_loop,
        args=(simulation_id, sim_data, max_rounds),
        daemon=True,
        name=f"sim-{simulation_id[:8]}"
    )
    _run_threads[simulation_id] = thread
    thread.start()

    logger.info(f"模拟启动: {simulation_id}, max_rounds={max_rounds}")
    return state


def stop_simulation(simulation_id: str):
    """停止模拟"""
    _stop_flags[simulation_id] = True
    state = _run_states.get(simulation_id)
    if state:
        state.runner_status = RunnerStatus.STOPPED
        state.twitter_running = False
        state.reddit_running = False
    logger.info(f"模拟停止: {simulation_id}")


def _simulation_loop(simulation_id: str, sim_data: Dict, max_rounds: int):
    """模拟主循环"""
    state = _run_states[simulation_id]
    state.runner_status = RunnerStatus.RUNNING

    profiles = sim_data.get('profiles', [])
    requirement = sim_data.get('simulation_requirement', '')
    config = sim_data.get('config', {})

    if not profiles:
        state.runner_status = RunnerStatus.FAILED
        state.error = "没有 Agent Profile"
        return

    # 每轮选取活跃 Agent 子集（避免每轮都调太多 LLM）
    agents_per_round = min(8, len(profiles))
    hours_per_round = 2.0  # 每轮模拟 2 小时
    sim_start_time = datetime(2024, 3, 8, 0, 30)  # MH370 事件起始时间

    llm = LLMClient()

    try:
        for round_num in range(1, max_rounds + 1):
            if _stop_flags.get(simulation_id, False):
                break

            sim_time = sim_start_time + timedelta(hours=(round_num - 1) * hours_per_round)
            sim_time_str = sim_time.strftime("%Y-%m-%d %H:%M")

            logger.info(f"[{simulation_id[:8]}] Round {round_num}/{max_rounds} @ {sim_time_str}")

            # 选取本轮活跃 Agent（轮转）
            start_idx = ((round_num - 1) * agents_per_round) % len(profiles)
            active_agents = []
            for i in range(agents_per_round):
                active_agents.append(profiles[(start_idx + i) % len(profiles)])

            # 构建上下文：最近的帖子
            recent_posts = state.all_actions[-20:]
            context_lines = []
            for a in recent_posts[-10:]:
                if a.get("action_type") == "CREATE_POST":
                    context_lines.append(f"[{a.get('platform','?')}] @{a.get('agent_name','?')}: {a.get('content','')[:100]}")
                elif a.get("action_type") == "CREATE_COMMENT":
                    context_lines.append(f"[{a.get('platform','?')}] @{a.get('agent_name','?')} 评论: {a.get('content','')[:80]}")
            context_str = "\n".join(context_lines) if context_lines else "(暂无动态)"

            # 构建 Agent 列表描述
            agents_desc = ""
            for i, ag in enumerate(active_agents):
                agents_desc += f"\n{i+1}. @{ag.get('username', ag.get('real_name','?'))} ({ag.get('entity_type','?')}) - {ag.get('bio','')[:60]}"

            # 一次 LLM 调用生成本轮所有 Agent 在两个平台的动作
            prompt = f"""你是一个社交媒体模拟引擎。当前正在模拟一个历史事件的社交媒体讨论。

事件背景: {requirement[:300]}
当前模拟时间: {sim_time_str}（事件发生后第 {round_num} 轮）

最近的社交动态:
{context_str}

本轮活跃用户:
{agents_desc}

请为每个用户生成 1-2 个社交媒体动作。动作类型包括：
- CREATE_POST: 发帖（必须有 content 和 platform）
- CREATE_COMMENT: 评论（必须有 content、platform 和 reply_to_agent）
- LIKE_POST: 点赞（必须有 platform 和 target_agent）
- REPOST: 转发（必须有 platform 和 target_agent）
- DO_NOTHING: 不操作

platform 只能是 "twitter" 或 "reddit"。

以JSON数组输出：
[{{"agent_index":0,"agent_name":"用户名","platform":"twitter","action_type":"CREATE_POST","content":"帖子内容","reply_to_agent":"","target_agent":""}}]

要求：
1. 内容要符合角色设定和事件背景
2. 随时间推进，讨论应该深入发展
3. 不同立场的角色应有不同观点
4. twitter 和 reddit 的内容风格应有区别（twitter 简短，reddit 详细）
5. 每个用户 1-2 个动作，总共输出 {agents_per_round} 到 {agents_per_round * 2} 个动作"""

            try:
                result = llm.chat_json([{"role": "user", "content": prompt}])
                if isinstance(result, dict):
                    result = result.get("actions") or result.get("data") or [result]
                if not isinstance(result, list):
                    result = [result]

                for action in result:
                    platform = action.get("platform", "twitter")
                    action_type = action.get("action_type", "DO_NOTHING")
                    agent_name = action.get("agent_name", "unknown")
                    content = action.get("content", "")

                    action_record = {
                        "id": f"act_{uuid.uuid4().hex[:8]}",
                        "round_num": round_num,
                        "timestamp": sim_time_str,
                        "platform": platform,
                        "agent_id": action.get("agent_index", 0),
                        "agent_name": agent_name,
                        "action_type": action_type,
                        "content": content,
                        "reply_to_agent": action.get("reply_to_agent", ""),
                        "target_agent": action.get("target_agent", ""),
                        "success": True,
                    }
                    state.all_actions.append(action_record)

                    # 更新平台计数
                    if platform == "twitter":
                        state.twitter_actions_count += 1
                    else:
                        state.reddit_actions_count += 1

                    # 记录帖子
                    if action_type == "CREATE_POST" and content:
                        state.posts.setdefault(platform, []).append({
                            "id": action_record["id"],
                            "author": agent_name,
                            "content": content,
                            "timestamp": sim_time_str,
                            "round": round_num,
                        })

            except Exception as e:
                logger.warning(f"Round {round_num} LLM 失败: {e}")
                # 生成默认动作
                for ag in active_agents[:2]:
                    state.all_actions.append({
                        "id": f"act_{uuid.uuid4().hex[:8]}",
                        "round_num": round_num,
                        "timestamp": sim_time_str,
                        "platform": "twitter",
                        "agent_id": 0,
                        "agent_name": ag.get('username', '?'),
                        "action_type": "DO_NOTHING",
                        "content": "",
                        "success": True,
                    })
                    state.twitter_actions_count += 1

            # 更新状态
            state.twitter_current_round = round_num
            state.reddit_current_round = round_num
            state.twitter_simulated_hours = round_num * hours_per_round
            state.reddit_simulated_hours = round_num * hours_per_round

            # 轮间等待（给前端时间轮询 + 避免 429）
            if round_num < max_rounds and not _stop_flags.get(simulation_id, False):
                time.sleep(3)

        # 完成
        state.twitter_completed = True
        state.reddit_completed = True
        state.twitter_running = False
        state.reddit_running = False
        state.runner_status = RunnerStatus.COMPLETED
        logger.info(f"模拟完成: {simulation_id}, actions={len(state.all_actions)}")

        # 保存结果到 simulation 数据
        _save_run_result(simulation_id, state)

    except Exception as e:
        logger.error(f"模拟异常: {simulation_id}: {e}", exc_info=True)
        state.runner_status = RunnerStatus.FAILED
        state.error = str(e)
        state.twitter_running = False
        state.reddit_running = False


def _save_run_result(simulation_id: str, state: SimulationRunState):
    """保存运行结果到磁盘"""
    try:
        sim_dir = os.path.join(Config.UPLOAD_FOLDER, 'simulations', simulation_id)
        os.makedirs(sim_dir, exist_ok=True)

        result_path = os.path.join(sim_dir, 'run_result.json')
        with open(result_path, 'w', encoding='utf-8') as f:
            json.dump({
                "simulation_id": simulation_id,
                "total_rounds": state.total_rounds,
                "total_actions": len(state.all_actions),
                "twitter_actions": state.twitter_actions_count,
                "reddit_actions": state.reddit_actions_count,
                "actions": state.all_actions,
                "posts": state.posts,
                "completed_at": datetime.now().isoformat(),
            }, f, ensure_ascii=False, indent=2)
        logger.info(f"运行结果已保存: {result_path}")
    except Exception as e:
        logger.warning(f"保存运行结果失败: {e}")
