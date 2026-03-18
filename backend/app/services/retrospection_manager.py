"""
TraceBack 回溯分析管理器
管理回溯分析的完整生命周期：任务输入→数据采集→因果推理→质证辩论→证据闭环→报告生成
"""

import os
import json
import uuid
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..config import Config
from ..utils.logger import get_logger
from .agent_profiles import AGENT_PROFILES, AgentProfile

logger = get_logger('traceback.retrospection')


class AnalysisPhase(str, Enum):
    """分析阶段"""
    CREATED = "created"
    DATA_COLLECTION = "data_collection"       # 数据采集（ArchiveHunter）
    TIMELINE_BUILDING = "timeline_building"   # 时间线重建（ChronoAnalyst）
    CAUSAL_REASONING = "causal_reasoning"     # 因果推理（CausalDetective）
    EVIDENCE_AUDIT = "evidence_audit"         # 证据审计（EvidenceAuditor）
    REPORT_GENERATION = "report_generation"   # 报告生成（RetrospectWriter）
    COMPLETED = "completed"
    FAILED = "failed"


class AnalysisStatus(str, Enum):
    """分析状态"""
    CREATED = "created"
    PREPARING = "preparing"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AgentAction:
    """Agent分析行动记录"""
    round_num: int
    timestamp: str
    phase: str
    agent_id: str
    agent_name: str
    action_type: str  # SEARCH_DATA, BUILD_TIMELINE, PROPOSE_HYPOTHESIS, etc.
    content: str = ""
    evidence_ids: List[str] = field(default_factory=list)
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "round_num": self.round_num,
            "timestamp": self.timestamp,
            "phase": self.phase,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "action_type": self.action_type,
            "content": self.content,
            "evidence_ids": self.evidence_ids,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


@dataclass
class DebateMessage:
    """质证辩论消息"""
    message_id: str
    round_num: int
    timestamp: str
    agent_id: str
    agent_name: str
    agent_icon: str
    agent_color: str
    message_type: str  # hypothesis, challenge, evidence, consensus, question
    content: str
    target_message_id: Optional[str] = None  # 回复/质疑的目标消息
    evidence_ids: List[str] = field(default_factory=list)
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "round_num": self.round_num,
            "timestamp": self.timestamp,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "agent_icon": self.agent_icon,
            "agent_color": self.agent_color,
            "message_type": self.message_type,
            "content": self.content,
            "target_message_id": self.target_message_id,
            "evidence_ids": self.evidence_ids,
            "confidence": self.confidence,
        }


@dataclass
class CausalNode:
    """因果网络节点"""
    node_id: str
    name: str
    node_type: str  # event, person, organization, evidence, location, condition
    timestamp: str = ""
    description: str = ""
    credibility_score: float = 0.5
    importance_score: float = 0.5
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.node_id,
            "name": self.name,
            "type": self.node_type,
            "timestamp": self.timestamp,
            "description": self.description,
            "credibility_score": self.credibility_score,
            "importance_score": self.importance_score,
            "metadata": self.metadata,
        }


@dataclass
class CausalEdge:
    """因果网络边"""
    edge_id: str
    source: str  # 源节点ID
    target: str  # 目标节点ID
    causal_type: str  # direct, indirect, root, temporal, evidential
    strength: float = 0.5
    confidence: float = 0.5
    evidence_ids: List[str] = field(default_factory=list)
    label: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.edge_id,
            "source": self.source,
            "target": self.target,
            "causal_type": self.causal_type,
            "strength": self.strength,
            "confidence": self.confidence,
            "evidence_ids": self.evidence_ids,
            "label": self.label,
        }


