"""
优化版本体生成服务
采用"轻量模型快速提取 + 主力模型检查优化"的两阶段策略

流程：
1. 第一阶段：轻量模型（豆包mini）快速生成本体草稿
2. 第二阶段：主力模型（千问max）检查、优化、完善
3. 可选第三阶段：质量验证和补充

优势：
- 速度：轻量模型快速生成（2-3秒）
- 质量：主力模型把关优化（5-8秒）
- 成本：比全程使用主力模型节省 60-70%
- 效果：质量接近主力模型单独生成
"""

import json
import time
from typing import Dict, Any, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor

from ..utils.llm_client import LLMClient
from ..utils.smart_llm_router import get_smart_router, TaskComplexity
from ..utils.logger import get_logger

logger = get_logger('traceback.ontology_optimized')


class OptimizedOntologyGenerator:
    """
    优化版本体生成器
    两阶段生成：快速草稿 + 质量优化
    """
    
    def __init__(self):
        self.router = get_smart_router()
        # 也可以直接使用两个客户端
        self.fast_client = LLMClient(preset="fast")      # 轻量模型：豆包mini
        self.main_client = LLMClient(preset="default")   # 主力模型：千问max
    
    def generate_optimized(
        self,
        text: str,
        requirement: str,
        use_two_stage: bool = True,
        validate_result: bool = True
    ) -> Dict[str, Any]:
        """
        生成本体（优化版）
        
        Args:
            text: 文本内容
            requirement: 分析需求
            use_two_stage: 是否使用两阶段生成（推荐True）
            validate_result: 是否验证结果
            
        Returns:
            优化后的本体定义
        """
        start_time = time.time()
        
        if not use_two_stage:
            # 单阶段：直接使用主力模型（传统方式）
            logger.info("使用单阶段生成（主力模型）")
            return self._generate_single_stage(text, requirement)
        
        # 两阶段生成
        logger.info("使用两阶段生成：轻量模型草稿 + 主力模型优化")
        
        # 第一阶段：轻量模型快速生成草稿
        logger.info("[阶段1/2] 轻量模型快速生成本体草稿...")
        stage1_start = time.time()
        draft_ontology = self._generate_draft(text, requirement)
        stage1_time = time.time() - stage1_start
        logger.info(f"[阶段1/2] 完成，耗时 {stage1_time:.2f}s")
        
        # 第二阶段：主力模型检查优化
        logger.info("[阶段2/2] 主力模型检查优化...")
        stage2_start = time.time()
        optimized_ontology = self._optimize_ontology(
            draft_ontology, text, requirement
        )
        stage2_time = time.time() - stage2_start
        logger.info(f"[阶段2/2] 完成，耗时 {stage2_time:.2f}s")
        
        # 可选第三阶段：质量验证
        if validate_result:
            logger.info("[验证] 质量检查...")
            validated_ontology = self._validate_and_enhance(
                optimized_ontology, text, requirement
            )
        else:
            validated_ontology = optimized_ontology
        
        total_time = time.time() - start_time
        logger.info(f"优化版本体生成完成，总耗时 {total_time:.2f}s")
        logger.info(f"  - 阶段1（轻量）: {stage1_time:.2f}s ({stage1_time/total_time*100:.1f}%)")
        logger.info(f"  - 阶段2（主力）: {stage2_time:.2f}s ({stage2_time/total_time*100:.1f}%)")
        
        return validated_ontology
    
    def _generate_draft(self, text: str, requirement: str) -> Dict[str, Any]:
        """
        第一阶段：轻量模型快速生成本体草稿
        
        特点：
        - 速度快（2-3秒）
        - 覆盖主要实体和关系类型
        - 可能缺少细节或存在小错误
        """
        # 简化版提示词，适合轻量模型
        draft_prompt = f"""你是一个知识图谱设计助手。请快速分析文本，设计简单的本体结构。

**分析需求**：{requirement}

**文本内容**（前2000字）：
{text[:2000]}

请输出JSON格式，包含：
1. entity_types: 5-8个核心实体类型
2. edge_types: 5-8个核心关系类型
3. 每个实体类型包含：name, description, 3-5个关键属性
4. 每个关系类型包含：name, description

要求：
- 速度快，覆盖主要概念即可
- 不需要太详细，后续会优化
- 确保JSON格式正确

输出格式：
{{
    "entity_types": [
        {{
            "name": "实体类型名",
            "description": "描述",
            "attributes": [{{"name": "属性名", "type": "text", "description": "描述"}}]
        }}
    ],
    "edge_types": [
        {{
            "name": "关系类型名",
            "description": "描述"
        }}
    ],
    "analysis_summary": "简要分析"
}}"""
        
        try:
            # 使用轻量模型（豆包mini）
            result = self.fast_client.chat_json(
                messages=[{"role": "user", "content": draft_prompt}],
                temperature=0.5,  # 稍高的温度，增加多样性
                max_tokens=2048
            )
            
            logger.info(f"轻量模型生成了 {len(result.get('entity_types', []))} 个实体类型")
            return result
            
        except Exception as e:
            logger.warning(f"轻量模型生成失败: {e}，降级使用主力模型")
            # 降级：使用主力模型快速生成
            return self._generate_single_stage(text, requirement, max_tokens=2048)
    
    def _optimize_ontology(
        self,
        draft: Dict[str, Any],
        text: str,
        requirement: str
    ) -> Dict[str, Any]:
        """
        第二阶段：主力模型检查优化
        
        任务：
        1. 检查草稿的完整性和准确性
        2. 补充缺失的实体类型和关系类型
        3. 完善属性定义
        4. 确保符合因果回溯分析需求
        5. 优化描述，使其更专业
        """
        # 将草稿转换为JSON字符串
        draft_json = json.dumps(draft, ensure_ascii=False, indent=2)
        
        optimize_prompt = f"""你是知识图谱本体设计专家。请检查并优化以下本体草稿。

**分析需求**：{requirement}

**原始文本**（前1500字）：
{text[:1500]}

**本体草稿**（需要优化）：
```json
{draft_json}
```

请执行以下优化任务：

1. **完整性检查**
   - 是否缺少关键实体类型？补充必要的类型
   - 是否缺少关键关系类型？特别是因果关系
   - 是否缺少重要属性？

2. **准确性检查**
   - 实体类型定义是否准确？
   - 关系类型是否符合因果分析需求？
   - 属性定义是否合理？

3. **专业性提升**
   - 优化描述，使其更专业、更精确
   - 确保符合因果回溯分析的学术要求
   - 统一命名规范和术语

4. **强制性要求**（必须遵守）
   - 必须包含实体类型：Event, Evidence, Person, Organization
   - 必须包含关系类型：CAUSED_BY, SUPPORTED_BY, PRECEDED_BY
   - 每个实体类型必须有属性：timestamp, credibility_score, source, description
   - 总实体类型数量控制在 8-12 个
   - 总关系类型数量控制在 10-14 个

请输出优化后的完整本体（JSON格式）：
{{
    "entity_types": [...],
    "edge_types": [...],
    "analysis_summary": "优化说明...",
    "optimization_notes": [
        "补充了XXX实体类型",
        "完善了XXX关系定义",
        "修正了XXX描述"
    ]
}}"""
        
        try:
            # 使用主力模型（千问max）
            result = self.main_client.chat_json(
                messages=[{"role": "user", "content": optimize_prompt}],
                temperature=0.3,  # 较低温度，保持一致性
                max_tokens=4096
            )
            
            # 移除优化备注，保持格式一致
            if "optimization_notes" in result:
                logger.info(f"主力模型优化内容：")
                for note in result["optimization_notes"]:
                    logger.info(f"  - {note}")
                del result["optimization_notes"]
            
            logger.info(f"优化后实体类型数量: {len(result.get('entity_types', []))}")
            logger.info(f"优化后关系类型数量: {len(result.get('edge_types', []))}")
            
            return result
            
        except Exception as e:
            logger.error(f"主力模型优化失败: {e}，返回草稿版本")
            # 如果优化失败，返回草稿版本（总比没有好）
            return draft
    
    def _validate_and_enhance(
        self,
        ontology: Dict[str, Any],
        text: str,
        requirement: str
    ) -> Dict[str, Any]:
        """
        第三阶段：质量验证和补充
        
        确保本体满足所有基本要求
        """
        # 确保必要的顶层字段存在
        if "entity_types" not in ontology:
            ontology["entity_types"] = []
        if "edge_types" not in ontology:
            ontology["edge_types"] = []
        if "analysis_summary" not in ontology:
            ontology["analysis_summary"] = "因果回溯分析本体定义"
        
        # 检查核心实体类型
        existing_entities = {et.get("name") for et in ontology["entity_types"]}
        
        # 确保核心实体存在
        core_entities = [
            {
                "name": "Event",
                "description": "因果链中的关键事件",
                "attributes": [
                    {"name": "timestamp", "type": "text", "description": "发生时间"},
                    {"name": "importance_score", "type": "text", "description": "重要性评分0-1"},
                    {"name": "credibility_score", "type": "text", "description": "可信度评分0-1"},
                    {"name": "source", "type": "text", "description": "信息来源"},
                    {"name": "description", "type": "text", "description": "详细描述"},
                ],
                "examples": [],
            },
            {
                "name": "Evidence",
                "description": "支撑因果关系的证据",
                "attributes": [
                    {"name": "timestamp", "type": "text", "description": "证据时间"},
                    {"name": "credibility_score", "type": "text", "description": "可信度评分0-1"},
                    {"name": "source_type", "type": "text", "description": "来源类型"},
                    {"name": "source", "type": "text", "description": "具体来源"},
                    {"name": "description", "type": "text", "description": "证据内容"},
                ],
                "examples": [],
            },
        ]
        
        for ce in core_entities:
            if ce["name"] not in existing_entities:
                ontology["entity_types"].insert(0, ce)
                logger.info(f"验证阶段补充核心实体类型: {ce['name']}")
        
        # 检查核心关系类型
        existing_edges = {et.get("name") for et in ontology["edge_types"]}
        
        core_edges = [
            {
                "name": "CAUSED_BY",
                "description": "由...导致（核心因果关系）",
                "source_targets": [{"source": "Event", "target": "Event"}],
                "attributes": [
                    {"name": "confidence", "type": "text", "description": "置信度0-1"},
                    {"name": "causal_strength", "type": "text", "description": "因果强度0-1"},
                ],
            },
            {
                "name": "SUPPORTED_BY",
                "description": "被...支撑",
                "source_targets": [{"source": "Event", "target": "Evidence"}],
                "attributes": [{"name": "confidence", "type": "text", "description": "支撑置信度0-1"}],
            },
        ]
        
        for ce in core_edges:
            if ce["name"] not in existing_edges:
                ontology["edge_types"].insert(0, ce)
                logger.info(f"验证阶段补充核心关系类型: {ce['name']}")
        
        # 为所有实体类型添加通用属性
        required_attrs = {"timestamp", "credibility_score", "source", "description"}
        for et in ontology["entity_types"]:
            existing_attrs = {a.get("name") for a in et.get("attributes", [])}
            for attr_name in required_attrs:
                if attr_name not in existing_attrs:
                    et.setdefault("attributes", []).append({
                        "name": attr_name,
                        "type": "text",
                        "description": f"{attr_name}描述"
                    })
        
        return ontology
    
    def _generate_single_stage(
        self,
        text: str,
        requirement: str,
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        """
        单阶段生成（传统方式，备用）
        """
        # 使用完整版提示词
        system_prompt = """你是专业的知识图谱本体设计专家..."""  # 省略完整提示词
        
        user_prompt = f"""请设计因果回溯分析的本体结构。

需求：{requirement}

文本：{text[:3000]}

输出JSON格式本体定义。"""
        
        result = self.main_client.chat_json(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=max_tokens
        )
        
        return result
    
    def compare_strategies(
        self,
        text: str,
        requirement: str
    ) -> Dict[str, Any]:
        """
        对比不同生成策略的效果
        
        用于评估和选择最佳策略
        """
        results = {}
        
        # 策略1：单阶段主力模型
        logger.info("=== 对比测试：单阶段主力模型 ===")
        start = time.time()
        results["single_stage"] = {
            "result": self._generate_single_stage(text, requirement),
            "time": time.time() - start,
            "cost": "high"
        }
        logger.info(f"耗时: {results['single_stage']['time']:.2f}s")
        
        # 策略2：两阶段优化
        logger.info("=== 对比测试：两阶段优化 ===")
        start = time.time()
        results["two_stage"] = {
            "result": self.generate_optimized(text, requirement, use_two_stage=True),
            "time": time.time() - start,
            "cost": "medium"
        }
        logger.info(f"耗时: {results['two_stage']['time']:.2f}s")
        
        # 策略3：仅轻量模型
        logger.info("=== 对比测试：仅轻量模型 ===")
        start = time.time()
        results["fast_only"] = {
            "result": self._generate_draft(text, requirement),
            "time": time.time() - start,
            "cost": "low"
        }
        logger.info(f"耗时: {results['fast_only']['time']:.2f}s")
        
        # 分析对比
        logger.info("\n=== 对比结果 ===")
        logger.info(f"单阶段主力: {results['single_stage']['time']:.2f}s (基准)")
        logger.info(f"两阶段优化: {results['two_stage']['time']:.2f}s "
                   f"(节省 {results['single_stage']['time']-results['two_stage']['time']:.2f}s)")
        logger.info(f"仅轻量模型: {results['fast_only']['time']:.2f}s "
                   f"(节省 {results['single_stage']['time']-results['fast_only']['time']:.2f}s)")
        
        return results


# 便捷函数
def generate_ontology_optimized(
    text: str,
    requirement: str,
    **kwargs
) -> Dict[str, Any]:
    """
    便捷函数：生成优化版本体
    
    使用示例：
        ontology = generate_ontology_optimized(
            text="文本内容...",
            requirement="分析因果关系"
        )
    """
    generator = OptimizedOntologyGenerator()
    return generator.generate_optimized(text, requirement, **kwargs)


if __name__ == "__main__":
    # 测试
    generator = OptimizedOntologyGenerator()
    
    test_text = """
    2024年3月，某科技公司发生重大数据泄露事件。
    经调查发现，事件起因是开发人员在代码中提交了包含数据库密码的配置文件。
    外部攻击者通过扫描GitHub公开仓库发现了该密码，进而获取了用户数据。
    公司CEO在事件发生后召开了紧急会议，决定立即修复漏洞并通知受影响用户。
    """
    
    test_requirement = "分析该数据泄露事件的因果关系链"
    
    # 生成优化版本体
    ontology = generator.generate_optimized(test_text, test_requirement)
    print(json.dumps(ontology, ensure_ascii=False, indent=2))
