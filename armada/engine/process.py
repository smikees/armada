"""Owned CLI lifetime: bounded pipe draining, output-independent deadlines and tree cleanup.

Provider modules own protocol parsing. A successful process exit alone is not a successful turn.
Windows children start suspended, enter a kill-on-close Job Object, then resume; POSIX children
start a new session. Cancellation is a request to this owner, never a bare Popen.kill().
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import json
import logging
import os
import queue
import signal
import subprocess
import threading
import time
from ..background import process_options

log = logging.getLogger(__name__)
MAX_LINE = 8 * 1024 * 1024
MAX_STDOUT = 32 * 1024 * 1024
MAX_COMMAND_STDOUT = 4 * 1024 * 1024
MAX_COMMAND_STDERR = 1024 * 1024
CLEANUP_SECONDS = 3


@dataclass
class ProcessResult:
    returncode: int | None = None
    stderr: str = ""
    error: str = ""
    cancelled: bool = False
    timed_out: bool = False
    stdout: str = ""


class RunProcess:
    """Cancellation handle passed to existing on_proc callers; kill requests owned cleanup."""
    def __init__(self, process):
        self._process = process
        self._cancel = threading.Event()

    @property
    def pid(self):
        return self._process.pid

    def poll(self):
        return self._process.poll()

    def kill(self):
        self._cancel.set()

    terminate = kill


def safe_emit(callback, event):
    """A disconnected observer must not abandon the child or prevent terminal persistence."""
    if callback:
        try:
            callback(event)
        except Exception:
            log.exception("CLI event observer failed")


def supervise(args, *, prompt, on_line, timeout, cwd=None, env=None, on_proc=None, raw_output=False):
    """Run one owned process; on_line receives complete lines and may reject malformed output.

