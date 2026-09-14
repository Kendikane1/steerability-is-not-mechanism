# Remote compute: operating and recovery guide

Recorded 2026-09-14. This is an infrastructure handoff, not a scientific result or permission
to download a model. The research remains pre-Phase-1. Read `AGENTS.md` before project work.

## Mental model

The Mac is the keyboard, editor, and browser. Windows runs Python and owns the GPU and files.
An SSH tunnel carries notebook traffic; it does not move execution or files automatically.
Save reusable code in the checkout and run it with that checkout's Python environment.
A saved notebook includes cells and possibly old outputs, not live Python variables.

## What was actually verified

| Check | Evidence and limit |
| --- | --- |
| SSH over different networks, signed out, and after cold boot | User reported repeated passes. |
| Windows environment and original six repository checks | Windows setup report, 2026-09-13: all passed, including 14 tests. |
| GPU arithmetic | Synthetic seeded 64×64 float64 multiplication matched CPU at rtol=atol=1e-10; maximum absolute error approximately 7.1e-15. |
| Mac notebook connection and remote kernel | User pasted the Windows project Python path and RTX 4060 GPU-check PASS. |
| Notebook connection loss | User recovered the previously assigned value 12345 after reconnecting, without assigning it again. |
| Jupyter start and GPU check after cold boot without desktop login | User reported PASS. This does not test every other scheduled task after boot. |
| Synthetic stop/resume | Windows report: preserved steps 1–463, resumed to 466, no duplicated completed steps. |
| Background job after launching SSH exits | Assistant observed 2 → 27 completed steps, same PID 14844 and single session; stopped safely at step 28. Other Mac connections were not forcibly closed. |

The completed 600-step checkpoint was preserved outside Git as
`Research\runs\synthetic-progress.completed-before-disconnect-20260914.json`.
The fresh checkpoint remains at step 28. Task state `Ready` means stopped; a checkpoint's
last-written `running` field can be stale after stopping a process.

These checks do not prove survival across power loss, model-backed checkpoint correctness,
FP16 model capacity, or indefinite unattended availability. A reboot destroys live kernels;
only durable application checkpoints can restore work.

## Environment and layout

Windows root is `%USERPROFILE%\Research`, outside OneDrive. Within it:

| Relative location | Purpose |
| --- | --- |
| `projects\steerability-is-not-mechanism` | Git checkout; its `.venv\Scripts\python.exe` runs research Python. |
| `tools\uv\uv.exe`, `tools\git\cmd\git.exe` | Portable tools. |
| `ops` | Existing machine-local launch and management scripts; not installed by `uv sync`. |
| `runs` | Job manifests, checkpoints, and logs; private, not Git. |
| `jupyter` | Configuration, kernels, runtime authentication; private, not Git. |
| `reports` | Original setup evidence, task exports, and backups; private, not Git. |
| `cache` | uv, model-library, and other caches; not Git. |

Observed Windows versions: Python 3.12.14, uv 0.12.13, torch 2.13.0+cu130,
torchvision 0.28.0+cu130, JupyterLab 4.6.3; RTX 4060, 8188 MiB VRAM, driver 591.86.
System RAM is approximately 7.9 GiB. Last reported free disk was 33.23 GiB, not a live guarantee.
Keep at least the setup's 20 GiB Windows reserve and budget model/cache/output space separately.
Mac review host: Apple Silicon, macOS 26.3, uv 0.11.7. The locked Mac torch wheel requires
macOS 14 or later. CUDA source selection applies only to Windows; Mac smoke policy stays MPS/CPU.

Mac consolidation verification (2026-09-14, Python 3.12.13): offline locked sync, pytest
(16 passed), Ruff lint, Ruff format (25 files), basedpyright (zero errors/warnings), and
synthetic smoke all passed. `git diff --check` and verbatim parent-snapshot comparison passed.
The two new tests cover the Windows-only index and platform-specific locked builds. No old
package name/version/source records were removed; only the two Windows CUDA builds were added.
Python patch versions currently differ between hosts; this is recorded, not a claim of
bit-identical execution. Freeze exact runtime versions/tolerances before model-backed comparison.

The Windows consolidation check initially found an undefined `connection_test` variable in a
saved, ignored infrastructure notebook. The notebook was preserved. Type checking now targets
`src/` and `tests/`, the reusable implementation and tests, rather than generated `outputs/`.
Future reusable modules must stay in that checked layout (or explicitly extend the check scope).
Final rerun, completed 2026-09-15 local time: all six checks passed on both Mac and Windows,
including 16 tests each and identical synthetic smoke values (margin 1.5, validation 1.0,
rescued coordinate 1.0, induced coordinate 4.0). Windows generated only Git line-ending
warnings, not check failures. Reviewed documentation/tests were copied to Windows; both
checkouts remain uncommitted and GitHub has not been updated by this consolidation.

## Daily notebook workflow

1. Ask someone to power on the PC. Desktop login was not required in the tested workflow.
2. Connect with the existing private SSH command. Keep your key/account/address and trusted
   host fingerprint in a private local note, not this public repository.
3. In the Windows SSH Command Prompt, run:

   ```cmd
   powershell -NoProfile -File "%USERPROFILE%\Research\ops\research.ps1" start-jupyter
   powershell -NoProfile -File "%USERPROFILE%\Research\ops\research.ps1" status
   ```

4. In a separate Mac terminal, use the existing SSH identity/account/host settings with
   `-N -T -o ExitOnForwardFailure=yes -L 127.0.0.1:8888:127.0.0.1:8888`.
   Retain strict host checking and public-key-only authentication. Leave this tunnel open.
