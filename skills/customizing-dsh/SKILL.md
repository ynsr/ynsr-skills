---
name: customizing-dsh
description: >-
  Use when customizing DSH agent presets: cloning agent.cordis.yml, adding/removing
  tool/skill/prompt rows, hiding global skills, or authoring a lite preset/profile.
disable-model-invocation: true
user-invocable: true
---

# Customizing DSH (DeepSeek Harness)

## Overview

Every DSH capability is a plugin row in a `cordis.yml` (agent preset) or a series of
bundle **patches** (host profile). Changing what an agent can do = changing which rows
are composed for it. Two planes decide where an edit belongs.

## Planes

- **Host composition** (`base.cordis.yml` + `web.cordis.yml`, under the deployment):
  registries (*tools*, *skills*, *systemPrompt*, *agents*, *agent-loop*, *sessions*),
  persistence, sandbox/approval stack, model route, subagent registry + backends.
- **Agent preset** (`agent.cordis.yml` under `~/.dsh/.agent-presets/<id>/`): one session's
  tool plugins, skill/prompt sections, compaction policy. Mounted once per standing scope.

## Off-limits

Never edit the **shipped** presets (`agent-presets/` beside the deployment config:
`standard`, `code`, `minimal`, `cordis`). Copy one into the user root and edit the copy.
A service row in a preset MUST sit in a group with an `isolate` realm (else it publishes
process-global and the 2nd session mounting collides).

## Authoring a preset

1. **Copy a shipped preset** via `agentPresets.copy(from, id, name)` — lands in
   `~/.dsh/.agent-presets/<id>/` with `preset.yml` + `agent.cordis.yml`.
2. Write `preset.yml` `name` + `description` (shows in the picker).
3. Edit `agent.cordis.yml` row by row, keeping plane/realm rules. A plain consumer row
   (tool/skill/prompt registration, no service published) needs no realm.
4. **Mount-validate**: `agentPresets.standingKeyFor(id)` composes the real tree minus the
   agent and rejects broken rows. Use a temporary dynamic cordis plugin exposing a
   `preset_validate` tool that calls it.
5. Hand off to the user to start a real session on the preset.

Agent-preset yaml `!!js` expressions run in the loader eval scope, so only Node globals
like `process` are reliably available — avoid helpers like `join`; use string concat.

## Project-only skills (hide global skills)

The skill registry merges `[global layer, ...preset scope layers]`; a preset CANNOT remove
host-layer skills. Global skills come from:
- `superpowers-dsh` bundle (a **profile** bundle) — remove by omitting it from the profile's
  `package.json` `dsh.profile.bundles`.
- host `skill-filesystem` scanning user roots `~/.dsh/skills` (*-cli) — exclude via
  `includeDefaultRoots: false` + `customSkillDirs` pointing at the workspace's own
  `.dsh/skills`, `.agents/skills`, `.claude/skills`.

Do both on the preset's own `skill-filesystem` row AND (for deployment-wide) in the
companion profile's `cordis.patch.yml`.

## Minimal / lite preset

Bare persona is the WHOLE system prompt:

```yaml
- id: persona
  name: '@deepseek-ai/dsh-persona'
  config:
    text: >- ... minimal text ...
    complete: true
    includeRuntimeContext: false
```

Drop subagent/delegation/workflow/goal/plan/web rows to slim the toolset.

## Companion profile

A profile is a dir `~/.dsh/profiles/<name>/` with `package.json`
(`dsh.profile.bundles`), `cordis.yml` (empty root), `cordis.patch.yml` (id-targeted
config overrides / disables / inserts). Patches replace the targeted row's whole config.
Boot it with `dsh --profile <name>`. Bundle packages resolve from the shared
`~/.dsh/profiles/node_modules`, so a new profile needs no install if its bundles are
already present.

## Common mistakes

- Editing a shipped preset instead of a copy.
- Publishing a service from a preset without an `isolate` realm → mount rejection.
- Using unavailable JS helpers in preset `!!js` (only `process` and other Node globals).
- Expecting one preset to hide host-layer skills.

## Example: this pattern in the wild

`ynsr/dsh-lite-agent` → `agent-presets/lite/` (bare persona, no subagents, project-only
skills) + `profiles/lite/` (bundle list without `superpowers-dsh`, patch hiding global
skill roots, `agent-presets.default: lite`).