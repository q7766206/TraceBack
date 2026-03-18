"""
优化版图谱构建服务
使用智能 LLM 路由，轻量模型辅助主力模型并发处理

优化策略：
1. 文本预处理：轻量模型 (qwen-turbo/豆包mini)
2. 实体抽取：中等任务，轻量模型优先，失败转主力
3. 关系抽取：中等任务，轻量模型优先，失败转主力
4. 本体生成：复杂任务，主力模型 (qwen-max)
5. 图谱验证：关键任务，双模型交叉验证
"""

import os
import uuid
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional

from ..config import Config
from ..models.task import TaskManager, TaskStatus
from ..utils.logger import get_logger
from ..utils.smart_llm_router import (
    get_smart_router, 
    TaskComplexity, 
    classify_task_complexity
)
from .local_graph_store import LocalGraphStore
from .text_processor import TextProcessor

logger = get_logger('traceback.graph_builder_optimized')


class OptimizedGraphBuilder:
    """
    优化版图谱构建器
    使用智能路由自动选择模型
    """
    
    def __init__(self):
        self.task_manager = TaskManager()
        self.graph_store = LocalGraphStore()
        self.router = get_smart_router()
    
    def build_graph_optimized(
        self,
        text: str,
        ontology: Dict[str, Any],
        graph_name: str,
        chunk_size: int = 1200,  # 增大块大小
        chunk_overlap: int = 150,
        max_workers: int = 5,     # 并发数
    ) -> str:
        """
        优化版图谱构建
        
        流程：
        1. 文本分块（同步）
        2. 实体抽取（并发，轻量模型优先）
        3. 关系抽取（并发，轻量模型优先）
        4. 质量验证（主力模型）
        """
        task_id = self.task_manager.create_task(
            task_type="graph_build_optimized",
            metadata={"graph_name": graph_name, "text_length": len(text)}
        )
        
        # 启动后台线程处理
        thread = threading.Thread(
            target=self._build_graph_worker,
            args=(task_id, text, ontology, graph_name, chunk_size, chunk_overlap, max_workers),
            daemon=True
        )
        thread.start()
        
        return task_id
    
    def _build_graph_worker(
        self, task_id: str, text: str, ontology: Dict[str, Any],
        graph_name: str, chunk_size: int, chunk_overlap: int, max_workers: int
    ):
        """后台工作线程"""
        try:
            self.task_manager.update_task(
                task_id, status=TaskStatus.PROCESSING, 
                progress=5, message="开始优化版图谱构建..."
            )
            
            # 1. 创建图谱
            graph_id = f"graph_opt_{uuid.uuid4().hex[:12]}"
            logger.info(f"创建优化版图谱: {graph_id}")
            
            # 2. 切分文本
            processor = TextProcessor()
            chunks = processor.split_text(text, chunk_size=chunk_size, overlap=chunk_overlap)
            total_chunks = len(chunks)
            logger.info(f"文本切分为 {total_chunks} 个块（优化版）")
            
            self.task_manager.update_task(
                task_id, progress=10, 
                message=f"文本切分为 {total_chunks} 个块，准备并发处理..."
            )
            
            # 3. 准备本体描述
            entity_types_desc = self._format_entity_types(ontology)
            edge_types_desc = self._format_edge_types(ontology)
            
            # 4. 并发提取（使用智能路由）
            all_entities = {}
            all_relations = []
            
            def process_chunk(idx_chunk):
                """处理单个块"""
                idx, chunk = idx_chunk
                
                # 实体抽取（中等复杂度）
                entities = self._extract_entities(
                    chunk, entity_types_desc, idx
                )
                
                # 关系抽取（中等复杂度）
                relations = self._extract_relations(
                    chunk, entities, edge_types_desc, idx
                )
                
                return idx, entities, relations
            
            # 使用线程池并发处理
            processed = 0
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 提交所有任务
                futures = {
                    executor.submit(process_chunk, (i, chunk)): i 
                    for i, chunk in enumerate(chunks)
                }
                
                # 收集结果
                for future in as_completed(futures):
                    chunk_idx = futures[future]
                    try:
                        idx, entities, relations = future.result()
                        
                        # 合并实体
                        for entity in entities:
                            name = entity.get("name", "").strip()
                            if name and name not in all_entities:
                                node = self.graph_store.add_node(
                                    graph_id=graph_id,
                                    name=name,
                                    labels=[entity.get("type", "Entity")],
                                    summary=entity.get("summary", ""),
                                    attributes=entity.get("attributes", {})
                                )
                                all_entities[name] = node.uuid
                        
                        # 合并关系
                        all_relations.extend(relations)
                        
                        processed += 1
                        progress = 10 + int((processed / total_chunks) * 70)
                        self.task_manager.update_task(
                            task_id, progress=progress,
                            message=f"已处理 {processed}/{total_chunks} 个块，发现 {len(all_entities)} 个实体"
                        )
                        
                    except Exception as e:
                        logger.warning(f"块 {chunk_idx} 处理失败: {e}")
            
            # 5. 添加关系
            self.task_manager.update_task(
                task_id, progress=80, message="构建关系网络..."
            )
            
            for rel in all_relations:
                source_name = rel.get("source", "").strip()
                target_name = rel.get("target", "").strip()
                
                if not source_name or not target_name:
                    continue
                
                # 确保实体存在
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
                
                # 添加关系
                self.graph_store.add_edge(
                    graph_id=graph_id,
                    name=rel.get("type", "RELATED_TO"),
                    fact=rel.get("fact", ""),
                    source_uuid=all_entities[source_name],
                    target_uuid=all_entities[target_name],
                    attributes=rel.get("attributes", {})
                )
            
            # 6. 质量验证（使用主力模型）
            self.task_manager.update_task(
                task_id, progress=90, message="质量验证..."
            )
            self._validate_graph(graph_id, ontology)
            
            # 7. 完成
            stats = self.graph_store.get_stats(graph_id)
            self.task_manager.complete_task(task_id, result={
                "graph_id": graph_id,
                "graph_name": graph_name,
                "stats": stats
            })
            
            logger.info(f"优化版图谱构建完成: {graph_id}")
            
            # 打印统计
            router_stats = self.router.get_stats()
            logger.info(f"路由统计: 主力模型 {router_stats['main_calls']} 次, "
                       f"轻量模型 {router_stats['fast_calls']} 次, "
                       f"降级 {router_stats['fallback_count']} 次")
            
        except Exception as e:
            logger.error(f"优化版图谱构建失败: {e}", exc_info=True)
            self.task_manager.fail_task(task_id, str(e))
    
    def _extract_entities(self, chunk: str, entity_types_desc: str, chunk_idx: int) -> List[Dict]:
        """提取实体（使用智能路由）"""
        prompt = f"""从以下文本中提取实体。

可识别的实体类型：
{entity_types_desc}

文本内容：
{chunk[:1500]}

请以JSON格式输出：
{{
    "entities": [
        {{
            "name": "实体名称",
            "type": "实体类型",
            "summary": "简要描述",
            "attributes": {{}}
        }}
    ]
}}"""
        
        try:
            # 使用智能路由，中等复杂度（轻量模型优先）
            result = self.router.route_task(
                messages=[{"role": "user", "content": prompt}],
                complexity=TaskComplexity.MEDIUM,
                temperature=0.2,
                max_tokens=2048
            )
            
            if result.success:
                import json
                data = json.loads(result.content)
                return data.get("entities", [])
            else:
                logger.warning(f"块 {chunk_idx} 实体抽取失败: {result.error}")
                return []
                
        except Exception as e:
            logger.warning(f"块 {chunk_idx} 实体抽取异常: {e}")
            return []
    
    def _extract_relations(self, chunk: str, entities: List[Dict], 
                          edge_types_desc: str, chunk_idx: int) -> List[Dict]:
        """提取关系（使用智能路由）"""
        if not entities:
            return []
        
        entity_names = [e.get("name") for e in entities[:20]]  # 限制数量
        
        prompt = f"""从以下文本中提取实体之间的关系。

文本中涉及的实体：
{', '.join(entity_names)}

可识别的关系类型：
{edge_types_desc}

文本内容：
{chunk[:1500]}

请以JSON格式输出：
{{
    "relations": [
        {{
            "source": "源实体名称",
            "target": "目标实体名称",
            "type": "关系类型",
            "fact": "关系描述"
        }}
    ]
}}"""
        
        try:
            # 使用智能路由，中等复杂度
            result = self.router.route_task(
                messages=[{"role": "user", "content": prompt}],
                complexity=TaskComplexity.MEDIUM,
                temperature=0.2,
                max_tokens=2048
            )
            
            if result.success:
                import json
                data = json.loads(result.content)
                return data.get("relations", [])
            else:
                return []
                
        except Exception as e:
            logger.warning(f"块 {chunk_idx} 关系抽取异常: {e}")
            return []
    
    def _validate_graph(self, graph_id: str, ontology: Dict[str, Any]):
        """验证图谱质量（使用主力模型）"""
        # TODO: 实现图谱质量验证
        pass
    
    def _format_entity_types(self, ontology: Dict) -> str:
        """格式化实体类型描述"""
        types = ontology.get("entity_types", [])
        return "\n".join([
            f"- {t.get('name')}: {t.get('description', '')}"
            for t in types[:10]  # 限制前10个
        ])
    
    def _format_edge_types(self, ontology: Dict) -> str:
        """格式化关系类型描述"""
        types = ontology.get("edge_types", [])
        return "\n".join([
            f"- {t.get('name')}: {t.get('description', '')}"
            for t in types[:8]  # 限制前8个
        ])


# 使用示例和测试
if __name__ == "__main__":
    # 测试智能路由
    router = get_smart_router()
    
    # 测试简单任务
    print("测试简单任务...")
    result = router.route_task(
        messages=[{"role": "user", "content": "提取这段文本的关键词"}],
        complexity=TaskComplexity.SIMPLE
    )
    print(f"模型: {result.model_used}, 耗时: {result.cost_time:.2f}s")
    
    # 测试复杂任务
    print("\n测试复杂任务...")
    result = router.route_task(
        messages=[{"role": "user", "content": "分析这段文本的因果关系"}],
        complexity=TaskComplexity.COMPLEX
    )
    print(f"模型: {result.model_used}, 耗时: {result.cost_time:.2f}s")
    
    # 打印统计
    print("\n路由统计:")
    stats = router.get_stats()
    print(f"主力模型: {stats['main_calls']} 次, 平均 {stats['main_avg_time']:.2f}s")
    print(f"轻量模型: {stats['fast_calls']} 次, 平均 {stats['fast_avg_time']:.2f}s")
    print(f"降级次数: {stats['fallback_count']}")
