# `armada/webui/__init__.py`

ARMADA web UI package.

Split from the former monolithic ``webui.py`` (Phase 3 of the refactor). The implementation
currently lives in ``_core`` and is progressively being carved into ``components`` and ``pages``
submodules; everything is re-exported here so existing callers (``from . import webui`` then
``webui.render_x(...)``, and a few underscored helpers used by serve.py/tests) are unchanged.

The re-export mirrors every non-dunder name from the implementation module(s) into this package's
namespace, so ``webui.<anything>`` resolves exactly as it did when this was one file.
