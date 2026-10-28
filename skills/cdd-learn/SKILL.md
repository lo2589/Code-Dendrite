---
name: cdd-learn
description: Teach a user a codebase layer by layer, from the whole-project map down to how data moves inside one function, using CodeDendrite's `cdd` CLI and its HTML views. Use when (1) the user says "walk me through this project", "help me understand this repo", 帮我看懂这个项目, 给我讲讲, (2) they want the implementation of one module or feature explained, (3) they need to trace where a value comes from and where it goes (dataflow), (4) onboarding a new teammate, (5) they want something to look at (code map, call timeline, relation graph, diagram).
---

# cdd-learn: guided, layer-by-layer learning

`cdd-understand` is for you to understand a project; this skill is for walking a **person** through it. The output is explanation plus pages they open in a browser. `<root>` is the project directory.

Setup is the same as cdd-understand: `pip install git+https://github.com/lo2589/Code-Dendrite`, then `cdd update <root>`.

## The path: L0 → L3

| Layer | Question it answers | Commands |
|------|-----------|------|
| L0 whole | What pieces is this made of? | `map`, `summary`, `tree build` |
| L1 module | What does this module do, who does it talk to? | `modules`, `module`, `graph` |
| L2 path | How does this feature go from entry to result? | `chain`, `timeline`, `archify` |
| L3 detail | How does data move through this code? | dataflow Python API |

Go in order and do not jump straight to L3. At every layer give the conclusion first, then the detail.

## L0: the map

```bash
cdd update <root>        # make sure the index is fresh
cdd map <root>           # code map HTML: have the user open it
cdd summary <root>       # hub ranking: which directories are the trunk
cdd tree build <root>    # semantic module tree + HTML
```

Tell the user: "this project is roughly N parts, the core is X", with the HTML path.

## L1: inside a module

```bash
cdd modules "<keyword>" <root>        # semantic modules matching a keyword
cdd module <module id or name> <root> # files and symbols in one module
cdd owner <file>::<symbol> <root>     # which module a function belongs to
cdd graph <root> --focus <core symbol> --radius 2   # the module's relations, as HTML
```

## L2: one feature, entry to result

```bash
cdd chain <entry> <root> --depth 12      # full call chain, down to the implementation
cdd timeline <entry> <root> --depth 8    # call timeline HTML: best for "what runs when"
cdd archify <entry> <root>               # interactive diagram, one node per file, edges are real calls
```

Narrate it as: entry → what each step does (one line) → where it crosses a file, process or transport (HTTP, worker: edges marked `dispatch` in relations.json) → what comes out.

## L3: how data moves

```python
from api import (
    analyze_dataflow,        # one function: inputs, outputs, transformations
    trace_variable,          # where one variable comes from and goes
    get_function_inputs, get_function_outputs, get_transformations,
    generate_dataflow_html,  # dataflow page for the user
)
analyze_dataflow("ClassName.method", "path/to/file.py")
trace_variable("path/to/file.py", "function_name", "variable_name")
```

Which parent class actually defines a method:

```python
from api import trace_inheritance, find_method_origin
trace_inheritance("ClassName", method="method_name", root="<root>")
```

## How to answer at each layer

1. **One-sentence conclusion** first ("this module does X").
2. **file:line** for every claim (e.g. `src/api/query/cmd_chain.py:168`) so they can jump there.
3. **One picture**: prefer an HTML path they can open; otherwise a text tree.
4. **Next step**: "which branch do you want to go into?" Let them steer.

## Notes

- On a big project do not pour every module out at L0; cover the 5 to 8 trunks with the most edges.
- Chain depth around 10 is enough; go deeper only when the explanation needs it.
- All generated HTML lives under `<root>/.codedendrite/`. Give the path; they can reopen it any time.
- When the user is stuck, go back one layer instead of digging further into L3.