5. Open `http://127.0.0.1:8888/lab`. Retrieve the token privately in your Windows terminal:

   ```cmd
   powershell -NoProfile -File "%USERPROFILE%\Research\ops\research.ps1" token
   ```

   Never paste that output into chat, logs, Git, or reports. Enter it only in the local browser.
   If Mac port 8888 is occupied, forward local 8889 to remote 8888 and browse local port 8889.
6. Select **Research GPU (Python 3.12)**. Confirm `import sys; print(sys.executable)` points
   to the Windows checkout's `.venv`. The existing synthetic notebook is under
   `outputs/infrastructure-checks/SYNTHETIC_kernel_check.ipynb` on Windows.

Closing the tunnel disconnects the browser; it does not request server shutdown. Save notebook
edits before disconnecting. To shut down deliberately, save work/checkpoints, then run
`research.ps1 stop-jupyter` using the same full PowerShell invocation above. This ends kernels.

## Code and dependency workflow

From Windows Command Prompt, enter the project shell:

```cmd
powershell -NoExit -NoProfile -File "%USERPROFILE%\Research\ops\enter-research.ps1"
```

From the project directory, on either machine:

```sh
uv sync --locked
uv run --locked pytest
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked basedpyright
uv run --locked sim-smoke --config configs/local_smoke.yaml
```

Do not copy `.venv` between operating systems or use global pip. Stop relevant tasks before
rebuilding their environment. `uv sync` installs dependencies, not scheduled tasks or SSH.
The imported lockfile SHA256 is
`60fbfffee69192568dbc860f88c2073016c1736d679eda9e26bb3960986d3f12`.

For future code transfer, inspect `git status --short` on both machines first. Review and
commit/push only with user authorization; then a clean receiving checkout can use
`git pull --ff-only`. Do not pull over the current uncommitted Windows dependency changes,
force-reset either checkout, or assume today's uncommitted Mac docs are already on GitHub.
Never sync runtime tokens, `.env`, SSH material, weights, datasets, or generated outputs.

## Long jobs and recovery

The installed on-demand tasks are `\Research\Jupyter`, `KernelCheck`, `SyntheticProgress`,
and `PythonJob`. They use Limited/S4U, no stored password, no boot triggers, unlimited execution
time, and IgnoreNew overlap handling. S4U has restrictions on network-resource credentials and
encrypted files; local execution tests do not validate future authenticated network jobs.

`research.ps1 start-test`, `test-status`, and `stop-test` manage the synthetic checkpoint test.
`start-job`, `job-status`, and `stop-job` manage the single PythonJob slot. The latter currently
selects only a synthetic probe through `runs\current-job.json`; changing it to research is a
separately authorized step. Its fields are `script`, `args` (string array), `cwd`, and `log`.
Edit only while stopped, use the script's real supported arguments, and never put secrets in
arguments or logs. Starting a task again reruns its entry point: it does not automatically add
checkpoint support. Do not use this wrapper to bypass the scientific execution guards.

| Symptom | Safe response |
| --- | --- |
| SSH unavailable | Check PC power/internet and Tailscale availability/expiry from both ends. Do not expose ports or weaken authentication. |
| Host-key mismatch | Stop and verify the PC's fingerprint through a trusted channel; do not disable checking. |
| Browser cannot connect | Verify SSH, tunnel, task status, and loopback listener; check for a local port conflict. |
| Token rejected after restart | Retrieve the new token privately; retain authentication. |
| Cell visible but variable missing | Saved file survived, live kernel did not. Rerun only appropriate setup cells, not an entire experiment blindly. |
| PC rebooted | Start Jupyter/chosen approved task on demand; recover durable checkpoints, not in-memory variables. |
| Jupyter shutdown stuck | Save what is possible; stopping only its scheduled task is a last resort and loses live kernel state. Leave SSH/Tailscale running. |
| Disk low | Stop new large jobs, inspect usage, expand storage or deliberately archive known artifacts. Do not recursively delete Research/caches/checkpoints blindly. |

## Rebuild boundary and remaining work

The checkout reproduces Python dependencies and the weight-free project checks. It is **not yet
a clean-machine installer** for SSH, Tailscale, or the machine-local helpers. The original private
setup reports remain the detailed machine-specific source. Before replacing the PC/disk, privately
back up reviewed `ops` scripts and task exports plus required configuration; avoid copying active
Jupyter runtime credentials into general backups. Re-create authentication separately.

Reviewed helper inventory: `enter-research.ps1`, `research.ps1`, `jupyter_launcher.py`,
`stop_jupyter.py`, `register_tasks.ps1`, `kernel_check.py`, `gpu_check.py`,
`synthetic_progress.py`, `python_job_entry.py`, `register_python_job.ps1`,
`job_helper_probe.py`, and `verify_project.py`. They depend on a machine-local
`ops/environment.json`, installed kernels, directories, and task registration. Do not blindly
rerun registration: it changes ACLs and starts tasks, and may partially succeed before failing.
The verification helper also needs manual exit-code review; its own exit status does not
aggregate every child check. No operational helper was changed or deployed in this review.

Remaining operational follow-ups: private backup/restore rehearsal, Tailscale expiry and account
recovery review before travel, Windows sleep/update/power planning, storage capacity, optional
Zed connection, and clean-machine helper packaging. None is evidence about the research hypothesis.
Scientific-model revisions, token convention, hook site, and resume protocol remain open in
`DECISIONS.md`. Start Phase 1 by discussing those choices; model downloads still need authorization.
