# systemd service add-on (Go tier only)

The `--service` add-on is scoped to the Go tier (spec §2.4): daemons, port listeners, background workers. User-scoped by default; system-wide only if explicitly requested or domain-required.

## User unit

`~/.config/systemd/user/<tool>.service`:

```ini
[Unit]
Description=<Tool> service
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=%h/.local/bin/<tool> serve --config %h/.config/<tool>/config.toml
Restart=on-failure
RestartSec=5
Environment=NO_COLOR=1

[Install]
WantedBy=default.target
```

- `%h` = user home (honors `$HOME`-redirected test homes via `systemd --user` per-user env only; for tests, template the path at install time instead).
- `WantedBy=default.target` is the user-mode equivalent of `multi-user.target`.

## Lingering

Without lingering the service dies at logout. `install` (or `<tool> service install`) checks and enables it:

```bash
loginctl enable-linger "$USER"
```

Uninstall disables it only if no other user service needs it:

```bash
loginctl disable-linger "$USER"   # only when uninstalling the last user service
```

## Ship lifecycle subcommands

Nobody hand-writes systemctl invocations. Every service-capable tool ships:

```
<tool> service install|uninstall|start|stop|restart|status|logs
```

- `install` — write unit file (atomic write), `systemctl --user daemon-reload`, `enable --now`, ensure linger.
- `uninstall` — `disable --now`, remove unit, `daemon-reload`; never touches linger unless last service.
- `status` — wraps `systemctl --user is-active` (exit code preserved; `status: ok|missing` style output consistent with doctor).
- `logs` — `journalctl --user -u <tool> -f` (pager only on TTY).

## Testing without a real boot

`systemctl --user` works in any session with a user bus. In CI/containers without systemd, gate the e2e on `systemctl --user` succeeding; otherwise verify unit-file generation only (rendered text assertions: `ExecStart`, `Restart=on-failure`, `WantedBy=default.target`).

## Verification

`<tool> service install && <tool> service status && <tool> service logs --lines 5 && <tool> service uninstall` — run the full cycle before delivering (untested lifecycle management is not delivered). `uninstall` must reverse everything `install` created.
