# Workaround patch — typer >= 0.27: add_completion=False breaks the env-var completion server
# Status as of 2026-09-20: reproducible on typer 0.27.0 and 0.27.2 (latest), NOT fixed upstream.
# Apply in the generated template's app module, immediately before `app = typer.Typer(...)`.
#
# Related upstream context: https://github.com/fastapi/typer/issues/1905
# (registry is lazy; no exact upstream issue found for this repro as of 2026-09-20 —
# searches for "Shell bash not supported" / add_completion=False returned no match)
#
# Root cause: typer.main.get_command() only calls completion_init() when
# _add_completion is truthy (it gates --install-completion/--show-completion param
# attachment). completion_init() is what registers BashComplete/ZshComplete/FishComplete/
# PowerShellComplete into typer._click.shell_completion._available_shells. With
# add_completion=False the registry stays empty, so typer.completion.shell_complete()
# hits `get_completion_class(shell) -> None` and prints "Shell bash not supported." (exit 1)
# for ALL FOUR generated tools (complete_bash/complete_zsh/complete_fish/complete_powershell).

```python
# --- begin 3-line workaround (idempotent; no-ops under add_completion=True) ---
import typer.completion as _typer_completion
# typer >=0.27: add_completion=False never registers shell completion classes,
# so the env-var completion server dies with "Shell bash not supported."
_typer_completion.completion_init()
# --- end workaround ---
```

# Verified: with the patch, `_TOOL_COMPLETE=complete_bash|complete_zsh|complete_fish`
# servers return correct candidates on 0.27.0 AND 0.27.2 (see report.md §2/§3).
# Delete this patch once typer registers completion classes unconditionally at import.
