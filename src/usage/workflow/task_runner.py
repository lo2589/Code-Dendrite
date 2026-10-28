"""
task_runner.py — 任务本执行器

用法：
    python -m api.task_runner task_book.json --llm openai/gpt-4o-mini
    python -m api.task_runner task_book.json --llm anthropic/claude-haiku-4-5-20251001

任务本格式见 task_book_example.json。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# ──────────────────────────────────────────────
# 命令解析
# ──────────────────────────────────────────────

_CMD_RE = re.compile(r"<([^>]+)>(?::(.+))?")


def _parse_cmd(text: str) -> Tuple[Optional[str], str]:
    m = _CMD_RE.search(text)
    if m:
        return m.group(1).strip(), (m.group(2) or "").strip()
    return None, ""


# ──────────────────────────────────────────────
# 模板变量展开
# ──────────────────────────────────────────────

def _expand_info(info_list: List[str], project: str) -> str:
    """展开 ${readme} / ${tree -L N} 等模板变量。"""
    parts = []
    for item in info_list:
        item = item.strip()
        if item.startswith("${tree"):
            # 提取 -L N，默认 2
            m = re.search(r"-L\s*(\d+)", item)
            depth = int(m.group(1)) if m else 2
            try:
                r = subprocess.run(
                    ["tree", project, f"/L", str(depth), "/F"],
                    capture_output=True, text=True, timeout=10
                )
                out = r.stdout or r.stderr
            except FileNotFoundError:
                # fallback: python glob
                lines = []
                root = Path(project)
                import os as _os
                for dirpath, dirnames, filenames in _os.walk(root):
                    rel = Path(dirpath).relative_to(root)
                    if len(rel.parts) >= depth:
                        dirnames.clear()
                        continue
                    indent = "  " * len(rel.parts)
                    lines.append(f"{indent}{Path(dirpath).name}/")
                    for fname in filenames:
                        if len(rel.parts) + 1 <= depth:
                            lines.append(f"{indent}  {fname}")
                out = "\n".join(lines[:80])
            parts.append(f"[目录结构 -L{depth}]\n{out[:1500]}")

        elif item.startswith("${readme}"):
            readme = None
            for name in ("README.md", "readme.md", "README.rst"):
                p = Path(project) / name
                if p.exists():
                    readme = p.read_text(encoding="utf-8", errors="ignore")[:800]
                    break
            parts.append(f"[README]\n{readme or '（无）'}")

        else:
            parts.append(item)
    return "\n\n".join(parts)


# ──────────────────────────────────────────────
# 工具执行（<cmd>:arg → 字符串结果）
# ──────────────────────────────────────────────

def _run_tool(cmd: str, arg: str, root: str, state: dict) -> str:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from api.inspector import (
        find_anchor, get_anchor_source, get_anchor_relations, list_file_anchors
    )

    if cmd in ("锚点源码", "查看锚点"):
        r = get_anchor_source(arg, root)
        if not r:
            # 自动兜底：搜索同名 anchor
            hits = find_anchor(arg, root)[:4]
            if not hits:
                return f"找不到 anchor: {arg}，也没有相似名称"
            suggestions = "\n".join(f"  {h['symbol']}  {h['file']}:{h['line']}" for h in hits)
            return f"找不到 anchor: {arg}，相似结果：\n{suggestions}\n---\n请用 <锚点源码>:正确名称 重试"
        return (
            f"{r['symbol']}  {r['file']} L{r['line_start']}-{r['line_end']}\n"
            f"```python\n{r['source']}\n```"
        )

    elif cmd in ("调用关系", "查看关系"):
        r = get_anchor_relations(arg, root, history=state.get("chain"))
        if not r:
            return f"找不到 anchor: {arg}"
        state["chain"] = r["visited_chain"]
        callers = [c["symbol"] for c in r["callers"] if c["resolved"]]
        callees = [c["symbol"] for c in r["callees"] if c["resolved"]]
        chain = r["visited_chain"]
        options = []
        for s in callees:
            if s not in chain:
                options.append(f"  → {s}")
        for s in callers:
            if s not in chain:
                options.append(f"  ← {s}")
        return (
            f"callers: {', '.join(callers) or '无'}\n"
            f"callees: {', '.join(callees) or '无'}\n"
            f"已探索链路: {' → '.join(chain)}\n"
            f"可跳转:\n" + ("\n".join(options) or "  （无）")
        )

    elif cmd in ("搜索", "搜索锚点"):
        results = find_anchor(arg, root)[:6]
        if not results:
            return f"没有找到: {arg}"
        return "\n".join(f"  {r['symbol']}  {r['file']}:{r['line']}" for r in results)

    elif cmd in ("文件锚点", "列文件"):
        results = list_file_anchors(arg, root)
        if not results:
            return f"文件无 anchor: {arg}"
        return "\n".join(f"  L{r['line']:4d}  {r['type']:<8} {r['symbol']}" for r in results)

    return f"未知命令: {cmd}"


# ──────────────────────────────────────────────
# 导航任务系统提示
# ──────────────────────────────────────────────

_NAV_SYSTEM = """\
你是代码导航 agent。正在为 {context} 工作。

