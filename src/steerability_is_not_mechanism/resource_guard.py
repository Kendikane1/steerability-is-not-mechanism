"""Weight-free macOS resource readings and fail-closed sustained-test limits."""

import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path

GIB = 1024**3
MIB = 1024**2
PRESSURE = {1: "normal", 2: "warning", 4: "critical"}


def parse_pressure(text: str) -> int:
    if text.strip() not in {"1", "2", "4"}:
        raise ValueError("unknown macOS memory-pressure reading")
    return int(text.strip())


def parse_swap(text: str) -> int:
    match = re.fullmatch(
        r"(?:vm.swapusage:\s*)?total = ([0-9]+(?:\.[0-9]+)?)M\s+"
        r"used = ([0-9]+(?:\.[0-9]+)?)M\s+free = ([0-9]+(?:\.[0-9]+)?)M"
        r"(?:\s+\(encrypted\))?",
        text.strip(),
    )
    if match is None:
        raise ValueError("unrecognized swap reading or units")
    total, used, free = (Decimal(v) * MIB for v in match.groups())
    if used > total or free > total:
        raise ValueError("inconsistent swap reading")
    return int(used)


@dataclass(frozen=True)
class SystemReading:
    started: float
    finished: float
    pressure: int
    swap_bytes: int
    free_disk_bytes: int
    raw_pressure: str
    raw_swap: str

    def as_dict(self) -> dict:
        return asdict(self)


def read_system(path: Path) -> SystemReading:
    if sys.platform != "darwin":
        raise RuntimeError("resource monitor requires macOS")
    started = time.monotonic()

    def read(key: str) -> str:
        return subprocess.check_output(
            ["/usr/sbin/sysctl", "-n", key], text=True, timeout=2
        ).strip()

    pressure, swap = read("kern.memorystatus_vm_pressure_level"), read("vm.swapusage")
    free = shutil.disk_usage(path).free
    return SystemReading(
        started, time.monotonic(), parse_pressure(pressure), parse_swap(swap), free, pressure, swap
    )


def check_system(
    reading: SystemReading,
    *,
    now: float,
    baseline_swap: int,
    startup: bool,
    output_bytes: int = 0,
    allow_warning: bool = False,
) -> None:
    if not (0 <= now - reading.started <= 5 and reading.started <= reading.finished <= now):
        raise RuntimeError("resource telemetry stale or invalid")
    if reading.pressure not in ({1, 2} if allow_warning else {1}):
        raise RuntimeError(f"memory pressure is {PRESSURE.get(reading.pressure, 'unknown')}")
    if min(reading.swap_bytes, reading.free_disk_bytes, baseline_swap, output_bytes) < 0:
        raise RuntimeError("negative resource reading")
    if reading.free_disk_bytes < (10 if startup else 5) * GIB:
        raise RuntimeError("disk reserve below approved limit")
    if reading.swap_bytes - baseline_swap >= 256 * MIB:
        raise RuntimeError("swap growth reached approved limit")
    if output_bytes >= 4 * GIB:
        raise RuntimeError("output budget reached approved limit")


def check_mps(driver_bytes: int, recommended_bytes: int) -> None:
    if driver_bytes < 0 or recommended_bytes <= 0:
        raise RuntimeError("invalid MPS telemetry")
    if 5 * driver_bytes >= 4 * recommended_bytes:
        raise RuntimeError("MPS allocation reached 80 percent of recommended working set")
