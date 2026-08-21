---
name: freebuff-delegation
description: Delegate a coding task to the FreeBuff harness (free AI coding assistant, freebuff.com). Use when handing a task to a human-in-the-loop agent, spinning up a second/parallel workstream, or when the orchestrator should not do the task itself. FreeBuff has NO automation API — interactive TUI only, no ACP — so delegation means preparing a task brief and launching (or handing over) the session.
disable-model-invocation: true
user-invocable: true
---

# FreeBuff Delegation

## What FreeBuff is

FreeBuff is a free AI coding assistant (freebuff.com). The agent ("Buffy") chats with you to write code in a project directory — fixing bugs, adding features, refactoring, explaining code. It currently runs on `deepseek/deepseek-v4-flash`.

## CLI reality (verified)

- `freebuff` (v0.0.152, a Bun binary) opens an **interactive TUI** — there is no non-interactive mode.
- Sole subcommand: `login`. Options: `--continue [conversation-id]` (resume), `--cwd <dir>` (target directory).
- **No ACP, no `-q`/query flag, no JSON/API mode** — you cannot script a task into it.
- **One instance at a time**: if one is running, a new `freebuff` shows "Freebuff is already running" with *Take over* / *Exit* choices. The running instance is tracked at `~/.config/manicode/freebuff-instance-owner.json` (instanceId/pid).

## How to delegate (agent-agnostic)

1. **Pick the project directory** — the task must be scoped to one checkout.
2. **Check for a running instance**: read `~/.config/manicode/freebuff-instance-owner.json`; if the pid is alive, either plan to *Take over* that session or have the user exit it first.
3. **Prepare the task brief** — in the chat or a `freebuff-handoff.md` in the project dir:
   - Goal and acceptance criteria (definition of done)
   - Relevant files / areas of the codebase
   - Constraints and environment notes (commands to run, ports, credentials *by reference only*)
   - Anything the assistant must NOT do
4. **Launch**: `cd <project-dir> && freebuff` (or `freebuff --cwd <project-dir>`). The human drives the session; the brief is the input. Use `freebuff --continue <conversation-id>` for follow-ups on the same task.
5. **Verify when done**: when the human reports back, confirm the outcome against the brief (files changed, tests pass) rather than trusting the report.

## Common mistakes

- Expecting CLI automation — it does not exist (no ACP/API/JSON mode); the human must drive the TUI.
- Forgetting the single-instance rule and confusing "already running / Take over" with an error.
- Launching from the wrong cwd — FreeBuff works inside the project dir you give it.
- Putting secrets or machine-specific values in the brief.
- Delegating something the orchestrator can do faster itself (FreeBuff is a human-in-the-loop session, not a subprocess).

## Hermes as orchestrator

Hermes' `delegation` toolset provides `delegate_task`, which spawns a **child Hermes agent** (isolated context, inherited toolsets) — it cannot invoke FreeBuff directly, and FreeBuff has no API to call anyway. To hand a task to FreeBuff from Hermes:

1. `delegate_task` a subagent whose job is to:
   - Write the task brief to the project dir (e.g. `freebuff-handoff.md`).
   - Launch the TUI for the human: `tmux new-session -d -s freebuff 'cd <project-dir> && freebuff'` (or tell the user to run `freebuff --cwd <project-dir>` in a terminal).
   - Report the brief path + how to attach (`tmux attach -t freebuff`).
2. The human takes over the tmux session / terminal and drives FreeBuff with the brief.
3. On follow-up, the subagent (or the user) runs `freebuff --continue <conversation-id>` in the same dir.
4. Verify the result against the brief when the human reports completion.

Keep the brief machine-agnostic and secret-free — the same rules as committed content.
