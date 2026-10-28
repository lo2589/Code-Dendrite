"""Turn a JavaScript module specifier into the file it names.

`require('./layout/ranking')` is easy and was already handled. `require('pkg/layout/ranking')`
is the one that matters, because that is what a module system's own output looks like,
and it was answered with "package calls remain external" — so a project organised into
modules had no cross-file edges at all, silently.

Nothing here knows about any particular project. Every answer comes from something the
project itself wrote down: a package.json's ``exports``/``main``, a tsconfig's ``paths``,
a workspace sibling's ``name``, or node_modules. That is the whole point — a rule keyed
to one repository would fix one repository.
"""

from __future__ import annotations
from scanner.shared.walk_exclude import keep_dir

import json
import os
import posixpath
from typing import Dict, List, Optional, Tuple

EXTENSIONS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")

# Conditions we answer to when reading a conditional export. Order is the
# preference: source before build output, because an index of the build output
# is an index of a copy.
CONDITIONS = ("source", "development", "import", "require", "node", "browser", "default")


def _read_json(path: str) -> Optional[dict]:
    try:
        with open(path, "r", encoding="utf8") as handle:
            return json.load(handle)
    except Exception:
        return None


def _walk_up(start_dir: str, root: str):
    """Yield `start_dir` and each parent up to and including `root`."""
    current = os.path.abspath(start_dir)
    stop = os.path.abspath(root)
    while True:
        yield current
        if current == stop or os.path.dirname(current) == current:
            return
        parent = os.path.dirname(current)
        if not parent.startswith(stop):
            return
        current = parent


