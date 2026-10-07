"""Desktop activation and startup failure reporting, including console-free launches."""
import logging
import sys
import threading


def report_failure(error, *, gui=False):
    """Keep diagnostics even when startup fails before the server/window exists."""
    location = "your ARMADA logs folder"
    try:
        from . import util
        util.init_logging("armada.log")
        location = str(util.data_dir() / "logs" / "armada.log")
        logging.getLogger(__name__).error("ARMADA failed to start", exc_info=(
            type(error), error, error.__traceback__))
    except Exception:  # silent-ok: logging is unavailable; native reporting is still attempted
        pass  # The native fallback must work even with an inaccessible config/log directory.
    message = f"ARMADA could not start.\n\n{error}\n\nDiagnostic log: {location}"
    if sys.stderr is not None:
        try:
            print(message, file=sys.stderr)
        except OSError:
            pass
    if gui and sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, message, "ARMADA - cannot start", 0x10010)
        except Exception:  # silent-ok: no native reporter; log and stderr were already attempted
            pass


def serve_with_desktop(realm, port):
    """Serve until stopped, or open the same owner/server in a native desktop on request."""
    from . import app, instance, serve
    finished, requested = threading.Event(), threading.Event()
    errors = []

    def worker():
        try:
            serve.serve(realm, port)
        except BaseException as error:  # silent-ok: re-raised on the main thread after worker exit
            errors.append(error)
        finally:
            finished.set()

    activation = instance.watch_activation(requested.set)
    threading.Thread(target=worker, daemon=True, name="armada-server").start()
    try:
        while not finished.wait(.1):
            if not requested.is_set():
                continue
            owner = instance.current()
            if owner.get('server_ready'):
                # Keep the account lock, listener, authentication and in-flight work.
                # pywebview must run on the original process's main thread.
                activation.set()
                instance.promote_to_desktop()
                logging.getLogger(__name__).info("Opening desktop for the existing background server")
                reason = "The desktop reported a startup failure."
                try:
                    code = app.run(serve.Handler.realm, owner['port'])
                except Exception as error:  # silent-ok: report_failure logs and displays this error
                    report_failure(error, gui=True)
                    reason, code = str(error), 1
                if not code:
                    return 0
                # A request to open a window is never permission to discard the server's work.
                # A failed WebView startup may not be reusable in this process; retain headless
                # service and explain the recorded failure on subsequent launches.
                instance.keep_headless(reason)
                requested.clear()
                logging.getLogger(__name__).error("Desktop failed; background server remains running: %s", reason)
        if errors:
            raise errors[0]
        return 0
    finally:
        activation.set()
