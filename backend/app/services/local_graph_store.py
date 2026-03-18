"""
TraceBack 本地知识图谱存储
用纯 Python + JSON 文件替代 Zep Cloud，实现知识图谱的存储和检索
MVP阶段完全不需要外部图数据库服务

核心能力：
1. 节点（实体）的增删改查
2. 边（关系）的增删改查
3. 基于关键词的图谱搜索
4. 基于LLM的语义搜索（通过DeepSeek做语义匹配）
5. 子图提取（给定节点，返回N跳邻居）
"""

import os
import json
import uuid
import time
from typing import Dict, Any, List, Optional, Set, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger('traceback.local_graph')


# ============================================================
# 数据结构
# ============================================================

@dataclass
class GraphNode:
    """图谱节点（实体）"""
    uuid: str
    name: str
    labels: List[str]  # 实体类型标签，如 ["Event", "Accident"]
    summary: str = ""
    attributes: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def match_keywords(self, keywords: List[str]) -> int:
        """关键词匹配评分"""
        score = 0
        text = f"{self.name} {self.summary} {' '.join(self.labels)} {json.dumps(self.attributes, ensure_ascii=False)}".lower()
        for kw in keywords:
            if kw.lower() in text:
                score += 1
                # 名称匹配加分
                if kw.lower() in self.name.lower():
                    score += 2
        return score


@dataclass
class GraphEdge:
    """图谱边（关系）"""
    uuid: str
    name: str  # 关系类型，如 "CAUSED_BY"
    fact: str  # 关系描述，如 "事件A由事件B导致"
    source_node_uuid: str
    target_node_uuid: str
    source_node_name: str = ""
    target_node_name: str = ""
    attributes: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    valid_at: str = ""
    invalid_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def match_keywords(self, keywords: List[str]) -> int:
        """关键词匹配评分"""
        score = 0
        text = f"{self.name} {self.fact} {self.source_node_name} {self.target_node_name}".lower()
        for kw in keywords:
            if kw.lower() in text:
                score += 1
        return score


# ============================================================
# 本地图谱存储
# ============================================================

