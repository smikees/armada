"""Shared scrolling chrome must work across page shells and embedded surfaces."""
import shutil
import subprocess
from pathlib import Path

import pytest

from armada.assets import CSS_LINKS

ROOT = Path(__file__).resolve().parents[1]


def test_scrollbar_interactions():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required for the browser-controller contract")
    subprocess.run(
        [node, str(ROOT / "tests/scrollbars_harness.js"),
         str(ROOT / "armada/webui/static/js/scrollbars.js")], check=True,
    )


def test_shared_asset_loads_deferred_controller():
    assert '<script src="/static/js/scrollbars.js' in CSS_LINKS
    assert ' defer></script>' in CSS_LINKS
