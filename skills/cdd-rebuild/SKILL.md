---
name: cdd-rebuild
description: Restructure a project's topology (move modules, split files, cut coupling) with CodeDendrite's `cdd` CLI checking every step against the real call graph. Use when (1) the user wants to reorganise directories, split a large file or merge duplicate modules, (2) you need to know who is affected if a file or symbol moves, (3) you need to see the current topology before planning a refactor, (4) you must verify a refactor did not break dependencies, (5) the user says "this module is a mess", "too coupled", 拆一下, 耦合太高.
---

# cdd-rebuild: topology refactoring

Rule: **see the topology → plan → move in small steps → re-index and verify after every step**. `<root>` is the project directory. Setup: `pip install git+https://github.com/lo2589/Code-Dendrite`.

## Step 0: fresh index

```bash
cdd update <root>
```

A stale index lies about everything that follows.

## Step 1: see the current topology

```bash
cdd summary <root> --full            # hub ranking: files and directories with the most edges
cdd tree build <root>                # semantic module tree + HTML
cdd tree check <root>                # coverage: which areas no module explains
cdd tree candidates <root>           # capability candidates the system sees
cdd module-graph <root> --no-isolated   # module graph without isolated modules
```

Products are in `<root>/.codedendrite/`: `module_tree_v2.json` (for programs) and `module_tree_v2.html` (for people).

## Step 2: pick what to move

```bash
cdd owner <file>::<symbol> <root>     # which module a symbol belongs to now
cdd module <module id or name> <root> # what a module is made of
cdd modules "cache" <root>            # modules related to a keyword
```

Smells:
- high in **and** out edges in `summary --full` = a hub; splitting it pays most
- a chain that crosses several semantic areas in the module tree = leaked responsibility
- same or near-same module names = merge candidates

## Step 3: blast radius before moving

```bash
cdd callers <file>::<symbol> <root> --depth 4   # everyone upstream: the imports you will have to fix
cdd chain <file>::<symbol> <root> --depth 6     # what it depends on: move it along or keep the import
cdd show <file>::<symbol> <root>                # direct in / out edges
```

With the MCP server configured, `cd_impact <symbol>` gives the blast radius in one call.

## Step 4: move, then verify every batch

```bash
cdd update <root> --files <moved files...>      # incremental re-index
cdd chain <key entry> <root> --depth 8          # spot-check that key paths still connect
cdd archify <key entry> <root>                  # optional: a diagram of the path, to compare before / after
```

Moving a large batch and verifying once means that when something breaks you cannot tell which move did it. **Small steps, re-index each time.**

## Step 5: report

```bash
cdd tree build <root>
cdd summary <root> --full
```

Report: module count before / after, edge counts of the hub files before / after, and the list of paths that broke and were reconnected.

## Notes

- CodeDendrite does **not** move files. It shows and verifies; `git mv` is done by you or the user.
- After moving a Python file its imports break; `cdd callers` lists exactly the importers to fix.
- After a mass rename run `cdd update` before analysing, or you are looking at old anchors.
- Refactor one semantic area at a time, following the module tree.
