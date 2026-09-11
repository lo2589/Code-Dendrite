"""
cache.py - 缓存系统
====================
提供通用缓存功能。
"""

import time
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Callable
from threading import Lock


@dataclass
class CacheStats:
    """缓存统计"""
    hits: int = 0
    misses: int = 0
    size: int = 0
    max_size: int = 0
    evictions: int = 0
    
    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    def to_dict(self) -> dict:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": f"{self.hit_rate:.1%}",
            "size": self.size,
            "max_size": self.max_size,
            "evictions": self.evictions
        }


class Cache:
    """
    通用缓存实现
    
    特性:
    - 支持TTL（过期时间）
    - 支持最大容量限制
    - 线程安全
    - LRU淘汰策略
    """
    
    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: Optional[float] = None
    ):
        """
        初始化缓存
        
        参数:
            max_size: 最大缓存条目数
            default_ttl: 默认过期时间（秒），None表示永不过期
        """
        self._cache: Dict[str, Dict] = {}
        self._access_order: Dict[str, float] = {}  # key -> 最后访问时间
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._lock = Lock()
        self._stats = CacheStats(max_size=max_size)
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取缓存值
        
        参数:
            key: 缓存键
            default: 默认值
        
        返回:
            缓存值，不存在或过期返回default
        """
        with self._lock:
            if key not in self._cache:
                self._stats.misses += 1
                return default
            
            entry = self._cache[key]
            
            # 检查过期
            if entry.get("expires_at") and time.time() > entry["expires_at"]:
                del self._cache[key]
                if key in self._access_order:
                    del self._access_order[key]
                self._stats.misses += 1
                self._stats.size = len(self._cache)
                return default
            
            # 更新访问时间
            self._access_order[key] = time.time()
            entry["hits"] = entry.get("hits", 0) + 1
            self._stats.hits += 1
            
            return entry["value"]
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None
    ):
        """
        设置缓存值
        
        参数:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒），None使用默认TTL
        """
        with self._lock:
            # 检查容量
            if len(self._cache) >= self._max_size and key not in self._cache:
                self._evict()
            
            ttl = ttl if ttl is not None else self._default_ttl
            expires_at = time.time() + ttl if ttl else None
            
            self._cache[key] = {
                "value": value,
                "created_at": time.time(),
                "expires_at": expires_at,
                "hits": 0
            }
            self._access_order[key] = time.time()
            self._stats.size = len(self._cache)
    
    def delete(self, key: str) -> bool:
        """
        删除缓存条目
        
        返回:
            是否成功删除
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                if key in self._access_order:
                    del self._access_order[key]
                self._stats.size = len(self._cache)
                return True
            return False
    
    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._access_order.clear()
            self._stats.size = 0
    
    def get_or_compute(
        self,
        key: str,
        compute_fn: Callable[[], Any],
        ttl: Optional[float] = None
    ) -> Any:
        """
        获取缓存值，不存在则计算并缓存
        
        参数:
            key: 缓存键
            compute_fn: 计算函数
            ttl: 过期时间
        
        返回:
            缓存值或计算结果
        """
        value = self.get(key)
        if value is not None:
            return value
        
        # 计算并缓存
        value = compute_fn()
        if value is not None:
            self.set(key, value, ttl)
        
        return value
    
    def _evict(self):
        """淘汰最久未访问的条目（LRU）"""
        if not self._access_order:
            return
        
        # 找到最久未访问的key
        oldest_key = min(self._access_order, key=self._access_order.get)
        
        if oldest_key in self._cache:
            del self._cache[oldest_key]
        if oldest_key in self._access_order:
            del self._access_order[oldest_key]
        
        self._stats.evictions += 1
    
    def cleanup_expired(self) -> int:
        """
        清理过期条目
        
        返回:
            清理的条目数
        """
        count = 0
        now = time.time()
        
        with self._lock:
            expired_keys = []
            for key, entry in self._cache.items():
                if entry.get("expires_at") and now > entry["expires_at"]:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self._cache[key]
                if key in self._access_order:
                    del self._access_order[key]
                count += 1
            
            self._stats.size = len(self._cache)
        
        return count
    
    @property
    def stats(self) -> CacheStats:
        """获取缓存统计"""
        self._stats.size = len(self._cache)
        return self._stats
    
    def __len__(self) -> int:
        return len(self._cache)
    
    def __contains__(self, key: str) -> bool:
        with self._lock:
            if key not in self._cache:
                return False
            entry = self._cache[key]
            if entry.get("expires_at") and time.time() > entry["expires_at"]:
                return False
            return True


class LayeredCache:
    """
    分层缓存
    
    为不同分析层提供独立的缓存。
    """
    
    def __init__(self):
        self._layers: Dict[str, Cache] = {}
    
    def get_layer(self, name: str, max_size: int = 500) -> Cache:
        """获取或创建分层缓存"""
        if name not in self._layers:
            self._layers[name] = Cache(max_size=max_size)
        return self._layers[name]
    
    def clear_all(self):
        """清空所有层的缓存"""
        for cache in self._layers.values():
            cache.clear()
    
    def get_all_stats(self) -> Dict[str, CacheStats]:
        """获取所有层的统计"""
        return {name: cache.stats for name, cache in self._layers.items()}
