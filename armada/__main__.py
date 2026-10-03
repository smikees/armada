import sys

# Before updater/imports: the GUI must never inherit a developer tool's lifetime
# or its private Windows filesystem view.
if len(sys.argv) > 1 and sys.argv[1] == "app":
    from .desktop_launch import relaunch_if_needed
    if relaunch_if_needed(sys.argv[1:]):
        sys.exit(0)

# An update downloaded and checked in the background (5.4) is put in place here, before the app is
# imported, when this is the only ARMADA process that could be running the old code. Then start
# again on the new code. See updater.boot.
if len(sys.argv) > 1 and sys.argv[1] in ("app", "schedule"):
    from . import updater
    if updater.boot(sys.argv[1]):
        updater.reexec()

from .cli import main
sys.exit(main())
