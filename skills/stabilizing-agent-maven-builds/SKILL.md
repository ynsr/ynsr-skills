---
name: stabilizing-agent-maven-builds
description: Use when an AI agent running Maven builds or tests freezes, stalls, or OOM-kills a Linux desktop — hangs at compile/test time, unresponsive GNOME, SIGKILLed containers. Not for ordinary test failures or CI-only flakes.
disable-model-invocation: true
user-invocable: true
---

# Stabilizing Agent Maven Builds

Core principle: a frozen desktop is host memory pressure, not a test failure. Stabilize the host first, then cap containers, then tune the pom.

## 1. Diagnose (evidence before fixes)

- `free -h; swapon --show` — zero swap means spikes stall instead of paging.
- `ps -eo pid,rss,cmd --sort=-rss | head -15` — baseline hogs (IDE, browsers, extra agents) count against build headroom.
- `docker inspect -f '{{.Name}} {{.State.OOMKilled}}'` — exit 137 alone proves nothing (any SIGKILL); `OOMKilled: true` proves kernel OOM.
- Same-timestamp exit-255 containers = daemon restart / hard reset, not OOM.

## 2. Host safety net

- zram (fast, pri 100) + small disk swapfile (pri 10); `vm.swappiness=100, vm.page-cluster=0`.
- `earlyoom -m 6 -s 10` with `--avoid` for gnome-shell/systemd — a spike gets a kill, not a stall.
- Close what you don't need during builds; caps can't fit a 7G+ run into 5G available.

## 3. Cap containers

- Per-container `withCreateContainerCmdModifier(...withMemory(...))`: CRDB ~3G + `--cache=256MB --max-sql-memory=512MB`; Hazelcast ~1G; NATS/MinIO ~512M.
- Changing a cap changes the reuse hash — `docker rm -f` stale reused containers afterward.
- Keep Testcontainers module versions aligned with the BOM; a newer `cockroachdb` jar may require the 8080 admin port mapped.

## 4. Pom and runner

- `.mvn/jvm.config`: cap the Maven JVM itself (e.g. `-Xmx2g`).
- Surefire/failsafe `argLine`: `@{argLine}` first (keeps JaCoCo attached) + `-XX:+ExitOnOutOfMemoryError`, metaspace cap, `forkedProcessTimeoutInSeconds`.
- Serialize agent builds (`flock` + `nice/ionice` + systemd `MemoryMax` scope); avoid `clean` — it retriggers codegen profiles.

## Mistakes

| Mistake | Fix |
|---|---|
| Reading exit 137 as OOM proof | Check `OOMKilled` flag |
| Swap without a killer | Pair zram/swap with earlyoom or oomd |
| `forkCount=1` as a fix | Already the default; timeouts and heap caps matter |
| Hard-capping CRDB at 2G | Set `--cache`/`--max-sql-memory` explicitly, cap ~3G |
| Freeze recurs with no evidence | Capture `journalctl -b -1 -k \| grep -iE 'oom\|killed'` + `earlyoom -v` — with earlyoom watching, the trail is solid |
