"""
shared - 共享基础设施
======================
提供缓存、类型定义等共享模块。
"""

from base.shared.cache import Cache, CacheStats
from base.shared.types import AnalysisReport, ScanResult, ErrorInfo
from base.shared.codedendrite_ignore import CodeDendriteIgnore, create_default_config
from base.shared.compat import normalize_path, path_matches
from base.shared.dblock import db_lock

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
