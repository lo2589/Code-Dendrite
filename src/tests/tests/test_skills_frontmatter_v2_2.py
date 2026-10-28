"""skills/*/SKILL.md 的 frontmatter 必须是合法 YAML。

`npx skills add` 解析失败时不报错，直接把这个 skill 跳过：cdd-learn 的 description 里一个
"look at: code map" 就让它从列表里消失过。
"""
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")
SKILLS = sorted((Path(__file__).resolve().parents[3] / "skills").glob("*/SKILL.md"))


def test_there_are_skills():
    assert SKILLS


@pytest.mark.parametrize("path", SKILLS, ids=lambda p: p.parent.name)
def test_frontmatter_parses_with_name_and_description(path):
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    meta = yaml.safe_load(text.split("---", 2)[1])
    assert meta["name"] == path.parent.name
    assert isinstance(meta["description"], str) and len(meta["description"]) <= 1024
