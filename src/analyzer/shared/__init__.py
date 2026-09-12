"""
shared - 共享基础设施
======================
提供缓存、类型定义等共享模块。
"""

from analyzer.shared.cache import Cache, CacheStats
from analyzer.shared.types import AnalysisReport, ScanResult, ErrorInfo
from analyzer.shared.codedendrite_ignore import CodeDendriteIgnore, create_default_config
from analyzer.shared.compat import normalize_path, path_matches
from analyzer.shared.dblock import db_lock

__all__ = [
    'Cache',
    'CacheStats',
    'AnalysisReport',
    'ScanResult',
    'ErrorInfo',
    'CodeDendriteIgnore',
    'create_default_config',
    'db_lock',
    'normalize_path',
    'path_matches',
]
