"""Explicit Windows CUDA engineering runtime. No scientific model selection or downloads."""

import ctypes
import hashlib
import importlib.metadata
import json
import os
import random
import shutil
import sys
import threading
import time
from pathlib import Path

import numpy as np
import torch
import yaml

from .engineering_config import load_engineering_config
from .local_qwen import CudaEngineeringRequest, _load_verified_adapter
from .sustained import atomic_json

GIB = 1024**3


def read_cuda_request(path: Path, protocol: Path):
    request = CudaEngineeringRequest.model_validate(yaml.safe_load(path.read_text()))
    if not request.execution_enabled:
        raise ValueError("CUDA engineering request disabled")
    if hashlib.sha256(protocol.read_bytes()).hexdigest() != request.protocol_sha256:
        raise ValueError("protocol hash mismatch")
    return request, load_engineering_config(protocol)


def configure_cuda(spec):
    if sys.platform != "win32":
        raise ValueError("reviewed CUDA runtime is Windows only")
    for name, value in {
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "HF_DEACTIVATE_ASYNC_LOAD": "1",
        "CUBLAS_WORKSPACE_CONFIG": ":4096:8",
    }.items():
        if os.environ.get(name) != value:
            raise ValueError(f"required CUDA environment: {name}")
    for name, value in {
        "torch": "2.13.0+cu130",
        "transformers": "5.15.0",
        "tokenizers": "0.22.2",
    }.items():
        if importlib.metadata.version(name) != value:
            raise ValueError(f"unreviewed CUDA package: {name}")
    if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
        raise ValueError("expected one available CUDA device")
    if torch.cuda.get_device_name(0) != "NVIDIA GeForce RTX 4060":
        raise ValueError("unexpected CUDA GPU")
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    random.seed(spec.runtime.seed)
    np.random.seed(spec.runtime.seed)
    torch.manual_seed(spec.runtime.seed)
    torch.use_deterministic_algorithms(True, warn_only=False)
    torch.backends.cuda.matmul.fp32_precision = "ieee"
    torch.backends.cudnn.fp32_precision = "ieee"
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    device = torch.device("cuda:0")
    torch.cuda.set_device(device)
    torch.cuda.reset_peak_memory_stats(device)
    return device


def load_cuda_adapter(request, spec, root: Path, device):
    if not isinstance(request, CudaEngineeringRequest):
        raise ValueError("scoped CUDA engineering request required")
    return _load_verified_adapter(
        request,
        spec,
        root / "outputs/phase1/p1-005/tokenizer",
        root / "models/Qwen3-0.6B" / spec.model.revision,
        device,
    )


class MemoryStatus(ctypes.Structure):
    _fields_ = [("length", ctypes.c_uint32), ("load", ctypes.c_uint32)] + [
        (n, ctypes.c_uint64)
        for n in [
            "total_phys",
            "avail_phys",
            "total_commit",
            "avail_commit",
            "total_virtual",
            "avail_virtual",
            "extended",
        ]
    ]


def windows_memory() -> dict:
    if sys.platform != "win32":
        raise ValueError("Windows memory API required")
    status = MemoryStatus()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise RuntimeError("Windows memory query failed")
    return {field[0]: int(getattr(status, field[0])) for field in status._fields_}


def check_resources(row: dict, startup: bool):
    if row["gpu_free"] < (4 if startup else 1) * GIB:
        raise RuntimeError("CUDA free-memory reserve breached")
    if row["disk_free"] < 20 * GIB:
        raise RuntimeError("Windows 20 GiB disk reserve breached")
    threshold = GIB if startup else GIB // 2
    if (
        row["ram"]["avail_phys"] < threshold
        or row["ram"]["avail_commit"] < threshold
        or row["ram"]["load"] >= 95
    ):
        raise RuntimeError("Windows RAM/commit reserve breached")


class CudaMonitor:
    def __init__(self, directory: Path, root: Path, seconds=180):
        self.directory, self.root = directory, root
        self.seconds = seconds
        self.deadline = time.monotonic() + seconds
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.sample(True)
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()

    def sample(self, startup=False):
        with self.lock:
            started = time.monotonic()
            free, total = torch.cuda.mem_get_info(0)
            row = {
                "time": started,
                "gpu_free": free,
                "gpu_total": total,
                "allocated": torch.cuda.memory_allocated(0),
                "reserved": torch.cuda.memory_reserved(0),
                "peak_allocated": torch.cuda.max_memory_allocated(0),
                "ram": windows_memory(),
                "disk_free": shutil.disk_usage(self.root).free,
            }
            with (self.directory / "resources.jsonl").open("a") as stream:
                stream.write(json.dumps(row) + "\n")
            row["finished"] = time.monotonic()
            atomic_json(self.directory / "resources_latest.json", row)
            check_resources(row, startup)
            if time.monotonic() - started > 5:
                raise RuntimeError("CUDA resource telemetry stale")
            if time.monotonic() > self.deadline:
                raise TimeoutError(f"CUDA worker exceeded {self.seconds}-second deadline")
            return row

    def loop(self):
        try:
            while not self.stop.wait(1):
                self.sample()
        except BaseException as error:
            atomic_json(
                self.directory / "abort.json", {"error": f"{type(error).__name__}: {error}"}
            )
            os._exit(70)  # This owned worker only; supervisor retains its partial evidence.

    def close(self):
        self.stop.set()
        self.thread.join(5)
        if self.thread.is_alive():
            raise RuntimeError("CUDA monitor did not stop")
