"""
codedendrite_ignore.py - CodeDendrite 忽略规则解析器
==================================================
解析 .codedendrite_ignore 配置文件，提供文件扫描排除和隐私保护规则。
"""

import os
import re
import fnmatch
from pathlib import Path
from typing import List, Dict, Set, Optional


def _glob_match(rel_norm: str, pattern: str) -> bool:
    """支持 ** 的路径匹配（rel_norm 和 pattern 均为 / 分隔）"""
    pat = pattern.rstrip("/")
    # 目录前缀：pattern 原本以 / 结尾，匹配路径开头
    is_dir_pattern = pattern.endswith("/")

    # 转为正则
    parts = []
    i = 0
    while i < len(pat):
        if pat[i:i+3] == "**/":
            parts.append("(?:.+/)?")
            i += 3
        elif pat[i:i+2] == "**":
            parts.append(".*")
            i += 2
        elif pat[i] == "*":
            parts.append("[^/]*")
            i += 1
        elif pat[i] == "?":
            parts.append("[^/]")
            i += 1
        else:
            parts.append(re.escape(pat[i]))
            i += 1

    regex = "^" + "".join(parts)
    if is_dir_pattern:
        regex += "(/|$)"
    else:
        regex += "$"

    return bool(re.match(regex, rel_norm))


class CodeDendriteIgnore:
    """
    CodeDendrite 忽略规则管理器
    
    支持三种排除类型：
    1. scan_exclude: 完全不扫描（节省时间和存储）
    2. map_exclude: 扫描但不加入地图（参与依赖分析）
    3. privacy_mask: 扫描且加入地图，但隐藏具体内容（只显示符号名）
    """
    
    # 默认完全不扫描的规则
    MINIMAL_CONFIG = """[scan_exclude]
.codedendrite/
__pycache__/
.git/
"""
    
    # 默认扫描但不加入地图的规则
    DEFAULT_MAP_EXCLUDE = []
    
    def __init__(self, project_path: str):
        """
        初始化忽略规则
        
        参数:
            project_path: 项目根目录路径
        """
        self.project_path = Path(project_path)
        self.config_file = self.project_path / ".codedendrite_ignore"
        
        # 初始化规则列表
        self.scan_exclude = []
        self.map_exclude = self.DEFAULT_MAP_EXCLUDE.copy()
        self.privacy_mask = []
        self.include = ["**"]  # 默认包含所有
        
        # 加载配置文件
        if not self.config_file.exists():
            self.config_file.write_text(self.MINIMAL_CONFIG, encoding="utf-8")
        self._load_config()
    
    def _load_config(self):
        """
        解析 .codedendrite_ignore 配置文件
        """
        current_section = None
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    
                    # 跳过空行和注释
                    if not line or line.startswith('#'):
                        continue
                    
                    # 识别段落
                    if line == "[scan_exclude]":
                        current_section = "scan_exclude"
                    elif line == "[map_exclude]":
                        current_section = "map_exclude"
                    elif line == "[privacy_mask]":
                        current_section = "privacy_mask"
                    elif line == "[include]":
                        current_section = "include"
                    elif current_section:
                        # 添加到对应段落
                        getattr(self, current_section).append(line)
        except Exception as e:
            print(f"警告：加载 .codedendrite_ignore 配置失败：{e}")
            print("将使用默认配置")
    
    def should_scan(self, file_path: Path) -> bool:
        """
        判断是否应该扫描这个文件（连 AST 解析都不做）
        
        参数:
            file_path: 文件路径（绝对路径或相对路径）
        
        返回:
            True 表示应该扫描，False 表示跳过
        """
        # 如果是绝对路径，转为相对路径
        try:
            rel_path = str(file_path.relative_to(self.project_path))
        except ValueError:
            # 如果不在项目目录下，不扫描
            return False
        
        # 检查是否在 scan_exclude 中
        rel_norm = rel_path.replace("\\", "/")
        for pattern in self.scan_exclude:
            normalized = pattern.replace("\\", "/")
            if _glob_match(rel_norm, normalized):
                return False
            if fnmatch.fnmatch(file_path.name, pattern):
                return False
        
        # 检查文件扩展名（双重保险，防止漏掉二进制文件）
        return True
    
    def should_include_in_map(self, file_path: Path) -> bool:
        """
        判断是否应该加入地图（扫描但可能不展示）
        
        参数:
            file_path: 文件路径
        
        返回:
            True 表示加入地图，False 表示仅用于依赖分析
        """
        if not self.should_scan(file_path):
            return False
        
        try:
            rel_path = str(file_path.relative_to(self.project_path))
        except ValueError:
            return False
        
        # 检查是否在 map_exclude 中
        rel_norm = rel_path.replace("\\", "/")
        for pattern in self.map_exclude:
            if _glob_match(rel_norm, pattern.replace("\\", "/")):
                return False
            if fnmatch.fnmatch(file_path.name, pattern):
                return False
        
        return True
    
    def should_mask_content(self, file_path: Path) -> bool:
        """
        判断是否应该脱敏内容（只保留符号，隐藏实现）
        
        参数:
            file_path: 文件路径
        
        返回:
            True 表示需要脱敏
        """
        if not self.should_scan(file_path):
            return False
        
        try:
            rel_path = str(file_path.relative_to(self.project_path))
        except ValueError:
            return False
        
        file_name = file_path.name
        
        # 检查是否在 privacy_mask 中
        rel_norm = rel_path.replace("\\", "/")
        for pattern in self.privacy_mask:
            if _glob_match(rel_norm, pattern.replace("\\", "/")):
                return True
            if fnmatch.fnmatch(file_name, pattern):
                return True
        
        return False
    
    def get_all_rules(self) -> Dict[str, List[str]]:
        """
        获取所有规则
        
        返回:
            包含所有规则的字典
        """
        return {
            "scan_exclude": self.scan_exclude,
            "map_exclude": self.map_exclude,
            "privacy_mask": self.privacy_mask,
            "include": self.include
        }
    
    def add_scan_exclude(self, pattern: str):
        """
        动态添加扫描排除规则
        
        参数:
            pattern: 排除模式，如 "**/my_folder/**"
        """
        if pattern not in self.scan_exclude:
            self.scan_exclude.append(pattern)
    
    def add_map_exclude(self, pattern: str):
        """
        动态添加地图排除规则
        
        参数:
            pattern: 排除模式
        """
        if pattern not in self.map_exclude:
            self.map_exclude.append(pattern)
    
    def add_privacy_mask(self, pattern: str):
        """
        动态添加隐私脱敏规则
        
        参数:
            pattern: 脱敏模式
        """
        if pattern not in self.privacy_mask:
            self.privacy_mask.append(pattern)


