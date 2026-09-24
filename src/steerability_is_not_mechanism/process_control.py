"""Verify and stop an owned Windows worker behind a virtualenv launcher."""

import subprocess


def validate_worker_pid(launcher_pid: int, worker_pid: int) -> None:
    if type(worker_pid) is not int or worker_pid <= 0:
        raise ValueError("invalid worker PID")
    if launcher_pid == worker_pid:
        return
    command = f"(Get-CimInstance Win32_Process -Filter 'ProcessId={worker_pid}').ParentProcessId"
    parent = subprocess.check_output(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
        text=True,
        timeout=5,
    ).strip()
    if parent != str(launcher_pid):
        raise ValueError("worker is not the owned launcher's child")


def kill_owned_tree(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    result = subprocess.run(
        ["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, timeout=10
    )
    if result.returncode != 0 and proc.poll() is None:
        raise RuntimeError("could not terminate owned Windows process tree")
    proc.wait(timeout=10)
