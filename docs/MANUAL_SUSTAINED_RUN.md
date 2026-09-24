# Start the overnight synthetic engineering test

The current work is on GitHub. This launcher runs on Windows through the existing scheduled
PythonJob slot; Codex does not supervise it. Keep the Windows PC powered and awake. Once started,
you may disconnect SSH and close the Mac. No model downloads or scientific data are involved.

## Start once, in the Windows SSH terminal

```cmd
powershell -NoProfile -File "%USERPROFILE%\Research\projects\steerability-is-not-mechanism\notebooks\remote_sustained_manual.ps1" -Action Start
```

Wait briefly, then use Status to confirm it has begun. Do not use the older rehearsal commands.
The launcher refuses an existing attempt or a busy scheduled-job slot. It preserves the slot's
previous manifest; no authentication/task registration is changed. Avoid starting another
PythonJob or changing project source/environment during the run.

## Check later

```cmd
powershell -NoProfile -File "%USERPROFILE%\Research\projects\steerability-is-not-mechanism\notebooks\remote_sustained_manual.ps1" -Action Status
```

Two arms run sequentially: uninterrupted, then deliberately interrupted/resumed. Expected elapsed
time is roughly8 hours plus replay/final audit, but this is an estimate. Each arm has a6-hour cap;
replay and final audit have separate1-hour caps. A complete run may therefore take up to roughly14
hours. It stops if a resource, numerical, integrity, memory-growth or deadline check fails.

At completion, expect `status: sustained_passed`, with at least7,200 active seconds per arm in
`comparison.active_seconds`. The two-hour minimum excludes loading/monitoring/writes/pauses;
a shorter completed workload cannot pass by simply sleeping or appending jobs.

`starting` in the supervisor report means the sequence is ongoing; use the attempt/worker_status,
completed and forward_calls fields for progress. `stopped` means preserve the report and send the
summary for diagnosis. A failure is not permission to rerun or relax a limit.

## Stop deliberately if needed

```cmd
powershell -NoProfile -File "%USERPROFILE%\Research\projects\steerability-is-not-mechanism\notebooks\remote_sustained_manual.ps1" -Action Stop
```

This asks the supervisor to stop its owned worker and retain outputs. Check Status afterward.
Do not stop only the outer scheduled task: that can orphan its child. Planned midpoint termination
is automatic. Unplanned power loss/reboot is not an automatic restart; do not launch again blindly.

Return the final Status summary. Full evidence remains at
`outputs/phase1/p1-027/manual-sustained-01/` in the Windows project.

The existing215 automated software tests and prior193 short model forward attempts provide
specific engineering evidence. They do not certify every future model, precision, dataset or
agent's experiment. This overnight test extends duration evidence for the pinned0.6B configuration.
