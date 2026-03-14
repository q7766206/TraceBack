"""
TraceBack 搜索工具封装 v2
支持多种搜索引擎：Bocha（国产直连）、Tavily、DuckDuckGo（免费兜底）、Serper
新增：LRU缓存层 + URL抓取缓存 + 超时控制

ArchiveHunter Agent 通过此模块进行历史数据搜索
"""

import json
import time
import hashlib
import threading
import requests
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger('traceback.search')


# ═══════════════════════════════════════════════════════════════
# 全局缓存（进程级，线程安全）
# ═══════════════════════════════════════════════════════════════

_search_cache: Dict[str, List] = {}       # query_hash -> results
_fetch_cache: Dict[str, str] = {}         # url -> content
_cache_lock = threading.Lock()
_SEARCH_CACHE_MAX = 200
_FETCH_CACHE_MAX = 100


def _cache_key(query: str, max_results: int) -> str:
    """生成缓存键"""
    return hashlib.md5(f"{query}||{max_results}".encode()).hexdigest()


def clear_search_cache():
    """清空搜索缓存（供外部调用）"""
    global _search_cache, _fetch_cache
    with _cache_lock:
        _search_cache.clear()
        _fetch_cache.clear()
    logger.info("搜索缓存已清空")


def get_cache_stats() -> Dict[str, int]:
    """获取缓存统计"""
    with _cache_lock:
        return {
            "search_cache_size": len(_search_cache),
            "fetch_cache_size": len(_fetch_cache),
        }


@dataclass
class SearchResult:
    """搜索结果"""
    title: str
    url: str
    snippet: str
    source: str = ""
    timestamp: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "source": self.source,
            "timestamp": self.timestamp,
        }


