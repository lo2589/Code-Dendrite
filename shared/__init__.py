"""
shared - 共享基础设施
======================
提供缓存、类型定义等共享模块。
"""

from .cache import Cache, CacheStats
from .types import AnalysisReport, ScanResult, ErrorInfo
from .codedendrite_ignore import CodeDendriteIgnore, create_default_config
from .compat import normalize_path, path_matches

__all__ = [
    'Cache',
    'CacheStats',
    'AnalysisReport',
    'ScanResult',
    'ErrorInfo',
    'CodeDendriteIgnore',
    'create_default_config',
    'normalize_path',
    'path_matches',
]
