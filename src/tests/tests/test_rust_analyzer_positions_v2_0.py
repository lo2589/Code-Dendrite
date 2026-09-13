from scanner.language.pipeline import parse_paths
from scanner.language.rust.analyzer import RustAnalyzer


def test_gbk_source_with_backslash_trail_byte_keeps_later_functions(tmp_path):
    # 「乗」的 GBK 编码是 81 5C；按 UTF-8 ignore 读只剩一个反斜杠，把右引号转义掉，
    # 字符串一路吞到 after_one 里的下一个引号
    source = (
        'fn before() { let a = "p"; }\n'
        '\n'
        'fn with_str() {\n'
        '    let s = "乗";\n'
        '}\n'
        '\n'
        'fn after_one() { let t = "x"; }\n'
        '\n'
        'fn after_two() {}\n'
    )
    path = tmp_path / "gbk.rs"
    path.write_bytes(source.encode("gbk"))

    functions = {f.name: f for f in RustAnalyzer(str(tmp_path)).analyze_file(str(path)).functions}

    assert set(functions) == {"before", "with_str", "after_one", "after_two"}
    assert (functions["with_str"].line_number, functions["with_str"].line_end) == (3, 5)
    assert functions["after_one"].line_number == 7


def test_struct_enum_trait_anchors_carry_real_line_ranges(tmp_path):
    path = tmp_path / "lib.rs"
    path.write_text(
        "// struct Fake in a comment\n"
        "const NOTE: &str = \"enum AlsoFake {}\";\n"
        "\n"
        "#[derive(Debug)]\n"
        "pub struct Point {\n"
        "    x: i32,\n"
        "}\n"
        "\n"
        "struct Meters(u32);\n"
        "\n"
        "enum Mode {\n"
        "    A,\n"
        "    B,\n"
        "}\n"
        "\n"
        "trait Draw {\n"
        "    fn draw(&self);\n"
        "}\n",
        encoding="utf-8",
    )

    parsed, failures, _ = parse_paths(tmp_path, [path])

    assert not failures
    ranges = {a.symbol: (a.line_start, a.line_end) for a in parsed.values() if a.symbol_type == "class"}
    assert ranges == {"Point": (5, 7), "Meters": (9, 9), "Mode": (11, 14), "Draw": (16, 18)}
