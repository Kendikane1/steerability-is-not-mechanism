# Run the prepared CUDA rehearsal manually

Status: publication fix verified;190 tests pass on Mac and Windows. Attempt02 stopped on host RAM; attempt03 is prepared after the user closed unused apps.

1. Connect to Windows using your existing private SSH command in the Mac Terminal app.
2. At the remote Windows Command Prompt, paste:

```cmd
powershell -NoProfile -File "%USERPROFILE%\Research\projects\steerability-is-not-mechanism\notebooks\run_remote_rehearsal_manual.ps1" -Attempt manual-rehearsal-03
```

3. Leave the terminal connected and keep both computers awake. No active Codex task is needed.
   This is a foreground rehearsal, not yet the disconnect-independent overnight setup.
4. When it finishes, copy the short JSON summary into the research conversation. Do not rerun
   after an error; the original evidence must be reviewed first.

The launcher checks reviewed file hashes, refuses to overwrite an existing attempt, preserves
all runtime guards and reports failures. The supervisor runs reference, interruption/resume,
replay and incompatible-identity checks, then estimates long-run storage. The two computation
arms each have a10-minute wall limit (recovery included in the second); short probes follow.
A passed rehearsal does not start the multi-hour test. No OpenAI API calls are made by this test.

Results stay on Windows in the project under
`outputs/phase1/p1-023/manual-rehearsal-03/report.json` and adjacent checkpoints/logs.
The preparation and later analysis still use Codex allowance; standalone execution does not.
