"""
TraceBack 图谱构建服务
优先使用 Zep Cloud 构建知识图谱（高速），降级使用本地 LLM + LocalGraphStore
支持图谱构建期间并发预生成 Agent Profile（流水线加速）
"""

import os
import uuid
import time
import json
import warnings
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass

from ..config import Config
from ..models.task import TaskManager, TaskStatus
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger
from .text_processor import TextProcessor
from .local_graph_store import LocalGraphStore

logger = get_logger('traceback.graph_builder')

# ═══════════════════════════════════════════════════════════════
# 全局预生成 Profile 缓存
# 图谱构建期间边等 Zep 处理边生成 Profile，第三步直接取用
# ═══════════════════════════════════════════════════════════════
_prebuilt_profiles_lock = threading.Lock()
_prebuilt_profiles = {}  # graph_id -> {"profiles": [...], "config_agents": [...], "status": "building"|"done"}


def get_prebuilt_profiles(graph_id: str) -> Optional[Dict]:
    """获取预生成的 profiles（供第三步调用）"""
    with _prebuilt_profiles_lock:
        data = _prebuilt_profiles.get(graph_id)
        if data and data.get("status") == "done" and len(data.get("profiles", [])) > 0:
            return data
    return None


def _generate_single_profile(node_name, entity_type, summary, requirement, llm):
    """为单个节点生成 Agent Profile（线程安全，纯 IO）"""
    prompt = f"""你是一个学术研究助手，正在为历史事件因果分析系统构建模拟角色档案。
这是严肃的学术研究项目，用于分析历史事件的因果关系。请为以下实体生成角色档案。

实体名称: {node_name}
实体类型: {entity_type}
实体描述: {summary}
研究课题: {requirement}

请以JSON格式输出：
{{
    "username": "该实体的显示名称",
    "real_name": "{node_name}",
    "entity_type": "{entity_type}",
    "bio": "100字以内的角色简介（学术视角）",
    "stance": "neutral/positive/negative/critical（对事件的学术立场）",
    "expertise": ["专业领域1", "专业领域2"],
    "personality_traits": ["特征1", "特征2"],
    "posts_per_hour": 2,
    "replies_per_hour": 3,
    "active_hours": [9, 10, 11, 14, 15, 16, 20, 21]
}}"""
    try:
        result = llm.chat_json([{"role": "user", "content": prompt}])
        if result:
            result['real_name'] = node_name
            result['entity_type'] = entity_type
            return result
    except Exception as e:
        logger.warning(f"预生成 profile 失败 ({node_name}): {e}")
    # 降级默认 profile
    return {
        "username": node_name,
        "real_name": node_name,
        "entity_type": entity_type,
        "bio": summary[:100] if summary else f"{entity_type}: {node_name}",
        "stance": "neutral",
        "expertise": [],
        "personality_traits": [],
        "posts_per_hour": 2,
        "replies_per_hour": 3,
        "active_hours": [9, 10, 11, 14, 15, 16, 20, 21],
    }


@dataclass
class GraphInfo:
    """图谱信息"""
    graph_id: str
    node_count: int
    edge_count: int
    entity_types: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "entity_types": self.entity_types,
        }


# LLM 提取实体和关系的提示词（本地降级模式使用）
EXTRACT_PROMPT = """你是一个专业的知识图谱构建专家。请从以下文本中提取实体和关系。

## 本体定义（你只能使用以下类型）

### 实体类型：
{entity_types}

### 关系类型：
{edge_types}

## 文本内容：
{text_chunk}

## 输出要求
请输出JSON格式，包含：
```json
{{
    "entities": [
        {{
            "name": "实体名称",
            "type": "实体类型（必须是上面定义的类型之一）",
            "summary": "实体描述",
            "attributes": {{
                "timestamp": "时间（如果有）",
                "credibility_score": "0.7",
                "source": "来源",
                "description": "详细描述"
            }}
        }}
    ],
    "relations": [
        {{
            "source": "源实体名称",
            "target": "目标实体名称",
            "type": "关系类型（必须是上面定义的类型之一）",
            "fact": "关系描述（一句话说明这个关系）",
            "attributes": {{
                "confidence": "0.8",
                "causal_strength": "0.7"
            }}
        }}
    ]
}}
```

注意：
1. 实体名称要简洁明确
2. 同一个实体在不同句子中出现时，使用相同的名称
3. 关系必须基于文本中的明确信息，不要推测
4. 每个关系都要有fact描述
"""


