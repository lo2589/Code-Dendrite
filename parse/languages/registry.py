"""Single source of truth for source-language extension routing."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class LanguageSpec:
    name: str
    extensions: tuple[str, ...]
    analyzer: str | None
    executable: bool = True


SPECS = (
    LanguageSpec("python", (".py", ".pyw"), "python"),
    LanguageSpec("typescript", (".ts", ".tsx"), "typescript"),
    LanguageSpec("javascript", (".js", ".jsx", ".mjs", ".cjs"), "typescript"),
    LanguageSpec("cpp", (".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx"), "cpp"),
    LanguageSpec("java", (".java",), "java"),
    LanguageSpec("kotlin", (".kt", ".kts"), "kotlin"),
    LanguageSpec("go", (".go",), "go"),
    LanguageSpec("rust", (".rs",), "rust"),
    LanguageSpec("swift", (".swift",), "swift"),
    LanguageSpec("php", (".php", ".phtml", ".php5", ".php7"), "php"),
    LanguageSpec("ruby", (".rb", ".rake", ".gemspec"), "ruby"),
    LanguageSpec("html", (".html", ".htm", ".xhtml"), "html"),
    LanguageSpec("csharp", (".cs",), "generic"),
    LanguageSpec("scala", (".scala", ".sc"), "generic"),
    LanguageSpec("objective-c", (".m", ".mm"), "generic"),
    LanguageSpec("shell", (".sh", ".bash", ".zsh"), "generic"),
    LanguageSpec("powershell", (".ps1", ".psm1", ".psd1"), "generic"),
    LanguageSpec("vue", (".vue",), "component"),
    LanguageSpec("svelte", (".svelte",), "component"),
    LanguageSpec("sql", (".sql",), "generic"),
    LanguageSpec("yaml", (".yaml", ".yml"), None, False),
    LanguageSpec("json", (".json",), None, False),
    LanguageSpec("toml", (".toml",), None, False),
)

_BY_EXTENSION = {ext: spec for spec in SPECS for ext in spec.extensions}


def language_for_path(path: str | Path) -> Optional[LanguageSpec]:
    return _BY_EXTENSION.get(Path(path).suffix.lower())


def supported_extensions(*, executable_only: bool = False) -> set[str]:
    return {
        ext
        for spec in SPECS
        if not executable_only or spec.executable
        for ext in spec.extensions
    }


def create_analyzer(root: str | Path, path: str | Path):
    spec = language_for_path(path)
    if spec is None or not spec.executable:
        return None
    if spec.analyzer == "generic":
        from parse.codeAnalysis.analyzer.generic_analyzer import GenericLanguageAnalyzer
        return GenericLanguageAnalyzer(str(root), spec.name, spec.extensions)
    if spec.analyzer == "component":
        from parse.codeAnalysis.analyzer.typescript_analyzer import TypeScriptAnalyzer
        return TypeScriptAnalyzer(str(root))
    from parse.codeAnalysis.analyzer import get_analyzer
    return get_analyzer(str(root), language=spec.analyzer)