每轮只输出一个命令，不要解释：
  <锚点源码>:symbol     查看函数源码
  <调用关系>:symbol     查看调用者/被调用者（含链路记忆）
  <搜索>:keyword        按名字搜索 anchor
  <文件锚点>:file.py    列出文件内所有函数
  <输出diff>            准备输出 unified diff（之后紧跟 diff 内容）
  <任务完成>            本轮结束

规则：
- 每轮只输一个命令
- 已探索链路里的 symbol 不要重复查
- 信息够修就直接 <输出diff>，不要继续跳"""

_NAV_APPEND = "\n---\n够修 → <输出diff>；需要更多 → 选一个命令"


def _nav_first_msg(task: dict, context: str) -> str:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from usage.jump_packet import build_jump_packet
    packet = build_jump_packet(
        symbol=task["entry"],
        root=task["project"],
        error_text=task.get("error", ""),
        project_brief=context,
    )
    return packet + _NAV_APPEND


# ──────────────────────────────────────────────
# 主执行器
# ──────────────────────────────────────────────

def run(task_book_path: str, call_llm: Callable[[str, List[dict]], str]) -> dict:
    """
    执行整个任务本。

    Args:
        task_book_path: JSON 文件路径
        call_llm: fn(system_prompt, messages) → str

    Returns:
        {"outputs": {task_id: result_str}, "diffs": [str, ...]}
    """
    tasks = json.loads(Path(task_book_path).read_text(encoding="utf-8"))
    outputs: Dict[str, str] = {}
    diffs: List[str] = []

    first_project = tasks[0]["project"]
    cd_root = str(Path(__file__).parent.parent)
    indexed: set = set()

    def _ensure_indexed(proj: str) -> None:
        if proj in indexed:
            return
        print(f"[cd_init] {proj}")
        r = subprocess.run(
            [sys.executable, "api/cli.py", proj, "--update"],
            cwd=cd_root, capture_output=True, text=True, timeout=180
        )
        print(r.stdout[-500:] or r.stderr[-200:])
        indexed.add(proj)

    _ensure_indexed(first_project)

    for task in tasks:
        tid = str(task["task_id"])
        project = task.get("project", first_project)
        print(f"\n{'='*50}\n[Task {tid}] {task.get('task', task.get('entry', ''))}")

        _ensure_indexed(project)

        # ── 注入前序输出 ──
        def inject(s: str) -> str:
            for k, v in outputs.items():
                s = s.replace(f"{{{k}}}", v)
            return s

        # ── 普通任务（info + task 字段）──
        if "task" in task and "entry" not in task:
            info_str = _expand_info(task.get("info", []), project)
            user_msg = f"{info_str}\n\n---\n{inject(task['task'])}"
            system = "你是项目分析 agent，简洁回答，不要废话。"
            msgs = [{"role": "user", "content": user_msg}]
            result = call_llm(system, msgs)
            print(f"[output] {result[:200]}")
            if "output_as" in task:
                outputs[task["output_as"]] = result.strip()
            continue

        # ── 导航任务（entry + error 字段）──
        context = inject(task.get("system_context", outputs.get("brief", "该项目")))
        system = _NAV_SYSTEM.format(context=context)
        state = {"chain": None}
        first_msg = _nav_first_msg(task, context)
        msgs: List[dict] = [{"role": "user", "content": first_msg}]

        collected_diff = []
        collecting = False
        consecutive_errors = 0

        for _ in range(20):  # 最多 20 跳
            try:
                response = call_llm(system, msgs)
            except Exception as e:
                print(f"  [llm_error] {e}")
                outputs[tid] = f"[FAILED] llm error: {e}"
                break

            msgs.append({"role": "assistant", "content": response})
            print(f"  [model] {response[:120]}")

            cmd, arg = _parse_cmd(response)

            if collecting:
                if cmd == "任务完成":
                    diff_text = "\n".join(collected_diff)
                    diffs.append(diff_text)
                    outputs[tid] = diff_text
                    print(f"  [diff collected] {len(diff_text)} chars")
                    break
                collected_diff.append(response)
                continue

            if cmd == "输出diff":
                collecting = True
                msgs.append({"role": "user", "content": "请输出 diff，完成后输出 <任务完成>"})
                consecutive_errors = 0
                continue

            if cmd == "任务完成" or cmd is None:
                if cmd is None:
                    consecutive_errors += 1
                    if consecutive_errors >= 3:
                        print(f"  [abort] 连续 3 轮无有效命令，任务终止")
                        outputs[tid] = "[FAILED] no valid command"
                        break
                    msgs.append({"role": "user", "content": "请输出一个有效命令，或 <任务完成> 结束。" + _NAV_APPEND})
                    continue
                break

            # 执行工具
            tool_result = _run_tool(cmd, arg, project, state)
            print(f"  [tool:{cmd}] {tool_result[:100]}")
            consecutive_errors = 0
            msgs.append({"role": "user", "content": tool_result + _NAV_APPEND})

    return {"outputs": outputs, "diffs": diffs}


# ──────────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────────

def _make_llm(model_str: str) -> Callable:
    """根据 model 字符串创建 call_llm 函数。"""
    if model_str.startswith("anthropic/"):
        import anthropic
        model_id = model_str.split("/", 1)[1]
        client = anthropic.Anthropic()

        def call(system: str, messages: list) -> str:
            resp = client.messages.create(
                model=model_id, max_tokens=1024, system=system, messages=messages
            )
            return resp.content[0].text

    else:
        from openai import OpenAI
        vendor, model_id = model_str.split("/", 1)
        base_urls = {
            "openai": None,
            "deepseek": "https://api.deepseek.com/v1",
            "ollama": os.environ.get("OLLAMA_URL", "http://localhost:11434") + "/v1",
        }
        client = OpenAI(
            base_url=base_urls.get(vendor),
            api_key=os.environ.get(f"{vendor.upper()}_API_KEY", "ollama")
        )

        def call(system: str, messages: list) -> str:
            full = [{"role": "system", "content": system}] + messages
            resp = client.chat.completions.create(model=model_id, messages=full, max_tokens=1024)
            return resp.choices[0].message.content

    return call


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("task_book")
    parser.add_argument("--llm", default="anthropic/claude-haiku-4-5-20251001")
    args = parser.parse_args()

    llm_fn = _make_llm(args.llm)
    result = run(args.task_book, llm_fn)
    print("\n=== 结果 ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))
