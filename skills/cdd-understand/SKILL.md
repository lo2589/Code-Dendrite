---
name: cdd-understand
description: Understand an unfamiliar codebase from static analysis (AST call/dataflow/inheritance edges, not vector search) with CodeDendrite's `cdd` CLI. Use when (1) opening a repository for the first time, (2) locating where a symbol or feature is defined and who calls it / what it calls, (3) checking the blast radius before an edit, (4) building a compact task-context packet for a smaller model, (5) the user asks "what does this project do", "where is X implemented", 看懂这个项目, 某个功能在哪实现.
---

# cdd-understand: understand a codebase

CodeDendrite indexes a project into anchors (function / class / method) and causal edges (call, dataflow, inherit, impact, dispatch). Every command reads the index, so answers come from the code, not from guesses. `<root>` is the project directory and may be omitted when you are already in it.

## Setup (once per machine, once per project)

```bash
pip install git+https://github.com/lo2589/Code-Dendrite   # Python >= 3.10, standard library only; gives `cdd`
cdd update <root>                                          # build the index; rerun after edits, it is incremental
cdd update <root> --files src/foo.py src/bar.py            # refresh only these files
cdd status <root>                                          # where the index is, how many anchors, when updated
```

If a query comes back empty, the index is missing or stale: run `cdd update` first.

## Workflow 1: the whole project in a minute

```bash
cdd summary <root>          # module dependency summary: hub directories ranked by edges
cdd summary <root> --full   # same, with anchor counts
cdd tree build <root>       # semantic module tree + HTML (.codedendrite/module_tree_v2.*)
cdd map <root>              # interactive code map HTML (for the user, not for you)
```

Reading it: directories with the most edges are hubs (changes there spread); where incoming edges far exceed outgoing, you are looking at a foundation layer.

## Workflow 2: locate symbols and relations

```bash
cdd anchors <keyword> <root>             # search anchors by path keyword
cdd file <relative/path.py> <root>       # classes and functions in one file
cdd show <file>::<symbol> <root>         # direct relations of one node
cdd find <keyword> <root>                # call / inherit / dataflow relations by keyword
cdd chain <file>::<symbol> <root> --depth 10   # what it calls, down to the implementation
cdd callers <file>::<symbol> <root>            # who calls it
cdd code <file>::<symbol> <root>               # print its source
```

Use the full anchor id `path/to/file.py::Class.method`. An ambiguous name lists every candidate id; rerun with the one you mean.

## Workflow 3: context and blast radius before an edit

```bash
cdd context "<symbol or keyword>" <root>          # compact task context packet (small-model sized)
cdd context "<symbol or keyword>" <root> --full   # full L0/L1/L2 packet
cdd chain2context <file>::<symbol> <root> --depth 6 --budget 8000   # chain + source of every anchor on it
cdd callers <file>::<symbol> <root> --depth 4     # everything upstream that a change can break
cdd debug <file> "<error text>" <root>            # rank suspicious functions for an error
```

With the MCP server configured (README, "MCP server"), the same answers come from tools: `cd_context`, `cd_symbol`, `cd_search`, `cd_impact`, `cd_modules`. Run `cd_impact` before every non-trivial edit.

## Workflow 4: pictures for the user

```bash
cdd graph <root> --focus <file>::<symbol> --radius 2   # relation graph around a symbol
cdd timeline <file>::<symbol> <root> --depth 5         # call timeline
```

## Notes

- Everything here is read-only except `cdd update` / `cdd rebuild` (index) and the `cdd log-*` commands (they insert temporary prints into source; `cdd log-remove` takes them out).
- Keep `--depth` small first; a deep chain is noise until you know which branch matters.
- Inheritance (which parent defines a method) has a Python API:
  ```python
  from api import trace_inheritance, find_method_origin
  trace_inheritance("ClassName", method="method_name", root="<root>")
  ```
- Build output (`build/lib*`, `dist/`, `node_modules/`, virtualenvs) never enters the index. Exclude anything else project-specific with `cdd ignore add <pattern> <root>`.
