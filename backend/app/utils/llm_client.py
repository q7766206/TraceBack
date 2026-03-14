"""
LLM客户端封装 v3 — 多模型架构
支持主力模型(default)、推理模型(reasoning)、轻量模型(fast)三种预设
内置全局速率限制器，防止 429 限流打爆后端
"""

import json
import re
import time
import threading
from typing import Optional, Dict, Any, List
from openai import OpenAI

from ..config import Config
from .logger import get_logger

logger = get_logger('traceback.llm')

# 全局 LLM 调用统计（线程安全）
_llm_stats_lock = threading.Lock()
_llm_stats = {"total_calls": 0, "total_time": 0.0, "errors": 0}


def get_llm_stats() -> Dict[str, Any]:
    """获取 LLM 调用统计"""
    with _llm_stats_lock:
        return dict(_llm_stats)


# ============== 全局速率限制器 ==============
class _RateLimiter:
    """简单的令牌桶限流器，限制每分钟请求数"""
    def __init__(self, rpm: int = 15):
        self._lock = threading.Lock()
        self._rpm = rpm
        self._interval = 60.0 / rpm  # 两次请求之间的最小间隔
        self._last_call = 0.0

    def acquire(self):
        """阻塞等待直到可以发送下一个请求"""
        with self._lock:
            now = time.time()
            wait = self._last_call + self._interval - now
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.time()

# 全局限流器：每分钟最多 5 个请求（保守值，确保不触发 429）
_global_limiter = _RateLimiter(rpm=5)


# ============== 预设配置映射 ==============
_PRESETS = {
    "default": {
        "api_key": lambda: Config.LLM_API_KEY,
        "base_url": lambda: Config.LLM_BASE_URL,
        "model": lambda: Config.LLM_MODEL_NAME,
    },
    "reasoning": {
        "api_key": lambda: Config.LLM_REASONING_API_KEY,
        "base_url": lambda: Config.LLM_REASONING_BASE_URL,
        "model": lambda: Config.LLM_REASONING_MODEL_NAME,
    },
    "fast": {
        "api_key": lambda: Config.LLM_FAST_API_KEY,
        "base_url": lambda: Config.LLM_FAST_BASE_URL,
        "model": lambda: Config.LLM_FAST_MODEL_NAME,
    },
}