class SearchEngine:
    """搜索引擎统一接口（带缓存）"""
    
    def __init__(self, provider: str = None, api_key: str = None):
        self.provider = provider or Config.SEARCH_PROVIDER
        self.api_key = api_key or Config.SEARCH_API_KEY
        self.max_results = Config.SEARCH_MAX_RESULTS
    
    def search(self, query: str, max_results: int = None) -> List[SearchResult]:
        """
        执行搜索（带缓存）
        
        Args:
            query: 搜索关键词
            max_results: 最大结果数
            
        Returns:
            搜索结果列表
        """
        max_results = max_results or self.max_results
        
        # 检查缓存
        key = _cache_key(query, max_results)
        with _cache_lock:
            if key in _search_cache:
                logger.debug(f"搜索缓存命中: {query[:50]}")
                return _search_cache[key]
        
        # 执行实际搜索
        results = self._do_search(query, max_results)
        
        # 写入缓存
        with _cache_lock:
            if len(_search_cache) >= _SEARCH_CACHE_MAX:
                # 简单LRU：删除最早的一半
                keys = list(_search_cache.keys())
                for k in keys[:len(keys)//2]:
                    del _search_cache[k]
            _search_cache[key] = results
        
        return results
    
    def _do_search(self, query: str, max_results: int) -> List[SearchResult]:
        """实际执行搜索（无缓存）"""
        if self.provider == "bocha":
            return self._search_bocha(query, max_results)
        elif self.provider == "tavily":
            return self._search_tavily(query, max_results)
        elif self.provider == "serper":
            return self._search_serper(query, max_results)
        elif self.provider == "duckduckgo":
            return self._search_duckduckgo(query, max_results)
        else:
            logger.warning(f"未知搜索引擎: {self.provider}，回退到DuckDuckGo")
            return self._search_duckduckgo(query, max_results)
    
    def search_news(self, query: str, max_results: int = None) -> List[SearchResult]:
        """搜索新闻"""
        max_results = max_results or self.max_results
        
        if self.provider == "duckduckgo":
            return self._search_duckduckgo_news(query, max_results)
        else:
            # 其他引擎暂时用普通搜索代替
            return self.search(query, max_results)
    
    # ===== DuckDuckGo（默认，免费无需Key）=====
    
    def _search_duckduckgo(self, query: str, max_results: int) -> List[SearchResult]:
        """使用DuckDuckGo搜索"""
        try:
            from duckduckgo_search import DDGS
            
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results):
                    results.append(SearchResult(
                        title=r.get("title", ""),
                        url=r.get("href", ""),
                        snippet=r.get("body", ""),
                        source="DuckDuckGo",
                    ))
            
            logger.info(f"DuckDuckGo搜索 '{query}' 返回 {len(results)} 条结果")
            return results
            
        except ImportError:
            logger.error("duckduckgo-search 未安装，请运行: pip install duckduckgo-search")
            return []
        except Exception as e:
            logger.error(f"DuckDuckGo搜索失败: {e}")
            # 限流时等待后重试一次
            if "ratelimit" in str(e).lower():
                logger.info("DuckDuckGo限流，等待5秒后重试...")
                time.sleep(5)
                try:
                    from duckduckgo_search import DDGS
                    results = []
                    with DDGS() as ddgs:
                        for r in ddgs.text(query, max_results=max_results):
                            results.append(SearchResult(
                                title=r.get("title", ""),
                                url=r.get("href", ""),
                                snippet=r.get("body", ""),
                                source="DuckDuckGo",
                            ))
                    return results
                except Exception:
                    pass
            return []
    
    def _search_duckduckgo_news(self, query: str, max_results: int) -> List[SearchResult]:
        """使用DuckDuckGo搜索新闻"""
        try:
            from duckduckgo_search import DDGS
            
            results = []
            with DDGS() as ddgs:
                for r in ddgs.news(query, max_results=max_results):
                    results.append(SearchResult(
                        title=r.get("title", ""),
                        url=r.get("url", ""),
                        snippet=r.get("body", ""),
                        source=r.get("source", "DuckDuckGo News"),
                        timestamp=r.get("date", ""),
                    ))
            
            return results
            
        except Exception as e:
            logger.error(f"DuckDuckGo新闻搜索失败: {e}")
            return []
    
    # ===== Tavily（AI专用搜索引擎）=====
    
    def _search_tavily(self, query: str, max_results: int) -> List[SearchResult]:
        """使用Tavily搜索"""
        import os
        tavily_key = os.environ.get('TAVILY_API_KEY', self.api_key)
        if not tavily_key:
            logger.warning("Tavily API Key未配置，回退到DuckDuckGo")
            return self._search_duckduckgo(query, max_results)
        
        try:
            import requests
            
            resp = requests.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": tavily_key,
                    "query": query,
                    "max_results": max_results,
                    "search_depth": "advanced",
                    "include_answer": True,
                },
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()
            
            results = []
            for r in data.get("results", []):
                results.append(SearchResult(
                    title=r.get("title", ""),
                    url=r.get("url", ""),
                    snippet=r.get("content", ""),
                    source="Tavily",
                    timestamp=r.get("published_date", ""),
                ))
            
            logger.info(f"Tavily搜索 '{query}' 返回 {len(results)} 条结果")
            return results
            
        except Exception as e:
            logger.error(f"Tavily搜索失败: {e}，回退到DuckDuckGo")
            return self._search_duckduckgo(query, max_results)
    
    # ===== Serper.dev（注册送2500次免费）=====
    
    def _search_serper(self, query: str, max_results: int) -> List[SearchResult]:
        """使用Serper.dev搜索（Google结果）"""
        if not self.api_key:
            logger.warning("Serper API Key未配置，回退到DuckDuckGo")
            return self._search_duckduckgo(query, max_results)
        
        try:
            import requests
            
            resp = requests.post(
                "https://google.serper.dev/search",
                headers={
                    "X-API-KEY": self.api_key,
                    "Content-Type": "application/json",
                },
                json={"q": query, "num": max_results},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            
            results = []
            for r in data.get("organic", []):
                results.append(SearchResult(
                    title=r.get("title", ""),
                    url=r.get("link", ""),
                    snippet=r.get("snippet", ""),
                    source="Google (Serper)",
                ))
            
            logger.info(f"Serper搜索 '{query}' 返回 {len(results)} 条结果")
            return results
            
        except Exception as e:
            logger.error(f"Serper搜索失败: {e}，回退到DuckDuckGo")
            return self._search_duckduckgo(query, max_results)
    
    # ===== Bocha 博查（国产，中国直连）=====
    
    def _search_bocha(self, query: str, max_results: int) -> List[SearchResult]:
        """使用博查搜索API"""
        if not self.api_key:
            logger.warning("Bocha API Key未配置，回退到DuckDuckGo")
            return self._search_duckduckgo(query, max_results)
        
        try:
            import requests
            
            resp = requests.post(
                "https://api.bochaai.com/v1/web-search",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "query": query,
                    "freshness": "noLimit",
                    "summary": True,
                    "count": max_results,
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            
            results = []
            for r in data.get("data", {}).get("webPages", {}).get("value", []):
                results.append(SearchResult(
                    title=r.get("name", ""),
                    url=r.get("url", ""),
                    snippet=r.get("summary", r.get("snippet", "")),
                    source="Bocha",
                    timestamp=r.get("dateLastCrawled", ""),
                ))
            
            logger.info(f"Bocha搜索 '{query}' 返回 {len(results)} 条结果")
            return results
            
        except Exception as e:
            logger.error(f"Bocha搜索失败: {e}，回退到DuckDuckGo")
            return self._search_duckduckgo(query, max_results)

    # ===== URL 内容抓取（带缓存） =====

    def fetch_url_content(self, url: str, max_chars: int = 4000, timeout: int = 10) -> Optional[str]:
        """
        抓取URL内容（带缓存，带超时）
        
        Args:
            url: 目标URL
            max_chars: 最大返回字符数
            timeout: 超时秒数
            
        Returns:
            网页文本内容，失败返回None
        """
        if not url or not url.startswith("http"):
            return None
        
        # 检查缓存
        with _cache_lock:
            if url in _fetch_cache:
                cached = _fetch_cache[url]
                return cached[:max_chars] if cached else None
        
        try:
            resp = requests.get(
                url,
                timeout=timeout,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
                allow_redirects=True,
            )
            resp.raise_for_status()
            
            # 简单提取文本
            from html.parser import HTMLParser
            
            class TextExtractor(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.texts = []
                    self._skip = False
                    self._skip_tags = {'script', 'style', 'nav', 'footer', 'header'}
                
                def handle_starttag(self, tag, attrs):
                    if tag in self._skip_tags:
                        self._skip = True
                
                def handle_endtag(self, tag):
                    if tag in self._skip_tags:
                        self._skip = False
                
                def handle_data(self, data):
                    if not self._skip:
                        text = data.strip()
                        if text:
                            self.texts.append(text)
            
            extractor = TextExtractor()
            extractor.feed(resp.text)
            content = "\n".join(extractor.texts)
            
            # 写入缓存
            with _cache_lock:
                if len(_fetch_cache) >= _FETCH_CACHE_MAX:
                    keys = list(_fetch_cache.keys())
                    for k in keys[:len(keys)//2]:
                        del _fetch_cache[k]
                _fetch_cache[url] = content
            
            return content[:max_chars] if content else None
            
        except Exception as e:
            logger.debug(f"URL抓取失败 {url[:80]}: {str(e)[:100]}")
            # 缓存失败结果避免重复请求
            with _cache_lock:
                _fetch_cache[url] = ""
            return None


# 便捷函数
def web_search(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """快捷搜索函数，返回字典列表"""
    engine = SearchEngine()
    results = engine.search(query, max_results)
    return [r.to_dict() for r in results]


def web_search_news(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """快捷新闻搜索函数"""
    engine = SearchEngine()
    results = engine.search_news(query, max_results)
    return [r.to_dict() for r in results]