@dataclass
class AnalysisState:
    """回溯分析状态"""
    analysis_id: str
    project_id: str
    graph_id: str

    # 任务信息
    task_description: str = ""
    time_range_start: str = ""
    time_range_end: str = ""

    # 状态
    status: AnalysisStatus = AnalysisStatus.CREATED
    current_phase: AnalysisPhase = AnalysisPhase.CREATED
    current_debate_round: int = 0
    max_debate_rounds: int = 3

    # 分析结果数据
    causal_nodes: List[Dict] = field(default_factory=list)
    causal_edges: List[Dict] = field(default_factory=list)
    timeline_events: List[Dict] = field(default_factory=list)
    evidence_chain: List[Dict] = field(default_factory=list)
    debate_messages: List[Dict] = field(default_factory=list)
    agent_actions: List[Dict] = field(default_factory=list)

    # 置信度评估
    overall_confidence: float = 0.0
    evidence_completeness: float = 0.0
    causal_chain_strength: float = 0.0
    agent_consensus_score: float = 0.0
    contradiction_count: int = 0

    # 时间戳
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # 错误信息
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "analysis_id": self.analysis_id,
            "project_id": self.project_id,
            "graph_id": self.graph_id,
            "task_description": self.task_description,
            "time_range_start": self.time_range_start,
            "time_range_end": self.time_range_end,
            "status": self.status.value if isinstance(self.status, AnalysisStatus) else self.status,
            "current_phase": self.current_phase.value if isinstance(self.current_phase, AnalysisPhase) else self.current_phase,
            "current_debate_round": self.current_debate_round,
            "max_debate_rounds": self.max_debate_rounds,
            "causal_nodes_count": len(self.causal_nodes),
            "causal_edges_count": len(self.causal_edges),
            "timeline_events_count": len(self.timeline_events),
            "evidence_count": len(self.evidence_chain),
            "debate_messages_count": len(self.debate_messages),
            "overall_confidence": self.overall_confidence,
            "evidence_completeness": self.evidence_completeness,
            "causal_chain_strength": self.causal_chain_strength,
            "agent_consensus_score": self.agent_consensus_score,
            "contradiction_count": self.contradiction_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "error": self.error,
        }

    def to_full_dict(self) -> Dict[str, Any]:
        """包含完整数据的字典（用于保存）"""
        d = self.to_dict()
        d.update({
            "causal_nodes": self.causal_nodes,
            "causal_edges": self.causal_edges,
            "timeline_events": self.timeline_events,
            "evidence_chain": self.evidence_chain,
            "debate_messages": self.debate_messages,
            "agent_actions": self.agent_actions,
        })
        return d


