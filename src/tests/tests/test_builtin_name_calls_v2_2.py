"""名字和内置方法撞了的用户函数，调用边不能丢。

噪声表（BUILTIN_NOISE）本来拦的是 print()、d.items()、s.split() 这类内置调用。
它按名字拦，所以本文件里自己定义的 ``def items()``、``def get()``，裸名调用
``items()`` 时边也一起没了；类里 ``self.update()`` 调自己的 ``update`` 方法同样。
09-12 那次召回率核对说"真值 100%"，就是没覆盖到这类名字。
"""
from analyzer.anchors import generate_all_anchors, load_anchors

SOURCE = '''
def items():
    return []


def get():
    return 1


def uses_items():
    return items()


def uses_get():
    return get()


def uses_builtins(d):
    print(d)
    return d.items()


class Store:
    def update(self):
        return 1

    def refresh(self):
        return self.update()
'''


def _anchors(tmp_path):
    (tmp_path / "m.py").write_text(SOURCE, encoding="utf-8")
    generate_all_anchors(root=str(tmp_path))
    return load_anchors(root=str(tmp_path))


def test_same_file_function_named_like_builtin_keeps_its_edge(tmp_path):
    anchors = _anchors(tmp_path)
    assert "m.py::items" in anchors["m.py::uses_items"].callees
    assert "m.py::get" in anchors["m.py::uses_get"].callees


def test_self_method_named_like_builtin_keeps_its_edge(tmp_path):
    anchors = _anchors(tmp_path)
    assert "m.py::Store.update" in anchors["m.py::Store.refresh"].callees


def test_real_builtins_still_do_not_bind_to_project_functions(tmp_path):
    anchors = _anchors(tmp_path)
    callees = anchors["m.py::uses_builtins"].callees
    # d.items() 是 dict 的方法，不是本文件的 items()；print 是内置
    assert "m.py::items" not in callees
    assert not any(str(c).endswith("::print") for c in callees)