class LocalGraphStore:
    """
    本地JSON文件图谱存储
    每个graph_id对应一个JSON文件，包含所有节点和边
    """

    def __init__(self, storage_dir: str = None):
        self.storage_dir = storage_dir or os.path.join(
            os.path.dirname(__file__), '..', 'uploads', 'graphs'
        )
        os.makedirs(self.storage_dir, exist_ok=True)

    def _graph_path(self, graph_id: str) -> str:
        return os.path.join(self.storage_dir, f"{graph_id}.json")

    def _load_graph(self, graph_id: str) -> Dict[str, Any]:
        path = self._graph_path(graph_id)
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"nodes": {}, "edges": {}, "metadata": {}}

    def _save_graph(self, graph_id: str, data: Dict[str, Any]):
        path = self._graph_path(graph_id)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ===== 节点操作 =====

    def add_node(self, graph_id: str, name: str, labels: List[str],
                 summary: str = "", attributes: Dict[str, Any] = None) -> GraphNode:
        """添加节点"""
        data = self._load_graph(graph_id)
        node_id = str(uuid.uuid4())[:12]
        now = datetime.now().isoformat()

        node = GraphNode(
            uuid=node_id,
            name=name,
            labels=labels,
            summary=summary,
            attributes=attributes or {},
            created_at=now,
            updated_at=now,
        )
        data["nodes"][node_id] = node.to_dict()
        self._save_graph(graph_id, data)
        logger.debug(f"添加节点: {name} ({node_id})")
        return node

    def get_node(self, graph_id: str, node_uuid: str) -> Optional[GraphNode]:
        """获取节点"""
        data = self._load_graph(graph_id)
        node_data = data["nodes"].get(node_uuid)
        if node_data:
            return GraphNode(**node_data)
        return None

    def get_all_nodes(self, graph_id: str) -> List[GraphNode]:
        """获取所有节点"""
        data = self._load_graph(graph_id)
        return [GraphNode(**v) for v in data["nodes"].values()]

    def find_node_by_name(self, graph_id: str, name: str) -> Optional[GraphNode]:
        """按名称查找节点"""
        data = self._load_graph(graph_id)
        for v in data["nodes"].values():
            if v["name"] == name:
                return GraphNode(**v)
        return None

    def update_node(self, graph_id: str, node_uuid: str, **kwargs) -> Optional[GraphNode]:
        """更新节点"""
        data = self._load_graph(graph_id)
        if node_uuid not in data["nodes"]:
            return None
        for k, v in kwargs.items():
            if k in data["nodes"][node_uuid]:
                data["nodes"][node_uuid][k] = v
        data["nodes"][node_uuid]["updated_at"] = datetime.now().isoformat()
        self._save_graph(graph_id, data)
        return GraphNode(**data["nodes"][node_uuid])

    def delete_node(self, graph_id: str, node_uuid: str):
        """删除节点及其关联边"""
        data = self._load_graph(graph_id)
        data["nodes"].pop(node_uuid, None)
        # 删除关联边
        edges_to_remove = [
            eid for eid, e in data["edges"].items()
            if e["source_node_uuid"] == node_uuid or e["target_node_uuid"] == node_uuid
        ]
        for eid in edges_to_remove:
            data["edges"].pop(eid, None)
        self._save_graph(graph_id, data)

    # ===== 边操作 =====

    def add_edge(self, graph_id: str, name: str, fact: str,
                 source_node_uuid: str, target_node_uuid: str,
                 attributes: Dict[str, Any] = None) -> GraphEdge:
        """添加边"""
        data = self._load_graph(graph_id)
        edge_id = str(uuid.uuid4())[:12]
        now = datetime.now().isoformat()

        # 获取节点名称
        source_name = data["nodes"].get(source_node_uuid, {}).get("name", "")
        target_name = data["nodes"].get(target_node_uuid, {}).get("name", "")

        edge = GraphEdge(
            uuid=edge_id,
            name=name,
            fact=fact,
            source_node_uuid=source_node_uuid,
            target_node_uuid=target_node_uuid,
            source_node_name=source_name,
            target_node_name=target_name,
            attributes=attributes or {},
            created_at=now,
        )
        data["edges"][edge_id] = edge.to_dict()
        self._save_graph(graph_id, data)
        logger.debug(f"添加边: {source_name} --[{name}]--> {target_name}")
        return edge

    def get_edge(self, graph_id: str, edge_uuid: str) -> Optional[GraphEdge]:
        """获取边"""
        data = self._load_graph(graph_id)
        edge_data = data["edges"].get(edge_uuid)
        if edge_data:
            return GraphEdge(**edge_data)
        return None

    def get_all_edges(self, graph_id: str) -> List[GraphEdge]:
        """获取所有边"""
        data = self._load_graph(graph_id)
        return [GraphEdge(**v) for v in data["edges"].values()]

    def get_node_edges(self, graph_id: str, node_uuid: str,
                       direction: str = "both") -> List[GraphEdge]:
        """获取节点的关联边"""
        data = self._load_graph(graph_id)
        edges = []
        for v in data["edges"].values():
            if direction in ("both", "outgoing") and v["source_node_uuid"] == node_uuid:
                edges.append(GraphEdge(**v))
            elif direction in ("both", "incoming") and v["target_node_uuid"] == node_uuid:
                edges.append(GraphEdge(**v))
        return edges

    # ===== 搜索 =====

    def keyword_search(self, graph_id: str, query: str,
                       top_k: int = 20) -> Dict[str, Any]:
        """
        关键词搜索：在节点和边中搜索匹配的内容
        """
        keywords = query.lower().split()
        data = self._load_graph(graph_id)

        # 搜索节点
        node_scores = []
        for v in data["nodes"].values():
            node = GraphNode(**v)
            score = node.match_keywords(keywords)
            if score > 0:
                node_scores.append((score, node))
        node_scores.sort(key=lambda x: x[0], reverse=True)

        # 搜索边
        edge_scores = []
        for v in data["edges"].values():
            edge = GraphEdge(**v)
            score = edge.match_keywords(keywords)
            if score > 0:
                edge_scores.append((score, edge))
        edge_scores.sort(key=lambda x: x[0], reverse=True)

        # 提取facts
        facts = [e.fact for _, e in edge_scores[:top_k] if e.fact]

        return {
            "facts": facts,
            "nodes": [n.to_dict() for _, n in node_scores[:top_k]],
            "edges": [e.to_dict() for _, e in edge_scores[:top_k]],
            "query": query,
            "total_count": len(node_scores) + len(edge_scores),
        }

    def get_subgraph(self, graph_id: str, center_node_uuid: str,
                     hops: int = 2) -> Dict[str, Any]:
        """
        子图提取：获取中心节点的N跳邻居子图
        """
        data = self._load_graph(graph_id)
        visited_nodes: Set[str] = {center_node_uuid}
        frontier: Set[str] = {center_node_uuid}
        result_edges: List[Dict] = []

        for _ in range(hops):
            next_frontier: Set[str] = set()
            for v in data["edges"].values():
                src, tgt = v["source_node_uuid"], v["target_node_uuid"]
                if src in frontier and tgt not in visited_nodes:
                    next_frontier.add(tgt)
                    result_edges.append(v)
                elif tgt in frontier and src not in visited_nodes:
                    next_frontier.add(src)
                    result_edges.append(v)
            visited_nodes |= next_frontier
            frontier = next_frontier
            if not frontier:
                break

        result_nodes = [
            data["nodes"][nid] for nid in visited_nodes
            if nid in data["nodes"]
        ]

        return {
            "nodes": result_nodes,
            "edges": result_edges,
            "center_node": center_node_uuid,
            "hops": hops,
        }

    # ===== 统计 =====

    def get_stats(self, graph_id: str) -> Dict[str, Any]:
        """获取图谱统计信息"""
        data = self._load_graph(graph_id)
        node_types = {}
        for v in data["nodes"].values():
            for label in v.get("labels", []):
                node_types[label] = node_types.get(label, 0) + 1

        edge_types = {}
        for v in data["edges"].values():
            name = v.get("name", "unknown")
            edge_types[name] = edge_types.get(name, 0) + 1

        return {
            "node_count": len(data["nodes"]),
            "edge_count": len(data["edges"]),
            "node_types": node_types,
            "edge_types": edge_types,
        }

    def graph_exists(self, graph_id: str) -> bool:
        """检查图谱是否存在"""
        return os.path.exists(self._graph_path(graph_id))

    def delete_graph(self, graph_id: str):
        """删除整个图谱"""
        path = self._graph_path(graph_id)
        if os.path.exists(path):
            os.remove(path)

    # ===== 导出 =====

    def get_graph_data(self, graph_id: str) -> Dict[str, Any]:
        """
        获取完整图谱数据（前端渲染用，与Zep模式格式一致）
        """
        data = self._load_graph(graph_id)

        nodes = []
        for v in data["nodes"].values():
            nodes.append({
                "uuid": v["uuid"],
                "name": v["name"],
                "labels": v["labels"],
                "summary": v.get("summary", ""),
                "attributes": v.get("attributes", {}),
                "created_at": v.get("created_at", ""),
            })

        edges = []
        for v in data["edges"].values():
            edges.append({
                "uuid": v["uuid"],
                "name": v["name"],
                "fact": v.get("fact", ""),
                "source_node_uuid": v["source_node_uuid"],
                "target_node_uuid": v["target_node_uuid"],
                "source_name": v.get("source_node_name", ""),
                "target_name": v.get("target_node_name", ""),
                "attributes": v.get("attributes", {}),
                "created_at": v.get("created_at", ""),
            })

        return {
            "nodes": nodes,
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges)
        }

    def export_for_visualization(self, graph_id: str) -> Dict[str, Any]:
        """
        导出为前端可视化格式
        返回 {nodes: [{id, name, type, ...}], edges: [{source, target, type, ...}]}
        """
        data = self._load_graph(graph_id)

        vis_nodes = []
        for v in data["nodes"].values():
            vis_nodes.append({
                "id": v["uuid"],
                "name": v["name"],
                "type": v["labels"][0] if v["labels"] else "Unknown",
                "labels": v["labels"],
                "summary": v.get("summary", ""),
                "credibility_score": float(v.get("attributes", {}).get("credibility_score", None) or 0.5),
            })

        vis_edges = []
        for v in data["edges"].values():
            vis_edges.append({
                "id": v["uuid"],
                "source": v["source_node_uuid"],
                "target": v["target_node_uuid"],
                "causal_type": v["name"].lower(),
                "label": v["name"],
                "fact": v.get("fact", ""),
                "strength": float(v.get("attributes", {}).get("causal_strength", None) or 0.5),
            })

        return {"nodes": vis_nodes, "edges": vis_edges}
