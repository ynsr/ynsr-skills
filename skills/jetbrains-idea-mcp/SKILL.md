---
name: jetbrains-idea-mcp
description: "Use when connecting to the JetBrains IDEA MCP server (SSE endpoint) for IDE-aware code operations: search, read, build, debug, run, refactor, terminal, VCS, database."
---

# JetBrains IDEA MCP Server

The IntelliJ IDEA MCP Server (bundled since IDEA 2025.2) exposes the running IDE's capabilities to external MCP clients — semantic code search, PSI-aware reading, compilation, debugger control, run configurations, database queries, and VCS status.

## Connection

The MCP Server is configured in **Settings | Tools | MCP Server** in the IDE. The IDE offers three transport types:

- **SSE** — e.g. `http://127.0.0.1:<port>/sse`
- **Stdio** — via `idea` CLI launcher
- **HTTP Stream**

### Important headers

When connecting via SSE, the `IJ_MCP_SERVER_PROJECT_PATH` header (set by the IDE auto-config or manually) **scopes which projects the server sees**. Only files and modules under that path are reachable. If you don't see a file or tool response is empty, confirm the header matches the expected project root.

## Available Tools

Every tool accepts an optional `projectPath` parameter — set it to the project root if the tool requires it. Leave unset when the scoped project is already correct.

### File & Read
- `read_file(file_path, mode, start_line, max_lines, ...)` — Read file with multiple modes (slice, lines, line_columns, offsets, indentation). Can read within archives (jars, jrt) and decompile class files. **Prefer over terminal `cat` for any file the IDE has indexed.**
- `create_new_file(pathInProject, text, overwrite)` — Create file with content inside the project.
- `open_file_in_editor(filePath)` — Open file in the IDE editor.
- `get_all_open_file_paths` — List all currently open editor tabs.
- `list_directory_tree(directoryPath, maxDepth)` — Recursive directory tree (like `tree` command).

### Search (semantic — use these instead of grep/find)
- `search_symbol(q, paths, include_external, limit)` — Find symbols (classes, methods, fields) via IDE index. Use `include_external=true` to search SDK/lib symbols. **Prefer over text/regex for symbol lookup.**
- `search_text(q, paths, limit)` — Fast literal substring search across project files.
- `search_regex(q, paths, limit)` — Regex search in project files with line/column/offset coordinates.
- `search_file(q, paths, limit)` — Glob path search within the project.
- `skill_search(mode, q, paths, ...)` — Unified search dispatching to file/text/regex/symbol by `mode`.

### Analysis & Build
- `analyze_calls(symbolFqn, analysisKind, depth, maxNodes, treePath, ...)` — IDE Call Hierarchy. `analysisKind`: `INCOMING_CALLS` (callers) or `OUTGOING_CALLS` (callees). **More precise than text/regex for call dependency analysis** — uses IDE index, not text matching.
- `get_file_problems(filePath, errorsOnly)` — Run IDE inspections on a single file, return errors/warnings.
- `lint_files(files, min_severity)` — Run inspections on multiple files at once.
- `build_project(rebuild, filesToRebuild, timeout)` — Compile project or specific files. **Call after edits to validate.**
- `get_project_dependencies` — List project library dependencies.
- `get_project_modules` — List project modules with types.
- `get_symbol_info(filePath, line, column)` — Quick-documentation style info for a symbol at a position.

### Refactoring & Patch
- `rename_refactoring(pathInProject, symbolName, newName)` — Context-aware rename via PSI (preferred over text search-and-replace).
- `apply_patch(input)` — Apply Codex apply_patch or unified Git diff format patches.
- `reformat_file(path)` — Format file using IDE code style settings.

### Execution
- `get_run_configurations(filePath?)` — List run configurations project-wide, or discover runnable entry points in a specific file.
- `execute_run_configuration(configurationName, filePath+line, timeout, waitForExit, programArguments, ...)` — Run a config or temporary run target. Supports one-time launch overrides when `supportsDynamicLaunchOverrides=true`.

