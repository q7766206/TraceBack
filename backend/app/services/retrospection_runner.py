"""
TraceBack 回溯分析运行器 (v4 - 极速深度回溯版)
在后台运行多Agent质证分析流程，记录每个Agent的分析动作

v4 核心改进（目标：2小时→15-20分钟）:
- 搜索从3轮精简为2轮（广度+深度），每轮query数量精简
- URL抓取使用SearchEngine缓存层，避免重复请求
- Phase 2+3 合并：时间线重建与因果推理一次LLM调用完成
- 辩论轮次智能控制：1-2轮（有实质分歧才继续）
- 所有可并行的LLM调用并行化
- 证据质量评分更严格，减少低质量数据进入后续阶段
"""

import os
import json
import time
import uuid
import threading
import concurrent.futures
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime

from ..config import Config
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger
from .agent_profiles import AGENT_PROFILES, get_agent_system_prompt
from .search_engine import SearchEngine
from .local_graph_store import LocalGraphStore
from .retrospection_manager import (
    RetrospectionManager, AnalysisPhase, AnalysisStatus,
    AgentAction, DebateMessage, CausalNode, CausalEdge
)

logger = get_logger('traceback.runner')


class RetrospectionRunner:
    """
    回溯分析运行器 v4
    按阶段执行多Agent深度分析流程（极速版）
    """

    _active_runners: Dict[str, 'RetrospectionRunner'] = {}
    _lock = threading.Lock()

    # 并发参数
    SEARCH_WORKERS = 6       # 搜索并发线程数
    FETCH_WORKERS = 10       # URL抓取并发线程数
    LLM_WORKERS = 4          # LLM调用并发线程数

    def __init__(self, analysis_id: str, graph_id: str):
        self.analysis_id = analysis_id
        self.graph_id = graph_id
        self.manager = RetrospectionManager()
        self.llm = LLMClient(preset="reasoning")
        self.search_engine = SearchEngine()
        self.graph_store = LocalGraphStore()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._progress_callback: Optional[Callable] = None
        self._phase_start_time: float = 0

    def start(self, callback: Callable = None):
        """启动分析（后台线程）"""
        self._progress_callback = callback
        self._thread = threading.Thread(
            target=self._run_analysis,
            daemon=True,
            name=f"traceback-{self.analysis_id}"
        )
        with self._lock:
            self._active_runners[self.analysis_id] = self
        self._thread.start()
        logger.info(f"回溯分析启动: {self.analysis_id}")

    def stop(self):
        """停止分析"""
        self._stop_event.set()
        logger.info(f"回溯分析停止请求: {self.analysis_id}")

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @classmethod
    def get_runner(cls, analysis_id: str) -> Optional['RetrospectionRunner']:
        with cls._lock:
            return cls._active_runners.get(analysis_id)

    @classmethod
    def register_cleanup(cls):
        """注册进程清理"""
        import atexit
        def cleanup():
            with cls._lock:
                for runner in cls._active_runners.values():
                    runner.stop()
        atexit.register(cleanup)

    # ═══════════════════════════════════════════════════════════
    # 核心分析流程（v4 精简版：6阶段→5阶段）
    # ═══════════════════════════════════════════════════════════

    def _run_analysis(self):
        """主分析流程"""
        total_start = time.time()
        try:
            state = self.manager.get_analysis(self.analysis_id)
            if not state:
                logger.error(f"分析不存在: {self.analysis_id}")
                return

            # v4: Phase 2+3 合并为 TIMELINE_CAUSAL
            phases = [
                (AnalysisPhase.DATA_COLLECTION, self._run_data_collection),
                (AnalysisPhase.TIMELINE_BUILDING, self._run_timeline_and_causal),  # 合并时间线+因果
                (AnalysisPhase.EVIDENCE_AUDIT, self._run_evidence_audit),
                (AnalysisPhase.DEBATE, self._run_debate),
                (AnalysisPhase.CONSENSUS, self._run_consensus),
            ]

            for phase, handler in phases:
                if self._stop_event.is_set():
                    logger.info(f"[{self.analysis_id}] 分析被用户停止")
                    self.manager.update_status(self.analysis_id, AnalysisStatus.STOPPED)
                    return

                self._phase_start_time = time.time()
                self.manager.update_phase(self.analysis_id, phase)
                state = self.manager.get_analysis(self.analysis_id)

                try:
                    handler(state)
                    elapsed = time.time() - self._phase_start_time
                    logger.info(f"[{self.analysis_id}] {phase.value} 完成，耗时 {elapsed:.1f}s")
                except Exception as e:
                    logger.error(f"[{self.analysis_id}] {phase.value} 失败: {str(e)}", exc_info=True)
                    self.manager.update_status(self.analysis_id, AnalysisStatus.FAILED, error=str(e))
                    return

            # 完成
            self.manager.update_phase(self.analysis_id, AnalysisPhase.COMPLETED)
            self.manager.update_status(self.analysis_id, AnalysisStatus.COMPLETED)
            total_elapsed = time.time() - total_start
            logger.info(f"[{self.analysis_id}] 全部分析完成！总耗时 {total_elapsed:.0f}s ({total_elapsed/60:.1f}分钟)")

        except Exception as e:
            logger.error(f"[{self.analysis_id}] 分析异常: {str(e)}", exc_info=True)
            try:
                self.manager.update_status(self.analysis_id, AnalysisStatus.FAILED, error=str(e))
            except:
                pass
        finally:
            with self._lock:
                self._active_runners.pop(self.analysis_id, None)

    # ═══════════════════════════════════════════════════════════
    # 工具方法
    # ═══════════════════════════════════════════════════════════

    def _call_agent(self, agent_id: str, user_message: str, context: str = "") -> str:
        """调用Agent获取文本响应"""
        system_prompt = get_agent_system_prompt(agent_id)
        if not system_prompt:
            raise ValueError(f"未知的Agent: {agent_id}")

        messages = [{"role": "system", "content": system_prompt}]
        if context:
            messages.append({"role": "user", "content": f"## 当前分析上下文\n{context}"})
            messages.append({"role": "assistant", "content": "已了解上下文。"})
        messages.append({"role": "user", "content": user_message})

        response = self.llm.chat(
            messages=messages,
            temperature=0.5,
            max_tokens=4096,
        )
        return response

    def _call_agent_json(self, agent_id: str, user_message: str, context: str = "") -> Dict:
        """调用Agent并获取JSON结构化输出"""
        system_prompt = get_agent_system_prompt(agent_id)
        if not system_prompt:
            raise ValueError(f"未知的Agent: {agent_id}")

        full_prompt = system_prompt + "\n\n**重要：你必须输出有效的JSON格式数据，不要输出任何其他内容。**"

        messages = [
            {"role": "system", "content": full_prompt},
        ]
        if context:
            messages.append({"role": "user", "content": f"## 当前分析上下文\n{context}"})
            messages.append({"role": "assistant", "content": "已了解上下文。"})
        messages.append({"role": "user", "content": user_message})

        result = self.llm.chat_json(
            messages=messages,
            temperature=0.3,
            max_tokens=8192,
        )
        return result

    def _record_action(self, phase: str, agent_id: str, action_type: str, content: str = "", **kwargs):
        """记录Agent行动"""
        profile = AGENT_PROFILES.get(agent_id)
        if not profile:
            return

        action = AgentAction(
            round_num=kwargs.get("round_num", 0),
            timestamp=datetime.now().isoformat(),
            phase=phase,
            agent_id=agent_id,
            agent_name=profile.name_cn,
            action_type=action_type,
            content=content,
            confidence=kwargs.get("confidence", 0.0),
        )
        self.manager.add_action(self.analysis_id, action)

    def _add_debate_msg(self, agent_id: str, msg_type: str, content: str, round_num: int = 0, **kwargs):
        """添加辩论消息"""
        profile = AGENT_PROFILES.get(agent_id)
        if not profile:
            return

        msg = DebateMessage(
            message_id=f"msg_{uuid.uuid4().hex[:8]}",
            round_num=round_num,
            timestamp=datetime.now().isoformat(),
            agent_id=agent_id,
            agent_name=profile.name_cn,
            agent_icon=profile.icon,
            agent_color=profile.color,
            message_type=msg_type,
            content=content,
            target_message_id=kwargs.get("target_id"),
            evidence_ids=kwargs.get("evidence_ids", []),
            confidence=kwargs.get("confidence", 0.0),
        )
        self.manager.add_debate_message(self.analysis_id, msg)

    def _retrieve_from_graph(self, query: str) -> str:
        """从知识图谱检索相关信息"""
        try:
            result = self.graph_store.search(self.graph_id, query, limit=15)
            if result and result.get("nodes"):
                parts = []
                for node in result["nodes"][:15]:
                    parts.append(f"- {node.get('name', '')}: {node.get('summary', '')[:100]}")
                return "\n".join(parts)
        except Exception as e:
            logger.debug(f"图谱检索失败: {e}")
        return ""

    def _execute_search_batch(self, queries: List[str], max_per_query: int = 8) -> List[Dict]:
        """并发批量搜索"""
        all_results = []
        seen_urls = set()

        def do_search(q):
            try:
                results = self.search_engine.search(q, max_results=max_per_query)
                return [r.to_dict() for r in results]
            except Exception as e:
                logger.warning(f"搜索失败 '{q[:50]}': {e}")
                return []

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.SEARCH_WORKERS) as executor:
            futures = {executor.submit(do_search, q): q for q in queries}
            for future in concurrent.futures.as_completed(futures):
                for r in future.result():
                    if r["url"] not in seen_urls:
                        seen_urls.add(r["url"])
                        all_results.append(r)

        return all_results

    def _fetch_urls_batch(self, results: List[Dict], max_count: int = 12, max_chars: int = 4000) -> List[Dict]:
        """并发批量抓取URL内容（使用SearchEngine缓存）"""
        fetched = []
        fetch_lock = threading.Lock()

        def fetch_one(r):
            url = r.get("url", "")
            content = self.search_engine.fetch_url_content(url, max_chars=max_chars, timeout=8)
            if content and len(content) > 200:
                return {"url": url, "title": r.get("title", ""), "full_text": content}
            return None

        candidates = [r for r in results if r.get("url", "").startswith("http")][:max_count]

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.FETCH_WORKERS) as executor:
            futures = [executor.submit(fetch_one, r) for r in candidates]
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result:
                    with fetch_lock:
                        fetched.append(result)

        return fetched

    def _build_debate_context(self, state) -> str:
        """构建辩论上下文"""
        parts = [f"## 回溯任务\n{state.task_description}"]

        if state.causal_nodes:
            parts.append("\n## 因果节点")
            for n in state.causal_nodes[:20]:
                n_data = n if isinstance(n, dict) else n.__dict__ if hasattr(n, '__dict__') else {}
                name = n_data.get('name', '')
                desc = n_data.get('description', '')
                parts.append(f"- {name}: {desc[:100]}")

        if state.causal_edges:
            parts.append("\n## 因果关系")
            for e in state.causal_edges[:15]:
                e_data = e if isinstance(e, dict) else e.__dict__ if hasattr(e, '__dict__') else {}
                parts.append(f"- {e_data.get('source_name','')} → {e_data.get('target_name','')}: {e_data.get('relation_type','')}")

        if state.debate_messages:
            parts.append("\n## 已有辩论记录")
            for msg in state.debate_messages[-10:]:
                m_data = msg if isinstance(msg, dict) else msg.__dict__ if hasattr(msg, '__dict__') else {}
                parts.append(f"[{m_data.get('agent_name','')}] {m_data.get('content','')[:200]}")

        return "\n".join(parts)

    # ═══════════════════════════════════════════════════════════
    # Phase 1: 高效数据采集（2轮精准搜索）
    # ═══════════════════════════════════════════════════════════

    def _run_data_collection(self, state):
        """Phase 1: 2轮精准数据采集（v4: 从3轮精简为2轮，query数量精简）"""
        logger.info(f"[{self.analysis_id}] Phase 1: 高效数据采集")
        self._record_action("data_collection", "archive_hunter", "SEARCH_DATA", "开始2轮精准搜索")

        all_raw_results = []
        fetched_urls = set()

        # ── 第一轮：广度搜索（并行：LLM生成关键词 + 图谱检索）──
        logger.info(f"[{self.analysis_id}] 第1轮：广度搜索")
        self._record_action("data_collection", "archive_hunter", "SEARCH_DATA", "第1轮：广度搜索")

        keyword_prompt = f"""请根据以下回溯分析任务，生成搜索关键词。

## 回溯任务
{state.task_description}

## 时间范围
开始: {state.time_range_start or '不限'}
结束: {state.time_range_end or '不限'}

请以JSON格式输出：
{{"search_queries": ["中文关键词1", "中文关键词2", ...], "search_queries_en": ["English keyword 1", "English keyword 2", ...]}}

要求：
- 中文关键词4-6个，英文关键词3-5个
- 覆盖：事件名称、关键人物、技术细节、官方调查报告
- 包含精确搜索词（如带引号的专有名词）
- 关键词要精准，避免过于宽泛"""

        # 并行：关键词生成 + 图谱检索
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.LLM_WORKERS) as executor:
            future_kw = executor.submit(self._call_agent_json, "archive_hunter", keyword_prompt)
            future_graph = executor.submit(self._retrieve_from_graph, state.task_description)
            kw_result = future_kw.result()
            graph_context = future_graph.result()

        queries_cn = kw_result.get("search_queries", [state.task_description])
        queries_en = kw_result.get("search_queries_en", [])
        all_queries = queries_cn + queries_en
        if not all_queries:
            all_queries = [state.task_description]

        logger.info(f"[{self.analysis_id}] 第1轮生成 {len(all_queries)} 个搜索关键词")

        # 并发搜索（限制最多10个query）
        round1_results = self._execute_search_batch(all_queries[:10], max_per_query=8)
        all_raw_results.extend(round1_results)

        # 并发抓取前12个URL原文
        logger.info(f"[{self.analysis_id}] 并发抓取关键文章原文...")
        fetched_contents = self._fetch_urls_batch(round1_results, max_count=12, max_chars=4000)
        for fc in fetched_contents:
            fetched_urls.add(fc["url"])
        logger.info(f"[{self.analysis_id}] 成功抓取 {len(fetched_contents)} 篇原文")

        # ── 第二轮：深度补充搜索（基于第一轮发现）──
        if self._stop_event.is_set():
            return

        logger.info(f"[{self.analysis_id}] 第2轮：深度补充搜索")
        self._record_action("data_collection", "archive_hunter", "SEARCH_DATA", "第2轮：深度补充搜索")

        # 基于第一轮结果生成补充关键词
        round1_summary = "\n".join([
            f"- {r['title']}: {r['snippet'][:80]}" for r in round1_results[:15]
        ])
        fetched_summary = "\n".join([
            f"- {fc['title']}: {fc['full_text'][:200]}" for fc in fetched_contents[:8]
        ])

        refine_prompt = f"""基于第一轮搜索结果，请生成补充搜索关键词，聚焦于：
1. 第一轮未覆盖的关键维度
2. 需要深入验证的关键事实
3. 权威来源（官方调查报告、学术论文、政府文件）

## 回溯任务
{state.task_description}

## 第一轮搜索结果摘要
{round1_summary}

## 已抓取文章摘要
{fetched_summary[:2000]}

请以JSON格式输出：
{{"search_queries": ["补充关键词1", "补充关键词2", ...], "search_queries_en": ["English keyword 1", ...]}}

要求：中文3-4个 + 英文2-3个，聚焦权威来源和未覆盖维度"""

        refine_result = self._call_agent_json("archive_hunter", refine_prompt)
        round2_queries = refine_result.get("search_queries", []) + refine_result.get("search_queries_en", [])

        if round2_queries:
            round2_results = self._execute_search_batch(round2_queries[:7], max_per_query=6)
            all_raw_results.extend(round2_results)

            # 补充抓取新URL
            new_results = [r for r in round2_results if r["url"] not in fetched_urls]
            if new_results:
                new_fetched = self._fetch_urls_batch(new_results, max_count=8, max_chars=3000)
                fetched_contents.extend(new_fetched)
                for fc in new_fetched:
                    fetched_urls.add(fc["url"])

        # ── 综合分析：LLM提取结构化证据 ──
        if self._stop_event.is_set():
            return

        logger.info(f"[{self.analysis_id}] 综合分析，提取结构化证据...")

        # 构建证据输入（搜索片段 + 原文摘要 + 图谱上下文）
        evidence_input_parts = []
        for r in all_raw_results[:30]:
            evidence_input_parts.append(f"[搜索] {r['title']}: {r['snippet'][:150]} (来源: {r['url'][:80]})")
        for fc in fetched_contents[:10]:
            evidence_input_parts.append(f"[原文] {fc['title']}: {fc['full_text'][:500]} (来源: {fc['url'][:80]})")
        if graph_context:
            evidence_input_parts.append(f"[知识图谱] {graph_context[:500]}")

        evidence_input = "\n".join(evidence_input_parts)

        analysis_prompt = f"""请分析以下搜索结果和原文数据，提取与回溯任务相关的结构化证据。

## 回溯任务
{state.task_description}

## 时间范围
开始: {state.time_range_start or '不限'}
结束: {state.time_range_end or '不限'}

## 原始数据
{evidence_input[:12000]}

请以JSON格式输出：
{{
    "evidence_items": [
        {{
            "id": "evt_001",
            "content": "证据内容（具体事实，包含数字、时间、人名等）",
            "source": "来源URL或描述",
            "source_type": "official_report/news/academic/witness/government/social_media",
            "timestamp": "事件时间（ISO格式或描述）",
            "credibility_score": 0.85,
            "relevance_score": 0.9,
            "tags": ["关键标签"]
        }}
    ],
    "data_quality_summary": "数据质量总结",
    "coverage_gaps": ["未覆盖的关键维度"]
}}

评分标准：
- credibility: 官方报告0.9+, 权威媒体0.7-0.9, 普通媒体0.5-0.7, 社交媒体0.3-0.5
- relevance: 直接相关0.8+, 间接相关0.5-0.8, 背景信息0.3-0.5
- 只保留credibility>=0.3且relevance>=0.4的证据"""

        evidence_result = self._call_agent_json("archive_hunter", analysis_prompt)
        evidence_items = evidence_result.get("evidence_items", [])

        # 存储到分析状态
        for item in evidence_items:
            self.manager.add_timeline_event(self.analysis_id, item)

        self._record_action(
            "data_collection", "archive_hunter", "ANALYZE_DATA",
            f"**数据采集完成**\n\n"
            f"- 搜索结果: {len(all_raw_results)} 条\n"
            f"- 抓取原文: {len(fetched_contents)} 篇\n"
            f"- 提取证据: {len(evidence_items)} 条\n"
            f"- 数据质量: {evidence_result.get('data_quality_summary', 'N/A')}\n"
            f"- 覆盖缺口: {', '.join(evidence_result.get('coverage_gaps', []))}",
            round_num=0
        )

    # ═══════════════════════════════════════════════════════════
    # Phase 2+3 合并: 时间线重建 + 因果推理（一次LLM调用）
    # ═══════════════════════════════════════════════════════════

    def _run_timeline_and_causal(self, state):
        """Phase 2+3 合并: 时间线重建 + 因果推理（v4: 合并为一次高质量LLM调用）"""
        logger.info(f"[{self.analysis_id}] Phase 2+3: 时间线重建 + 因果推理")

        state = self.manager.get_analysis(self.analysis_id)
        evidence_summary = json.dumps(state.timeline_events[:40], ensure_ascii=False, indent=1)

        prompt = f"""请同时完成两个任务：(A) 时间线重建 和 (B) 因果推理。

## 回溯任务
{state.task_description}

## 时间范围
开始: {state.time_range_start or '不限'}
结束: {state.time_range_end or '不限'}

## 采集到的证据数据
{evidence_summary[:10000]}

请以JSON格式输出：
{{
    "timeline": [
        {{
            "event_name": "事件名称",
            "timestamp": "精确时间（ISO格式或描述）",
            "timestamp_precision": "exact/minute/hour/day/approximate",
            "description": "详细描述（包含具体数字、人名、地点）",
            "importance_score": 0.9,
            "evidence_ids": ["支撑证据ID"],
            "category": "action/decision/discovery/communication/failure"
        }}
    ],
    "key_turning_points": [
        {{
            "timestamp": "时间",
            "description": "转折点描述",
            "impact": "影响说明",
            "before_state": "转折前状态",
            "after_state": "转折后状态"
        }}
    ],
    "timeline_gaps": [
        {{
            "gap_start": "空白开始时间",
            "gap_end": "空白结束时间",
            "significance": "该空白期的重要性说明"
        }}
    ],
    "causal_hypotheses": [
        {{
            "hypothesis_id": "H1",
            "description": "因果假设描述",
            "causal_chain": ["原因A → 结果B → 结果C"],
            "supporting_evidence": ["支撑证据ID或描述"],
            "counter_evidence": ["反对证据"],
            "confidence": 0.75,
            "hypothesis_type": "root_cause/contributing_factor/trigger/enabling_condition"
        }}
    ],
    "root_causes": [
        {{
            "cause": "根本原因描述",
            "confidence": 0.8,
            "evidence_chain": "完整证据链描述",
            "mechanism": "作用机制"
        }}
    ],
    "causal_network": [
        {{
            "source": "原因节点名称",
            "target": "结果节点名称",
            "relation_type": "CAUSED_BY/CONTRIBUTED_TO/TRIGGERED/ENABLED",
            "strength": 0.8,
            "evidence": "支撑证据"
        }}
    ],
    "uncertainty_notes": "不确定性说明"
}}

要求：
1. 时间线按时间顺序排列，标记关键转折点和时间空白
2. 因果推理要区分直接原因、间接原因、根本原因
3. 每个假设必须有证据支撑，标注置信度
4. 诚实声明不确定性和证据不足之处"""

        self._record_action("timeline_building", "chrono_analyst", "BUILD_TIMELINE", "开始时间线重建+因果推理")
        result = self._call_agent_json("chrono_analyst", prompt)

        # 存储时间线节点
        timeline = result.get("timeline", [])
        for event in timeline:
            node = CausalNode(
                node_id=f"evt_{uuid.uuid4().hex[:8]}",
                name=event.get("event_name", ""),
                node_type=event.get("category", "event"),
                timestamp=event.get("timestamp", ""),
                description=event.get("description", ""),
                importance_score=event.get("importance_score", 0.5),
            )
            self.manager.add_causal_node(self.analysis_id, node)

        self._record_action(
            "timeline_building", "chrono_analyst", "BUILD_TIMELINE",
            f"**时间线重建完成**\n\n"
            f"- 事件节点: {len(timeline)} 个\n"
            f"- 关键转折点: {len(result.get('key_turning_points', []))} 个\n"
            f"- 时间空白: {len(result.get('timeline_gaps', []))} 个",
            round_num=0
        )

        # 存储因果关系
        hypotheses = result.get("causal_hypotheses", [])
        causal_network = result.get("causal_network", [])
        root_causes = result.get("root_causes", [])

        for rel in causal_network:
            edge = CausalEdge(
                edge_id=f"edge_{uuid.uuid4().hex[:8]}",
                source=rel.get("source", ""),
                target=rel.get("target", ""),
                causal_type=rel.get("relation_type", "RELATED"),
                strength=rel.get("strength", 0.5),
                label=rel.get("evidence", ""),
            )
            self.manager.add_causal_edge(self.analysis_id, edge)

        chain_strength = sum(h.get("confidence", 0.5) for h in hypotheses) / max(len(hypotheses), 1)

        self._record_action(
            "causal_reasoning", "causal_detective", "PROPOSE_HYPOTHESIS",
            f"**因果推理完成**\n\n"
            f"- 因果假设: {len(hypotheses)} 个\n"
            f"- 因果关系: {len(causal_network)} 条\n"
            f"- 因果链强度: {chain_strength:.2f}\n\n"
            f"**根本原因:**\n" + "\n".join(
                f"🔴 [{rc.get('confidence',0):.0%}] {rc.get('cause','')}"
                for rc in root_causes[:5]
            ) + f"\n\n**不确定性:** {result.get('uncertainty_notes', '无')}",
            round_num=0,
            confidence=chain_strength
        )

    # ═══════════════════════════════════════════════════════════
    # Phase 4: 严格证据审计
    # ═══════════════════════════════════════════════════════════

    def _run_evidence_audit(self, state):
        """Phase 4: 严格证据审计"""
        logger.info(f"[{self.analysis_id}] Phase 4: 严格证据审计")

        state = self.manager.get_analysis(self.analysis_id)
        evidence_summary = json.dumps(state.timeline_events[:30], ensure_ascii=False, indent=1)

        nodes_data = []
        for n in state.causal_nodes[:20]:
            n_dict = n if isinstance(n, dict) else n.__dict__ if hasattr(n, '__dict__') else {}
            nodes_data.append(n_dict)

        edges_data = []
        for e in state.causal_edges[:15]:
            e_dict = e if isinstance(e, dict) else e.__dict__ if hasattr(e, '__dict__') else {}
            edges_data.append(e_dict)

        prompt = f"""请对以下回溯分析的证据链进行严格审计。

## 回溯任务
{state.task_description}

## 证据数据
{evidence_summary[:6000]}

## 因果节点
{json.dumps(nodes_data, ensure_ascii=False, indent=1)[:3000]}

## 因果关系
{json.dumps(edges_data, ensure_ascii=False, indent=1)[:2000]}

请完成以下严格审计：
1. 逐条评估每条证据的可靠性（权威性、时效性、一致性、独立性、可验证性）
2. 检查每个因果假设的证据链是否完整——是否存在"跳跃推理"
3. 识别证据之间的矛盾——同一事实的不同说法
4. 检查是否存在循环论证
5. 评估整体证据质量——有多少是一手来源vs二手转述
6. 计算严格的置信度评分

评分标准（严格）：
- 95%+: 多个独立权威来源交叉验证，无矛盾，证据链完整
- 80-95%: 主要事实有多源验证，少量次要细节未验证
- 60-80%: 核心事实有来源支撑但交叉验证不足
- 40-60%: 部分事实有来源，但存在矛盾或证据链断裂
- <40%: 证据严重不足或存在重大矛盾

请以JSON格式输出：
{{
    "evidence_ratings": [
        {{
            "evidence_id": "证据ID",
            "reliability_score": 0.8,
            "issues": ["问题1"],
            "source_type": "primary/secondary/tertiary"
        }}
    ],
    "chain_integrity": [
        {{
            "hypothesis": "假设描述",
            "chain_complete": true,
            "gaps": ["缺口描述"],
            "jump_reasoning": false
        }}
    ],
    "contradictions": [
        {{
            "fact": "矛盾事实",
            "source_a": "来源A说法",
            "source_b": "来源B说法",
            "resolution": "建议解决方式"
        }}
    ],
    "overall_confidence": 0.72,
    "confidence_breakdown": {{
        "data_sufficiency": 0.75,
        "source_authority": 0.80,
        "cross_validation": 0.65,
        "chain_integrity": 0.70
    }},
    "audit_summary": "审计总结"
}}"""

        self._record_action("evidence_audit", "evidence_auditor", "AUDIT_EVIDENCE", "开始严格证据审计")
        result = self._call_agent_json("evidence_auditor", prompt)

        overall_confidence = result.get("overall_confidence", 0.5)
        self.manager.update_confidence(self.analysis_id, overall_confidence)

        self._record_action(
            "evidence_audit", "evidence_auditor", "AUDIT_EVIDENCE",
            f"**证据审计完成**\n\n"
            f"- 整体置信度: {overall_confidence:.0%}\n"
            f"- 矛盾点: {len(result.get('contradictions', []))} 个\n"
            f"- 审计总结: {result.get('audit_summary', 'N/A')}\n\n"
            f"**置信度分解:**\n"
            f"  数据充分性: {result.get('confidence_breakdown', {}).get('data_sufficiency', 'N/A')}\n"
            f"  来源权威性: {result.get('confidence_breakdown', {}).get('source_authority', 'N/A')}\n"
            f"  交叉验证: {result.get('confidence_breakdown', {}).get('cross_validation', 'N/A')}\n"
            f"  证据链完整性: {result.get('confidence_breakdown', {}).get('chain_integrity', 'N/A')}",
            round_num=0,
            confidence=overall_confidence
        )

    # ═══════════════════════════════════════════════════════════
    # Phase 5: 高效质证辩论（v4: 智能轮次控制，1-2轮）
    # ═══════════════════════════════════════════════════════════

    def _run_debate(self, state):
        """Phase 5: 高效质证辩论（v4: 1-2轮，有实质分歧才继续第2轮）"""
        logger.info(f"[{self.analysis_id}] Phase 5: 高效质证辩论")

        state = self.manager.get_analysis(self.analysis_id)
        max_rounds = min(state.max_debate_rounds or 2, 3)  # v4: 默认2轮，最多3轮

        for round_num in range(1, max_rounds + 1):
            if self._stop_event.is_set():
                return

            logger.info(f"[{self.analysis_id}] 辩论第 {round_num}/{max_rounds} 轮")
            state = self.manager.get_analysis(self.analysis_id)
            context = self._build_debate_context(state)

            # v4: 质疑+回应+裁判 并行准备质疑和回应的上下文
            # 5a. 魔鬼代言人提出质疑
            round1_focus = (
                "- 质疑根本原因的认定是否正确，是否存在替代解释\n"
                "- 质疑证据链的薄弱环节，寻找反例\n"
                "- 检查认知偏见（确认偏见、幸存者偏见、后见之明偏见）"
            )
            round2_focus = (
                "- 针对上一轮未解决的分歧深入质疑\n"
                "- 提出最终质疑和替代假设"
            )
            focus_text = round1_focus if round_num == 1 else round2_focus
            challenge_prompt = f"""这是第 {round_num}/{max_rounds} 轮质证辩论。请对当前的分析结论进行系统性质疑。

{context}

第 {round_num} 轮质疑重点：
{focus_text}

请以JSON格式输出：
{{
    "challenges": [
        {{
            "target": "被质疑的结论/假设",
            "challenge_type": "alternative_explanation/missing_evidence/logical_flaw/bias_detection/contradiction",
            "description": "质疑的详细描述",
            "counter_evidence": "反证或反例",
            "severity": "critical/major/minor",
            "alternative_explanation": "替代解释（如果有）"
        }}
    ],
    "bias_alerts": [
        {{
            "bias_type": "confirmation_bias/survivorship_bias/hindsight_bias/anchoring_bias",
            "description": "偏见描述",
            "affected_conclusions": ["受影响的结论"]
        }}
    ],
    "unresolved_questions": ["未解决的关键问题"]
}}"""

            challenge_result = self._call_agent_json("devils_advocate", challenge_prompt, context)
            challenges = challenge_result.get("challenges", [])
            bias_alerts = challenge_result.get("bias_alerts", [])

            for ch in challenges[:5]:
                self._add_debate_msg(
                    "devils_advocate", "challenge",
                    f"**[{ch.get('severity','').upper()}] {ch.get('challenge_type','')}**\n\n"
                    f"质疑目标: {ch.get('target','')}\n\n"
                    f"{ch.get('description','')}\n\n"
                    f"反证: {ch.get('counter_evidence','无')}\n"
                    f"替代解释: {ch.get('alternative_explanation','无')}",
                    round_num=round_num
                )

            for ba in bias_alerts[:3]:
                self._add_debate_msg(
                    "devils_advocate", "bias_alert",
                    f"⚠️ **认知偏见警告: {ba.get('bias_type','')}**\n\n{ba.get('description','')}",
                    round_num=round_num
                )

            # 5b. 因果侦探回应质疑
            if not challenges:
                logger.info(f"[{self.analysis_id}] 无实质性质疑，跳过回应")
                break

            challenge_text = "\n".join([
                f"[{ch.get('severity','')}] {ch.get('description','')}" for ch in challenges[:5]
            ])

            response_prompt = f"""魔鬼代言人提出了以下质疑，请逐一回应：

{challenge_text}

{context}

请以JSON格式输出：
{{
    "responses": [
        {{
            "target_challenge": "被回应的质疑",
            "response": "回应内容",
            "evidence_support": "支撑证据",
            "concession": "承认的不足（如果有）",
            "revised_confidence": 0.75
        }}
    ],
    "revised_hypotheses": ["修正后的假设（如果有修正）"]
}}"""

            response_result = self._call_agent_json("causal_detective", response_prompt, context)
            responses = response_result.get("responses", [])

            for resp in responses[:5]:
                self._add_debate_msg(
                    "causal_detective", "response",
                    f"**回应质疑**\n\n"
                    f"目标: {resp.get('target_challenge','')}\n\n"
                    f"{resp.get('response','')}\n\n"
                    f"证据: {resp.get('evidence_support','')}\n"
                    f"让步: {resp.get('concession','无')}",
                    round_num=round_num
                )

            # 5c. 主持人裁判
            mod_prompt = f"""请对第 {round_num} 轮辩论进行总结裁判。

## 质疑
{json.dumps(challenges[:5], ensure_ascii=False, indent=1)[:3000]}

## 回应
{json.dumps(responses[:5], ensure_ascii=False, indent=1)[:3000]}

{context}

请以JSON格式输出：
{{
    "round_summary": "本轮辩论总结",
    "consensus_reached": ["已达成共识的结论"],
    "unresolved": ["仍有分歧的问题"],
    "hypothesis_status": {{
        "strengthened": ["被加强的假设"],
        "weakened": ["被削弱的假设"],
        "abandoned": ["被放弃的假设"]
    }},
    "should_continue": false,
    "continue_reason": "继续辩论的理由（如果should_continue为true）"
}}"""

            mod_result = self._call_agent_json("forensic_moderator", mod_prompt, context)
            consensus = mod_result.get("consensus_reached", [])
            unresolved = mod_result.get("unresolved", [])
            h_status = mod_result.get("hypothesis_status", {})

            self._add_debate_msg(
                "forensic_moderator", "consensus",
                f"**第 {round_num} 轮辩论总结**\n\n"
                f"{mod_result.get('round_summary', '')}\n\n"
                f"**已达成共识:**\n" + "\n".join(f"✅ {c}" for c in consensus) +
                f"\n\n**仍有分歧:**\n" + "\n".join(f"❓ {u}" for u in unresolved) +
                (f"\n\n**假设状态变化:**\n"
                 + "\n".join(f"↑ {h}" for h in h_status.get("strengthened", []))
                 + "\n".join(f"↓ {h}" for h in h_status.get("weakened", []))
                 + "\n".join(f"✗ {h}" for h in h_status.get("abandoned", []))
                 if h_status else ""),
                round_num=round_num
            )

            # v4: 智能轮次控制——无实质分歧则提前结束
            if not mod_result.get("should_continue", False) or len(unresolved) == 0:
                logger.info(f"[{self.analysis_id}] 辩论在第 {round_num} 轮达成共识，结束")
                break

    # ═══════════════════════════════════════════════════════════
    # Phase 6: 严格共识形成
    # ═══════════════════════════════════════════════════════════

    def _run_consensus(self, state):
        """Phase 6: 严格共识形成"""
        logger.info(f"[{self.analysis_id}] Phase 6: 严格共识形成")

        state = self.manager.get_analysis(self.analysis_id)
        context = self._build_debate_context(state)

        prompt = f"""质证辩论已结束。请综合所有Agent的分析结果，形成最终共识。

## 完整分析上下文
{context[:8000]}

请以JSON格式输出最终共识：
{{
    "final_conclusions": [
        {{
            "conclusion": "结论描述",
            "confidence": 0.85,
            "evidence_summary": "支撑证据摘要",
            "dissenting_views": "反对意见（如果有）",
            "caveats": "注意事项/限制条件"
        }}
    ],
    "root_causes_ranked": [
        {{
            "rank": 1,
            "cause": "根本原因描述",
            "confidence": 0.85,
            "evidence_chain": "完整证据链",
            "counter_arguments": "反对意见",
            "mechanism": "作用机制"
        }}
    ],
    "overall_confidence": 0.75,
    "key_uncertainties": ["关键不确定性"],
    "recommendations": ["建议"],
    "methodology_limitations": ["方法论局限"]
}}"""

        self._record_action("consensus", "forensic_moderator", "FORM_CONSENSUS", "开始形成最终共识")
        result = self._call_agent_json("forensic_moderator", prompt, context)

        final_confidence = result.get("overall_confidence", 0.5)
        self.manager.update_confidence(self.analysis_id, final_confidence)

        conclusions = result.get("final_conclusions", [])
        root_causes = result.get("root_causes_ranked", [])

        self._add_debate_msg(
            "forensic_moderator", "final_consensus",
            f"**最终共识报告**\n\n"
            f"整体置信度: {final_confidence:.0%}\n\n"
            f"**核心结论:**\n" + "\n".join(
                f"[{c.get('confidence',0):.0%}] {c.get('conclusion','')}" for c in conclusions
            ) + f"\n\n**根本原因排序:**\n" + "\n".join(
                f"#{rc.get('rank',0)} [{rc.get('confidence',0):.0%}] {rc.get('cause','')}"
                for rc in root_causes
            ) + f"\n\n**关键不确定性:**\n" + "\n".join(
                f"- {u}" for u in result.get("key_uncertainties", [])
            ) + f"\n\n**方法论局限:**\n" + "\n".join(
                f"- {l}" for l in result.get("methodology_limitations", [])
            ),
            round_num=0,
            confidence=final_confidence
        )

        self._record_action(
            "consensus", "forensic_moderator", "FORM_CONSENSUS",
            f"**最终共识形成完成** - 置信度: {final_confidence:.0%}",
            round_num=0,
            confidence=final_confidence
        )
