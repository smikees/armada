from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace

import pytest

from armada.webui import agentcommon


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is needed for browser script checks")
def test_pagination_filter_sort_and_delete():
    result = subprocess.run(["node", str(Path(__file__).with_name("artefacts_pagination_harness.js"))],
        capture_output=True, text=True, encoding="utf-8", timeout=15)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("only_agent", [None, "finance"])
def test_realm_and_agent_views_hide_rows_after_the_first_page(tmp_path, monkeypatch, only_agent):
    rows = [{"name": f"report {i}.md", "path": "", "exists": False, "owner_id": "finance",
             "owner": "Warren", "thread": "Main", "thread_slug": "main", "type": "output",
             "ext": "md", "date_iso": "2026-10-01T12:00:00", "ymd": "2026-10-01"}
            for i in range(101)]
    monkeypatch.setattr(agentcommon, "_gather_artifacts", lambda *args: rows)
    html = agentcommon._realm_artefacts(SimpleNamespace(agents=[]), tmp_path, only_agent)
    assert html.count('class="mc-row"') == 101
    assert html.count('style="display:none;"') == 1
    assert 'id="art-pager-top"' in html and 'id="art-pager-bottom"' in html
