"""Statistics and low-overhead resource sampling for queue experiments."""

from __future__ import annotations

import json
import os
import statistics
import subprocess
import threading
import time
from collections.abc import Callable
from typing import Any


def percentile(samples: list[float], fraction: float) -> float:
    if not samples:
        return 0.0
    ordered = sorted(samples)
    return ordered[min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * fraction))))]


def summarize(samples: list[float], *, unit: str = "s") -> dict[str, Any]:
    if not samples:
        return {"samples": 0, "p50": 0.0, "p95": 0.0, "p99": 0.0, "mean": 0.0, "unit": unit}
    return {
        "samples": len(samples),
        "p50": round(percentile(samples, 0.50), 4),
        "p95": round(percentile(samples, 0.95), 4),
        "p99": round(percentile(samples, 0.99), 4),
        "mean": round(statistics.fmean(samples), 4),
        "min": round(min(samples), 4),
        "max": round(max(samples), 4),
        "unit": unit,
    }


def _parse_percent(value: str) -> float:
    try:
        return float(value.strip().rstrip("%"))
    except (TypeError, ValueError, AttributeError):
        return 0.0


def _parse_mib(value: str) -> float:
    text = value.strip().split("/", 1)[0].strip()
    units = {"GiB": 1024.0, "MiB": 1.0, "KiB": 1 / 1024, "B": 1 / (1024 * 1024)}
    for suffix, factor in units.items():
        if text.endswith(suffix):
            try:
                return float(text[: -len(suffix)].strip()) * factor
            except ValueError:
                continue
    return 0.0


def docker_stats(names: list[str]) -> dict[str, dict[str, float]]:
    if not names:
        return {}
    try:
        completed = subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "{{json .}}", *names],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {}
    result: dict[str, dict[str, float]] = {}
    for line in completed.stdout.splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        result[str(row.get("Name"))] = {
            "cpu_percent": _parse_percent(row.get("CPUPerc", "")),
            "mem_mib": _parse_mib(row.get("MemUsage", "")),
        }
    return result


def _proc_usage(pid: int) -> tuple[float, float]:
    try:
        stat = open(f"/proc/{pid}/stat", encoding="utf-8").read().split()
        ticks = (int(stat[13]) + int(stat[14])) / os.sysconf("SC_CLK_TCK")
    except (OSError, ValueError, IndexError):
        ticks = 0.0
    rss = 0.0
    try:
        for line in open(f"/proc/{pid}/status", encoding="utf-8"):
            if line.startswith("VmRSS:"):
                rss = float(line.split()[1]) / 1024
                break
    except OSError:
        pass
    return ticks, rss


class ResourceSampler:
    def __init__(self, *, containers: list[str], pids: Callable[[], list[int]], interval: float = 1.0) -> None:
        self.containers = containers
        self.pids = pids
        self.interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.samples: list[dict[str, Any]] = []

    def _sample(self) -> None:
        started = time.monotonic()
        containers = docker_stats(self.containers)
        worker_ticks = 0.0
        worker_rss = 0.0
        for pid in self.pids():
            ticks, rss = _proc_usage(pid)
            worker_ticks += ticks
            worker_rss += rss
        self.samples.append(
            {
                "at": started,
                "containers": containers,
                "worker_ticks": worker_ticks,
                "worker_rss_mib": worker_rss,
            }
        )

    def _run(self) -> None:
        while not self._stop.is_set():
            started = time.monotonic()
            self._sample()
            self._stop.wait(max(0.05, self.interval - (time.monotonic() - started)))

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def summary(self) -> dict[str, Any]:
        if not self.samples:
            return {"samples": 0}
        result: dict[str, Any] = {"samples": len(self.samples)}
        for name in self.containers:
            cpu = [item["containers"].get(name, {}).get("cpu_percent", 0.0) for item in self.samples]
            mem = [item["containers"].get(name, {}).get("mem_mib", 0.0) for item in self.samples]
            result[name] = {
                "cpu_percent_mean": round(statistics.fmean(cpu), 3),
                "cpu_percent_max": round(max(cpu), 3),
                "mem_mib_mean": round(statistics.fmean(mem), 3),
                "mem_mib_max": round(max(mem), 3),
            }
        first, last = self.samples[0], self.samples[-1]
        elapsed = max(0.0001, last["at"] - first["at"])
        ticks = max(0.0, last["worker_ticks"] - first["worker_ticks"])
        result["workers"] = {
            "cpu_seconds": round(ticks, 4),
            "cpu_percent_mean": round(ticks / elapsed * 100, 3),
            "rss_mib_max": round(max(item["worker_rss_mib"] for item in self.samples), 3),
        }
        return result