### Debugger
- `xdebug_start_debugger_session(configurationName?, filePath+line?)` — Start a debug session (set breakpoints first, else the run may complete without pausing).
- `xdebug_set_breakpoint(breakpointId?, filePath, line, condition, isLogMessage, ...)` — Set/modify breakpoints (line, temporary, conditional, tracepoint).
- `xdebug_control_session(sessionId, action)` — RESUME, STEP_OVER/INTO/OUT, PAUSE, WAIT_FOR_PAUSE, DRAIN_EVENTS, etc.
- `xdebug_get_stack(sessionId)` — Get current thread stack frames.
- `xdebug_get_frame_values(sessionId, frameIndex)` — Inspect local variables in a stack frame.
- `xdebug_evaluate_expression(sessionId, frameIndex, expression)` — Evaluate an expression in the debug context.
- `xdebug_get_value_by_path(sessionId, frameIndex, path)` — Drill into complex values.
- `xdebug_set_variable(sessionId, frameIndex, path, newValue)` — Mutate a variable.
- `xdebug_list_breakpoints(sessionId?, filePath?)` — List breakpoints; optional location filter.

### Terminal
- `execute_terminal_command(command, executeInShell, timeout, maxLinesCount, truncateMode)` — Run shell command in IDE terminal. Requires user confirmation unless **Brave Mode** is enabled in MCP Server settings.

### Database (requires Database Tools & SQL plugin + AI Assistant plugin)
- Connection lifecycle: `list_database_connections` → `create_database_connection` / `edit_database_connection`
- Schema: `list_database_schemas` → `introspect_schema` → `list_schema_object_kinds` → `list_schema_objects` → `get_database_object_description`
- Query: `execute_sql_query` → `fetch_query_result` (pagination), `cancel_sql_query`
- Preview: `preview_table_data`
- History: `list_recent_sql_queries`

### VCS
- `get_repositories` — List all VCS roots in the project.
- `git_status(repositoryPathRelativeToProject, includeUntracked, includeIgnored)` — Porcelain-style status with summary counters.

### Universal
- `execute_tool(command)` — Invoke any IDE MCP tool from a command-line string. Useful for scripting or clients that can't bind individual tools.

### Inspection.kts (authoring IntelliJ inspection scripts)
- `generate_inspection_kts_api(language)` / `generate_inspection_kts_examples(language)` — API docs and example templates.
- `generate_psi_tree(code, language)` — Parse code and show its PSI tree (for inspection writing).
- `run_inspection_kts(inspectionKtsCode, contextPath, targetFileContent?)` / `validate_inspection_kts(inspectionKtsCode, pathToSpecification)` — Compile, run, and validate inspection scripts.

## When to use this skill

- You need IDE-aware code operations: symbol search over call hierarchy, PSI-based read/refactor, project compilation, or debugger control.
- IntelliJ IDEA is running with the bundled MCP Server plugin enabled (Settings | Tools | MCP Server).
- You have the connection details (URL/port) from the IDE's MCP Server settings panel.
- Prefer `search_symbol` (IDE-indexed) over grep for finding classes/methods/fields.
- Prefer `analyze_calls` (call hierarchy) over text search for call dependency analysis.
- Prefer `read_file` (PSI-aware, can decompile classes/jar entries) over terminal `cat`.
- After edits, call `build_project` or `lint_files` to validate compilation.

## Pitfalls

- **Project scope**: The `IJ_MCP_SERVER_PROJECT_PATH` header (for SSE) or equivalent config scopes which project files are accessible. Verify this matches your target project root.
- **Brave Mode**: `execute_terminal_command` requires interactive user confirmation unless Brave Mode is enabled (Settings | Tools | MCP Server → Command execution).
- **Database tools**: Require both the **Database Tools and SQL** plugin and the **AI Assistant** plugin to be installed and enabled.
- **Debugger**: Always set at least one breakpoint before calling `xdebug_start_debugger_session`, or the program may run to completion without pausing.
- **`projectPath` parameter**: Many tools accept it to disambiguate which project to operate on. Pass it explicitly when working in multi-project IDE windows.
- **MCP Server must be enabled**: Toggle on in Settings | Tools | MCP Server.
- **Tool visibility**: Tools can be hidden behind the dedicated router tool. If a tool you expect isn't showing, check Settings | Tools | MCP Server → Exposed Tools for router-only settings.