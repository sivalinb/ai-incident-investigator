"""Run the real stack natively on macOS/Linux, with verified official binaries."""
import argparse
import hashlib
import json
import os
import platform
import signal
import subprocess
import sys
import tarfile
import time
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent
GRAFANA_VERSION = "12.3.6"
PROMETHEUS_VERSION = "3.15.0"


def download(url, output):
    print("Downloading " + url.rsplit("/", 1)[-1], flush=True)
    with urlopen(url, timeout=180) as source, open(output, "wb") as destination:
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            destination.write(chunk)


def unpack(archive, destination):
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with tarfile.open(archive) as tar:
        for item in tar.getmembers():
            path = (root / item.name).resolve()
            if root not in path.parents and path != root:
                raise ValueError("Archive member escapes destination")
            if item.issym() or item.islnk():
                link = (path.parent / item.linkname).resolve()
                if root not in link.parents and link != root:
                    raise ValueError("Unsafe archive link")
        tar.extractall(root)
    return next(p for p in destination.iterdir() if p.is_dir())


def native_binaries(runtime):
    system = platform.system().lower()
    machine = platform.machine().lower()
    arch = "arm64" if machine in ("arm64", "aarch64") else "amd64" if machine in ("x86_64", "amd64") else None
    if system not in ("darwin", "linux") or not arch:
        raise SystemExit("Use Docker Compose on this platform")
    bins = runtime / "bin"
    bins.mkdir(parents=True, exist_ok=True)
    grafana_dirs = list((bins / "grafana").glob("*/bin/grafana"))
    prometheus_dirs = list((bins / "prometheus").glob("*/prometheus"))
    if not grafana_dirs:
        grafana_name = "grafana-" + GRAFANA_VERSION + "." + system + "-" + arch + ".tar.gz"
        url = "https://dl.grafana.com/oss/release/" + grafana_name
        archive = bins / grafana_name
        download(url, archive)
        with urlopen(url + ".sha256", timeout=30) as response:
            expected = response.read().decode().split()[0]
        if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
            raise ValueError("Grafana checksum mismatch")
        home = unpack(archive, bins / "grafana")
    else:
        home = grafana_dirs[0].parent.parent
    if not prometheus_dirs:
        name = "prometheus-" + PROMETHEUS_VERSION + "." + system + "-" + arch + ".tar.gz"
        url = "https://github.com/prometheus/prometheus/releases/download/v" + PROMETHEUS_VERSION + "/"
        archive = bins / name
        download(url + name, archive)
        with urlopen(url + "sha256sums.txt", timeout=30) as response:
            checksums = response.read().decode().splitlines()
        expected = next(line.split()[0] for line in checksums if line.split()[-1] == name)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
            raise ValueError("Prometheus checksum mismatch")
        prometheus = unpack(archive, bins / "prometheus") / "prometheus"
    else:
        prometheus = prometheus_dirs[0]
    return home, prometheus


def wait_for(url, processes, timeout=90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if any(p.poll() is not None for p in processes):
            raise RuntimeError("A demo service exited; inspect .runtime/logs")
        try:
            with urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(.5)
    raise RuntimeError("Service did not become ready: " + url)


