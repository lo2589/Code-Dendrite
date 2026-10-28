---
name: cdd-diagram
description: Draw a diagram of how a real codebase works where every edge is a call that static analysis found in the code, not something the agent inferred. CodeDendrite's `cdd archify` turns a call chain into an archify interactive HTML diagram, one node per file, with source links pinned to the current commit and verified line by line. Use when the user asks to diagram, map or visualise a code path, request flow, feature or entry point of THIS repository ("draw how X works", "map the call flow from main", "architecture diagram of this code", 把这段调用画出来, 画一下这个功能的代码流程), or wants a diagram they can trust for review. For diagrams of ideas or plans with no code behind them, use archify directly.
---

# cdd-diagram: diagrams whose edges come from the code

archify renders and validates the picture; CodeDendrite supplies the facts. `cdd archify` walks the call graph from an entry function, groups the functions it reaches by file, and writes archify's Architecture JSON:

- **node** = a file on the path; `SRC n` lists the functions on the path with their line ranges
- **edge** = the index has a real call from one file into the other; the label is the callee
- **column** = call depth from the entry, so the picture reads left to right in call order
- **dashed box** = a layer (`src/usage`, `src/analyzer`, ...), drawn only when it encloses no node from another layer
- `meta.repository` pins the origin URL and HEAD; archify checks every cited line against that commit

## Setup (once)

```bash
pip install git+https://github.com/lo2589/Code-Dendrite   # gives `cdd`
npx skills add tt-a1i/archify -g                          # the renderer (needs Node.js)
cdd update <root>                                         # index the project
```

`cdd archify` finds archify in the usual global skill folders (`~/.agents`, `~/.claude`, `~/.codex`, `~/.cursor`, opencode). Point `ARCHIFY_CLI` at `archify/bin/archify.mjs` and `ARCHIFY_NODE` at a node binary if they live elsewhere.

## Draw

1. Find the entry. If the user names a feature rather than a function:
   ```bash
   cdd anchors <keyword> <root>
   cdd context "<feature>" <root>
   ```
2. Check the path is the one they mean, keeping depth modest:
   ```bash
   cdd chain <file>::<symbol> <root> --depth 6
   ```
3. Draw it:
   ```bash
   cdd archify <file>::<symbol> <root> --depth 6
   ```
   The output is `<root>/.codedendrite/archify/<name>.html` plus the IR next to it. Give the user the HTML path. They can press `/` to find a node, `R` to trace a path, and use Upstream / Downstream on a focused node.

Without archify installed, `cdd archify` still writes the IR and prints the exact render command.

## When archify rejects the layout

`cdd archify` prints archify's diagnostics (`code`, subject, measured evidence). Layout problems (a label that does not fit, a crowded corridor) are fixed in the IR with the fields archify lists under `supportedFixes`, then render again with the printed command. Two rounds at most.

Do **not** add, remove or relabel edges or nodes by hand. The point of this diagram is that every edge exists in the code. To show less, lower `--depth` or start from a deeper entry. To show more, raise `--depth`.

## Reading it with the user

- Lead with the path in one sentence: "the request enters at `server.py`, builds the packet in `anchor.py`, loads the index in `core_load.py`".
- Point at `SRC` markers for line ranges, and quote `file:line`.
- If a file they expected is missing, the index has no static call into it from this entry. Check `cdd callers` on it before claiming it is unused: dynamic dispatch or reflection can hide a call.
- Lines in source links refer to the pinned commit. If `cdd archify` warned about uncommitted files, the line numbers for those files follow the working tree.
