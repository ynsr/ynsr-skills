---
name: adding-omp-settings
description: Use when adding or changing a user-facing oh-my-pi (omp) setting or config key, when a config change has no effect in the installed binary, or when porting local oh-my-pi patches onto a new upstream version
---

# Adding oh-my-pi Settings

## Overview
Adding a setting in oh-my-pi is three touchpoints: **register** the key, **consume** it at the feature site, **test** via `Settings.isolated`. The installed binary only honors a key after rebuild — verify there, not just in source.

## Where things live
- Repo: `~/projects/github/oh-my-pi` (fork: `ynsr/oh-my-pi`). Binary: `~/.bun/bin/omp` (bun-compiled bundle).
- Settings registry: `packages/coding-agent/src/session/settings.ts` — `register({ id, type, default, ui: { tab, group, label, description } })`. UI text lives here.
- Consumers read via the exported `cfg*` const: `cfgX.get(this.#host.settings)` (e.g. `turn-recovery.ts`).
- User config: `~/.omp/agent/config.yml` (YAML, nested by id: `features:\n  unexpectedStopMaxRetries: 20`).
- Tests: `Settings.isolated({ "key.id": value })`; session-level harnesses take a settingsOverrides param (see `agent-session-unexpected-stop-guard.test.ts` `createHarness`).

## Steps
1. Register in `settings.ts` near related keys. `type: "number"`, `default` per request.
2. Consume at the feature site — replace module-level `const X = 3` caps with an accessor reading the setting. Floor with `Math.max(0, …)` so `0` = disabled.
3. Tests: pin old defaults explicitly (`"features.turnRecoveryMaxRetries": 3`) in tests that assert old wording (`Attempt #1/3`) so they keep testing cap semantics; add one test asserting the new default renders.
4. Verify: `bun run check:types` (in `packages/coding-agent`), targeted `bun test test/<relevant>*.test.ts`, `bunx oxfmt <files>`, `bunx oxlint <files>`.

## Install / verify the change is live
- Dev install: `cd packages/coding-agent && bun link && sh ../../scripts/link-omp.sh` → `~/.bun/bin/omp` becomes a wrapper into the repo.
- Native addon must match the package version or omp crashes (`pi_natives.*.node is the @17.x addon, not @18.y`). Rebuild: `cd packages/natives && bun run build`. Needs `cmake` + `ninja` on PATH (opusic-sys). No sudo required: Kitware tarball into `~/.local/opt/cmake-*/bin`.
- Smoke: `omp -p --no-session --auto-approve --thinking minimal "Reply with exactly: hi"` → expect output, exit 0.

## Config change had no effect? Triage order
1. Is the key in the *installed binary*? `strings -a "$(which omp)" | grep -F "your.key"`. Absent → binary predates the change; rebuild or link dev wrapper.
2. Is the key consumed where you think? Minified bundles show template fills like `maxRetries: rao` where `rao = 3` is a **hardcoded module constant**, not a settings read — check source, not strings.
3. Wrong file? `~/.omp/agent/config.yml` is the global one; check nesting matches the id path.
4. Running sessions keep old settings; restart omp.

## Common Mistakes
- Assuming `retry.maxRetries` governs turn-recovery injections — it only feeds provider-error auto-retry (`getRetrySettings()`).
- Reading behavior from `strings` on the compiled binary and concluding a constant is configurable — cross-check the repo source.
- Skipping the native rebuild after `bun link` — the stale `.node` addon is a hard crash, not a warning.
- Editing `config.yml` with `sed a\` after a multi-line match — duplicates the appended line; verify with a re-read.

## Porting to a future version
Re-locate the three touchpoints by name (they survive refactors): registry `register({` in `settings.ts`, the `cfg*.get(settings)` consumer, and the cap constants/`MAX_RETRIES` in the feature file. Re-apply the same pattern; rerun the targeted test files listed above.