class LLMClient:
    """LLM客户端 - 内置重试和超时，支持多模型预设"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        preset: str = "default",
    ):
        """
        Args:
            api_key/base_url/model: 显式指定时优先使用
            preset: 预设名称 "default" | "reasoning" | "fast"
        """
        p = _PRESETS.get(preset, _PRESETS["default"])
        self.api_key = api_key or p["api_key"]()
        self.base_url = base_url or p["base_url"]()
        self.model = model or p["model"]()
        
        if not self.api_key:
            raise ValueError(f"LLM API Key 未配置 (preset={preset})")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=120.0,
            max_retries=2,
        )
        
        logger.info(f"LLMClient 初始化: preset={preset}, model={self.model}, base_url={self.base_url[:40]}...")
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None,
    ) -> str:
        """
        发送聊天请求
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            response_format: 响应格式
            
        Returns:
            LLM响应文本
        """
        global _llm_stats
        
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        if response_format:
            kwargs["response_format"] = response_format
        
        start_time = time.time()
        last_error = None
        
        # 全局速率限制：等待令牌
        _global_limiter.acquire()
        
        # 应用层重试（覆盖 JSON 解析失败等非网络错误）
        for attempt in range(3):
            try:
                response = self.client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content
                # 部分模型会在content中包含<think>思考内容，需要移除
                content = re.sub(r'<think>[\s\S]*?</think>', '', content).strip()
                
                elapsed = time.time() - start_time
                with _llm_stats_lock:
                    _llm_stats["total_calls"] += 1
                    _llm_stats["total_time"] += elapsed
                
                if elapsed > 30:
                    logger.warning(f"LLM 调用耗时 {elapsed:.1f}s（较慢）")
                
                return content
                
            except Exception as e:
                last_error = e
                with _llm_stats_lock:
                    _llm_stats["errors"] += 1
                
                err_str = str(e)
                
                # 400 类客户端错误（参数不支持等）不重试，直接抛出
                if "Error code: 400" in err_str or "Error code: 401" in err_str or "Error code: 403" in err_str:
                    logger.error(f"LLM 客户端错误，不重试: {err_str[:200]}")
                    raise
                
                # 429 限流：指数退避，等待更长时间
                if "429" in err_str or "RateLimitExceeded" in err_str or "TooManyRequests" in err_str:
                    wait = (2 ** attempt) * 8  # 8s, 16s, 32s
                    logger.warning(f"LLM 429 限流（第{attempt+1}次），{wait}s后重试: {err_str[:200]}")
                    time.sleep(wait)
                elif attempt < 2:
                    wait = (attempt + 1) * 2
                    logger.warning(f"LLM 调用失败（第{attempt+1}次），{wait}s后重试: {str(e)[:200]}")
                    time.sleep(wait)
                else:
                    logger.error(f"LLM 调用3次均失败: {str(e)[:300]}")
                    raise
        
        raise last_error  # 不应到达此处
    
    # 记录不支持 json_object 的模型，避免重复尝试
    _no_json_format_models = set()

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        """
        发送聊天请求并返回JSON
        先尝试 response_format=json_object，若模型不支持则回退到纯 prompt 模式
        已知不支持的模型会直接跳过第一次尝试
        """
        # 构造纯 prompt 回退的消息
        def _make_fallback_messages():
            fb = [m.copy() for m in messages]
            if fb:
                fb[-1]["content"] = fb[-1]["content"] + "\n\n请严格以JSON格式返回结果，不要包含任何其他文字说明。"
            return fb

        # 如果模型已知不支持 json_object，直接走纯 prompt
        if self.model in self._no_json_format_models:
            response = self.chat(
                messages=_make_fallback_messages(),
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return self._parse_json_response(response)

        # 第一次尝试：带 response_format
        try:
            response = self.chat(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"}
            )
            return self._parse_json_response(response)
        except Exception as e:
            err_str = str(e)
            # 如果是 response_format 不支持，记住并回退到纯 prompt 模式
            if "response_format" in err_str or "json_object" in err_str:
                self._no_json_format_models.add(self.model)
                logger.warning(f"模型 {self.model} 不支持 response_format=json_object，已标记，后续直接走纯prompt模式")
                response = self.chat(
                    messages=_make_fallback_messages(),
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return self._parse_json_response(response)
            else:
                raise
    
    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """从 LLM 响应中提取并解析 JSON，多重容错"""
        cleaned = response.strip()
        
        # 1. 移除 markdown 代码块标记
        cleaned = re.sub(r'^```(?:json)?\s*\n?', '', cleaned, flags=re.IGNORECASE)
        # 移除末尾的 ``` 标记
        fence_end = re.compile(r'\n?```\s*\Z')
        cleaned = fence_end.sub('', cleaned)
        cleaned = cleaned.strip()
        
        # 2. 直接尝试解析
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
        
        # 3. 尝试提取第一个 {...} 或 [...]
        obj_match = re.search(r'\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\}', cleaned, re.DOTALL)
        if obj_match:
            try:
                return json.loads(obj_match.group())
            except json.JSONDecodeError:
                pass
        
        # 4. 更激进：找到第一个 { 和最后一个 } 之间的内容
        first_brace = cleaned.find('{')
        last_brace = cleaned.rfind('}')
        if first_brace != -1 and last_brace > first_brace:
            candidate = cleaned[first_brace:last_brace + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                # 修复常见问题：尾部多余逗号
                candidate_fixed = re.sub(r',\s*([}\]])', r'\1', candidate)
                try:
                    return json.loads(candidate_fixed)
                except json.JSONDecodeError:
                    pass
        
        # 5. 尝试数组
        first_bracket = cleaned.find('[')
        last_bracket = cleaned.rfind(']')
        if first_bracket != -1 and last_bracket > first_bracket:
            candidate = cleaned[first_bracket:last_bracket + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass
        
        logger.error(f"JSON解析彻底失败，原始响应前500字符: {cleaned[:500]}")
        raise ValueError(f"LLM返回的JSON格式无效: {cleaned[:200]}")