class GraphBuilderService:
    """
    图谱构建服务
    优先使用 Zep Cloud（快速），降级使用本地 LLM 抽取
    """

    def __init__(self):
        self.task_manager = TaskManager()
        self.graph_store = LocalGraphStore()

        # 尝试初始化 Zep 客户端
        self._zep_client = None
        self._use_zep = False
        if Config.ZEP_API_KEY:
            try:
                from zep_cloud.client import Zep
                self._zep_client = Zep(api_key=Config.ZEP_API_KEY)
                self._use_zep = True
                logger.info("Zep Cloud 已启用，图谱构建将使用 Zep 加速")
            except Exception as e:
                logger.warning(f"Zep Cloud 初始化失败，降级使用本地模式: {e}")

        if not self._use_zep:
            try:
                self.llm = LLMClient(preset="fast")
                logger.info("使用本地 LLM + LocalGraphStore 模式")
            except ValueError:
                self.llm = None
                logger.info("LLM API Key 未配置，使用纯本地模式（简化图谱构建）")

    # ================================================================
    # 公共接口
    # ================================================================

    def build_graph_async(
        self,
        text: str,
        ontology: Dict[str, Any],
        graph_name: str = "TraceBack Graph",
        chunk_size: int = 800,
        chunk_overlap: int = 100,
        batch_size: int = 3
    ) -> str:
        """异步构建图谱，返回任务ID"""
        task_id = self.task_manager.create_task(
            task_type="graph_build",
            metadata={"graph_name": graph_name, "text_length": len(text)}
        )

        if self._use_zep:
            target = self._build_graph_zep_worker
        else:
            target = self._build_graph_local_worker

        thread = threading.Thread(
            target=target,
            args=(task_id, text, ontology, graph_name, chunk_size, chunk_overlap, batch_size),
            daemon=True
        )
        thread.start()

        return task_id

    def get_graph_info(self, graph_id: str) -> Optional[GraphInfo]:
        """获取图谱信息"""
        if self._use_zep:
            return self._get_graph_info_zep(graph_id)
        else:
            return self._get_graph_info_local(graph_id)

    def get_graph_data(self, graph_id: str) -> Dict[str, Any]:
        """获取完整图谱数据"""
        if self._use_zep:
            return self._get_graph_data_zep(graph_id)
        else:
            return self._get_graph_data_local(graph_id)

    # ================================================================
    # Zep Cloud 模式
    # ================================================================

    def _build_graph_zep_worker(
        self, task_id: str, text: str, ontology: Dict[str, Any],
        graph_name: str, chunk_size: int, chunk_overlap: int, batch_size: int
    ):
        """Zep Cloud 图谱构建（高速）"""
        try:
            from zep_cloud import EpisodeData
            self.task_manager.update_task(task_id, status=TaskStatus.PROCESSING, progress=5, message="开始构建图谱...")

            # 1. 创建 Zep 图谱
            graph_id = self._zep_create_graph(graph_name)
            self.task_manager.update_task(task_id, progress=10, message=f"图谱已创建: {graph_id}")

            # 2. 设置本体
            self._zep_set_ontology(graph_id, ontology)
            self.task_manager.update_task(task_id, progress=15, message="本体已设置")

            # 3. 文本分块
            chunks = TextProcessor.split_text(text, chunk_size, chunk_overlap)
            total_chunks = len(chunks)
            self.task_manager.update_task(task_id, progress=20, message=f"文本已分割为 {total_chunks} 个块")

            # 4. 分批发送数据到 Zep
            episode_uuids = []
            for i in range(0, total_chunks, batch_size):
                batch_chunks = chunks[i:i + batch_size]
                batch_num = i // batch_size + 1
                total_batches = (total_chunks + batch_size - 1) // batch_size

                progress = 20 + int(((i + len(batch_chunks)) / total_chunks) * 40)
                self.task_manager.update_task(
                    task_id, progress=progress,
                    message=f"发送第 {batch_num}/{total_batches} 批数据 ({len(batch_chunks)} 块)..."
                )

                episodes = [EpisodeData(data=chunk, type="text") for chunk in batch_chunks]
                try:
                    batch_result = self._zep_client.graph.add_batch(graph_id=graph_id, episodes=episodes)
                    if batch_result and isinstance(batch_result, list):
                        for ep in batch_result:
                            ep_uuid = getattr(ep, 'uuid_', None) or getattr(ep, 'uuid', None)
                            if ep_uuid:
                                episode_uuids.append(ep_uuid)
                    time.sleep(1)
                except Exception as e:
                    logger.warning(f"批次 {batch_num} 发送失败: {e}")
                    raise

            # 5. 等待 Zep 处理完成 + 并发预生成 Agent Profile（流水线）
            self.task_manager.update_task(task_id, progress=60, message="等待 Zep 处理数据（同步预生成 Profile）...")
            
            # 实时更新回调：接收进度和增量图谱数据
            def progress_callback_with_data(msg, prog, incremental_data=None):
                progress = 60 + int(prog * 30)
                update_data = {
                    "progress": progress,
                    "message": msg
                }
                # 如果有增量数据，存入 progress_detail 供前端实时获取
                if incremental_data:
                    update_data["progress_detail"] = {
                        "incremental_graph": incremental_data,
                        "nodes_count": incremental_data.get("node_count", 0),
                        "edges_count": incremental_data.get("edge_count", 0)
                    }
                self.task_manager.update_task(task_id, **update_data)
            
            self._zep_wait_for_episodes(
                episode_uuids,
                progress_callback_with_data,
                graph_id=graph_id,
                requirement=graph_name,
            )

            # 6. 获取结果
            self.task_manager.update_task(task_id, progress=90, message="读取图谱数据...")
            info = self._get_graph_info_zep(graph_id)

            self.task_manager.update_task(
                task_id,
                status=TaskStatus.COMPLETED,
                progress=100,
                result=info.to_dict() if info else {"graph_id": graph_id},
                message=f"图谱构建完成 (Zep): {info.node_count}个节点, {info.edge_count}条边" if info else "图谱构建完成"
            )
            logger.info(f"Zep 图谱构建完成: {graph_id}")

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Zep 图谱构建失败: {error_msg}", exc_info=True)
            import traceback as tb
            tb.print_exc()
            # 确保错误信息是字符串类型
            self.task_manager.fail_task(task_id, error_msg)

    def _zep_create_graph(self, graph_name: str) -> str:
        """创建 Zep 图谱"""
        graph_id = f"traceback_{uuid.uuid4().hex[:12]}"
        self._zep_client.graph.create(graph_id=graph_id, name=graph_name)
        logger.info(f"Zep 图谱已创建: {graph_id}")
        return graph_id

    def _zep_set_ontology(self, graph_id: str, ontology: Dict[str, Any]):
        """设置 Zep 图谱本体"""
        from typing import Optional as Opt
        from pydantic import Field
        from zep_cloud.external_clients.ontology import EntityModel, EntityText, EdgeModel

        warnings.filterwarnings('ignore', category=UserWarning, module='pydantic')

        RESERVED_NAMES = {'uuid', 'name', 'group_id', 'name_embedding', 'summary', 'created_at'}

        def safe_attr_name(attr_name: str) -> str:
            if attr_name.lower() in RESERVED_NAMES:
                return f"entity_{attr_name}"
            return attr_name

        # 动态创建实体类型
        entity_types = {}
        for entity_def in ontology.get("entity_types", []):
            name = entity_def["name"]
            description = entity_def.get("description", f"A {name} entity.")
            attrs = {"__doc__": description}
            annotations = {}
            # 限制属性数量不超过10个，以符合Zep Cloud API限制
            attributes = entity_def.get("attributes", [])[:10]
            for attr_def in attributes:
                attr_name = safe_attr_name(attr_def["name"])
                attr_desc = attr_def.get("description", attr_name)
                attrs[attr_name] = Field(description=attr_desc, default=None)
                annotations[attr_name] = Opt[EntityText]
            attrs["__annotations__"] = annotations
            entity_class = type(name, (EntityModel,), attrs)
            entity_class.__doc__ = description
            entity_types[name] = entity_class

        # 动态创建边类型
        edge_definitions = {}
        for edge_def in ontology.get("edge_types", []):
            name = edge_def["name"]
            description = edge_def.get("description", f"A {name} relationship.")
            source_targets = []
            for st in edge_def.get("source_targets", []):
                source_type = st.get("source", "")
                target_type = st.get("target", "")
                if source_type in entity_types and target_type in entity_types:
                    from zep_cloud import EntityEdgeSourceTarget
                    source_targets.append(EntityEdgeSourceTarget(
                        source=source_type,
                        target=target_type
                    ))
            if source_targets:
                edge_class = type(name, (EdgeModel,), {"__doc__": description})
                edge_class.__doc__ = description
                edge_definitions[name] = {"model": edge_class, "source_targets": source_targets}

        # 应用本体 — 使用 set_ontology API（Zep SDK v3）
        entities_dict = {ename: eclass for ename, eclass in entity_types.items()}
        edges_dict = {}
        for ename, edef in edge_definitions.items():
            edges_dict[ename] = (edef["model"], edef["source_targets"])

        self._zep_client.graph.set_ontology(
            entities=entities_dict,
            edges=edges_dict if edges_dict else None,
            graph_ids=[graph_id]
        )
        logger.info(f"Zep 本体已设置: {len(entity_types)} 实体类型, {len(edge_definitions)} 关系类型")

    def _zep_wait_for_episodes(
        self, episode_uuids: List[str],
        progress_callback: Optional[Callable] = None,
        timeout: int = 600,
        graph_id: str = "",
        requirement: str = "",
    ):
        """等待所有 episode 处理完成，同时并发预生成 Agent Profile"""
        if not episode_uuids:
            if progress_callback:
                progress_callback("无需等待", 1.0)
            return

        start_time = time.time()
        pending = set(episode_uuids)
        completed = 0
        total = len(episode_uuids)

        # ── 流水线：边等 Zep 边生成 Profile ──
        seen_node_names = set()       # 已提交生成的节点名
        profile_futures = {}          # future -> node_name
        profiles_done = []            # 已完成的 profile
        config_agents_done = []
        llm_for_profiles = LLMClient()  # 用 default 模型生成 profile（fast 模型安全策略过严）
        profile_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="profile_gen")

        # 初始化缓存
        if graph_id:
            with _prebuilt_profiles_lock:
                _prebuilt_profiles[graph_id] = {
                    "profiles": [], "config_agents": [], "status": "building"
                }

        def _submit_new_nodes():
            """拉取 Zep 新增节点，提交 profile 生成任务"""
            if not graph_id:
                return
            try:
                from ..utils.zep_paging import fetch_all_nodes
                current_nodes = fetch_all_nodes(self._zep_client, graph_id)
                for zn in current_nodes:
                    name = getattr(zn, 'name', '') or ''
                    if not name or name in seen_node_names:
                        continue
                    seen_node_names.add(name)
                    summary = getattr(zn, 'summary', '') or ''
                    raw_labels = getattr(zn, 'labels', None) or getattr(zn, 'entity_type', None)
                    if isinstance(raw_labels, str):
                        entity_type = raw_labels
                    elif isinstance(raw_labels, list) and raw_labels:
                        entity_type = raw_labels[0]
                    else:
                        entity_type = "Entity"
                    node_id = getattr(zn, 'uuid_', None) or getattr(zn, 'uuid', None) or ''

                    fut = profile_executor.submit(
                        _generate_single_profile,
                        name, entity_type, summary, requirement, llm_for_profiles
                    )
                    profile_futures[fut] = (name, entity_type, node_id)
            except Exception as e:
                logger.debug(f"拉取新节点时出错（非致命）: {e}")

        def _collect_finished_profiles():
            """收集已完成的 profile 生成结果"""
            done_futs = [f for f in profile_futures if f.done()]
            for fut in done_futs:
                name, entity_type, node_id = profile_futures.pop(fut)
                try:
                    result = fut.result()
                    if result:
                        result['node_id'] = node_id
                        profiles_done.append(result)
                        config_agents_done.append({
                            "agent_id": node_id or f"agent_{len(config_agents_done)}",
                            "username": result.get('username', name),
                            "real_name": name,
                            "entity_type": entity_type,
                            "stance": result.get('stance', 'neutral'),
                            "posts_per_hour": result.get('posts_per_hour', 2),
                            "replies_per_hour": result.get('replies_per_hour', 3),
                            "active_hours": result.get('active_hours', [9, 10, 11, 14, 15, 16, 20, 21]),
                        })
                except Exception as e:
                    logger.warning(f"profile 结果收集失败 ({name}): {e}")

        # ── 主轮询循环 ──
        poll_count = 0
        last_incremental_update = 0  # 上次增量更新节点数
        while pending and (time.time() - start_time) < timeout:
            for ep_uuid in list(pending):
                try:
                    ep = self._zep_client.graph.episode.get(ep_uuid)
                    if getattr(ep, 'processed', False):
                        pending.discard(ep_uuid)
                        completed += 1
                except Exception:
                    pass

            # 每 3 轮获取一次增量图谱数据（实时可视化）
            poll_count += 1
            incremental_data = None
            if poll_count % 3 == 0 and graph_id:
                try:
                    from ..utils.zep_paging import fetch_all_nodes, fetch_all_edges
                    nodes = fetch_all_nodes(self._zep_client, graph_id)
                    edges = fetch_all_edges(self._zep_client, graph_id)
                    
                    # 只有节点数变化时才更新
                    if len(nodes) > last_incremental_update:
                        last_incremental_update = len(nodes)
                        
                        # 转换为前端格式
                        nodes_data = []
                        for node in nodes:
                            nodes_data.append({
                                "uuid": node.uuid_,
                                "name": node.name,
                                "labels": node.labels or [],
                                "summary": node.summary or "",
                            })
                        
                        edges_data = []
                        for edge in edges:
                            # 获取边的 UUID
                            edge_uuid = getattr(edge, 'uuid_', None) or getattr(edge, 'uuid', '')
                            # 获取源和目标节点 UUID（使用正确的属性名）
                            source_uuid = getattr(edge, 'source_node_uuid', None) or getattr(edge, 'source', '')
                            target_uuid = getattr(edge, 'target_node_uuid', None) or getattr(edge, 'target', '')
                            # 获取关系类型
                            rel_type = getattr(edge, 'relation_type', None) or getattr(edge, 'fact_type', 'RELATED_TO')
                            
                            edges_data.append({
                                "uuid": edge_uuid,
                                "source_node_uuid": source_uuid,
                                "target_node_uuid": target_uuid,
                                "fact_type": rel_type,
                                "name": rel_type,
                                "summary": getattr(edge, 'summary', '') or "",
                            })
                        
                        incremental_data = {
                            "nodes": nodes_data,
                            "edges": edges_data,
                            "node_count": len(nodes),
                            "edge_count": len(edges)
                        }
                        logger.info(f"增量更新: {len(nodes)} 节点, {len(edges)} 边")
                except Exception as e:
                    logger.warning(f"增量数据获取失败: {e}")

            if progress_callback:
                prog = completed / total if total > 0 else 1.0
                profile_msg = f"（已预生成 {len(profiles_done)} 个 Profile）" if profiles_done else ""
                # 传递增量数据用于实时可视化
                progress_callback(
                    f"Zep 处理中: {completed}/{total} 完成 {profile_msg}", 
                    prog,
                    incremental_data  # 增量图谱数据
                )

            # 每 2 轮拉一次新节点（避免太频繁）
            if poll_count % 2 == 0:
                _submit_new_nodes()
            _collect_finished_profiles()

            if pending:
                time.sleep(3)

        # ── 最后一次拉取 + 等待所有 profile 完成 ──
        _submit_new_nodes()
        # 等待剩余 profile futures 完成（最多 180s，容忍超时）
        remaining_futs = list(profile_futures.keys())
        if remaining_futs:
            logger.info(f"等待剩余 {len(remaining_futs)} 个 profile 生成完成...")
            try:
                for fut in as_completed(remaining_futs, timeout=180):
                    pass
            except TimeoutError:
                logger.warning(f"部分 profile 生成超时，已完成 {len(profiles_done)} 个，跳过剩余")
            _collect_finished_profiles()

        profile_executor.shutdown(wait=False)

        # 写入全局缓存
        if graph_id and profiles_done:
            with _prebuilt_profiles_lock:
                _prebuilt_profiles[graph_id] = {
                    "profiles": profiles_done,
                    "config_agents": config_agents_done,
                    "status": "done"
                }
            logger.info(f"流水线预生成完成: {len(profiles_done)} 个 Profile 已缓存 (graph={graph_id})")

        if pending:
            logger.warning(f"Zep 处理超时，{len(pending)} 个 episode 未完成")

    def _get_graph_info_zep(self, graph_id: str) -> Optional[GraphInfo]:
        """从 Zep 获取图谱信息"""
        try:
            from ..utils.zep_paging import fetch_all_nodes, fetch_all_edges
            nodes = fetch_all_nodes(self._zep_client, graph_id)
            edges = fetch_all_edges(self._zep_client, graph_id)

            entity_types = set()
            for node in nodes:
                if node.labels:
                    for label in node.labels:
                        if label not in ["Entity", "Node"]:
                            entity_types.add(label)

            return GraphInfo(
                graph_id=graph_id,
                node_count=len(nodes),
                edge_count=len(edges),
                entity_types=list(entity_types)
            )
        except Exception as e:
            logger.error(f"获取 Zep 图谱信息失败: {e}")
            return None

    def _get_graph_data_zep(self, graph_id: str) -> Dict[str, Any]:
        """从 Zep 获取完整图谱数据"""
        try:
            from ..utils.zep_paging import fetch_all_nodes, fetch_all_edges
            from zep_cloud.core import ApiError
            nodes = fetch_all_nodes(self._zep_client, graph_id)
            edges = fetch_all_edges(self._zep_client, graph_id)

            node_map = {}
            for node in nodes:
                node_map[node.uuid_] = node.name or ""

            nodes_data = []
            for node in nodes:
                created_at = getattr(node, 'created_at', None)
                if created_at:
                    created_at = str(created_at)
                nodes_data.append({
                    "uuid": node.uuid_,
                    "name": node.name,
                    "labels": node.labels or [],
                    "summary": node.summary or "",
                    "attributes": node.attributes or {},
                    "created_at": created_at,
                })

            edges_data = []
            for edge in edges:
                source_uuid = getattr(edge, 'source_node_uuid', None) or ""
                target_uuid = getattr(edge, 'target_node_uuid', None) or ""
                edges_data.append({
                    "uuid": getattr(edge, 'uuid_', '') or getattr(edge, 'uuid', ''),
                    "name": edge.name or "",
                    "fact": edge.fact or "",
                    "source_node_uuid": source_uuid,
                    "target_node_uuid": target_uuid,
                    "source_name": node_map.get(source_uuid, ""),
                    "target_name": node_map.get(target_uuid, ""),
                    "attributes": edge.attributes or {},
                })

            return {"nodes": nodes_data, "edges": edges_data}
        except ApiError as e:
            if e.status_code == 429:
                logger.warning(f"Zep 429 速率限制，graph_id={graph_id}")
                return {"error": "rate_limit", "message": str(e), "nodes": [], "edges": []}
            else:
                logger.error(f"获取 Zep 图谱数据失败: {e}")
                return {"nodes": [], "edges": []}
        except Exception as e:
            logger.error(f"获取 Zep 图谱数据失败: {e}")
            return {"nodes": [], "edges": []}

    # ================================================================
    # 本地 LLM 降级模式
    # ================================================================

    def _build_graph_local_worker(
        self, task_id: str, text: str, ontology: Dict[str, Any],
        graph_name: str, chunk_size: int, chunk_overlap: int, batch_size: int
    ):
        """本地 LLM 图谱构建（降级模式，并发抽取）"""
        try:
            self.task_manager.update_task(task_id, status=TaskStatus.PROCESSING)

            # 1. 创建图谱
            graph_id = f"graph_{uuid.uuid4().hex[:12]}"
            logger.info(f"创建本地图谱: {graph_id} ({graph_name})")

            # 2. 切分文本
            processor = TextProcessor()
            chunks = processor.split_text(text, chunk_size=chunk_size, overlap=chunk_overlap)
            total_chunks = len(chunks)
            logger.info(f"文本切分为 {total_chunks} 个块")

            # 3. 准备本体类型描述
            entity_types_desc = "\n".join([
                f"- {et['name']}: {et.get('description', '')}"
                for et in ontology.get("entity_types", [])
            ])
            edge_types_desc = "\n".join([
                f"- {et['name']}: {et.get('description', '')}"
                for et in ontology.get("edge_types", [])
            ])

            # 4. 提取实体和关系
            all_entities = {}
            processed = 0
            
            # 获取当前图谱数据的辅助函数（用于实时更新）
            def get_incremental_data():
                try:
                    graph_data = self.graph_store.get_graph_data(graph_id)
                    return {
                        "nodes": graph_data.get("nodes", []),
                        "edges": graph_data.get("edges", []),
                        "node_count": len(graph_data.get("nodes", [])),
                        "edge_count": len(graph_data.get("edges", []))
                    }
                except Exception:
                    return None

            if self.llm:
                # 使用 LLM 提取
                def _extract_chunk(idx_chunk):
                    idx, chunk = idx_chunk
                    prompt = EXTRACT_PROMPT.format(
                        entity_types=entity_types_desc,
                        edge_types=edge_types_desc,
                        text_chunk=chunk
                    )
                    return idx, self.llm.chat_json(
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.2,
                        max_tokens=4096
                    )

                with ThreadPoolExecutor(max_workers=batch_size) as executor:
                    for batch_start in range(0, total_chunks, batch_size):
                        batch = list(enumerate(chunks[batch_start:batch_start + batch_size], start=batch_start))
                        futures = {executor.submit(_extract_chunk, item): item[0] for item in batch}

                        for future in as_completed(futures):
                            chunk_idx = futures[future]
                            try:
                                idx, result = future.result()

                                for entity in result.get("entities", []):
                                    name = entity.get("name", "").strip()
                                    if not name:
                                        continue
                                    if name not in all_entities:
                                        node = self.graph_store.add_node(
                                            graph_id=graph_id, name=name,
                                            labels=[entity.get("type", "Entity")],
                                            summary=entity.get("summary", ""),
                                            attributes=entity.get("attributes", {})
                                        )
                                        all_entities[name] = node.uuid
                                    else:
                                        existing = self.graph_store.get_node(graph_id, all_entities[name])
                                        if existing:
                                            new_summary = existing.summary
                                            if entity["summary"] not in new_summary:
                                                new_summary += f"; {entity['summary']}"
                                            self.graph_store.update_node(
                                                graph_id, all_entities[name], summary=new_summary
                                            )

                                for rel in result.get("relations", []):
                                    source_name = rel.get("source", "").strip()
                                    target_name = rel.get("target", "").strip()
                                    if not source_name or not target_name:
                                        continue
                                    if source_name not in all_entities:
                                        node = self.graph_store.add_node(
                                            graph_id=graph_id, name=source_name,
                                            labels=["Entity"], summary=""
                                        )
                                        all_entities[source_name] = node.uuid
                                    if target_name not in all_entities:
                                        node = self.graph_store.add_node(
                                            graph_id=graph_id, name=target_name,
                                            labels=["Entity"], summary=""
                                        )
                                        all_entities[target_name] = node.uuid
                                    self.graph_store.add_edge(
                                        graph_id=graph_id,
                                        name=rel.get("type", "RELATED_TO"),
                                        fact=rel.get("fact", ""),
                                        source_node_uuid=all_entities[source_name],
                                        target_node_uuid=all_entities[target_name],
                                        attributes=rel.get("attributes", {})
                                    )

                                processed += 1
                                progress = int((processed / total_chunks) * 100)
                                
                                # 获取增量数据用于实时更新
                                incremental_data = get_incremental_data()
                                message = f"已处理 {processed}/{total_chunks} 个文本块"
                                progress_detail = None
                                if incremental_data:
                                    progress_detail = {
                                        "incremental_graph": incremental_data,
                                        "nodes_count": incremental_data["node_count"],
                                        "edges_count": incremental_data["edge_count"]
                                    }
                                
                                self.task_manager.update_task(
                                    task_id, 
                                    progress=progress, 
                                    message=message,
                                    progress_detail=progress_detail
                                )
                                logger.info(f"块 {idx+1}/{total_chunks} 处理完成")

                            except Exception as e:
                                logger.warning(f"块 {chunk_idx+1} 处理失败: {e}")
                                continue
            else:
                # 无 LLM 降级模式：基于规则的简单提取
                logger.info("使用无 LLM 降级模式，基于规则提取实体和关系")
                
                # 从本体中获取实体类型
                entity_types = [et["name"] for et in ontology.get("entity_types", [])]
                edge_types = [et["name"] for et in ontology.get("edge_types", [])]
                
                # 简单的基于关键词的提取
                for idx, chunk in enumerate(chunks):
                    try:
                        # 提取句子
                        sentences = processor.split_into_sentences(chunk)
                        
                        # 简单处理：每个句子作为一个实体
                        for i, sentence in enumerate(sentences):
                            sentence = sentence.strip()
                            if len(sentence) < 5:
                                continue
                            
                            # 创建句子实体
                            entity_name = f"Sentence_{idx}_{i}"
                            if entity_name not in all_entities:
                                node = self.graph_store.add_node(
                                    graph_id=graph_id, name=entity_name,
                                    labels=["Sentence"],
                                    summary=sentence[:100],
                                    attributes={"content": sentence}
                                )
                                all_entities[entity_name] = node.uuid
                        
                        processed += 1
                        progress = int((processed / total_chunks) * 100)
                        
                        # 获取增量数据用于实时更新
                        incremental_data = get_incremental_data()
                        message = f"已处理 {processed}/{total_chunks} 个文本块（无 LLM 模式）"
                        progress_detail = None
                        if incremental_data:
                            progress_detail = {
                                "incremental_graph": incremental_data,
                                "nodes_count": incremental_data["node_count"],
                                "edges_count": incremental_data["edge_count"]
                            }
                        
                        self.task_manager.update_task(
                            task_id, 
                            progress=progress, 
                            message=message,
                            progress_detail=progress_detail
                        )
                        logger.info(f"块 {idx+1}/{total_chunks} 处理完成（无 LLM 模式）")
                        
                    except Exception as e:
                        logger.warning(f"块 {idx+1} 处理失败: {e}")
                        continue

            # 5. 完成
            stats = self.graph_store.get_stats(graph_id)
            self.task_manager.update_task(
                task_id,
                status=TaskStatus.COMPLETED,
                progress=100,
                result={
                    "graph_id": graph_id,
                    "node_count": stats["node_count"],
                    "edge_count": stats["edge_count"],
                    "entity_types": list(stats["node_types"].keys()),
                },
                message=f"图谱构建完成 (本地): {stats['node_count']}个节点, {stats['edge_count']}条边"
            )
            logger.info(f"本地图谱构建完成: {graph_id}")

        except Exception as e:
            error_msg = str(e)
            logger.error(f"本地图谱构建失败: {error_msg}", exc_info=True)
            # 确保错误信息是字符串类型
            self.task_manager.fail_task(task_id, error_msg)

    def _get_graph_info_local(self, graph_id: str) -> Optional[GraphInfo]:
        """从本地获取图谱信息"""
        if not self.graph_store.graph_exists(graph_id):
            return None
        stats = self.graph_store.get_stats(graph_id)
        return GraphInfo(
            graph_id=graph_id,
            node_count=stats["node_count"],
            edge_count=stats["edge_count"],
            entity_types=list(stats["node_types"].keys())
        )

    def _get_graph_data_local(self, graph_id: str) -> Dict[str, Any]:
        """从本地获取完整图谱数据"""
        return self.graph_store.get_graph_data(graph_id)
