# Cline CLI Tool Mapping

Skills speak in actions ("dispatch a subagent", "create a todo", "read a file"). On Cline these resolve to the tools below.

| Action skills request | Cline equivalent |
|---|---|
| Read a file | `read_file` / `read_files` |
| Create a new file | `write_file` |
| Edit a file | `apply_patch` / `replace_in_file` |
| Run a shell command | `execute_command` |
| Search file contents | `search_files` |
| Find files by name | `search_files` / `list_files` |
| Fetch a URL | `fetch` / `web_fetch` |
| Search the web | `tavily_search` / `search` (if available) |
| Dispatch a subagent (`Subagent (general-purpose):` template) | `spawn_agent {systemPrompt, task}` — ephemeral, fresh context, returns report. This is the SDD/parallel-agents primitive. |
| Spawn a persistent teammate (long-lived collaborator) | `team_spawn_teammate {agentId, rolePrompt}` — lead-only, creates a named teammate; use `team_send_message` / `team_broadcast` to coordinate. **Not** the SDD primitive. |
| Task tracking ("create a todo", "mark complete") | Ledger file at `.superpowers/sdd/<plan>/progress.md` (SDD) plus artifacts; no `TodoWrite` tool — keep a markdown checklist in the ledger/workspace. |
| Invoke a skill | Skills auto-load from `~/.agents/skills/<name>/SKILL.md` (cross-runtime alias, shared with Codex/Copilot) and `<workspace>/.agents/skills/`. Use `cline skill list` to verify. |
| Workflows / rules | `workflows` and `rules` via the same records system (`~/.cline/workflows`, `~/.cline/rules`) — not needed for Superpowers. |

## Subagent dispatch (critical for Superpowers)

Superpowers skills `subagent-driven-development` and `dispatching-parallel-agents` say:

```
Subagent (general-purpose):
  description: "Implement Task N: ..."
  model: <tier>
  prompt: |
    Read your task brief first: [BRIEF_FILE]
    ...
```

On **Cline**, translate that to:

```
spawn_agent {
  systemPrompt: "<the prompt body — include brief path, report path, context, and the 'You Do Not Dispatch Subagents' contract verbatim>",
  task: "Implement Task N: <name> — read [BRIEF_FILE] first"
}
```

- `spawn_agent` schema is `{systemPrompt: string, task: string}` (see `sWe` in binary: `f.object({systemPrompt, task})`). There is **no `model` field** — Cline subagents inherit the parent session's provider/model (here `openrouter / openrouter/stealth/ox-alpha` via Bifrost at `http://localhost:7698/v1`). To pin a cheaper/stronger tier, add a preamble to `systemPrompt` like `Model hint: use the cheapest tier — this is mechanical transcription.` — Cline honours the hint as instruction, not as a hard model switch.
- For fix-loop rounds 1–3 SDD says "resume implementer"; on Cline re-invoke `spawn_agent` with the same `systemPrompt` plus the previous report + review findings. There is no `followup_task`/`resume` primitive.
- **Do not use `team_spawn_teammate` for SDD tasks.** That tool creates a persistent named teammate (lead-only, `agentId`+`rolePrompt`) meant for ongoing collaboration, not for SDD's one-task-one-ephemeral-subagent pattern. Using it per-task leaks teammates and breaks SDD's fresh-context guarantee.

## Kanban-spawned Cline

`kanban` embeds the Cline SDK in-process (`source: "cline-sdk"`) and forwards `enableSpawnAgent: enableSpawn !== false` (defaults `true`). So kanban-spawned Cline tasks **also** have `spawn_agent` available headlessly (`headlessToolNames: ["spawn_agent"]`). No extra config needed after the Bifrost provider fix (registered under builtin id `openrouter`).

## Keep localhost LLM routing

All LLM traffic must stay on `http://localhost:7698/v1` (Bifrost). Never set a remote `baseUrl`; the corporate transparent proxy returns 403 for direct `api.cline.bot` calls. The fix in `~/.cline/data/settings/providers.json` aliases Bifrost under the builtin provider id `openrouter` (`model: openrouter/stealth/ox-alpha`, `lastUsedProvider: openrouter`) so both `cline` CLI and `kanban`'s older embedded SDK resolve it.

## Instructions file

When a skill mentions "your instructions file", on Cline this is **`CLAUDE.md` / `AGENTS.md`** in the workspace root (Cline reads both hierarchically). Global defaults live at `~/.cline/`.

## Personal skills directory

- **Global (installed here):** `~/.agents/skills/` — the `npx skills --agent cline` installer writes here (symlinked/copied per skill). Verified: `~/.agents/skills/subagent-driven-development/SKILL.md` exists at v6.3.0.
- **Project:** `<workspace>/.agents/skills/` — e.g. `~/dev/agents/hermes/.agents/skills/` (also populated by the same install).
- Cline also honours `~/.cline/skills/` if present, but the canonical cross-runtime path is `~/.agents/skills/`.

## Verify

```bash
cline skill list                          # should list 14 superpowers skills
cline -P openrouter -m openrouter/stealth/ox-alpha "Reply with exactly: SPAWN_OK — then spawn_agent with systemPrompt='You are a test subagent' task='Reply DONE'"
# Check Bifrost hit:
sqlite3 ~/projects/personal/cli-agents-config/setup-ubuntu-server/bifrost/data/logs.db \
  "select created_at,payload->>'model',payload->>'provider' from logs where payload->>'model' like '%stealth%' order by id desc limit 5;"
```
