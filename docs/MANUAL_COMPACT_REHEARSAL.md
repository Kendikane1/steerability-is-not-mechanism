# Run the next short test manually

This is a new synthetic engineering test of the live lossless storage writer.
It does not start either multi-hour arm or run scientific data. The previous rehearsal's
results remain preserved. Do not use its old launcher for this new check.

## On the Windows SSH terminal

Keep the terminal connected and both machines awake. Run:

```cmd
powershell -NoProfile -File "%USERPROFILE%\Research\projects\steerability-is-not-mechanism\notebooks\run_compact_rehearsal_manual.ps1"
```

The launcher verifies the deployed source hashes and prior Windows publication probe,
refuses an existing output directory, acquires the shared exclusive launcher lock, and
runs the short supervisor. It sets offline mode; no weights are downloaded. No Codex
session is needed while it runs. Resource limits remain active and failures stop the run.

An optional preflight uses the same command with `-CheckOnly`; it does not load the model.
The run is foreground-only: it is not ready for an unattended SSH disconnect.

## What to return

Copy the final summary. Expected successful status is `rehearsal_passed`, with forward
counts `[96, 49, 48, 0, 0]`. `compact_storage` reports observed catalog sizes and unique
payload counts. `multi_hour_ready` is intentionally false even on success: the saved
results need review, actual timing/storage recalibration and a frozen long-run protocol.

If it stops, copy the error and report path. Do not change limits or rerun. The output
folder is `outputs/phase1/p1-025/manual-compact-01` inside the Windows checkout; preserving
that folder lets us diagnose without another model run. Historical outputs are untouched.

## What happens next

Review the saved short-run arrays, checksums, resources and measured overhead. Then prepare
and verify a separate long-run supervisor with bounded memory/state/logging, explicit
memory-growth checks, two-hour active-time minimum per arm and three-hour wall cap per arm,
plus launch/status/stop commands that survive SSH disconnection. This handoff does not yet
supply those commands or claim that sustained engineering has passed.
