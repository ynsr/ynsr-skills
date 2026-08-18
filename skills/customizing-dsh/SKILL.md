---
name: customizing-dsh
description: >-
  Use when customizing DeepSeek Harness (DSH): editing or authoring agent presets
  (agent.cordis.yml), adding/removing tool/skill/prompt rows, hiding global skills,
  or creating companion profiles/cordis patches.
disable-model-invocation: true
user-invocable: true
---

# Customizing DSH (DeepSeek Harness)

## Overview

Every DSH capability is a plugin row — either in an **agent preset** (`agent.cordis.yml`)
or in a series of bundle **patches** on the **host composition** (a profile). Changing
what an agent can do means changing which rows are composed for it. Two planes decide
where any edit belongs.

## The two planes

- **Host composition** (shipped `base.cordis.yml` + `web.cordis.yml` under the deployment):
  the registries themselves (*tools*, *skills*, *systemPrompt*, *agents*, *agent-loop*,
  *sessions*), persistence, sandbox/approval stack, model route, subagent registry/backends.
  Shared across sessions; one instance for the process.
- **Agent preset** (`~/.dsh/.agent-presets/<id>/agent.cordis.yml`): one session's
  tool plugins, skill/prompt sections, compaction policy, persona. Mounted once per
  standing scope; unwound when the session closes.

The rule: anything with a consumer outside the agent plane (any cross-session reader)
belongs on the host plane; what one session alone needs belongs in the preset.

## Authoring an agent preset

1. **Start from a copy.** Never edit the **shipped** presets (`agent-presets/` beside the
   deployment config: `standard`, `code`, `minimal`, `cordis`). Copy one into the user
   root via `agentPresets.copy(from, id, name)` → lands at `~/.dsh/.agent-presets/<id>/`
   with `preset.yml` + `agent.cordis.yml`.
2. Write `preset.yml` `name` + `description` (shows in the preset picker).
3. Edit `agent.cordis.yml` row by row. A row that only registers tools/skills/prompt
   sections (a *consumer*) needs no realm. A row that **publishes a service** MUST sit in
   a group with an `isolate` realm — otherwise it lands process-global and the second
   session mounting the preset collides, and mount rejects it.
4. **Mount-validate** before shipping: `agentPresets.standingKeyFor(id)` composes the real
   tree minus the agent and rejects broken rows (missing package, invalid config, service
   leaked into root realm, row that never activated). Expose it via a temporary dynamic
   cordis plugin tool and read the failure message.
5. Hand off to the user to start a real session — only a real session reveals the actual
   tool schemas and prompt sections.

### `!!js` expressions in preset yaml

They run in the loader's eval scope, which supplies only Node globals like `process`.
Avoid helper names that aren't imported there (e.g. `join`); use string concatenation.

## Skills: how the catalog is built

The skill registry merges **layers**: `[global layer, ...preset scope layers]`. Consequence:
a single preset can ADD skills (and shadow same-named ones) to its own layer, but it
**cannot remove** skills that the deployment registers at the host/global layer. Global
skills come from two distinct places:

- A skill **provider bundle** mounted into a profile (e.g. `superpowers-dsh`). Removing it
  means omitting that bundle from the profile's `package.json` `dsh.profile.bundles`.
- The host `skill-filesystem` provider scanning **user roots** (`~/.dsh/skills`,
  `~/.agents/skills`) and the bundled root. Exclude those with `includeDefaultRoots: false`
  on the `skill-filesystem` row, and instead list explicit `customSkillDirs` for the skill
  roots you DO want (e.g. the workspace's own `.dsh/skills`, `.agents/skills`,
  `.claude/skills`).

Scope matters: doing this on the preset's own `skill-filesystem` row affects only that
preset's layer; doing it in a profile's patch affects it for every preset mounted under
that profile.

## Persona / system prompt

The persona section controls the system prompt. `complete: true` makes the persona the
WHOLE prompt; `includeRuntimeContext: false` suppresses auto-appended identity/web/tool
guidance.

```yaml
- id: persona
  name: '@deepseek-ai/dsh-persona'
  config:
    text: >-
      ... your persona text ...
    complete: true
    includeRuntimeContext: false
```

## Companion profile

A profile is a dir `~/.dsh/profiles/<name>/` with `package.json`
(`dsh.profile.bundles`), `cordis.yml` (empty root — don't edit), and `cordis.patch.yml`
(id-targeted config overrides / disables / inserts). A patch replaces the targeted row's
**whole** config rather than merging. Bundle packages resolve from the shared
`~/.dsh/profiles/node_modules`, so a new profile needs no install if its bundles are
already present. Boot with `dsh --profile <name>`.

## Common mistakes

- Editing a shipped preset instead of a copy (an upgrade overwrites the deploy install).
- Publishing a service from a preset without an `isolate` realm → mount rejection.
- Using unavailable JS helpers in preset `!!js` (only `process` and other Node globals).
- Expecting one preset to hide host-layer (deployment-registered) skills.
- Forgetting green-field presets need a group realm or a host consumer row that resolves.

## Worked example: the `lite` preset

A concrete use of the facts above — a minimal, low-noise agent for small tasks:

- **Copy** `standard` → `lite` (`agentPresets.copy`), drop the subagent/delegation,
  workflow, goal, plan-mode, and web rows to slim the toolset.
- **Skills:** the preset's `skill-filesystem` uses `includeDefaultRoots: false` +
  `customSkillDirs` at the workspace's `.dsh/skills`, `.agents/skills`, `.claude/skills`
  so only project skills appear.
- **Persona:** `complete: true` + `includeRuntimeContext: false` with a short "Make the
  minimal change and stop" prompt.
- **Mount-validate** via `standingKeyFor`, then hand off.
- **Companion `lite` profile:** bundle list omits `superpowers-dsh`, and
  `cordis.patch.yml` points the host `skill-filesystem` at project-only roots and sets
  `agent-presets.default: lite`.

Live reference: `ynsr/dsh-lite-agent`.