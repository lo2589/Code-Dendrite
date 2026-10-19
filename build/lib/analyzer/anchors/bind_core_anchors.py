#!/usr/bin/env python3
"""
批量创建 CodeAnchor 锚点 - P0 核心功能

使用方法:
    cd /path/to/your/project
    python bind_core_anchors.py
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from analyzer.identity.engine import create_anchor


def bind_main_module_anchors():
    """绑定 main.py 核心锚点"""
    print("\n{'='*60}")
    print("绑定 main.py 核心锚点")
    print("{'='*60}\n")
    
    anchors = [
        ("main.chat_handler", "backend/main.py", "LLMSchedulerServer._handle_chat_with_model", 
         "聊天请求处理入口，支持多模型和工具调用"),
        
        ("main.balance_handler", "backend/main.py", "LLMSchedulerServer._handle_get_balance", 
         "Token 余额查询，返回本地和云端 API 额度"),
        
        ("main.ollama_status", "backend/main.py", "LLMSchedulerServer._handle_check_ollama_memory", 
         "Ollama 本地模型状态检查"),
        
        ("main.handle_request", "backend/main.py", "LLMSchedulerServer.handle_request", 
         "JSON-RPC 请求主入口，路由到对应处理函数"),
    ]
    
    for anchor_id, file, symbol, desc in anchors:
        try:
            result = create_anchor(anchor_id, file, symbol, description=desc)
            if result['status'] == 'created':
                print(f"✅ {anchor_id}: 成功 (hash={result['hash']})")
            else:
                print(f"❌ {anchor_id}: 失败 ({result['status']})")
        except Exception as e:
            print(f"❌ {anchor_id}: 异常 - {e}")


def bind_master_agent_anchors():
    """绑定 master_agent.py 核心锚点"""
    print("\n{'='*60}")
    print("绑定 master_agent.py 核心锚点")
    print("{'='*60}\n")
    
    anchors = [
        ("master.decompose", "backend/master_agent.py", "MasterAgent.decompose_task", 
         "将复杂任务分解为可执行的子任务"),
        
        ("master.route", "backend/master_agent.py", "MasterAgent.route", 
         "路由到最合适的 Agent（DevOps/Frontend/Database 等）"),
    ]
    
    for anchor_id, file, symbol, desc in anchors:
        try:
            result = create_anchor(anchor_id, file, symbol, description=desc)
            if result['status'] == 'created':
                print(f"✅ {anchor_id}: 成功 (hash={result['hash']})")
            else:
                print(f"❌ {anchor_id}: 失败 ({result['status']})")
        except Exception as e:
            print(f"❌ {anchor_id}: 异常 - {e}")


def bind_llm_scheduler_anchors():
    """绑定 LLM 调度相关锚点"""
    print("\n{'='*60}")
    print("绑定 LLM 调度相关锚点")
    print("{'='*60}\n")
    
    anchors = [
        ("llm.select_best", "backend/llm_capability_rater.py", "LLMCapabilityRater.select_best_model", 
         "基于任务类型、成本、性能选择最佳模型"),
        
        ("scheduler.get_load", "backend/intelligent_scheduler.py", "IntelligentScheduler.get_load_status", 
         "获取各 LLM 提供商的当前负载状态"),
        
        ("billing.update", "backend/llm_billing_query.py", "LLMBillingQuery.update_config_from_official", 
         "从官方 API 更新计费配置和 Token 价格"),
    ]
    
    for anchor_id, file, symbol, desc in anchors:
        try:
            result = create_anchor(anchor_id, file, symbol, description=desc)
            if result['status'] == 'created':
                print(f"✅ {anchor_id}: 成功 (hash={result['hash']})")
            else:
                print(f"❌ {anchor_id}: 失败 ({result['status']})")
        except Exception as e:
            print(f"❌ {anchor_id}: 异常 - {e}")


def bind_tool_executor_anchors():
    """绑定工具执行相关锚点"""
    print("\n{'='*60}")
    print("绑定工具执行相关锚点")
    print("{'='*60}\n")
    
    anchors = [
        ("tools.execute", "backend/tool_executor.py", "ToolExecutor.execute", 
         "执行工具调用并返回结果，支持多种工具类型"),
        
        ("dag.generate", "backend/dag_scheduler.py", "DAGScheduler.generate_dag", 
         "生成任务依赖图（DAG），支持并行执行"),
    ]
    
    for anchor_id, file, symbol, desc in anchors:
        try:
            result = create_anchor(anchor_id, file, symbol, description=desc)
            if result['status'] == 'created':
                print(f"✅ {anchor_id}: 成功 (hash={result['hash']})")
            else:
                print(f"❌ {anchor_id}: 失败 ({result['status']})")
        except Exception as e:
            print(f"❌ {anchor_id}: 异常 - {e}")


def main():
    """主函数：批量绑定所有核心锚点"""
    print("\n" + "="*60)
    print("开始批量创建 CodeAnchor 核心锚点")
    print("="*60)
    
    # 绑定各模块锚点
    bind_main_module_anchors()
    bind_master_agent_anchors()
    bind_llm_scheduler_anchors()
    bind_tool_executor_anchors()
    
    print("\n" + "="*60)
    print("锚点绑定完成！")
    print("="*60)
    
    # 显示统计
    db_path = Path("backend/.code_anchors.json")
    if db_path.exists():
        import json
        db = json.loads(db_path.read_text())
        print(f"\n已创建 {len(db)} 个锚点")
        print(f"锚点数据库：{db_path.absolute()}")
    
    print("\n下一步:")
    print("1. 查看锚点：cat backend/.code_anchors.json")
    print("2. 检查漂移：python tools/codeAnalysis/anchor_cli.py check")
    print("3. 刷新锚点：python tools/codeAnalysis/anchor_cli.py refresh <anchor_id>")


if __name__ == "__main__":
    main()
