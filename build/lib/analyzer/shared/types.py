"""
types.py - 共享类型定义
========================
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Literal
from datetime import datetime


@dataclass
class ErrorInfo:
    """错误信息"""
    error_type: str
    message: str
    file: Optional[str] = None
    line: Optional[int] = None
    column: Optional[int] = None
    traceback: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "error_type": self.error_type,
            "message": self.message,
            "file": self.file,
            "line": self.line,
            "column": self.column
        }


@dataclass
class AnalysisReport:
    """分析报告"""
    # 基本信息
    target: str                        # 分析目标（文件/函数/符号）
    analysis_type: str                 # 分析类型
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # 分析结果
    findings: List[Dict] = field(default_factory=list)
    errors: List[ErrorInfo] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    
    # 统计
    elapsed_ms: int = 0
    layers_used: List[str] = field(default_factory=list)  # 使用的分析层
    
    # 严重程度
    severity: str = "low"              # "low" | "medium" | "high" | "critical"
    
    def to_dict(self) -> dict:
        return {
            "target": self.target,
            "analysis_type": self.analysis_type,
            "timestamp": self.timestamp,
            "findings": self.findings,
            "errors": [e.to_dict() for e in self.errors],
            "suggestions": self.suggestions,
            "elapsed_ms": self.elapsed_ms,
            "layers_used": self.layers_used,
            "severity": self.severity
        }
    
    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0
    
    @property
    def is_critical(self) -> bool:
        return self.severity == "critical"


@dataclass
class ScanResult:
    """项目扫描结果"""
    # 基本信息
    root_path: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # 扫描统计
    total_files: int = 0
    scanned_files: int = 0
    skipped_files: int = 0
    
    # 语言分布
    languages: Dict[str, int] = field(default_factory=dict)  # {语言: 文件数}
    
    # 发现
    classes_count: int = 0
    functions_count: int = 0
    anchors_count: int = 0
    
    # 问题
    issues: List[Dict] = field(default_factory=list)
    
    # 性能
    elapsed_ms: int = 0
    
    def to_dict(self) -> dict:
        return {
            "root_path": self.root_path,
            "timestamp": self.timestamp,
            "total_files": self.total_files,
            "scanned_files": self.scanned_files,
            "skipped_files": self.skipped_files,
            "languages": self.languages,
            "classes_count": self.classes_count,
            "functions_count": self.functions_count,
            "anchors_count": self.anchors_count,
            "issues": self.issues,
            "elapsed_ms": self.elapsed_ms
        }


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    value: Any
    created_at: float                  # 时间戳
    expires_at: Optional[float] = None # 过期时间戳
    hits: int = 0
    
    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        import time
        return time.time() > self.expires_at


@dataclass
class Anchor:
    """统一锚点数据结构，整合所有模块输出"""
    # 基础（codeAnalysis）
    id: str                              # 唯一标识：file::symbol
    symbol: str
    file: str                            # 相对路径
    line_start: int
    line_end: int
    hash: str                            # 结构哈希
    column_start: int = 0
    column_end: int = 0
    qualified_name: str = ""
    signature: str = ""
    imports: List[str] = field(default_factory=list)
    code: str = ""                       # 代码体（codeGenome）
    # 调用关系（codeGenome + dataFlow）
    callers: List[str] = field(default_factory=list)
    callees: List[str] = field(default_factory=list)
    call_sites: List[dict] = field(default_factory=list)
    inputs: List[dict] = field(default_factory=list)
    outputs: List[dict] = field(default_factory=list)
    # 继承关系（inheritance / cpp_inheritance）
    parent_classes: List[str] = field(default_factory=list)
    overrides: Optional[str] = None
    overridden_by: List[str] = field(default_factory=list)
    mro: List[str] = field(default_factory=list)
    own_methods: List[str] = field(default_factory=list)       # 自身方法 nid 列表（class anchor 专用）
    effective_methods: Dict[str, str] = field(default_factory=dict)  # {method_name: nid}，含继承
    # AI 记忆（anchorMemory）
    observations: List[str] = field(default_factory=list)
    # 基础字段
    language: str = "python"
    symbol_type: str = "function"        # function / class / method
    description: str = ""
    drift: str = "ok"                    # ok / stale / missing_symbol / missing_file
    is_virtual: bool = False
    virtual_kind: Optional[str] = None   # condition / loop / try
    parent_anchor: Optional[str] = None
    scope_label: Optional[str] = None
    block_metadata: Dict[str, Any] = field(default_factory=dict)
    registered_as: Optional[str] = None  # @register_io("name") 注册的 io 名


EdgeType = Literal[
    "call", "inherit", "dataflow", "impact", "dispatch", "config",
    "http", "ffi", "process", "sql",
]


@dataclass
class Edge:
    """代码关系边：file::symbol → file::symbol"""
    from_id: str          # file::symbol（调用方/子类）
    to_id: str            # file::symbol（被调用方/父类）
    edge_type: EdgeType   # call / inherit / dataflow / impact / dispatch
    data_in: str = ""     # 传入数据类型描述
    data_out: str = ""    # 传出数据类型描述
    outer_hash: str = ""  # 两端节点的联合哈希，用于漂移检测
    # dispatch 边专用字段
    condition: Optional[str] = None       # 条件表达式，如 'method == "chat_message"'
    dispatch_key: Optional[str] = None    # 分发键，如 'method'
    dispatch_value: Optional[str] = None  # 分发值，如 'chat_message'
    is_conditional: bool = False          # 是否为条件边
    scope_label: Optional[str] = None     # body / case:0 / default / finally
    seq: List[int] = field(default_factory=list)  # 在 caller.callees 中的位置序号（重复调用有多个）
    call_line: int = 0
    call_column: int = 0
    resolution: str = "exact"             # exact / possible / unresolved
    evidence: str = ""
    bridge_kind: Optional[str] = None
