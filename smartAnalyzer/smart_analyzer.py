"""
smart_analyzer.py - 智能代码分析器 (Medium L5-001)
====================================================
统一入口，整合所有分析层。
"""

import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Any

# 添加父目录到路径
_PARENT = Path(__file__).parent.parent
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))

from shared.cache import Cache, LayeredCache, CacheStats
from shared.types import AnalysisReport, ScanResult, ErrorInfo
from shared.codedendrite_ignore import CodeDendriteIgnore
from api.anchors import load_anchors, get_anchor


# 按需激活规则
LAYERS_CONFIG = {
    "low": ["L1_Hash", "L2_AnchorRepair"],
    "medium": ["L1_Hash", "L2_AnchorRepair", "L3_Inheritance"],
    "high": ["L1_Hash", "L2_AnchorRepair", "L3_Inheritance", "L4_DataFlow"],
    "critical": ["L1_Hash", "L2_AnchorRepair", "L3_Inheritance", "L4_DataFlow"]
}


class SmartCodeAnalyzer:
    """
    智能代码分析器 (Medium L5-001)
    
    整合L1-L4所有分析层，根据需求按需调用。
    """
    
    def __init__(self, project_root: str):
        """
        初始化分析器
        
        参数:
            project_root: 项目根目录
        """
        self.root = Path(project_root)
        self._cache = LayeredCache()
        
        # 加载忽略规则
        self._ignore_rules = CodeDendriteIgnore(str(self.root))
        
        # 延迟加载各层
        self._l1_hash = None
        self._l2_anchor = None
        self._l3_inheritance = None
        self._l4_dataflow = None
        
        # 类索引缓存
        self._class_index = None
    
    @property
    def l1_hash(self):
        """懒加载已生成的 anchors（替代直接访问 HashDatabase）"""
        if self._l1_hash is None:
            try:
                self._l1_hash = load_anchors(str(self.root))
            except FileNotFoundError:
                self._l1_hash = {}
        return self._l1_hash
    
    @property
    def l3_class_index(self):
        """懒加载类索引"""
        if self._class_index is None:
            from inheritance import build_class_index
            self._class_index = build_class_index(str(self.root))
        return self._class_index
    
    def analyze_error(
        self,
        error_msg: str,
        file_path: Optional[str] = None,
        severity: str = "medium"
    ) -> AnalysisReport:
        """
        分析错误 (Hard L5-002)
        
        参数:
            error_msg: 错误信息
            file_path: 相关文件路径
            severity: 严重程度，决定启用哪些分析层
        
        返回:
            AnalysisReport对象
        """
        start = time.time()
        
        layers = LAYERS_CONFIG.get(severity, LAYERS_CONFIG["medium"])
        findings = []
        errors = []
        suggestions = []
        
        # 解析错误信息
        error_info = self._parse_error(error_msg)
        target_file = file_path or error_info.get("file")
        target_line = error_info.get("line")
        
        # L1: 检查文件锚点（通过 api 层）
        if "L1_Hash" in layers and target_file:
            try:
                file_anchors = {
                    k: v for k, v in self.l1_hash.items()
                    if v.file == target_file or v.file.endswith(target_file)
                }
                if file_anchors:
                    findings.append({
                        "layer": "L1_Hash",
                        "type": "file_info",
                        "data": {"anchor_count": len(file_anchors)}
                    })
            except Exception as e:
                errors.append(ErrorInfo(
                    error_type="L1_Hash",
                    message=str(e)
                ))
        
        # L2: 检查相关锚点
        if "L2_AnchorRepair" in layers and target_file:
            try:
                from api.anchors import check_all_anchors
                anchor_statuses = check_all_anchors(str(self.root))
                
                stale_anchors = [s for s in anchor_statuses if s.needs_repair]
                if stale_anchors:
                    findings.append({
                        "layer": "L2_AnchorRepair",
                        "type": "stale_anchors",
                        "count": len(stale_anchors),
                        "anchors": [s.anchor_id for s in stale_anchors]
                    })
                    suggestions.append(f"有 {len(stale_anchors)} 个锚点需要更新")
            except Exception as e:
                errors.append(ErrorInfo(
                    error_type="L2_AnchorRepair",
                    message=str(e)
                ))
        
        # L3: 检查继承链
        if "L3_Inheritance" in layers:
            # 从错误信息提取类名
            class_name = error_info.get("class")
            if class_name:
                try:
                    from inheritance import resolve_inheritance
                    chain = resolve_inheritance(class_name, self.l3_class_index)
                    
                    if chain:
                        findings.append({
                            "layer": "L3_Inheritance",
                            "type": "inheritance_chain",
                            "class": class_name,
                            "chain": [e.name for e in chain]
                        })
                except Exception as e:
                    errors.append(ErrorInfo(
                        error_type="L3_Inheritance",
                        message=str(e)
                    ))
        
        # L4: 分析数据流
        if "L4_DataFlow" in layers and target_file:
            func_name = error_info.get("function")
            if func_name:
                try:
                    from dataFlow import analyze_function_flow
                    flow = analyze_function_flow(str(self.root / target_file), func_name)
                    
                    if flow:
                        findings.append({
                            "layer": "L4_DataFlow",
                            "type": "function_flow",
                            "function": func_name,
                            "inputs": len(flow.inputs),
                            "outputs": len(flow.outputs),
                            "transformations": len(flow.transformations)
                        })
                except Exception as e:
                    errors.append(ErrorInfo(
                        error_type="L4_DataFlow",
                        message=str(e)
                    ))
        
        elapsed_ms = int((time.time() - start) * 1000)
        
        return AnalysisReport(
            target=target_file or error_msg[:50],
            analysis_type="error_analysis",
            findings=findings,
            errors=errors,
            suggestions=suggestions,
            elapsed_ms=elapsed_ms,
            layers_used=layers,
            severity=severity
        )
    
    def find_definition(self, symbol: str, file_path: str) -> Optional[Dict]:
        """
        查找符号定义位置 (Medium L5-003)
        
        参数:
            symbol: 符号名（如 "ClassName" 或 "function_name"）
            file_path: 当前文件路径
        
        返回:
            定义位置信息，未找到返回None
        """
        # 检查缓存
        cache_key = f"{file_path}:{symbol}"
        cache = self._cache.get_layer("definitions")
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        result = None
        
        # 首先在类索引中查找
        if symbol in self.l3_class_index.classes:
            entry = self.l3_class_index.classes[symbol]
            result = {
                "symbol": symbol,
                "file": entry.file,
                "line": entry.line,
                "type": "class"
            }
        
        # 如果是方法（ClassName.method）
        elif "." in symbol:
            class_name, method_name = symbol.split(".", 1)
            if class_name in self.l3_class_index.classes:
                entry = self.l3_class_index.classes[class_name]
                for method in entry.methods:
                    if method.name == method_name:
                        result = {
                            "symbol": symbol,
                            "file": entry.file,
                            "line": method.start_line,
                            "type": "method"
                        }
                        break
        
        if result:
            cache.set(cache_key, result, ttl=300)  # 5分钟缓存
        
        return result
    
    def trace_data(
        self,
        variable: str,
        function: str,
        file_path: str
    ) -> Optional[Dict]:
        """
        追踪变量数据流 (Medium L5-004)
        
        参数:
            variable: 变量名
            function: 函数名
            file_path: 文件路径
        
        返回:
            变量追踪结果
        """
        try:
            from dataFlow import trace_variable
            result = trace_variable(str(self.root / file_path), function, variable)
            
            if result:
                return result.to_dict()
        except Exception:
            pass
        
        return None
    
    def on_files_changed(
        self,
        changed_files: List[str],
        include_virtual_blocks: bool = False,
    ) -> Dict:
        """
        处理文件变更 (Medium L5-005)
        
        参数:
            changed_files: 变更的文件列表
        
        返回:
            处理结果
        """
        start = time.time()
        results = {}
        
        # L1: 更新哈希
        # 2026-05-08: 原来是空实现，hash DB 从未被更新，导致 get_stale_files() 永远返回全量文件。
        # 现在在 anchor 更新后写入新 hash，下次 update 才能正确识别增量变化。
        # results["hash_updated"] = 0
        try:
            from hash.database import HashDatabase
            db = HashDatabase(str(self.root))
            results["hash_updated"] = db.update(changed_files)
            db.save()
        except Exception as e:
            results["hash_error"] = str(e)
        
        # L2: 刷新受影响文件的 anchors（通过 api 层重新生成）
        try:
            from api.anchors import update_anchors_for_files
            gen_result = update_anchors_for_files(
                str(self.root),
                changed_files,
                include_virtual_blocks=include_virtual_blocks,
            )
            results["anchors"] = gen_result
            # 清空缓存，下次访问时重新加载
            self._l1_hash = None
        except Exception as e:
            results["anchors_error"] = str(e)

        # 重建类索引（增量）
        if self._class_index:
            try:
                from inheritance import build_class_index
                self._class_index = build_class_index(str(self.root))
                results["index_rebuilt"] = True
            except Exception as e:
                results["index_error"] = str(e)
        
        results["elapsed_ms"] = int((time.time() - start) * 1000)
        
        return results
    
    def get_cache_stats(self) -> Dict[str, CacheStats]:
        """
        获取各层缓存统计 (Easy L5-006)
        
        返回:
            各层缓存统计
        """
        return self._cache.get_all_stats()
    
    def scan_project(self, incremental: bool = True) -> ScanResult:
        """
        扫描项目 (Medium L5-007)
        
        参数:
            incremental: 是否增量扫描
        
        返回:
            扫描结果
        """
        start = time.time()
        
        result = ScanResult(root_path=str(self.root))
        issues = []
        
        # 统计文件
        languages = {}
        total_files = 0
        scanned_files = 0
        skipped_files = 0
        privacy_masked = 0
        
        import ast as _ast

        ext_lang = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".java": "java",
            ".cpp": "cpp",
            ".c": "c",
            ".h": "cpp",
        }

        py_func_count = 0
        py_class_count = 0

        for dirpath, dirnames, filenames in os.walk(self.root):
            dp = Path(dirpath)
            dirnames[:] = [d for d in dirnames if self._ignore_rules.should_scan(dp / d / "_x.py")]
            for fname in filenames:
                file_path = dp / fname
                total_files += 1

                if not self._ignore_rules.should_scan(file_path):
                    skipped_files += 1
                    continue

                ext = file_path.suffix.lower()
                if ext in ext_lang:
                    lang = ext_lang[ext]
                    languages[lang] = languages.get(lang, 0) + 1
                    scanned_files += 1

                    if self._ignore_rules.should_mask_content(file_path):
                        privacy_masked += 1

                if ext == ".py":
                    try:
                        src = file_path.read_text(encoding="utf-8-sig", errors="ignore")
                        tree = _ast.parse(src)
                        for node in _ast.walk(tree):
                            if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                                py_func_count += 1
                            elif isinstance(node, _ast.ClassDef):
                                py_class_count += 1
                    except Exception:
                        pass

        result.classes_count = py_class_count
        result.functions_count = py_func_count
        
        # 检查锚点
        try:
            from anchorRepair import check_all_anchors
            anchor_statuses = check_all_anchors(str(self.root))
            result.anchors_count = len(anchor_statuses)
            
            broken = [s for s in anchor_statuses if s.is_broken]
            if broken:
                issues.append({
                    "type": "broken_anchors",
                    "count": len(broken),
                    "anchors": [s.anchor_id for s in broken[:5]]
                })
        except Exception:
            pass
        
        result.total_files = total_files
        result.scanned_files = scanned_files
        result.skipped_files = skipped_files
        result.languages = languages
        result.privacy_masked = privacy_masked
        result.issues = issues
        result.elapsed_ms = int((time.time() - start) * 1000)
        
        return result
    
    def _parse_error(self, error_msg: str) -> Dict:
        """解析错误信息，提取关键信息"""
        import re
        
        result = {}
        
        # 提取文件路径
        file_match = re.search(r'File "([^"]+)"', error_msg)
        if file_match:
            result["file"] = file_match.group(1)
        
        # 提取行号
        line_match = re.search(r'line (\d+)', error_msg)
        if line_match:
            result["line"] = int(line_match.group(1))
        
        # 提取类名（从 "in <class_name>" 或 "class <class_name>"）
        class_match = re.search(r'(?:in |class )(\w+)', error_msg)
        if class_match:
            result["class"] = class_match.group(1)
        
        # 提取函数名
        func_match = re.search(r'(?:in |def )(\w+)\(', error_msg)
        if func_match:
            result["function"] = func_match.group(1)
        
        return result
