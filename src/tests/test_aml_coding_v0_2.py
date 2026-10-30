import json
import re
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import numpy as np
import pytest

from usage.aml_coding import embed
from usage.aml_coding.anchors import attach, edges, extract
from usage.aml_coding.search import BUDGET_CHARS, search
from usage.aml_coding.server import App, make_handler
from usage.aml_coding.store import RequestConflict, add, init
from usage.aml_coding.trajectory import events, replay

SOURCE = "class Bar:\n    def update(self, n):\n        return self.render(n)\n\n    def render(self, n):\n        return str(n)\n"


def numbered(text):
    return "\n".join(f"{i}\t{line}" for i, line in enumerate(text.split("\n"), 1))


def trajectory(issue="Bar.update renders the wrong width", extra=""):
    read = numbered(SOURCE)
    cut = len(read) // 2
    return [
        {"role": "user", "content": f"# Issue\n\n{issue}", "timestamp": 1_600_000_000_000},
        {"role": "assistant", "content": "[thinking] Look at `Bar.update` first." + extra},
        {"role": "assistant", "content": '[tool_use Read] {"file_path": "/testbed/pkg/bar.py"}'},
        {"role": "user", "content": "[tool_result] " + read[:cut]},
        {"role": "user", "content": read[cut:]},
        {"role": "assistant", "content": '[tool_use Edit] {"file_path": "/testbed/pkg/bar.py", '
                                         '"old_string": "        return self.render(n)", "new_string": "        return self.render(n + 1)"}'},
        {"role": "user", "content": "[tool_result] edited"},
        {"role": "assistant", "content": '[tool_use Bash] {"command": "pytest pkg/test_bar.py::test_update"}'},
        {"role": "user", "content": "[tool_result] 1 passed"},
        {"role": "assistant", "content": "Here's a summary: fixed Bar.update."},
    ]


def body(user, req, msgs):
    return {"request_id": req, "user_id": user, "session_id": "s", "messages": msgs}


class FakeAPI:
    def __init__(self):
        self.calls = 0

    def __call__(self, texts):
        self.calls += 1
        out = np.zeros((len(texts), 32), np.float32)
        for i, t in enumerate(texts):
            for w in re.findall(r"[a-z]+", t.lower()):
                out[i, hash(w) % 32] += 1
        return embed.normalize(out + 1e-3), 0


def test_continuation_is_glued_and_files_replayed():
    evs = events(trajectory())
    read = next(e for e in evs if e.tool == "Read")
    assert read.result.count("\t") == SOURCE.count("\n") + 1      # split result glued back mid-line
    state = replay(evs)["pkg/bar.py"]
    assert state.contiguous() and "self.render(n + 1)" in state.text() and len(state.edits) == 1


def test_anchors_edges_and_links():
    evs = events(trajectory())
    files = replay(evs)
    anchors, capped = extract(files)
    attach(evs, files, anchors)
    keys = {a.key: a for a in anchors}
    assert not capped and {"pkg/bar.py::Bar", "pkg/bar.py::Bar.update", "pkg/bar.py::Bar.render"} <= set(keys)
    assert ("pkg/bar.py::Bar.update", "pkg/bar.py::Bar.render") in edges(anchors)
    assert "edit" in keys["pkg/bar.py::Bar.update"].links and "mention" in keys["pkg/bar.py::Bar.update"].links


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "aml.db"
    init(path)
    api = FakeAPI()
    return path, api, embed.Embedder(tmp_path / "cache.db", call=api)


def test_same_trajectory_is_stored_once(db):
    path, api, embedder = db
    first = add(path, body("u1", "r", trajectory()), embedder)
    calls = api.calls
    second = add(path, body("u2", "r", trajectory()), embedder)
    assert first["new_trajectory"] and not second["new_trajectory"] and api.calls == calls
    assert add(path, body("u1", "r", trajectory()), embedder)["duplicate"]
    with pytest.raises(RequestConflict):
        add(path, body("u1", "r", trajectory(issue="other")), embedder)


def test_symbol_query_puts_the_anchor_first_and_respects_budget(db):
    path, _, embedder = db
    add(path, body("u", "r", trajectory()), embedder)
    data, _ = search(path, {"query": "Bar.update", "user_id": "u", "top_k": 50}, embedder)
    assert data[0]["content"].startswith("pkg/bar.py::Bar.update")
    assert "edit:" in data[0]["content"] and "calls: Bar.render" in data[0]["content"]
    assert sum(len(d["content"]) for d in data) <= BUDGET_CHARS
    assert search(path, {"query": "Bar.update", "user_id": "nobody", "top_k": 5}, embedder)[0] == []


def test_big_trajectory_reply_stays_under_budget(db):
    path, _, embedder = db
    noise = " ".join(f"word{i}" for i in range(30_000))
    add(path, body("u", "r", trajectory(extra=noise)), embedder)
    data, _ = search(path, {"query": "word1 word2 Bar", "user_id": "u", "top_k": 100}, embedder)
    assert sum(len(d["content"]) for d in data) <= BUDGET_CHARS


def test_http_contract(tmp_path):
    app = App(tmp_path, "k", 10.0, embedder=embed.Embedder(tmp_path / "c.db", call=FakeAPI()))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    base = f"http://127.0.0.1:{httpd.server_address[1]}"

    def call(path, payload=None, key="k"):
        req = urllib.request.Request(base + path, data=None if payload is None else json.dumps(payload).encode(),
                                     headers={"Authorization": f"Token {key}"})
        try:
            with opener.open(req) as r:
                return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            return e.code, json.load(e)
    try:
        assert call("/aml/health")[0] == 200
        assert call("/aml/add", body("u", "r", trajectory()), key="bad")[0] == 401
        status, reply = call("/aml/add", body("u", "r", trajectory()))
        assert status == 200 and reply == {"success": True, "request_id": "r", "user_id": "u", "session_id": "s"}
        status, reply = call("/aml/search", {"query": "Bar.update", "user_id": "u", "top_k": 3})
        assert status == 200 and len(reply["data"]) <= 3 and set(reply["data"][0]) == {"id", "content", "score", "created_at"}
        assert call("/aml/search", {"query": "x", "user_id": "u", "top_k": 0})[0] == 400
    finally:
        httpd.shutdown()
