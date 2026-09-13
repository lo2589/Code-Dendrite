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


def test_lens_plugin_self_chain_is_not_flattened_or_cross_wired():
    root = Path(__file__).resolve().parents[3] / "lens"   # 插件已拉到顶层，与 src 平级
    paths = [
        root / "src" / "host.js",
        root / "src" / "index_worker.js",
        root / "lib" / "client.js",
    ]
    parsed, failures, completed = parse_paths(root, paths)
    assert not failures
    assert len(completed) == len(paths)
    anchors = _anchors(parsed)

    fake = {"call", "or", "is", "target", "can", "showed"}
    assert not fake.intersection(
        item.symbol for item in anchors.values() if item.symbol_type == "class"
    )

    host = anchors["src/host.js::apply"]
    # 行号从源码现算，不写死：往插件文件前面加几行就会让 115 变成 139，而这条测试
    # 真正要验的是"锚点落在那个函数上、父子链没被压平"，不是某个魔数。
    source_lines = (root / "src" / "host.js").read_text(encoding="utf-8").split("\n")
    apply_at = next(
        i for i, line in enumerate(source_lines, 1) if line.strip().startswith("apply(")
    )
    assert host.line_start <= apply_at <= host.line_end
    assert host.line_end > host.line_start + 500
    route = anchors["src/host.js::apply.register#1"]
    route_handler = anchors["src/host.js::apply.register#1.handler"]
    assert route.parent_anchor == host.id
    assert route_handler.parent_anchor == route.id
    assert "src/host.js::apply.json" in route_handler.callees

    worker_chain = anchors["src/index_worker.js::chain#1"]
    worker_visit = anchors["src/index_worker.js::chain#1.visit"]
    assert worker_visit.parent_anchor == worker_chain.id
    assert "src/index_worker.js::chain#1.visit" in worker_visit.callees
    assert "src/index_worker.js::describe" in worker_chain.callees

    lens = anchors["lib/client.js::factory#49.LensPanel"]
    effect = anchors["lib/client.js::factory#49.LensPanel.useEffect#1"]
    assert lens.line_end > lens.line_start
    assert effect.parent_anchor == lens.id
