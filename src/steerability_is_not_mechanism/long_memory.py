"""Bounded post-warm-up memory windows for the synthetic endurance gate."""

from collections import deque
from statistics import median

import psutil

from .remote_cuda import CudaMonitor
from .sustained import atomic_json


class GrowthWindow:
    def __init__(self):
        self.baseline = []
        self.tail = deque()
        self.last_second = -1

    def add(self, elapsed, reserved, rss):
        second = int(elapsed)
        if second <= self.last_second:
            return
        self.last_second = second
        row = (second, reserved, rss)
        if 600 <= second < 1200:
            self.baseline.append(row)
        if second >= 600:
            self.tail.append(row)
        while self.tail and self.tail[0][0] <= second - 600:
            self.tail.popleft()

    def result(self):
        if len(self.baseline) < 590 or len(self.tail) < 590 or self.last_second < 1800:
            raise ValueError("insufficient memory-growth windows")
        rows = {}
        for index, key in [(1, "reserved"), (2, "rss")]:
            first = median(r[index] for r in self.baseline)
            last = median(r[index] for r in self.tail)
            limit = max(256 * 1024**2, first * 0.1)
            rows[key] = {
                "baseline_median": first,
                "final_median": last,
                "growth_limit": limit,
                "passed": last - first <= limit,
            }
        if not all(r["passed"] for r in rows.values()):
            raise ValueError("post-warm-up memory growth exceeded limit")
        return rows


class LongMonitor(CudaMonitor):
    def __init__(self, directory, root, seconds):
        self.growth = GrowthWindow()
        self.loaded_at = None
        self.process = psutil.Process()
        super().__init__(directory, root, seconds)

    def sample(self, startup=False):
        row = super().sample(startup)
        if self.loaded_at is not None:
            with self.lock:
                elapsed = row["time"] - self.loaded_at
                rss = self.process.memory_info().rss
                if int(elapsed) > self.growth.last_second:
                    with (self.directory / "memory-seconds.jsonl").open("a") as stream:
                        import json

                        stream.write(
                            json.dumps(
                                {"elapsed": elapsed, "reserved": row["reserved"], "rss": rss}
                            )
                            + "\n"
                        )
                self.growth.add(elapsed, row["reserved"], rss)
        return row

    def finish_growth(self):
        with self.lock:
            result = self.growth.result()
            atomic_json(self.directory / "memory-growth.json", result)
            return result
