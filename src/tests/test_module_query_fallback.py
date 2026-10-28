"""Human module queries retain ownership when only the V2 tree has evidence."""

import json

from usage.structure.module_tree import find_module_for_symbol, get_module, query_modules


def test_v2_module_is_visible_to_all_query_entrypoints(tmp_path):
    index = tmp_path / ".codedendrite"
    index.mkdir()
    (index / "module_tree.json").write_text(
        json.dumps({"semantic_modules": []}), encoding="utf-8"
    )
    (index / "anchors.json").write_text(
        json.dumps({"shop/pricing.py::discount": {
            "id": "shop/pricing.py::discount", "symbol": "discount",
            "file": "shop/pricing.py", "line_start": 1, "line_end": 2,
            "hash": "fixture",
        }}), encoding="utf-8"
    )
    (index / "relations.json").write_text(
        json.dumps({"edges": []}), encoding="utf-8"
    )
    (index / "module_tree_v2.json").write_text(
        json.dumps({"modules": [{
            "id": "mod_001", "name": "shop.checkout", "what": "Handle checkout",
            "files": ["shop/pricing.py"], "functions": [], "entrypoints": [],
            "evidence": {"classes": []}, "confidence": "A",
        }]}), encoding="utf-8"
    )

    root = str(tmp_path)
    assert query_modules("shop", root)[0]["id"] == "mod_001"
    assert find_module_for_symbol("shop/pricing.py::discount", root)["id"] == "mod_001"
    assert get_module("mod_001", root)["name"] == "shop.checkout"
