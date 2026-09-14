"""Weight-free checks for the shared Mac/Windows dependency contract."""

import tomllib
from pathlib import Path


def test_cuda_index_is_explicit_and_windows_only() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text())
    uv = project["tool"]["uv"]
    assert uv["index"] == [
        {
            "name": "pytorch-cu130",
            "url": "https://download.pytorch.org/whl/cu130",
            "explicit": True,
        }
    ]
    for name in ("torch", "torchvision"):
        assert uv["sources"][name] == [
            {"index": "pytorch-cu130", "marker": "sys_platform == 'win32'"}
        ]


def test_lock_keeps_platform_specific_torch_builds() -> None:
    lock = tomllib.loads(Path("uv.lock").read_text())
    for name, version in (("torch", "2.13.0"), ("torchvision", "0.28.0")):
        records = [package for package in lock["package"] if package["name"] == name]
        assert {(p["version"], p["source"]["registry"]) for p in records} == {
            (version, "https://pypi.org/simple"),
            (version + "+cu130", "https://download.pytorch.org/whl/cu130"),
        }
        cuda = next(p for p in records if p["version"].endswith("+cu130"))
        assert all("sys_platform == 'win32'" in m for m in cuda["resolution-markers"])
        assert any("cp312-cp312-win_amd64" in w["url"] for w in cuda["wheels"])
