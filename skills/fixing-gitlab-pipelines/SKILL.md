---
name: fixing-gitlab-pipelines
description: Use when a GitLab CI pipeline is red, a job fails with exit codes or missing artifacts, or CI passes locally but fails on the runner
---

# Fixing GitLab Pipelines

## Overview

Red pipeline? Fix one job at a time: triage, read the trace, fix the root cause, push, re-check. Never batch fixes across jobs — each failure masks the next.

## Triage Loop

1. **List jobs:** `glab ci get --pipeline-id <id> --with-job-details` — find the first failed job.
2. **Read the trace:** `glab api projects/:id/jobs/<job-id>/trace` — grep `step_script` for the actual error.
3. **Reproduce locally** if possible (script tests, `sh -n` syntax check).
4. **Fix one failure**, get user approval per change, commit, push.
5. **Re-check** the new pipeline. Repeat until green.

Also: `glab ci list`, `glab api 'projects/:id/pipelines?ref=<branch>&per_page=5'`, `glab api projects/:id/jobs/<id>/trace | grep -B3 -A8 -i 'error|denied|not found'`.

## Failure Patterns

| Symptom | Root cause | Fix |
|---|---|---|
| `Permission denied`, exit 126 | Script lacks exec bit in git (`100644`) | `chmod +x` invocation in CI **and** `git update-index --chmod=+x`; other jobs already do this |
| Missing dotenv artifact (`deploy.env: no matching files`) | Failing job exits before writing the artifact | Make the script always write the artifact (fail-open: exit 0 with `STATE=new`), never `exit 1` on probe failure |
| `no docker login credentials ... in /root/.docker/config.json` | Job container has no registry creds; runner host auth doesn't propagate | Probe via daemon-side `docker pull` (same auth path as `docker push`), not the registry HTTP API |
| `JAVA_HOME is not defined` | Job image has no JDK env set | Switch to an image proven by other jobs (e.g. `openjdk:21-jdk-bullseye-tools` over `oracle-jdk:21`) |
| `You are not allowed to push code`, 403 | `CI_JOB_TOKEN` can't push to protected branch | Enable Settings → CI/CD → Job token permissions → "Allow Git push requests" |

## Rules

- **Per-fix approval:** each fix gets explicit user approval before commit+push (user instruction, not optional).
- **One failure per iteration:** push, wait for the pipeline, read the next trace. Never assume what the next failure will be.
- **Verify the image:** a job's `image:` may lack tools you assume (`curl`, `JAVA_HOME`) — check what sibling jobs use.
- **Fail-open probes:** a *check* job should degrade to "build anyway", never block the pipeline on flaky probing.
