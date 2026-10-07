import sys


def entrypoint():
    try:
        # Before updater/imports: the GUI must never inherit a developer tool's lifetime
        # or its private Windows filesystem view.
        if len(sys.argv) > 1 and sys.argv[1] == "app":
            from .desktop_launch import relaunch_if_needed
            if relaunch_if_needed(sys.argv[1:]):
                return 0

        # Explicit `python -m armada` commands also acquire a process lease. Normal installed shortcuts
        # enter through the stable bootstrap directly, which can recover even when this package is absent.
        if "armada_bootstrap" not in sys.modules or not getattr(sys.modules["armada_bootstrap"], "_leases", {}):
            from . import updater
            if updater.installed():
                updater.reexec()

        from .cli import main
        return main()
    except Exception as error:  # silent-ok: report_failure logs and displays this error
        from .startup import report_failure
        report_failure(error, gui=len(sys.argv) > 1 and sys.argv[1] == "app")
        return 1


if __name__ == "__main__":
    sys.exit(entrypoint())
