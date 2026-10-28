"""CDD V1.20 JS/TS lexical-scope and call-chain regressions."""

from pathlib import Path

from analyzer.anchors import _finalize_anchor_graph, generate_all_anchors, load_anchors
from scanner.language.typescript.analyzer import TypeScriptAnalyzer
from scanner.language.pipeline import parse_paths
from analyzer.shared.types import Anchor


def _anchors(parsed):
    values = {
        item.id: Anchor(
            id=item.id, symbol=item.symbol, file=item.file,
            line_start=item.line_start, line_end=item.line_end,
            hash=item.hash, language=item.language,
            symbol_type=item.symbol_type, parent_anchor=item.parent_anchor,
            callees=item.callees, call_sites=item.call_sites,
        )
        for item in parsed.values()
    }
    _finalize_anchor_graph(values)
    return values


def test_comments_strings_and_regexes_do_not_create_fake_classes(tmp_path):
    source = (
        "// class call is not real\n"
        "const text = 'class or {}';\n"
        "const pattern = /class\\s+target/;\n"
        "class Real { run(){ return 1; } }\n"
    )
    analyzer = TypeScriptAnalyzer(str(tmp_path))
    assert analyzer._extract_classes(source) == ["Real"]


def test_nested_functions_have_real_ranges_and_scoped_calls(tmp_path):
    path = tmp_path / "plugin.js"
    path.write_text(
        "module.exports = {\n"
        "  apply(ctx) {\n"
        "    const projector = createProjector();\n"
        "    function resolveSession(){ return readSessionMeta(); }\n"
        "    server.register({ handler: async (req, res) => {\n"
        "      const meta = await resolveSession();\n"
        "      projector.schedule(meta);\n"
        "    }});\n"
        "  }\n"
        "};\n"
        "function createProjector(){\n"
        "  function schedule(job){ return job; }\n"
        "  return { schedule };\n"
        "}\n"
        "function readSessionMeta(){ return {}; }\n",
        encoding="utf-8",
    )
    parsed, failures, _ = parse_paths(tmp_path, [path])
    assert not failures
    anchors = _anchors(parsed)

    assert not [item for item in anchors.values() if item.symbol_type == "class"]
    assert anchors["plugin.js::apply"].line_end == 9
    assert anchors["plugin.js::apply.resolveSession"].parent_anchor == "plugin.js::apply"
    handler = anchors["plugin.js::apply.handler"]
    assert handler.line_start == 5 and handler.line_end == 8
    assert "plugin.js::apply.resolveSession" in handler.callees
    assert "plugin.js::createProjector.schedule" in handler.callees
    assert "plugin.js::readSessionMeta" in anchors["plugin.js::apply.resolveSession"].callees
    # Nested handler calls belong to the handler, not its enclosing apply().
    assert "plugin.js::apply.resolveSession" not in anchors["plugin.js::apply"].callees
    assert "plugin.js::apply.handler" in anchors["plugin.js::apply"].callees


def test_receiver_call_never_becomes_an_unrelated_leaf_candidate(tmp_path):
    prod = tmp_path / "prod.js"
    fake = tmp_path / "test.js"
    prod.write_text("function run(ctx) { return ctx.get('service'); }\n", encoding="utf-8")
    fake.write_text("function get() { return null; }\n", encoding="utf-8")
    parsed, failures, _ = parse_paths(tmp_path, [prod, fake])
    assert not failures
    anchors = _anchors(parsed)
    site = anchors["prod.js::run"].call_sites[0]
    assert site["target"] == "get"
    assert site["resolution"] == "unresolved"
    assert "candidate_ids" not in site
    assert not anchors["test.js::get"].callers


def test_js_static_url_helper_connects_to_registered_route(tmp_path):
    (tmp_path / "host.js").write_text(
        "const ROUTE = '/plugin';\n"
        "function apply(server) {\n"
        "  server.register({ path: ROUTE + '/state', handler: async (req, res) => {\n"
        "    return res.end('ok');\n"
        "  }});\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "client.js").write_text(
        "const ROUTE = '/plugin';\n"
        "async function getJson(url) { return fetch(url); }\n"
        "function stateUrl() { return ROUTE + '/state?session=x'; }\n"
        "async function loadState() { return getJson(stateUrl()); }\n",
        encoding="utf-8",
    )
    generate_all_anchors(str(tmp_path))
    anchors = load_anchors(str(tmp_path))
    load = anchors["client.js::loadState"]
    site = next(site for site in load.call_sites if site.get("bridge_kind") == "js-http")
    assert site["target"] == "host.js::apply.handler"
    assert site["resolution"] == "exact"