Callbacks must return promptly. Memory is bounded at the transport: at most 8 queued lines
of 8 MiB and 64 stderr chunks. Cleanup has its own bounded grace period after the run deadline.
"""
    result = ProcessResult()
    proc = tree = None
    group_closed = False
    workers = []
    stopping = threading.Event()
    events = queue.Queue(maxsize=8)
    stderr = deque(maxlen=None if raw_output else 64)
    worker_errors = []
    deadline = time.monotonic() + timeout if timeout else None

    def put(event):
        while not stopping.is_set():
            try:
                events.put(event, timeout=0.05)
                return
            except queue.Full:
                pass

    def stdout_reader():
        try:
            read = (lambda: proc.stdout.read(4096)) if raw_output else (lambda: proc.stdout.readline(MAX_LINE + 1))
            while line := read():
                if not raw_output and len(line) > MAX_LINE:
                    raise ValueError("CLI output line exceeded the 8 MiB limit")
                put(("line", line))
        except Exception as exc:
            log.exception("CLI stdout reader failed")
            worker_errors.append(f"stdout read failed: {exc}")
            put(("error", f"stdout read failed: {exc}"))
        finally:
            put(("eof", None))

    def stderr_reader():
        try:
            received = 0
            while chunk := proc.stderr.read(4096):
                received += len(chunk.encode('utf-8'))
                if raw_output and received > MAX_COMMAND_STDERR:
                    raise ValueError("Command stderr exceeded the 1 MiB limit; process tree stopped")
                stderr.append(chunk)
        except Exception as exc:
            log.exception("CLI stderr reader failed")
            worker_errors.append(f"stderr read failed: {exc}")
            put(("error", f"stderr read failed: {exc}"))

    def feed():
        try:
            proc.stdin.write(prompt)
            proc.stdin.close()
        except (OSError, ValueError) as exc:
            # A provider may reject a request before reading all of stdin. Its exit and terminal
            # event still decide the result; broken pipes must never hold the supervisor open.
            log.debug("CLI closed stdin: %s", exc)

    def close_tree():
        nonlocal tree, group_closed
        if tree is not None:
            tree.close()
            tree = None
        elif proc is not None and os.name != "nt" and not group_closed:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            group_closed = True

    try:
        if os.name == "nt":
            from .windows_job import WindowsJob
            tree = WindowsJob()
        proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace" if raw_output else "strict",
                                cwd=cwd, env=env, **process_options(suspended=True),
                                start_new_session=os.name != "nt")
        if tree is not None:
            tree.attach_and_resume(proc)
        # stdout is a UTF-8 protocol, while stderr is best-effort human diagnostics.
        proc.stderr.reconfigure(errors="replace")
        handle = RunProcess(proc)
        for fn in (stdout_reader, stderr_reader, feed):
            worker = threading.Thread(target=fn, name="armada-cli-" + fn.__name__, daemon=True)
            worker.start()
            workers.append(worker)
        if on_proc:
            on_proc(handle)
        eof = False
        received = 0
        cleanup_deadline = None
        while True:
            if handle._cancel.is_set():
                result.cancelled = True
                result.error = "Run stopped by the owner."
                break
            if deadline is not None and time.monotonic() >= deadline:
                result.timed_out = True
                result.error = f"CLI timed out after {timeout}s"
                break
            if cleanup_deadline is not None and time.monotonic() >= cleanup_deadline:
                break  # failed OS cleanup is bounded even for an explicitly unlimited turn
            exited = proc.poll() is not None
            if exited:
                try:
                    close_tree()  # descendants must not keep inherited pipes open after CLI exit
                except Exception as exc:
                    # Keep draining already-produced output even when cleanup needs a retry.
                    result.error = result.error or f"CLI tree cleanup failed: {exc}"
                    cleanup_deadline = cleanup_deadline or time.monotonic() + CLEANUP_SECONDS
                    log.exception("CLI tree cleanup failed")
            if eof and exited:
                break
            try:
                kind, value = events.get(timeout=0.05)
            except queue.Empty:
                continue
            if kind == "eof":
                eof = True
            elif kind == "error":
                raise RuntimeError(value)
            else:
                received += len(value.encode('utf-8'))
                if received > (MAX_COMMAND_STDOUT if raw_output else MAX_STDOUT):
                    raise ValueError("Command stdout exceeded the 4 MiB limit; process tree stopped" if raw_output
                                     else "CLI stdout exceeded the 32 MiB turn limit")
                if raw_output or value.strip():
                    on_line(value)
    except Exception as exc:
        result.error = f"CLI process failed: {exc}"
        log.debug("CLI supervisor failed", exc_info=True)
    finally:
        stopping.set()
        # Each cleanup step gets a chance even when an earlier one fails.
        try:
            close_tree()
        except Exception as exc:
            result.error = result.error or f"CLI tree cleanup failed: {exc}"
            log.exception("CLI tree cleanup failed")
            try:
                close_tree()
            except Exception:
                log.exception("CLI tree cleanup retry failed")
        if proc is not None:
            try:
                if proc.poll() is None:
                    proc.kill()  # fallback for a failed job assignment/termination
                proc.wait(timeout=CLEANUP_SECONDS)
            except Exception as exc:
                result.error = result.error or f"CLI process cleanup failed: {exc}"
                log.exception("CLI process cleanup failed")
            until = time.monotonic() + CLEANUP_SECONDS
            for worker in workers:
                worker.join(max(0, until - time.monotonic()))
            if any(worker.is_alive() for worker in workers):
                result.error = result.error or "CLI pipe cleanup did not finish."
            else:
                for pipe in (proc.stdin, proc.stdout, proc.stderr):
                    try:
                        if pipe:
                            pipe.close()
                    except Exception as exc:
                        log.exception("CLI pipe close failed")
                        result.error = result.error or f"CLI pipe cleanup failed: {exc}"
            result.returncode = proc.returncode
            if os.name == "nt" and result.returncode is not None:
                try:
                    proc._handle.Close()
                except Exception as exc:
                    log.exception("CLI process handle close failed")
                    result.error = result.error or f"CLI handle cleanup failed: {exc}"
        result.stderr = "".join(stderr) if raw_output else "".join(stderr)[-4000:]
        if worker_errors and not result.error:
            result.error = worker_errors[0]
    if result.returncode != 0 and not result.error:
        result.error = f"CLI exited with code {result.returncode}: {result.stderr}"
    return result


def supervise_command(args, *, timeout, cwd=None, env=None, on_proc=None):
    """Own a noninteractive command without parsing a provider protocol.

    Preserve whitespace and replacement decoding. Exceeding either output limit stops the
    entire tree and reports failure, so a truncated success cannot pass job-result checks.
    """
    chunks = []
    result = supervise(args, prompt="", on_line=chunks.append, timeout=timeout, cwd=cwd,
                       env=env, on_proc=on_proc, raw_output=True)
    result.stdout = "".join(chunks)
    return result


def supervise_rpc(args, *, start, on_message, timeout, cwd=None, env=None, on_proc=None):
    """Own one interactive newline-JSON CLI session until its terminal notification.

    `start(send)` sends initialization; `on_message(message, send)` may send dependent
    requests and returns true only after the turn has completed. The same process ownership,
    byte caps, timeout and cancellation rules as `supervise` apply.
    """
    result = ProcessResult()
    proc = tree = None
    incoming = queue.Queue(maxsize=8)
    stderr = deque(maxlen=64)
    workers = []
    stopping = threading.Event()
    deadline = time.monotonic() + timeout if timeout else None

    def put(value):
        while not stopping.is_set():
            try:
                incoming.put(value, timeout=.05)
                return
            except queue.Full:
                pass

    def read_stdout():
        try:
            while line := proc.stdout.readline(MAX_LINE + 1):
                if len(line) > MAX_LINE:
                    raise ValueError("CLI output line exceeded the 8 MiB limit")
                put(("line", line))
        except Exception as exc:
            logging.getLogger(__name__).exception('CLI stdout reader failed')
            put(("error", str(exc)))
        finally:
            put(("eof", None))

    def read_stderr():
        try:
            while chunk := proc.stderr.read(4096):
                stderr.append(chunk)
        except Exception as exc:
            logging.getLogger(__name__).exception('CLI stderr reader failed')
            put(("error", str(exc)))

    try:
        if os.name == "nt":
            from .windows_job import WindowsJob
            tree = WindowsJob()
        proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="strict",
                                cwd=cwd, env=env, **process_options(suspended=True),
                                start_new_session=os.name != "nt")
        if tree is not None:
            tree.attach_and_resume(proc)
        proc.stderr.reconfigure(errors="replace")
        handle = RunProcess(proc)
        for fn in (read_stdout, read_stderr):
            worker = threading.Thread(target=fn, name="armada-rpc-" + fn.__name__, daemon=True)
            worker.start()
            workers.append(worker)
        if on_proc:
            on_proc(handle)

        def send(message):
            proc.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
            proc.stdin.flush()

        start(send)
        received = 0
        eof = False
        while True:
            if handle._cancel.is_set():
                result.cancelled, result.error = True, "Run stopped by the owner."
                break
            if deadline is not None and time.monotonic() >= deadline:
                result.timed_out = True
                result.error = f"CLI timed out after {timeout}s"
                break
            if eof and proc.poll() is not None:
                result.error = "Codex app server ended before completing the turn."
                break
            try:
                kind, value = incoming.get(timeout=.05)
            except queue.Empty:
                continue
            if kind == "eof":
                eof = True
                continue
            if kind == "error":
                raise RuntimeError(value)
            received += len(value)
            if received > MAX_STDOUT:
                raise ValueError("CLI stdout exceeded the 32 MiB turn limit")
            message = json.loads(value)
            if not isinstance(message, dict):
                raise ValueError("Malformed Codex app-server message")
            if on_message(message, send):
                break
    except Exception as exc:
        result.error = f"CLI process failed: {exc}"
        log.debug("CLI RPC supervisor failed", exc_info=True)
    finally:
        stopping.set()
        if tree is not None:
            try:
                tree.close()
            except Exception as exc:
                logging.getLogger(__name__).exception('CLI tree cleanup failed')
                result.error = result.error or f"CLI tree cleanup failed: {exc}"
        elif proc is not None and os.name != "nt":
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if proc is not None:
            try:
                if proc.poll() is None:
                    proc.kill()
                proc.wait(timeout=CLEANUP_SECONDS)
            except Exception as exc:
                logging.getLogger(__name__).exception('CLI process cleanup failed')
                result.error = result.error or f"CLI process cleanup failed: {exc}"
            until = time.monotonic() + CLEANUP_SECONDS
            for worker in workers:
                worker.join(max(0, until - time.monotonic()))
            if any(worker.is_alive() for worker in workers):
                result.error = result.error or "CLI pipe cleanup did not finish."
            for pipe in (proc.stdin, proc.stdout, proc.stderr):
                try:
                    if pipe:
                        pipe.close()
                except Exception:
                    logging.getLogger(__name__).exception('CLI pipe close failed')
                    pass
            result.returncode = proc.returncode
            if os.name == "nt" and result.returncode is not None:
                try:
                    proc._handle.Close()
                except Exception:
                    logging.getLogger(__name__).exception('CLI handle close failed')
                    pass
        result.stderr = "".join(stderr)[-4000:]
    return result
