"""Boundary tests for approved resource limits; no model or host pressure generation."""

from dataclasses import replace

import pytest

from steerability_is_not_mechanism.resource_guard import (
    GIB,
    MIB,
    SystemReading,
    check_mps,
    check_system,
    parse_pressure,
    parse_swap,
)


def reading():
    return SystemReading(10, 10.1, 1, 100 * MIB, 11 * GIB, "1", "fixture")


@pytest.mark.parametrize("value", ["", "0", "3", "-1", "normal", "2\n1"])
def test_unknown_pressure_fails_closed(value):
    with pytest.raises(ValueError):
        parse_pressure(value)


@pytest.mark.parametrize("level", [1, 2, 4])
def test_pressure_mapping_and_refusal(level):
    assert parse_pressure(f"{level}\n") == level
    r = replace(reading(), pressure=level)
    if level == 1:
        check_system(r, now=11, baseline_swap=100 * MIB, startup=True)
    else:
        with pytest.raises(RuntimeError, match="pressure"):
            check_system(r, now=11, baseline_swap=100 * MIB, startup=True)


def test_swap_units_and_malformed_readings():
    assert parse_swap("total = 9216.00M used = 8409.50M free = 806.50M (encrypted)") == 8409.5 * MIB
    for text in [
        "used = 10G",
        "total = 1M used = 2M free = 0M",
        "",
        "total = 1M used = -1M free = 2M",
    ]:
        with pytest.raises(ValueError):
            parse_swap(text)


@pytest.mark.parametrize(
    "changes,kwargs,match",
    [
        ({"free_disk_bytes": 10 * GIB - 1}, {}, "disk"),
        ({"free_disk_bytes": 5 * GIB - 1}, {"startup": False}, "disk"),
        ({"swap_bytes": 356 * MIB}, {}, "swap"),
        ({}, {"now": 15.001}, "stale"),
        ({"finished": 20}, {}, "stale"),
        ({}, {"output_bytes": 4 * GIB}, "output"),
    ],
)
def test_limit_boundaries(changes, kwargs, match):
    with pytest.raises(RuntimeError, match=match):
        check_system(
            replace(reading(), **changes),
            now=kwargs.get("now", 11),
            baseline_swap=100 * MIB,
            startup=kwargs.get("startup", True),
            output_bytes=kwargs.get("output_bytes", 0),
        )


def test_exact_disk_minimum_and_just_below_growth_limit_pass():
    check_system(
        replace(reading(), free_disk_bytes=10 * GIB, swap_bytes=356 * MIB - 1),
        now=11,
        baseline_swap=100 * MIB,
        startup=True,
    )
    check_mps(799, 1000)
    for driver, recommendation in [(800, 1000), (0, 0), (-1, 1000)]:
        with pytest.raises(RuntimeError):
            check_mps(driver, recommendation)


def test_missing_telemetry_is_not_substituted(monkeypatch, tmp_path):
    import subprocess

    from steerability_is_not_mechanism import resource_guard

    monkeypatch.setattr(resource_guard.sys, "platform", "darwin")

    def unavailable(*args, **kwargs):
        raise subprocess.TimeoutExpired("sysctl", 2)

    monkeypatch.setattr(resource_guard.subprocess, "check_output", unavailable)
    with pytest.raises(subprocess.TimeoutExpired):
        resource_guard.read_system(tmp_path)


def test_cli_persists_failure_without_importing_model_packages(monkeypatch, tmp_path):
    import builtins
    import json
    import runpy
    import sys

    from steerability_is_not_mechanism import resource_guard

    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in {"torch", "transformers"}:
            pytest.fail("startup gate imported model runtime")
        return original_import(name, *args, **kwargs)

    def unavailable(*args):
        raise RuntimeError("telemetry unavailable")

    output = tmp_path / "attempt"
    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(resource_guard, "read_system", unavailable)
    monkeypatch.setattr(sys, "argv", ["check_sustained_resources.py", "--output-dir", str(output)])
    with pytest.raises(SystemExit) as error:
        runpy.run_path("notebooks/check_sustained_resources.py", run_name="__main__")
    assert error.value.code == 1
    report = json.loads((output / "report.json").read_text())
    assert report["status"] == "refused"
    assert report["model_loaded"] is False and report["forward_calls"] == 0
    assert "telemetry unavailable" in report["error"]
