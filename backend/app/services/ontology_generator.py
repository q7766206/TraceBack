"""
TraceBack 本体生成服务
分析文本内容，生成适合因果回溯分析的实体和关系类型定义
"""

import json
from typing import Dict, Any, List, Optional
from ..utils.llm_client import LLMClient


# ============================================================
# 因果回溯本体生成的系统提示词
# ============================================================
ONTOLOGY_SYSTEM_PROMPT = """你是一个专业的知识图谱本体设计专家。你的任务是分析给定的文本内容和回溯分析需求，设计适合**因果回溯分析**的实体类型和关系类型。

**极其重要：你必须输出有效的JSON格式数据，严格遵守以下规则：**

1. **只输出JSON**，不要输出任何其他文字、说明或markdown标记
2. **确保JSON格式完全正确**：
   - 所有字符串用双引号包裹
   - 对象和数组的元素之间必须有逗号分隔
   - 最后一个元素后面不能有逗号
   - 所有括号必须正确匹配
3. **不要在JSON中包含注释**
4. **如果字符串中包含双引号，必须转义为 \\"**
5. **确保所有字符串值都是有效的UTF-8编码**

**输出前请检查JSON格式是否正确！**

## 核心任务背景

我们正在构建一个**因果回溯分析系统（TraceBack）**。在这个系统中：
- 我们需要从历史数据中重建事件的因果链条
- 每个实体都是因果链中的一个节点——可以是事件、人物、物证、地点、组织、文件等
- 实体之间的关系主要是因果关系、时序关系、证据支撑关系
- 我们需要追溯"为什么会发生"，找到根本原因

因此，**实体必须是因果链中可追溯的具体对象**：

**可以是**：
- 具体事件（事故、决策、行动、公告、会议等）
- 具体人物（决策者、当事人、目击者、专家等）
- 具体组织（公司、政府部门、机构等）
- 具体物证/文件（报告、合同、邮件、数据记录等）
- 具体地点（事发地、关键场所等）
- 具体条件/状态（天气状况、设备状态、市场环境等）

**不可以是**：
- 过于抽象的概念（如"责任"、"风险"、"影响"）
- 主观情感（如"愤怒"、"恐惧"）
- 未发生的假设（如"如果..."）

## 输出格式

请输出JSON格式，包含以下结构：

```json
{
    "entity_types": [
        {
            "name": "实体类型名称（英文，PascalCase）",
            "description": "简短描述（英文，不超过100字符）",
            "attributes": [
                {
                    "name": "属性名（英文，snake_case）",
                    "type": "text",
                    "description": "属性描述"
                }
            ],
            "examples": ["示例实体1", "示例实体2"]
        }
    ],
    "edge_types": [
        {
            "name": "关系类型名称（英文，UPPER_SNAKE_CASE）",
            "description": "简短描述（英文，不超过100字符）",
            "source_targets": [
                {"source": "源实体类型", "target": "目标实体类型"}
            ],
            "attributes": []
        }
    ],
    "analysis_summary": "对文本内容的简要分析说明（中文）"
}
```

## 设计指南（极其重要！）

### 1. 实体类型设计 - 必须严格遵守

**数量要求：必须正好10个实体类型**

**层次结构要求**：

你的10个实体类型必须包含以下层次：

A. **核心因果实体类型（必须包含，放在列表前4个）**：
   - `Event`: 任何可追溯的事件（事故、决策、行动、公告等）。这是因果链的核心节点。必须包含 timestamp、importance_score 属性。
   - `Evidence`: 支撑因果关系的证据（文件、数据、证词等）。必须包含 credibility_score、source_type 属性。
   - `Person`: 因果链中的关键人物。必须包含 role_in_event 属性。
   - `Organization`: 因果链中的关键组织。必须包含 role_in_event 属性。

B. **兜底类型（必须包含，放在列表最后2个）**：
   - `Location`: 任何地理位置的兜底类型。
   - `Condition`: 任何环境条件/状态的兜底类型（天气、设备状态、市场环境等）。

C. **具体类型（4个，根据文本内容设计）**：
   - 针对文本中出现的具体角色和对象，设计更具体的类型
   - 例如：如果文本涉及工业事故，可以有 `Equipment`, `SafetyReport`, `Inspector`, `Regulation`
   - 例如：如果文本涉及金融事件，可以有 `Transaction`, `Contract`, `Auditor`, `FinancialReport`

### 2. 关系类型设计 - 因果关系为核心

**必须包含的关系类型（前6个）**：

1. `CAUSED_BY`: A由B导致（核心因果关系，从结果指向原因）
2. `PRECEDED_BY`: A在B之后发生（时序关系）
3. `SUPPORTED_BY`: 结论A被证据B支撑
4. `CONTRADICTED_BY`: 结论A被证据B反驳
5. `PARTICIPATED_IN`: 人物/组织A参与了事件B
6. `LOCATED_AT`: 事件A发生在地点B

**可选的关系类型（根据文本内容选择4-6个）**：
- `DERIVED_FROM`: A从B衍生/派生
- `APPROVED_BY`: A被B批准/授权
- `REPORTED_BY`: A被B报告/记录
- `SUPERVISED_BY`: A被B监管/监督
- `TRIGGERED_BY`: A被B触发（比CAUSED_BY更直接）
- `PREVENTED_BY`: A被B阻止/预防（反事实关系）
- `CORRELATED_WITH`: A与B相关但因果性待定
- `OWNED_BY`: A归B所有/管理

**关系总数：10-12个**

### 3. 属性设计要求

**所有实体类型都必须包含以下通用属性**：
- `timestamp`: 时间戳（text类型，ISO格式或描述性时间）
- `credibility_score`: 可信度评分（text类型，0.0-1.0）
- `source`: 信息来源（text类型）
- `description`: 详细描述（text类型）

**所有关系类型都必须包含以下通用属性**：
- `confidence`: 关系置信度（0.0-1.0）
- `evidence_ids`: 支撑该关系的证据ID列表
- `causal_strength`: 因果强度（仅因果关系需要，0.0-1.0）

### 4. 设计原则

1. **因果导向**：所有设计都围绕"追溯原因"这个核心目标
2. **可追溯性**：每个实体和关系都必须可以追溯到具体的证据
3. **时间敏感**：所有实体都必须有时间属性，因为时序是因果推理的基础
4. **可信度标注**：所有实体和关系都必须有可信度评分
5. **具体而非抽象**：实体必须是具体的、可观察的对象，不能是抽象概念
"""


