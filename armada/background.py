"""Windows launch options for unattended probes (never interactive sign-in windows)."""
import os
import subprocess


def process_options(*, suspended=False) -> dict:
    """Suppress console allocation and hide helper windows inherited from a GUI parent."""
    if os.name != "nt":
        return {}
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    return {"creationflags": subprocess.CREATE_NO_WINDOW | (0x4 if suspended else 0), "startupinfo": startup}
