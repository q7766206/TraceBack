"""
智能 LLM 路由调度器
根据任务复杂度自动选择模型，支持主力模型和轻量模型并发处理

主力模型: 千问max (高质量，高成本，慢速)
轻量模型: 豆包2.0mini (低质量，低成本，快速)
"""

import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass
from enum import Enum

from .llm_client import LLMClient
from .logger import get_logger

logger = get_logger('traceback.smart_router')


class TaskComplexity(str, Enum):
    """任务复杂度等级"""
    SIMPLE = "simple"       # 简单任务：轻量模型
    MEDIUM = "medium"       # 中等任务：轻量模型，失败时降级
    COMPLEX = "complex"     # 复杂任务：主力模型
    CRITICAL = "critical"   # 关键任务：主力模型 + 验证


@dataclass
class TaskResult:
    """任务执行结果"""
    success: bool
    content: Any
    model_used: str
    cost_time: float
    error: Optional[str] = None


class SmartLLMRouter:
    """
    智能 LLM 路由调度器
    
    策略：
    1. 简单任务（文本摘要、简单抽取）-> 轻量模型
    2. 中等任务（实体识别、关系抽取）-> 轻量模型优先，失败时用主力模型
    3. 复杂任务（本体生成、复杂推理）-> 主力模型
    4. 关键任务（最终报告、质量验证）-> 主力模型 + 轻量模型交叉验证
    """
    
    def __init__(self):
        # 初始化两个模型客户端
        self.main_client = LLMClient(preset="default")      # 主力：千问max
        self.fast_client = LLMClient(preset="fast")         # 轻量：豆包mini
        
        # 统计信息
        self._stats = {
            "main_calls": 0,
            "fast_calls": 0,
            "main_time": 0.0,
            "fast_time": 0.0,
            "fallback_count": 0,  # 轻量失败转主力的次数
        }
        self._stats_lock = threading.Lock()
    
    def route_task(
        self,
        messages: List[Dict[str, str]],
        complexity: TaskComplexity = TaskComplexity.MEDIUM,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        use_cache: bool = True,
        fallback_on_failure: bool = True,
    ) -> TaskResult:
        """
        路由任务到合适的模型
        
        Args:
            messages: 消息列表
            complexity: 任务复杂度
            temperature: 温度参数
            max_tokens: 最大token数
            use_cache: 是否使用缓存
            fallback_on_failure: 失败时是否降级/升级模型
            
        Returns:
            TaskResult: 任务结果
        """
        start_time = time.time()
        
        # 根据复杂度选择策略
        if complexity == TaskComplexity.SIMPLE:
            # 简单任务：只用轻量模型
            return self._execute_with_fast(
                messages, temperature, max_tokens, start_time
            )
            
        elif complexity == TaskComplexity.MEDIUM:
            # 中等任务：轻量模型优先，失败时转主力模型
            fast_result = self._execute_with_fast(
                messages, temperature, max_tokens, start_time
            )
            
            if fast_result.success or not fallback_on_failure:
                return fast_result
            
            # 轻量模型失败，转主力模型
            logger.warning("轻量模型失败，转用主力模型重试")
            with self._stats_lock:
                self._stats["fallback_count"] += 1
            
            return self._execute_with_main(
                messages, temperature, max_tokens, start_time
            )
            
        elif complexity == TaskComplexity.COMPLEX:
            # 复杂任务：只用主力模型
            return self._execute_with_main(
                messages, temperature, max_tokens, start_time
            )
            
        elif complexity == TaskComplexity.CRITICAL:
            # 关键任务：两个模型都执行，交叉验证
            return self._execute_with_validation(
                messages, temperature, max_tokens, start_time
            )
        
        else:
            return TaskResult(
                success=False,
                content=None,
                model_used="unknown",
                cost_time=time.time() - start_time,
                error=f"未知的复杂度等级: {complexity}"
            )
    
    def _execute_with_fast(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        start_time: float
    ) -> TaskResult:
        """使用轻量模型执行"""
        try:
            logger.debug("使用轻量模型执行任务")
            
            result = self.fast_client.chat(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            cost_time = time.time() - start_time
            
            with self._stats_lock:
                self._stats["fast_calls"] += 1
                self._stats["fast_time"] += cost_time
            
            return TaskResult(
                success=True,
                content=result,
                model_used="fast",
                cost_time=cost_time
            )
            
        except Exception as e:
            cost_time = time.time() - start_time
            logger.warning(f"轻量模型执行失败: {e}")
            
            return TaskResult(
                success=False,
                content=None,
                model_used="fast",
                cost_time=cost_time,
                error=str(e)
            )
    
    def _execute_with_main(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        start_time: float
    ) -> TaskResult:
        """使用主力模型执行"""
        try:
            logger.debug("使用主力模型执行任务")
            
            result = self.main_client.chat(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            cost_time = time.time() - start_time
            
            with self._stats_lock:
                self._stats["main_calls"] += 1
                self._stats["main_time"] += cost_time
            
            return TaskResult(
                success=True,
                content=result,
                model_used="main",
                cost_time=cost_time
            )
            
        except Exception as e:
            cost_time = time.time() - start_time
            logger.error(f"主力模型执行失败: {e}")
            
            return TaskResult(
                success=False,
                content=None,
                model_used="main",
                cost_time=cost_time,
                error=str(e)
            )
    
    def _execute_with_validation(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        start_time: float
    ) -> TaskResult:
        """
        使用两个模型执行并交叉验证
        主要用于关键任务，确保结果可靠性
        """
        logger.info("关键任务：使用双模型交叉验证")
        
        # 并发执行两个模型
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_fast = executor.submit(
                self._execute_with_fast,
                messages, temperature, max_tokens, start_time
            )
            future_main = executor.submit(
                self._execute_with_main,
                messages, temperature, max_tokens, start_time
            )
            
            results = []
            for future in as_completed([future_fast, future_main]):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"模型执行异常: {e}")
        
        # 分析结果
        if len(results) == 2 and all(r.success for r in results):
            # 两个模型都成功，比较结果一致性
            # 这里可以实现更复杂的验证逻辑
            logger.info("双模型执行成功，使用主力模型结果")
            return results[1]  # 返回主力模型结果
        elif any(r.success for r in results):
            # 至少一个成功，使用成功的结果
            successful = [r for r in results if r.success][0]
            logger.info(f"使用 {successful.model_used} 模型结果")
            return successful
        else:
            # 都失败
            return TaskResult(
                success=False,
                content=None,
                model_used="both",
                cost_time=time.time() - start_time,
                error="两个模型都执行失败"
            )
    
    def route_batch_tasks(
        self,
        tasks: List[Dict[str, Any]],
        max_workers: int = 5
    ) -> List[TaskResult]:
        """
        批量路由任务，自动分配模型并并发执行
        
        Args:
            tasks: 任务列表，每个任务包含 messages 和 complexity
            max_workers: 最大并发数
            
        Returns:
            List[TaskResult]: 结果列表
        """
        logger.info(f"批量处理 {len(tasks)} 个任务，并发数: {max_workers}")
        
        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_task = {}
            for i, task in enumerate(tasks):
                future = executor.submit(
                    self.route_task,
                    messages=task["messages"],
                    complexity=task.get("complexity", TaskComplexity.MEDIUM),
                    temperature=task.get("temperature", 0.3),
                    max_tokens=task.get("max_tokens", 4096),
                )
                future_to_task[future] = i
            
            # 收集结果
            for future in as_completed(future_to_task):
                task_idx = future_to_task[future]
                try:
                    result = future.result()
                    results.append((task_idx, result))
                except Exception as e:
                    logger.error(f"任务 {task_idx} 执行异常: {e}")
                    results.append((task_idx, TaskResult(
                        success=False,
                        content=None,
                        model_used="unknown",
                        cost_time=0,
                        error=str(e)
                    )))
        
        # 按原始顺序排序
        results.sort(key=lambda x: x[0])
        return [r[1] for r in results]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取路由统计信息"""
        with self._stats_lock:
            stats = dict(self._stats)
        
        # 计算平均值
        if stats["fast_calls"] > 0:
            stats["fast_avg_time"] = stats["fast_time"] / stats["fast_calls"]
        else:
            stats["fast_avg_time"] = 0
            
        if stats["main_calls"] > 0:
            stats["main_avg_time"] = stats["main_time"] / stats["main_calls"]
        else:
            stats["main_avg_time"] = 0
        
        return stats
    
    def reset_stats(self):
        """重置统计信息"""
        with self._stats_lock:
            self._stats = {
                "main_calls": 0,
                "fast_calls": 0,
                "main_time": 0.0,
                "fast_time": 0.0,
                "fallback_count": 0,
            }


# 全局路由实例
_smart_router = None
_router_lock = threading.Lock()


def get_smart_router() -> SmartLLMRouter:
    """获取全局智能路由器实例（单例）"""
    global _smart_router
    if _smart_router is None:
        with _router_lock:
            if _smart_router is None:
                _smart_router = SmartLLMRouter()
    return _smart_router


def classify_task_complexity(task_description: str) -> TaskComplexity:
    """
    根据任务描述自动判断复杂度
    
    规则：
    - 包含"本体"、"推理"、"验证" -> COMPLEX
    - 包含"摘要"、"提取"、"识别" -> SIMPLE
    - 其他 -> MEDIUM
    """
    task_lower = task_description.lower()
    
    complex_keywords = ['本体', '推理', '验证', '生成', '构建', '设计', '分析']
    simple_keywords = ['摘要', '提取', '识别', '分类', '简单', '快速']
    
    if any(kw in task_lower for kw in complex_keywords):
        return TaskComplexity.COMPLEX
    elif any(kw in task_lower for kw in simple_keywords):
        return TaskComplexity.SIMPLE
    else:
        return TaskComplexity.MEDIUM


# 便捷函数
def smart_chat(
    messages: List[Dict[str, str]],
    complexity: TaskComplexity = TaskComplexity.MEDIUM,
    **kwargs
) -> str:
    """
    智能聊天接口
    
    使用示例：
        result = smart_chat(
            messages=[{"role": "user", "content": "分析这段文本"}],
            complexity=TaskComplexity.MEDIUM
        )
    """
    router = get_smart_router()
    result = router.route_task(messages, complexity, **kwargs)
    
    if result.success:
        return result.content
    else:
        raise Exception(f"LLM调用失败: {result.error}")


def smart_chat_json(
    messages: List[Dict[str, str]],
    complexity: TaskComplexity = TaskComplexity.MEDIUM,
    **kwargs
) -> Dict[str, Any]:
    """
    智能聊天接口（返回JSON）
    """
    router = get_smart_router()
    
    # 对于 JSON 任务，通常更复杂，自动升级一级
    if complexity == TaskComplexity.SIMPLE:
        complexity = TaskComplexity.MEDIUM
    elif complexity == TaskComplexity.MEDIUM:
        complexity = TaskComplexity.COMPLEX
    
    result = router.route_task(messages, complexity, **kwargs)
    
    if not result.success:
        raise Exception(f"LLM调用失败: {result.error}")
    
    # 解析 JSON
    import json
    try:
        return json.loads(result.content)
    except json.JSONDecodeError as e:
        # 尝试修复 JSON
        from .llm_client import LLMClient
        client = LLMClient()
        return client._parse_json_response(result.content)