class RetrospectionManager:
    """
    回溯分析管理器
    管理分析的创建、状态流转、数据持久化
    """

    def __init__(self):
        self.data_dir = Config.TRACEBACK_ANALYSIS_DATA_DIR
        os.makedirs(self.data_dir, exist_ok=True)

    def create_analysis(
        self,
        project_id: str,
        graph_id: str,
        task_description: str,
        time_range_start: str = "",
        time_range_end: str = "",
        max_debate_rounds: int = None,
    ) -> AnalysisState:
        """创建新的回溯分析"""
        analysis_id = f"analysis_{uuid.uuid4().hex[:12]}"

        state = AnalysisState(
            analysis_id=analysis_id,
            project_id=project_id,
            graph_id=graph_id,
            task_description=task_description,
            time_range_start=time_range_start,
            time_range_end=time_range_end,
            max_debate_rounds=max_debate_rounds or Config.TRACEBACK_MAX_DEBATE_ROUNDS,
        )

        self._save_state(state)
        logger.info(f"创建回溯分析: {analysis_id}, 项目: {project_id}")
        return state

    def get_analysis(self, analysis_id: str) -> Optional[AnalysisState]:
        """获取分析状态"""
        return self._load_state(analysis_id)

    def update_phase(self, analysis_id: str, phase: AnalysisPhase) -> Optional[AnalysisState]:
        """更新分析阶段"""
        state = self._load_state(analysis_id)
        if not state:
            return None
        state.current_phase = phase
        state.updated_at = datetime.now().isoformat()
        if phase == AnalysisPhase.COMPLETED:
            state.status = AnalysisStatus.COMPLETED
        elif phase == AnalysisPhase.FAILED:
            state.status = AnalysisStatus.FAILED
        else:
            state.status = AnalysisStatus.RUNNING
        self._save_state(state)
        return state

    def add_causal_node(self, analysis_id: str, node: CausalNode) -> bool:
        """添加因果网络节点"""
        state = self._load_state(analysis_id)
        if not state:
            return False
        state.causal_nodes.append(node.to_dict())
        state.updated_at = datetime.now().isoformat()
        self._save_state(state)
        return True

    def add_causal_edge(self, analysis_id: str, edge: CausalEdge) -> bool:
        """添加因果网络边"""
        state = self._load_state(analysis_id)
        if not state:
            return False
        state.causal_edges.append(edge.to_dict())
        state.updated_at = datetime.now().isoformat()
        self._save_state(state)
        return True

    def add_timeline_event(self, analysis_id: str, event: Dict[str, Any]) -> bool:
        """添加时间线事件"""
        state = self._load_state(analysis_id)
        if not state:
            return False
        state.timeline_events.append(event)
        # 按时间排序
        state.timeline_events.sort(key=lambda x: x.get("timestamp", ""))
        state.updated_at = datetime.now().isoformat()
        self._save_state(state)
        return True

    def add_debate_message(self, analysis_id: str, message: DebateMessage) -> bool:
        """添加质证辩论消息"""
        state = self._load_state(analysis_id)
        if not state:
            return False
        state.debate_messages.append(message.to_dict())
        state.updated_at = datetime.now().isoformat()
        self._save_state(state)
        return True

    def add_agent_action(self, analysis_id: str, action: AgentAction) -> bool:
        """记录Agent行动"""
        state = self._load_state(analysis_id)
        if not state:
            return False
        state.agent_actions.append(action.to_dict())
        state.updated_at = datetime.now().isoformat()
        self._save_state(state)
        return True

    def update_confidence(
        self,
        analysis_id: str,
        overall: float = None,
        evidence_completeness: float = None,
        causal_strength: float = None,
        consensus: float = None,
        contradictions: int = None,
    ) -> bool:
        """更新置信度评估"""
        state = self._load_state(analysis_id)
        if not state:
            return False
        if overall is not None:
            state.overall_confidence = overall
        if evidence_completeness is not None:
            state.evidence_completeness = evidence_completeness
        if causal_strength is not None:
            state.causal_chain_strength = causal_strength
        if consensus is not None:
            state.agent_consensus_score = consensus
        if contradictions is not None:
            state.contradiction_count = contradictions
        state.updated_at = datetime.now().isoformat()
        self._save_state(state)
        return True

    def get_causal_graph_data(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        """获取因果网络图数据（供前端可视化）"""
        state = self._load_state(analysis_id)
        if not state:
            return None
        return {
            "nodes": state.causal_nodes,
            "edges": state.causal_edges,
        }

    def get_timeline_data(self, analysis_id: str) -> Optional[List[Dict]]:
        """获取时间线数据"""
        state = self._load_state(analysis_id)
        if not state:
            return None
        return state.timeline_events

    def get_debate_messages(self, analysis_id: str, since_index: int = 0) -> Optional[List[Dict]]:
        """获取质证辩论消息（支持增量获取）"""
        state = self._load_state(analysis_id)
        if not state:
            return None
        return state.debate_messages[since_index:]

    def get_evidence_chain(self, analysis_id: str) -> Optional[List[Dict]]:
        """获取证据链数据"""
        state = self._load_state(analysis_id)
        if not state:
            return None
        return state.evidence_chain

    def list_analyses(self, project_id: str = None, limit: int = 50) -> List[Dict]:
        """列出分析任务"""
        analyses = []
        if not os.path.exists(self.data_dir):
            return analyses
        for fname in os.listdir(self.data_dir):
            if fname.endswith(".json"):
                try:
                    fpath = os.path.join(self.data_dir, fname)
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if project_id and data.get("project_id") != project_id:
                        continue
                    analyses.append({
                        "analysis_id": data.get("analysis_id"),
                        "project_id": data.get("project_id"),
                        "task_description": data.get("task_description", ""),
                        "status": data.get("status"),
                        "current_phase": data.get("current_phase"),
                        "overall_confidence": data.get("overall_confidence", 0),
                        "created_at": data.get("created_at"),
                    })
                except Exception:
                    continue
        analyses.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return analyses[:limit]

    # ===== 持久化 =====

    def _save_state(self, state: AnalysisState):
        """保存分析状态到JSON文件"""
        fpath = os.path.join(self.data_dir, f"{state.analysis_id}.json")
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(state.to_full_dict(), f, ensure_ascii=False, indent=2)

    def _load_state(self, analysis_id: str) -> Optional[AnalysisState]:
        """从JSON文件加载分析状态"""
        fpath = os.path.join(self.data_dir, f"{analysis_id}.json")
        if not os.path.exists(fpath):
            return None
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            state = AnalysisState(
                analysis_id=data["analysis_id"],
                project_id=data["project_id"],
                graph_id=data["graph_id"],
            )
            # 填充所有字段
            state.task_description = data.get("task_description", "")
            state.time_range_start = data.get("time_range_start", "")
            state.time_range_end = data.get("time_range_end", "")
            state.status = AnalysisStatus(data.get("status", "created"))
            state.current_phase = AnalysisPhase(data.get("current_phase", "created"))
            state.current_debate_round = data.get("current_debate_round", 0)
            state.max_debate_rounds = data.get("max_debate_rounds", 3)
            state.causal_nodes = data.get("causal_nodes", [])
            state.causal_edges = data.get("causal_edges", [])
            state.timeline_events = data.get("timeline_events", [])
            state.evidence_chain = data.get("evidence_chain", [])
            state.debate_messages = data.get("debate_messages", [])
            state.agent_actions = data.get("agent_actions", [])
            state.overall_confidence = data.get("overall_confidence", 0.0)
            state.evidence_completeness = data.get("evidence_completeness", 0.0)
            state.causal_chain_strength = data.get("causal_chain_strength", 0.0)
            state.agent_consensus_score = data.get("agent_consensus_score", 0.0)
            state.contradiction_count = data.get("contradiction_count", 0)
            state.created_at = data.get("created_at", "")
            state.updated_at = data.get("updated_at", "")
            state.error = data.get("error")
            return state
        except Exception as e:
            logger.error(f"加载分析状态失败: {analysis_id}, 错误: {e}")
            return None