def test_worker_postmessage_connects_both_message_handlers(tmp_path):
    (tmp_path / "host.js").write_text(
        "const PROJECTION_WORKER = path.resolve(__dirname, 'worker.js');\n"
        "function createProjector() {\n"
        "  const worker = new Worker(PROJECTION_WORKER);\n"
        "  function launch(job) { worker.postMessage(job); }\n"
        "  worker.on('message', (message) => { finish(message); });\n"
        "  return { launch };\n"
        "}\n"
        "function finish() {}\n",
        encoding="utf-8",
    )
    (tmp_path / "worker.js").write_text(
        "parentPort.on('message', (job) => {\n"
        "  project(job);\n"
        "  parentPort.postMessage(job);\n"
        "});\n"
        "function project() {}\n",
        encoding="utf-8",
    )
    generate_all_anchors(str(tmp_path))
    anchors = load_anchors(str(tmp_path))
    launch = anchors["host.js::createProjector.launch"]
    sent = next(site for site in launch.call_sites if site.get("bridge_kind") == "worker-message")
    # Anonymous callbacks are named by their order among same-named siblings,
    # not by line, so a unique one carries no suffix at all.
    assert sent["target"].startswith("worker.js::on")
    worker_handler = anchors[sent["target"]]
    returned = next(site for site in worker_handler.call_sites if site.get("bridge_kind") == "worker-message")
    assert returned["target"].startswith("host.js::createProjector.on")


def test_rust_cfg_duplicates_and_tauri_invokes_are_preserved(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.js").write_text(
        "import { invoke } from '@tauri-apps/api/core';\n"
        "async function focusAgent() {\n"
        "  await invoke('focus', { windowId: 'w', agentId: 'a' });\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "main.rs").write_text(
        "#[cfg(target_os = \"macos\")]\n"
        "fn run_server() {}\n"
        "\n"
        "#[cfg(target_os = \"windows\")]\n"
        "fn run_server() {}\n"
        "\n"
        "#[cfg(target_os = \"macos\")]\n"
        "fn keystroke_yes() {}\n"
        "\n"
        "#[cfg(target_os = \"windows\")]\n"
        "fn keystroke_yes() {}\n"
        "\n"
        "#[tauri::command]\n"
        "fn approve() { keystroke_yes(); }\n"
        "\n"
        "#[tauri::command]\n"
        "fn focus() {}\n"
        "\n"
        "#[tauri::command]\n"
        "fn set_auto_approve() {}\n"
        "\n"
        "#[tauri::command]\n"
        "fn get_auto_approve() {}\n"
        "\n"
        "fn main() {\n"
        "  run_server();\n"
        "  tauri::Builder::default()\n"
        "    .invoke_handler(tauri::generate_handler![approve, focus, set_auto_approve, get_auto_approve]);\n"
        "}\n",
        encoding="utf-8",
    )

    generate_all_anchors(str(tmp_path))
    anchors = load_anchors(str(tmp_path))

    run_server_ids = sorted(aid for aid in anchors if aid.startswith("src/main.rs::run_server"))
    assert run_server_ids == [
        "src/main.rs::run_server@cfg(target_os=macos)",
        "src/main.rs::run_server@cfg(target_os=windows)",
    ]
    keystroke_ids = sorted(aid for aid in anchors if aid.startswith("src/main.rs::keystroke_yes"))
    assert keystroke_ids == [
        "src/main.rs::keystroke_yes@cfg(target_os=macos)",
        "src/main.rs::keystroke_yes@cfg(target_os=windows)",
    ]
    assert anchors["src/main.rs::focus"].registered_as == "focus"

    focus_agent = anchors["src/app.js::focusAgent"]
    invoke_site = next(site for site in focus_agent.call_sites if site.get("bridge_kind") == "tauri-command")
    assert invoke_site["target"] == "src/main.rs::focus"

    main = anchors["src/main.rs::main"]
    assert set(run_server_ids) <= set(main.callees)
    registered = {
        site["target"]
        for site in main.call_sites
        if site.get("bridge_kind") == "tauri-command-registration"
    }
    assert registered == {
        "src/main.rs::approve",
        "src/main.rs::focus",
        "src/main.rs::set_auto_approve",
        "src/main.rs::get_auto_approve",
    }
    approve = anchors["src/main.rs::approve"]
    assert set(keystroke_ids) <= set(approve.callees)
    assert "src/app.js::focusAgent" in anchors["src/main.rs::focus"].callers
    assert "src/main.rs::main" in anchors["src/main.rs::approve"].callers
    assert "src/main.rs::approve" in anchors["src/main.rs::keystroke_yes@cfg(target_os=macos)"].callers


