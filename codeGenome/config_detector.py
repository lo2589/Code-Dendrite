"""
config_detector.py - 配置文件检测器
===================================
使用特征向量相似度来判断是否为配置文件
"""

import ast
import math
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from collections import Counter
import math


class ConfigDetector:
    """
    配置文件检测器
    
    使用多维度特征向量 + 余弦相似度来判断文件是否为配置文件
    并识别配置文件的格式类型
    """
    
    def __init__(self):
        # 已知格式的特征模板
        self.known_formats = {
            'mmdet': {
                'patterns': ['_base_', 'dataset_type', 'data_root', 'model = dict('],
                'datasets': ['coco', 'voc', 'cityscapes', 'lvis'],
                'models': ['RCNN', 'YOLO', 'Transformer', 'SSD'],
            },
            'yolo': {
                'patterns': ['nc =', 'anchors =', 'names ='],
                'datasets': ['coco', 'voc'],
                'models': ['YOLO'],
            },
        }
        
        # 未知格式收集（用于发现新格式）
        self.unknown_configs = []
    
    def extract_features(self, file_path: Path) -> Optional[Dict[str, float]]:
        """
        提取文件的特征向量
        
        参数:
            file_path: 文件路径
            
        返回:
            特征向量化字典，失败返回 None
        """
        try:
            source = file_path.read_text(encoding='utf-8')
            tree = ast.parse(source)
        except Exception:
            return None
        
        # 统计 AST 节点
        stats = {
            'imports': 0,
            'assigns': 0,
            'classes': 0,
            'methods': 0,
            'functions': 0,
            'statements': 0,
        }
        
        # 统计代码特征
        code_stats = {
            'has_dict': 0,
            'has_base': 0,
        }
        
        total_nodes = 0
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                stats['imports'] += 1
            elif isinstance(node, ast.Assign):
                stats['assigns'] += 1
            elif isinstance(node, ast.ClassDef):
                stats['classes'] += 1
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # 检查是否在类内部
                is_method = any(
                    isinstance(parent, ast.ClassDef) 
                    for parent in self._get_parents(tree, node)
                )
                if is_method:
                    stats['methods'] += 1
                else:
                    stats['functions'] += 1
            elif isinstance(node, ast.Expr) and not isinstance(node.value, (ast.Constant, ast.Str)):
                stats['statements'] += 1
            
            total_nodes += 1
        
        # 统计源码文本特征
        lines = source.split('\n')[:30]  # 只看前 30 行
        for line in lines:
            if 'dict(' in line:
                code_stats['has_dict'] += 1
            if '_base_' in line:
                code_stats['has_base'] += 1
        
        # 归一化
        total = sum(stats.values())
        if total == 0:
            return None
        
        features = {}
        for key, count in stats.items():
            features[key] = count / total
        
        # 添加代码特征（归一化到 0-1）
        features['has_dict'] = min(code_stats['has_dict'] / len(lines), 1.0)
        features['has_base'] = min(code_stats['has_base'] / len(lines), 1.0)
        
        return features
    
    def _get_parents(self, tree: ast.AST, target_node: ast.AST) -> List[ast.AST]:
        """获取节点的所有父节点（用于判断是否是方法）"""
        parents = []
        
        class ParentFinder(ast.NodeVisitor):
            def __init__(self):
                self.path = []
            
            def generic_visit(self, node):
                if node == target_node:
                    parents.extend(self.path)
                    return
                
                self.path.append(node)
                for child in ast.iter_child_nodes(node):
                    self.generic_visit(child)
                self.path.pop()
        
        finder = ParentFinder()
        finder.generic_visit(tree)
        return parents
    
    def cosine_similarity(self, vec1: Dict[str, float], vec2: Dict[str, float]) -> float:
        """
        计算两个特征向量的余弦相似度
        
        参数:
            vec1: 向量 1
            vec2: 向量 2
            
        返回:
            相似度 (0-1)，1 表示完全相同
        """
        # 所有特征键
        all_keys = set(vec1.keys()) | set(vec2.keys())
        
        # 计算点积
        dot_product = sum(vec1.get(k, 0) * vec2.get(k, 0) for k in all_keys)
        
        # 计算模长
        mag1 = math.sqrt(sum(vec1.get(k, 0) ** 2 for k in all_keys))
        mag2 = math.sqrt(sum(vec2.get(k, 0) ** 2 for k in all_keys))
        
        if mag1 == 0 or mag2 == 0:
            return 0
        
        return dot_product / (mag1 * mag2)
    
    def is_config_file(
        self, 
        file_path: Path, 
        threshold: float = 0.85,
        use_template: str = 'config'
    ) -> Tuple[bool, float, str]:
        """
        判断文件是否为配置文件
        
        参数:
            file_path: 文件路径
            threshold: 相似度阈值 (默认 0.85)
            use_template: 使用哪个模板 ('config' 或 'source')
            
        返回:
            (是否为配置，相似度，判断依据)
        """
        features = self.extract_features(file_path)
        if features is None:
            return False, 0.0, "无法解析文件"
        
        # 计算与配置模板的相似度
        config_sim = self.cosine_similarity(features, self.config_template)
        source_sim = self.cosine_similarity(features, self.source_template)
        
        # 计算差异
        sim_diff = config_sim - source_sim
        
        if config_sim >= threshold and sim_diff > 0.1:
            return True, config_sim, f"与配置文件模板相似度：{config_sim:.1%}"
        elif source_sim > config_sim:
            return False, source_sim, f"与源代码模板相似度：{source_sim:.1%}"
        else:
            return False, config_sim, f"特征不明显 (配置相似度：{config_sim:.1%})"
    
    def detect_config_format(self, file_path: Path) -> Optional[Dict]:
        """
        检测配置文件的格式和关键信息
        
        策略:
        1. 先匹配已知格式
        2. 如果不匹配，标记为未知格式并收集特征
        3. 返回格式信息和是否需要学习新格式的标志
        
        返回:
            {
                'format': 'mmdet',  # 配置文件类型
                'is_known': True,   # 是否是已知格式
                'base': '_base_.py',  # 继承的基配置
                'dataset': 'coco',  # 数据集
                'model_type': 'FasterRCNN',  # 模型类型
                'key_items': ['model', 'data', 'optimizer']  # 关键配置项
            }
        """
        try:
            source = file_path.read_text(encoding='utf-8')
            lines = source.split('\n')[:50]  # 只看前 50 行
            content = '\n'.join(lines)
            
            result = {
                'format': 'unknown',
                'is_known': False,
                'base': None,
                'dataset': None,
                'model_type': None,
                'key_items': [],
                'new_features': []  # 新发现的特征
            }
            
            # Step 1: 尝试匹配已知格式
            for format_name, format_info in self.known_formats.items():
                patterns = format_info['patterns']
                match_count = sum(1 for p in patterns if p in content)
                
                # 如果匹配 2 个以上特征模式，认为是该格式
                if match_count >= 2:
                    result['format'] = format_name
                    result['is_known'] = True
                    break
            
            # Step 2: 提取具体信息
            if result['format'] == 'mmdet' or '_base_' in content:
                # MMDetection 风格配置
                if result['format'] != 'mmdet':
                    result['format'] = 'mmdet'  # 默认归类为 mmdet 风格
                
                # 提取_base_
                for line in lines:
                    if '_base_' in line and '=' in line:
                        import re
                        match = re.search(r"_base_\s*=\s*['\"](.+?)['\"]", line)
                        if match:
                            result['base'] = match.group(1)
                
                # 提取数据集 - 增强版
                dataset_patterns = [
                    (r'CocoDataset', 'coco'),
                    (r'VOCDataset', 'voc'),
                    (r'CityscapesDataset', 'cityscapes'),
                    (r'LVISDataset', 'lvis'),
                    (r'OpenImagesDataset', 'openimages'),
                ]
                for pattern, dataset_name in dataset_patterns:
                    if pattern in content:
                        result['dataset'] = dataset_name
                        break
                
                # 如果没有明确数据集，检查数据路径
                if not result['dataset']:
                    path_patterns = [
                        (r'data/coco', 'coco'),
                        (r'data/VOC', 'voc'),
                        (r'data/cityscapes', 'cityscapes'),
                    ]
                    for pattern, dataset_name in path_patterns:
                        if pattern in content.lower():
                            result['dataset'] = dataset_name
                            break
                
                # 提取模型类型
                model_patterns = [
                    (r"type=['\"]([\w]+RCNN)['\"]", 'model_type'),
                    (r"type=['\"]([\w]+YOLO)['\"]", 'model_type'),
                    (r"type=['\"]([\w]+Transformer)['\"]", 'model_type'),
                    (r"type=['\"]([\w]+SSD)['\"]", 'model_type'),
                ]
                for pattern, key in model_patterns:
                    import re
                    matches = re.findall(pattern, content)
                    if matches:
                        result[key] = matches[0]
                        break
                
                # 提取关键配置项
                config_items = []
                for line in lines:
                    if '=' in line and not line.strip().startswith('#'):
                        var_name = line.split('=')[0].strip()
                        if var_name and not var_name.startswith('_'):
                            config_items.append(var_name)
                result['key_items'] = config_items[:10]
            
            else:
                # Step 3: 未知格式，收集特征
                result['format'] = 'unknown'
                result['is_known'] = False
                
                # 收集新特征
                new_features = []
                for line in lines[:20]:
                    if '=' in line and not line.strip().startswith('#'):
                        var_name = line.split('=')[0].strip()
                        if var_name and len(var_name) > 2:
                            new_features.append(var_name)
                
                result['new_features'] = new_features[:10]
                
                # 记录未知配置，用于后续学习
                self.unknown_configs.append({
                    'file': str(file_path),
                    'features': new_features,
                    'sample_lines': lines[:10]
                })
            
            return result
            
        except Exception as e:
            print(f"Error detecting config format: {e}")
            return None
    
    def get_unknown_configs(self) -> List[Dict]:
        """获取所有未识别的配置文件（用于发现新格式）"""
        return self.unknown_configs
    
    def add_new_format(self, format_name: str, patterns: List[str]):
        """
        添加新的已知格式
        
        参数:
            format_name: 格式名称
            patterns: 特征模式列表
        """
        self.known_formats[format_name] = {
            'patterns': patterns,
            'datasets': [],
            'models': []
        }
        print(f"✓ 已添加新格式：{format_name}")