class JsResolver:
    """Resolve specifiers for one repository, remembering what it has read.

    A project's manifests do not change while an index is being built, so they are
    read once. The cost of getting this wrong is a per-call-site directory walk over
    a repository with thousands of call sites.
    """

    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        self._manifests: Dict[str, Optional[dict]] = {}
        self._packages: Optional[Dict[str, Tuple[str, dict]]] = None
        self._ts_configs: Dict[str, Optional[dict]] = {}

    # -- manifests ---------------------------------------------------------

    def _manifest(self, directory: str) -> Optional[dict]:
        if directory not in self._manifests:
            self._manifests[directory] = _read_json(os.path.join(directory, "package.json"))
        return self._manifests[directory]

    def _nearest_manifest(self, from_dir: str) -> Tuple[Optional[dict], Optional[str]]:
        for directory in _walk_up(from_dir, self.root):
            found = self._manifest(directory)
            if found is not None:
                return found, directory
        return None, None

    def _by_name(self) -> Dict[str, Tuple[str, dict]]:
        """Every package.json in the repo, keyed by the name it declares.

        A monorepo's packages refer to each other by name, and — the case that
        matters here — a package refers to ITSELF by name, which is legal Node
        and is what a bundle's own parts do.
        """
        if self._packages is not None:
            return self._packages
        found: Dict[str, Tuple[str, dict]] = {}
        for base, dirs, files in os.walk(self.root):
            dirs[:] = [d for d in dirs if keep_dir(d)]  # 唯一一份跳过名单，见 scanner/shared/walk_exclude.py
            if "package.json" not in files:
                continue
            data = _read_json(os.path.join(base, "package.json"))
            name = (data or {}).get("name")
            if isinstance(name, str) and name and name not in found:
                found[name] = (base, data)
        self._packages = found
        return found

    def _tsconfig(self, from_dir: str) -> Tuple[Optional[dict], Optional[str]]:
        for directory in _walk_up(from_dir, self.root):
            if directory not in self._ts_configs:
                data = _read_json(os.path.join(directory, "tsconfig.json"))
                if data is None:
                    data = _read_json(os.path.join(directory, "jsconfig.json"))
                self._ts_configs[directory] = data
            if self._ts_configs[directory] is not None:
                return self._ts_configs[directory], directory
        return None, None

    # -- exports -----------------------------------------------------------

    @staticmethod
    def _pick_condition(value):
        """Reduce a conditional exports value to one target."""
        seen = 0
        while isinstance(value, dict) and seen < 8:
            seen += 1
            for condition in CONDITIONS:
                if condition in value:
                    value = value[condition]
                    break
            else:
                value = next(iter(value.values()), None)
        if isinstance(value, list):
            value = next((v for v in value if isinstance(v, str)), None)
        return value if isinstance(value, str) else None

    def _from_exports(self, exports, subpath: str) -> Optional[str]:
        """Map one subpath through an ``exports`` field.

        Exact keys win over patterns, which is Node's own rule and matters here:
        a package that declares both ``"./client"`` and ``"./*"`` means the first
        one for that subpath.
        """
        if isinstance(exports, str):
            return exports if subpath == "." else None
        if not isinstance(exports, dict):
            return None
        # A bare condition map with no "./" keys is the "." entry written short.
        if not any(str(k).startswith(".") for k in exports):
            return self._pick_condition(exports) if subpath == "." else None
        if subpath in exports:
            return self._pick_condition(exports[subpath])
        best: Optional[str] = None
        best_key = ""
        for key, value in exports.items():
            key = str(key)
            if "*" not in key:
                continue
            head, _, tail = key.partition("*")
            if not subpath.startswith(head) or not subpath.endswith(tail):
                continue
            if len(subpath) < len(head) + len(tail):
                continue
            # The most specific pattern wins, same as Node.
            if len(head) + len(tail) < len(best_key):
                continue
            target = self._pick_condition(value)
            if target is None:
                continue
            filled = subpath[len(head):len(subpath) - len(tail) or None]
            best = target.replace("*", filled)
            best_key = head + tail
        return best

    # -- the answer --------------------------------------------------------

    def candidates(self, specifier: str, importer_file: str) -> List[str]:
        """Files a specifier could name, repo-relative, best guess first.

        @param specifier - what was written inside require() or from '...'.
        @param importer_file - the repo-relative file doing the importing.
        @returns candidate paths; empty when nothing the project declared explains it.
        """
        if not specifier or not importer_file:
            return []
        importer = importer_file.replace("\\", "/")
        base_dir = posixpath.dirname(importer)

        if specifier.startswith("."):
            return self._expand(posixpath.normpath(posixpath.join(base_dir, specifier)))
        if specifier.startswith("/"):
            return self._expand(specifier.lstrip("/"))

        abs_dir = os.path.join(self.root, base_dir.replace("/", os.sep))
        out: List[str] = []

        # 1. tsconfig paths, which is the project saying what its own aliases mean.
        config, config_dir = self._tsconfig(abs_dir)
        if config is not None:
            options = (config.get("compilerOptions") or {})
            base_url = options.get("baseUrl") or "."
            paths = options.get("paths") or {}
            root_of = os.path.join(config_dir or self.root, str(base_url))
            for pattern, targets in paths.items():
                pattern = str(pattern)
                head, star, tail = pattern.partition("*")
                if star:
                    if not (specifier.startswith(head) and specifier.endswith(tail)):
                        continue
                    filled = specifier[len(head):len(specifier) - len(tail) or None]
                elif specifier != pattern:
                    continue
                else:
                    filled = ""
                for target in (targets if isinstance(targets, list) else [targets]):
                    resolved = str(target).replace("*", filled)
                    full = os.path.normpath(os.path.join(root_of, resolved))
                    out += self._expand(self._relative(full))

        # 2. A package name, its own or a sibling's, with the subpath run
        #    through whatever that package declared.
        name, subpath = _split_specifier(specifier)
        packages = self._by_name()
        entry = packages.get(name)
        if entry is not None:
            pkg_dir, data = entry
            target = self._from_exports(data.get("exports"), subpath)
            if target is None and subpath == ".":
                target = (data.get("module") or data.get("main")
                          or (data.get("browser") if isinstance(data.get("browser"), str) else None)
                          or "index.js")
            if target is None:
                # No exports field: a subpath is just a path inside the package.
                target = subpath[2:] if subpath.startswith("./") else None
            if target is not None:
                full = os.path.normpath(os.path.join(pkg_dir, str(target).lstrip("./")))
                out += self._expand(self._relative(full))

        # 3. node_modules, only useful when the dependency is indexed too.
        for directory in _walk_up(abs_dir, self.root):
            candidate = os.path.join(directory, "node_modules", *specifier.split("/"))
            out += self._expand(self._relative(candidate))

        return list(dict.fromkeys(p for p in out if p))

    # -- paths -------------------------------------------------------------

    def _relative(self, absolute: str) -> str:
        try:
            return os.path.relpath(absolute, self.root).replace(os.sep, "/")
        except ValueError:
            return ""

    @staticmethod
    def _expand(path: str) -> List[str]:
        """A path without an extension names several possible files."""
        if not path or path.startswith(".."):
            return []
        path = path.replace("\\", "/")
        if posixpath.splitext(path)[1] in EXTENSIONS:
            return [path]
        out = [path + ext for ext in EXTENSIONS]
        out += [posixpath.join(path, "index" + ext) for ext in EXTENSIONS]
        return out


def _split_specifier(specifier: str) -> Tuple[str, str]:
    """Split `@scope/pkg/deep/path` into the package name and its subpath."""
    parts = specifier.split("/")
    if specifier.startswith("@") and len(parts) >= 2:
        name = "/".join(parts[:2])
        rest = parts[2:]
    else:
        name = parts[0]
        rest = parts[1:]
    return name, ("./" + "/".join(rest)) if rest else "."


_CACHE: Dict[str, JsResolver] = {}


def resolver_for(root: str) -> JsResolver:
    """One resolver per repository, kept so the manifests are read once."""
    key = os.path.abspath(root)
    if key not in _CACHE:
        _CACHE[key] = JsResolver(key)
    return _CACHE[key]