# 以前这条测试拿 lens 插件的活代码当样本（host.js / index_worker.js / client.js），
# lens 一改名就红：index_worker.js::chain#1 改没了、LensPanel 删掉了，09-14 起它就一直
# 失败，还被归成「pre-existing，不修」。它要验的从来不是 lens 长什么样，而是 JS 解析的
# 三件事：嵌套函数的父子链不被压平、递归自调用认得出、注释里的词不被当成类。
# 所以样本写死在这里，形状照 lens 当年那几段：插件 apply 里注册回调、worker 里递归 visit、
# 模块工厂里的组件带 useEffect。
_JS_SELF_CHAIN = {
    "src/host.js": (
        "// Every route here is reached from a click: a class call or class is never a class.\n"
        "module.exports = {\n"
        "  name: 'demo',\n"
        "  apply(ctx) {\n"
        "    const json = (res, body) => {\n"
        "      res.end(JSON.stringify(body))\n"
        "    }\n"
        "    const register = (path, handler) => ctx.routes.push({ path, handler })\n"
        "    register('/health', {\n"
        "      handler(req, res) {\n"
        "        json(res, { ok: true, note: 'the class target can be showed' })\n"
        "      },\n"
        "    })\n"
        "  },\n"
        "}\n"
    ),
    "src/worker.js": (
        "function describe(id) {\n"
        "  return String(id)\n"
        "}\n\n"
        "function walkAll(graph, seeds) {\n"
        "  const seen = new Set()\n"
        "  const visit = (id) => {\n"
        "    if (seen.has(id)) return\n"
        "    seen.add(id)\n"
        "    for (const next of graph.get(id) || []) visit(next)\n"
        "  }\n"
        "  seeds.forEach(visit)\n"
        "  const names = []\n"
        "  for (const id of seeds) names.push(describe(id))\n"
        "  return names\n"
        "}\n\n"
        "module.exports = { walkAll, describe }\n"
    ),
    "src/client.js": (
        "window.__loader.load({\n"
        "  id: 'demo/panel',\n"
        "  factory: (require) => {\n"
        "    const React = require('react')\n"
        "    function Panel(props) {\n"
        "      React.useEffect(function () {\n"
        "        props.onOpen()\n"
        "      }, [])\n"
        "      return null\n"
        "    }\n"
        "    return { Panel }\n"
        "  },\n"
        "})\n"
    ),
}


def test_js_self_chain_is_not_flattened_or_cross_wired(tmp_path):
    for rel, text in _JS_SELF_CHAIN.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text, encoding="utf-8")
    paths = [tmp_path / rel for rel in _JS_SELF_CHAIN]
    parsed, failures, completed = parse_paths(tmp_path, paths)
    assert not failures
    assert len(completed) == len(paths)
    anchors = _anchors(parsed)

    # 注释和字符串里的 "class call"、"class target" 不是类
    fake = {"call", "or", "is", "target", "can", "showed"}
    assert not fake.intersection(
        item.symbol for item in anchors.values() if item.symbol_type == "class"
    )

    # 插件 apply 里的注册回调：父子链不压平，回调调到 apply 里的辅助函数
    host = anchors["src/host.js::apply"]
    handler = anchors["src/host.js::apply.handler"]
    helper = anchors["src/host.js::apply.json"]
    assert handler.parent_anchor == host.id
    assert helper.parent_anchor == host.id
    assert helper.id in handler.callees

    # worker 里的递归：visit 挂在 walkAll 下、调自己；walkAll 调到顶层的 describe
    walk = anchors["src/worker.js::walkAll"]
    visit = anchors["src/worker.js::walkAll.visit"]
    assert visit.parent_anchor == walk.id
    assert visit.id in visit.callees
    assert "src/worker.js::describe" in walk.callees

    # 模块工厂里的组件和它的 effect：一层一层挂着
    panel = anchors["src/client.js::factory.Panel"]
    effect = anchors["src/client.js::factory.Panel.useEffect"]
    assert panel.parent_anchor == "src/client.js::factory"
    assert effect.parent_anchor == panel.id
    assert panel.line_end > panel.line_start
