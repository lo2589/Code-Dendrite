#!/usr/bin/env python
"""
test_ignore_rules.py - 测试文件忽略规则
"""

import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from shared.codedendrite_ignore import CodeDendriteIgnore

def test_project_ignore_rules():
    """测试项目根目录的忽略规则"""
    
    # 使用绝对路径
    project_root = Path(__file__).parent.parent.parent
    print(f"测试项目根目录：{project_root}\n")
    
    ignore = CodeDendriteIgnore(str(project_root))
    
    print("当前规则配置:")
    print(f"  scan_exclude: {len(ignore.scan_exclude)} 条")
    print(f"  map_exclude: {len(ignore.map_exclude)} 条")
    print(f"  privacy_mask: {len(ignore.privacy_mask)} 条")
    print(f"  include: {len(ignore.include)} 条\n")
    
    # 测试一些关键文件
    test_files = [
        # 应该被扫描的
        "backend/main.py",
        "extension/src/extension.ts",
        "tools/CodeDendrite/smartAnalyzer/smart_analyzer.py",
        
        # 应该被跳过的（scan_exclude）
        "dataset/image001.png",
        "extension/node_modules/lodash/index.js",
        "htmlcov/index.html",
        ".git/config",
        
        # 应该扫描但不入地图（map_exclude）
        "tests/test_backend.py",
        "docs/README.md",
        "CHANGELOG.md",
        
        # 应该脱敏的（privacy_mask）
        ".env",
        ".quota_status.json",
        "backend/config/secrets.json",
    ]
    
    print("测试结果:")
    print("-" * 100)
    print(f"{'文件路径':<60s} {'扫描':<8s} {'地图':<8s} {'隐私':<8s}")
    print("-" * 100)
    
    for test_file in test_files:
        file_path = project_root / test_file
        should_scan = ignore.should_scan(file_path)
        in_map = ignore.should_include_in_map(file_path)
        masked = ignore.should_mask_content(file_path)
        
        scan_status = "✓扫描" if should_scan else "✗跳过"
        map_status = "入地图" if in_map and should_scan else "仅依赖" if should_scan else "-"
        mask_status = "🔒脱敏" if masked else "明文"
        
        print(f"{test_file:<60s} {scan_status:<8s} {map_status:<8s} {mask_status:<8s}")
    
    print("-" * 100)
    
    # 统计信息
    total_tested = len(test_files)
    will_scan = sum(1 for f in test_files if ignore.should_scan(project_root / f))
    will_skip = total_tested - will_scan
    will_mask = sum(1 for f in test_files if ignore.should_mask_content(project_root / f))
    
    print(f"\n汇总:")
    print(f"  测试文件数：{total_tested}")
    print(f"  将扫描：{will_scan}")
    print(f"  将跳过：{will_skip}")
    print(f"  将脱敏：{will_mask}")


if __name__ == "__main__":
    test_project_ignore_rules()