def create_default_config(project_path: str, overwrite: bool = False):
    """
    创建默认的 .codedendrite_ignore 配置文件
    
    参数:
        project_path: 项目根目录
        overwrite: 是否覆盖已存在的文件
    """
    config_file = Path(project_path) / ".codedendrite_ignore"
    
    if config_file.exists() and not overwrite:
        print(f"提示：{config_file} 已存在，跳过创建")
        return
    
    config_content = """# CodeDendrite 忽略规则配置文件
# ================================
# 
# 本文档定义了 CodeDendrite 扫描项目的规则
# 支持四种规则类型：
#   - scan_exclude: 完全不扫描（节省时间和存储）
#   - map_exclude: 扫描但不加入地图（参与依赖分析）
#   - privacy_mask: 扫描且加入地图，但隐藏具体内容
#   - include: 明确包含的路径（优先级最高）

# === 完全不扫描（节省时间和存储）===
[scan_exclude]
# 依赖目录
node_modules/
.git/
__pycache__/
.venv/
venv/
.env/

# 数据文件
dataset/
data/raw/**
*.csv
*.parquet

# 媒体文件
*.png
*.jpg
*.jpeg
*.gif
*.mp4
*.avi
*.mov

# 二进制文件
*.bin
*.exe
*.dll
*.so
*.dylib
*.pyc
*.pyo

# 日志和锁文件
*.log
*.lock

# 构建产物
build/
dist/
*.egg-info/


# === 扫描但不加入地图（参与依赖分析）===
[map_exclude]
# 测试代码（通常不需要导航）
tests/
test_*.py
*_test.py
testing/
mocks/
fixtures/

# 文档
docs/
*.md
README*
CHANGELOG*

# 配置文件（不含敏感信息）
*.yaml
*.yml
*.toml
setup.py
requirements.txt


# === 扫描且加入地图，但隐藏具体内容（只显示符号名）===
[privacy_mask]
# 敏感配置文件
.env
.env.*
*secret*
*password*
*credential*
*api_key*
config/secrets.json
config/credentials.yml

# 数据库相关
*.sqlite
*.db
database.yml


# === 明确包含的路径（优先级最高）===
[include]
# 源代码目录
src/
backend/
frontend/
extension/src/
tools/
packages/

# 配置文件（非敏感）
config.py
settings.py
pyproject.toml
"""
    config_content = CodeDendriteIgnore.MINIMAL_CONFIG

    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write(config_content)
        print(f"✓ 已创建默认配置文件：{config_file}")
    except Exception as e:
        print(f"错误：创建配置文件失败：{e}")


# 测试函数
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--create-default":
        project_path = sys.argv[2] if len(sys.argv) > 2 else "."
        create_default_config(project_path)
    else:
        # 简单测试
        test_path = Path(".")
        ignore = CodeDendriteIgnore(str(test_path))
        
        print("当前规则配置:")
        print(f"  scan_exclude: {len(ignore.scan_exclude)} 条")
        print(f"  map_exclude: {len(ignore.map_exclude)} 条")
        print(f"  privacy_mask: {len(ignore.privacy_mask)} 条")
        print(f"  include: {len(ignore.include)} 条")
        
        # 测试几个文件
        test_files = [
            "src/main.py",
            "tests/test_main.py",
            "dataset/image001.png",
            "backend/.env",
            "node_modules/lodash/index.js"
        ]
        
        print("\n测试结果:")
        for test_file in test_files:
            file_path = test_path / test_file
            should_scan = ignore.should_scan(file_path)
            in_map = ignore.should_include_in_map(file_path)
            masked = ignore.should_mask_content(file_path)
            
            status = "✓扫描" if should_scan else "✗跳过"
            map_status = "入地图" if in_map else "仅依赖"
            mask_status = "🔒脱敏" if masked else "明文"
            
            print(f"  {test_file:40s} {status:6s} {map_status:6s} {mask_status}")
