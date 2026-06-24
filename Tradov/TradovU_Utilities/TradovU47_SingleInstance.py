#!/usr/bin/env python3
"""Process-level single-instance lock helper for Tradov."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


try:
    import fcntl
except ImportError:  # pragma: no cover - Linux is the target runtime
    fcntl = None  # type: ignore[assignment]


@dataclass
class SingleInstanceLock:
    """Hold an OS-level lock for the lifetime of the process."""

    path: Path
    fd: int | None = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o644)
        if fcntl is None:
            return True

        try:
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(self.fd)
            self.fd = None
            return False

        os.ftruncate(self.fd, 0)
        os.write(self.fd, f"pid={os.getpid()}\n".encode("utf-8"))
        os.fsync(self.fd)
        return True

    def release(self) -> None:
        if self.fd is None:
            return
        try:
            if fcntl is not None:
                fcntl.flock(self.fd, fcntl.LOCK_UN)
        finally:
            try:
                os.close(self.fd)
            finally:
                self.fd = None

    def __enter__(self) -> "SingleInstanceLock":
        if not self.acquire():
            raise RuntimeError(f"Another Tradov instance is already running: {self.path}")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()


def get_tradov_instance_lock_path() -> Path:
    """Return the canonical lock-file path."""
    return Path(__file__).resolve().parents[2] / ".tradov" / "tradov.lock"


def try_acquire_tradov_instance_lock() -> SingleInstanceLock | None:
    """Try to acquire the global Tradov process lock."""
    lock = SingleInstanceLock(get_tradov_instance_lock_path())
    return lock if lock.acquire() else None