# 用户提示词模板
ONTOLOGY_USER_PROMPT_TEMPLATE = """请分析以下文本内容，并根据回溯分析需求设计知识图谱本体。

## 回溯分析需求
{requirement}

## 文本内容（前{text_length}字）
{text_preview}

请严格按照系统提示中的格式和要求输出JSON。"""


class OntologyGenerator:
    """因果回溯本体生成器"""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()

    def generate(
        self,
        text: str,
        requirement: str = "分析该事件的因果链，找出根本原因",
        max_text_preview: int = 8000,
    ) -> Dict[str, Any]:
        """
        生成因果回溯本体

        Args:
            text: 输入文本
            requirement: 回溯分析需求描述
            max_text_preview: 发送给LLM的文本预览最大长度

        Returns:
            本体定义字典
        """
        text_preview = text[:max_text_preview]
        if len(text) > max_text_preview:
            text_preview += f"\n\n... (共{len(text)}字，已截取前{max_text_preview}字)"

        user_prompt = ONTOLOGY_USER_PROMPT_TEMPLATE.format(
            requirement=requirement,
            text_length=min(len(text), max_text_preview),
            text_preview=text_preview,
        )

        messages = [
            {"role": "system", "content": ONTOLOGY_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        # 调用LLM生成本体
        result = self.llm.chat_json(
            messages=messages,
            temperature=0.3,
            max_tokens=4096,
        )

        # 验证和后处理
        result = self._validate_and_fix(result)

        return result

    def _validate_and_fix(self, ontology: Dict[str, Any]) -> Dict[str, Any]:
        """验证并修复本体定义"""

        # 确保必要的顶层字段存在
        if "entity_types" not in ontology:
            ontology["entity_types"] = []
        if "edge_types" not in ontology:
            ontology["edge_types"] = []
        if "analysis_summary" not in ontology:
            ontology["analysis_summary"] = ""

        # 确保核心实体类型存在
        existing_entity_names = {et["name"] for et in ontology["entity_types"]}
        core_entities = [
            {
                "name": "Event",
                "description": "Any traceable event in the causal chain",
                "attributes": [
                    {"name": "timestamp", "type": "text", "description": "When the event occurred"},
                    {"name": "importance_score", "type": "text", "description": "Importance score 0.0-1.0"},
                    {"name": "credibility_score", "type": "text", "description": "Credibility score 0.0-1.0"},
                    {"name": "source", "type": "text", "description": "Information source"},
                    {"name": "description", "type": "text", "description": "Detailed description"},
                ],
                "examples": [],
            },
            {
                "name": "Evidence",
                "description": "Evidence supporting causal relationships",
                "attributes": [
                    {"name": "timestamp", "type": "text", "description": "When the evidence was created"},
                    {"name": "credibility_score", "type": "text", "description": "Credibility score 0.0-1.0"},
                    {"name": "source_type", "type": "text", "description": "Type of source (official/media/witness/etc)"},
                    {"name": "source", "type": "text", "description": "Specific source"},
                    {"name": "description", "type": "text", "description": "Evidence content"},
                ],
                "examples": [],
            },
        ]

        for ce in core_entities:
            if ce["name"] not in existing_entity_names:
                ontology["entity_types"].insert(0, ce)

        # 确保核心关系类型存在
        existing_edge_names = {et["name"] for et in ontology["edge_types"]}
        core_edges = [
            {
                "name": "CAUSED_BY",
                "description": "A was caused by B (core causal relationship)",
                "source_targets": [{"source": "Event", "target": "Event"}],
                "attributes": [
                    {"name": "confidence", "type": "text", "description": "Causal confidence 0.0-1.0"},
                    {"name": "causal_strength", "type": "text", "description": "Causal strength 0.0-1.0"},
                    {"name": "evidence_ids", "type": "text", "description": "Supporting evidence IDs"},
                ],
            },
            {
                "name": "SUPPORTED_BY",
                "description": "Conclusion A is supported by evidence B",
                "source_targets": [
                    {"source": "Event", "target": "Evidence"},
                ],
                "attributes": [
                    {"name": "confidence", "type": "text", "description": "Support confidence 0.0-1.0"},
                ],
            },
        ]

        for ce in core_edges:
            if ce["name"] not in existing_edge_names:
                ontology["edge_types"].insert(0, ce)

        # 为所有实体类型添加缺失的通用属性
        required_attrs = {"timestamp", "credibility_score", "source", "description"}
        for et in ontology["entity_types"]:
            existing_attrs = {a["name"] for a in et.get("attributes", [])}
            for attr_name in required_attrs:
                if attr_name not in existing_attrs:
                    et.setdefault("attributes", []).append({
                        "name": attr_name,
                        "type": "text",
                        "description": f"Auto-added: {attr_name}",
                    })

        return ontology

    def generate_with_retry(
        self,
        text: str,
        requirement: str = "分析该事件的因果链，找出根本原因",
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """带重试的本体生成（含 429 限流退避）"""
        import time
        last_error = None
        for attempt in range(max_retries):
            try:
                result = self.generate(text, requirement)
                # 基本验证
                if result.get("entity_types") and result.get("edge_types"):
                    return result
            except Exception as e:
                last_error = e
                error_str = str(e)
                # 429 限流：指数退避等待
                if "429" in error_str or "RateLimitExceeded" in error_str or "TooManyRequests" in error_str:
                    wait_time = (2 ** attempt) * 5  # 5s, 10s, 20s
                    import logging
                    logging.getLogger('traceback.ontology').warning(
                        f"429 限流，第 {attempt+1} 次重试，等待 {wait_time}s..."
                    )
                    time.sleep(wait_time)
                else:
                    time.sleep(2)
                continue

        raise RuntimeError(
            f"本体生成失败（已重试{max_retries}次）: {last_error}"
        )
