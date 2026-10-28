"""按名字兜底解析不能跨语言：Python 里局部定义的 words() 不能连到 JS 里同名的 words()。"""
from pathlib import Path

from analyzer.anchors import generate_all_anchors, load_anchors
from analyzer.anchors.language_family import can_call_by_name

PY = (
    "def keys(values):\n"
    "    def words(value):\n"
    "        return value.split('.')\n"
    "    return [w for v in values for w in words(v)]\n"
)
JS = "export function words(text) {\n  return text.split(' ');\n}\n"


def test_python_local_helper_does_not_bind_to_js_function(tmp_path: Path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "profile.py").write_text(PY, encoding="utf-8")
    (tmp_path / "web").mkdir()
    (tmp_path / "web" / "worker.js").write_text(JS, encoding="utf-8")
    generate_all_anchors(root=str(tmp_path))
    anchors = load_anchors(root=str(tmp_path))
    assert "web/worker.js::words" in anchors
    for aid, anchor in anchors.items():
        if anchor.file == "pkg/profile.py":
            assert "web/worker.js::words" not in (anchor.callees or []), aid


def test_language_families():
    assert can_call_by_name("typescript", "javascript")
    assert can_call_by_name("swift", "objective-c")
    assert can_call_by_name("kotlin", "java")
    assert can_call_by_name("javascript", "html")      # DOM 节点
    assert can_call_by_name("python", "css")           # 模板里的选择器
    assert not can_call_by_name("python", "javascript")
    assert not can_call_by_name("javascript", "python")
    assert not can_call_by_name("go", "rust")
    assert can_call_by_name("", "javascript")          # 语言未知不拦