# ==================== 使用示例 ====================

if __name__ == "__main__":
    detector = ConfigDetector()
    
    print("=" * 70)
    print("配置文件检测器测试")
    print("=" * 70)
    
    # 测试几个文件
    test_files = [
        Path("mmdet_source/configs/glip/odinw/glip_atss_swin-t_a_fpn_dyhead_pretrain_odinw35.py"),
        Path("mmdet_source/mmdet/version.py"),
        Path("mmdet_source/mmdet/apis/inference.py"),
    ]
    
    for file_path in test_files:
        if file_path.exists():
            is_config, sim, reason = detector.is_config_file(file_path)
            print(f"\n{file_path.name}:")
            print(f"  是否配置：{'✓ 是' if is_config else '✗ 否'}")
            print(f"  相似度：{sim:.1%}")
            print(f"  原因：{reason}")
    
    # 批量检测
    print("\n\n" + "=" * 70)
    print("批量检测 configs/ 目录")
    print("=" * 70)
    
    configs_dir = Path("mmdet_source/configs")
    if configs_dir.exists():
        results = detector.batch_detect(configs_dir)
        
        config_count = sum(1 for _, is_cfg, _, _ in results if is_cfg)
        print(f"\n扫描文件数：{len(results)}")
        print(f"识别为配置：{config_count} ({config_count/len(results)*100:.1f}%)")
        
        # 显示最像配置的前 10 个
        print("\n【最像配置文件的 Top 10】")
        for i, (path, is_cfg, sim, reason) in enumerate(results[:10], 1):
            print(f"{i:2d}. {path.name:50s} → {sim:.1%}")
