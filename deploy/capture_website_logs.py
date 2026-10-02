"""Capture a service's combined stdout/stderr without expiry or copytruncate.

Only successfully closed, synced files lose the .active suffix. A failed capture
stops its child and leaves incomplete files for operator recovery, not deletion.
"""

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import queue
import re
import signal
import subprocess
import sys
import threading
import time
import uuid


CHUNK_BYTES = 64 * 1024
DEFAULT_MAX_BYTES = 16 * 1024 * 1024


def utc_now():
    return datetime.now(timezone.utc)


class LogWriter:
    def __init__(self, directory, prefix, max_bytes=DEFAULT_MAX_BYTES, clock=utc_now):
        self.directory = Path(directory)
        if (
            not self.directory.is_absolute()
            or self.directory.resolve() != self.directory
            or not self.directory.is_dir()
        ):
            raise ValueError("A real, absolute, existing log directory is required.")
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,47}", prefix) or max_bytes < 1:
            raise ValueError("Invalid stream name or rotation size.")
        self.prefix = prefix
        self.max_bytes = max_bytes
        self.clock = clock
        self.session = uuid.uuid4().hex
        self.sequence = 0
        self.fd = None
        self.active = None
        self.day = None
        self.size = 0
        try:
            self._open()
        except OSError:
            self.abort()
            raise

    def _sync_directory(self):
        if os.name == "posix":
            fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)

    def _open(self):
        stamp = self.clock().astimezone(timezone.utc)
        self.day = stamp.date()
        self.sequence += 1
        name = (
            f"{self.prefix}-{stamp:%Y%m%dT%H%M%S%fZ}-"
            f"{self.session}-{self.sequence:06d}.log.active"
        )
        self.active = self.directory / name
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_APPEND
        flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
        self.fd = os.open(self.active, flags, 0o640)
        self.size = 0
        self._sync_directory()

    def seal(self):
        if self.fd is None:
            return
        os.fsync(self.fd)
        if hasattr(os, "fchmod"):
            os.fchmod(self.fd, 0o440)
        os.fsync(self.fd)
        os.close(self.fd)
        self.fd = None
        # link() fails on a collision; replace()/rename() may overwrite history.
        sealed = self.active.with_suffix("")
        os.link(self.active, sealed)
        self._sync_directory()
        self.active.unlink()
        if not hasattr(os, "fchmod"):
            os.chmod(sealed, 0o440)
        self._sync_directory()

    def abort(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def rotate_if_due(self):
        if self.fd is not None and self.clock().astimezone(timezone.utc).date() != self.day:
            self.seal()

    def write(self, data):
        remaining = memoryview(data)
        while remaining:
            self.rotate_if_due()
            if self.fd is None:
                self._open()
            available = self.max_bytes - self.size
            portion = remaining[:available]
            while portion:
                written = os.write(self.fd, portion)
                if written <= 0:
                    raise OSError("Log write made no progress.")
                self.size += written
                remaining = remaining[written:]
                portion = portion[written:]
            os.fsync(self.fd)
            if self.size == self.max_bytes:
                self.seal()


def signal_child(child, signum):
    try:
        if os.name == "posix":
            os.killpg(child.pid, signum)
        elif child.poll() is None:
            child.send_signal(signum)
    except ProcessLookupError:
        pass


def capture(directory, prefix, command, max_bytes=DEFAULT_MAX_BYTES, shutdown_seconds=30):
    writer = None
    child = None
    handlers = {}
    received = []
    pipe = None
    complete = False
    try:
        writer = LogWriter(directory, prefix, max_bytes)
        forwarded = ("SIGTERM", "SIGINT", "SIGHUP", "SIGQUIT", "SIGUSR1", "SIGUSR2")
        for name in forwarded:
            signum = getattr(signal, name, None)
            if signum is not None:
                handlers[signum] = signal.getsignal(signum)
                signal.signal(signum, lambda number, _frame: received.append(number))
        child = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
            start_new_session=os.name == "posix",
        )
        pipe = child.stdout
        chunks = queue.Queue(maxsize=16)

        def read_output():
            try:
                while True:
                    data = os.read(pipe.fileno(), CHUNK_BYTES)
                    if not data:
                        break
                    chunks.put(data)
                chunks.put(None)
            except OSError as error:
                chunks.put(error)

        threading.Thread(target=read_output, daemon=True).start()
        deadline = None
        killed_at = None
        eof = False
        while not eof or child.poll() is None:
            while received:
                signum = received.pop(0)
                signal_child(child, signum)
                if signum in (signal.SIGTERM, signal.SIGINT) and deadline is None:
                    deadline = time.monotonic() + shutdown_seconds
            if child.poll() is not None and deadline is None:
                # Descendants may still have the output pipe open.
                deadline = time.monotonic() + shutdown_seconds
            if deadline is not None and time.monotonic() >= deadline and killed_at is None:
                signal_child(child, getattr(signal, "SIGKILL", signal.SIGTERM))
                killed_at = time.monotonic()
            if killed_at is not None and time.monotonic() - killed_at > 5:
                raise OSError("Child output did not close after forced shutdown.")
            writer.rotate_if_due()
            if eof:
                time.sleep(0.05)
                continue
            try:
                chunk = chunks.get(timeout=0.2)
            except queue.Empty:
                continue
            if chunk is None:
                eof = True
            elif isinstance(chunk, OSError):
                raise chunk
            else:
                writer.write(chunk)
        writer.seal()
        code = child.wait()
        complete = True
        return code if code >= 0 else 128 - code
    except (OSError, ValueError):
        # Never echo argv, environment, paths, exception text or captured bytes.
        print(
            "STYL website log capture failed; stopping child. Preserve .active "
            "files; output may be incomplete. Check storage and configuration.",
            file=sys.stderr,
        )
        return 74
    finally:
        if child is not None and not complete:
            signal_child(child, signal.SIGTERM)
            try:
                child.wait(timeout=shutdown_seconds)
            except subprocess.TimeoutExpired:
                signal_child(child, getattr(signal, "SIGKILL", signal.SIGTERM))
                child.wait(timeout=5)
            # A parent can exit while a descendant ignores TERM and holds the pipe.
            signal_child(child, getattr(signal, "SIGKILL", signal.SIGTERM))
        if pipe is not None:
            pipe.close()
        if writer is not None:
            writer.abort()
        for signum, handler in handlers.items():
            signal.signal(signum, handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", default=os.environ.get("STYL_WEBSITE_LOG_DIR"))
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    parser.add_argument("--shutdown-seconds", type=int, default=30)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not args.directory or not command or args.max_bytes < 1 or args.shutdown_seconds < 1:
        parser.error("directory, command and positive limits are required")
    return capture(args.directory, args.prefix, command, args.max_bytes, args.shutdown_seconds)


if __name__ == "__main__":
    sys.exit(main())
