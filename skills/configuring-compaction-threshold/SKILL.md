---
name: configuring-compaction-threshold
description: "DeepSeek Harness: Use when auto context compaction fires too early/late, token budget tuning, thresholdRatio/retainRatio/retainTokens issues, or model context-window compaction mismatches."
disable-model-invocation:  true
user-invocable: true
---

# Configuring the Compaction Threshold

## Overview

DSH auto-compacts conversation history when estimated tokens cross
**`thresholdTokens = floor(contextWindow × thresholdRatio)`** (`thresholdRatio`
defaults to `0.8`, so auto-compaction fires at **80% of model capacity**).

There is **no absolute-token threshold key**. To set a fixed token size (e.g.
90K), compute the ratio that produces it for **your model's `contextWindow`**
and apply that ratio.

## Understanding the Budget

| Field | Default | Meaning |
|---|---|---|
| `thresholdRatio` | `0.8` | Compact when estimated tokens exceed `floor(window × ratio)`. Must be in `(0, 1]`. |
| `retainRatio` | `0.16` | Recent tail kept verbatim, as fraction of window. **Mutually exclusive** with `retainTokens`. Must be **below** `thresholdRatio`. |
| `retainTokens` | none | Absolute tail budget in tokens. **Must be less than the resolved `thresholdTokens`** — otherwise plugin load fails. |

**Critical:** Changing `thresholdRatio` to a lower value means `retainTokens`
(or `retainRatio × window`) may now exceed the new threshold, and the plugin
will **fail to load**. Supply `retainTokens` (absolute, safe) or lower
`retainRatio` together.

## Computing the Ratio

```
thresholdRatio = desired_threshold_tokens / contextWindow
```

Example — model declares `contextWindow: 600000`, desired 90K trigger:

```
thresholdRatio = 90000 / 600000 = 0.15
```

Find the model's effective `contextWindow`:
- In `~/.dsh/settings.yaml` under the provider's `models` array
- Default for `deepseek-official` models: **1,000,000 tokens**
- Default for **pi-ai** models: set per model in settings (typically `600000`)

## Applying the Config

### Option A: Host profile override (applies to ALL sessions in that profile)

Edit the profile's `cordis.patch.yml` (e.g. `~/.dsh/profiles/web/cordis.patch.yml`
or `~/.dsh/profiles/lite/cordis.patch.yml`), target `compaction-basic` by id:

```yaml
# ── compaction threshold ──────────────────────────────────────────────────────
- id: compaction-basic
  config:
    thresholdRatio: 0.15        # ~90K on a 600K window
    retainTokens: 32768         # absolute tail budget (< 90000)
```

The profile's loader merges this config over the base bundle's
`compaction-basic` row (`@deepseek-ai/dsh-base` bundle). No `name` is needed
for an id-targeted override.

**No restart needed** — the `dsh web` server picks it up after restart; for
CLI sessions, restart the shell or `dsh` process.

### Option B: Preset composition (per-agent-preset)

In an agent preset's `agent.cordis.yml` (a local copy of `standard`):

```yaml
- id: compaction
  name: cordis:group
  group: true
  isolate:
    compaction: true
    toolResultPruner: true
  config:
    - id: compaction-basic
      name: '@deepseek-ai/dsh-compaction-basic'
      config:
        thresholdRatio: 0.15
        retainTokens: 32768

    - id: command-compact
      name: '@deepseek-ai/dsh-command-compact'

    - id: tool-result-pruner
      name: '@deepseek-ai/dsh-compaction-tool-result-pruner'
```

### Option C: Per-model overrides (different thresholds per model)

```yaml
- id: compaction-basic
  config:
    thresholdRatio: 0.15
    retainTokens: 32768
    modelPolicies:
      - provider: deepseek-official
        model: deepseek-v4-pro
        thresholdRatio: 0.08        # = 80K on a 1M window
        retainTokens: 16384
      - provider: pi-ai
        model: cline-pass/mimo-v2.5
        thresholdRatio: 0.18        # = 90K on a 500K window
        retainTokens: 32768
```

`modelPolicies` entries match on **both** `provider` and `model` (not just the
model id). Fields not supplied inherit from the top-level defaults.

## Validation

A config load failure (retain >= threshold, mutually exclusive retention,
duplicate modelPolicies target) produces a plugin activation error visible in:

- The **console/logs** of the `dsh web` process
- `dsh agent-presets validate <id>` — validates a preset composition
- Profile startup output

The safest bet: start with `retainTokens: 32768` (32K absolute budget) when
setting a lower threshold; it cannot accidentally exceed the threshold.

## Troubleshooting

| Error | Likely Cause | Fix |
|---|---|---|
| `retainTokens must be less than threshold tokens` | `retainTokens ≥ thresholdTokens` after ratio change | Lower `retainTokens` or raise `thresholdRatio` |
| `retainRatio must be less than resolved thresholdRatio` | `retainRatio ≥ thresholdRatio` | Lower `retainRatio` (e.g. `0.1`) or switch to `retainTokens` |
| `retainRatio and retainTokens are mutually exclusive` | Both set | Keep only one |
| `no context capacity for provider/model` | Model missing `contextWindow` config | Set `contextWindow` in `settings.yaml` model entry for that provider |
| Compaction never fires | Model window larger than expected → threshold higher than desired | Verify the model's actual `contextWindow` value |