"""ARMADA web UI package.

Split from the former monolithic ``webui.py`` (Phase 3 of the refactor). The implementation
currently lives in ``_core`` and is progressively being carved into ``components`` and ``pages``
submodules; everything is re-exported here so existing callers (``from . import webui`` then
``webui.render_x(...)``, and a few underscored helpers used by serve.py/tests) are unchanged.

The re-export mirrors every non-dunder name from the implementation module(s) into this package's
namespace, so ``webui.<anything>`` resolves exactly as it did when this was one file.
"""
from __future__ import annotations

from . import _core
from . import pages   # render_* entrypoints (carved from _core in P3.3)

# Mirror every public and underscored name (helpers, render_*, constants) so the package namespace
# is a drop-in replacement for the old module namespace. _core first (helpers/constants), then pages
# (the render_* functions), which shadows nothing since render_* no longer live in _core.
globals().update({k: v for k, v in vars(_core).items() if not k.startswith("__")})
globals().update({k: v for k, v in vars(pages).items() if not k.startswith("__")})

# NB: _core stays accessible as webui._core. Internal cross-references between rendering functions
# resolve within _core's namespace, so anything monkeypatching an internal helper must target
# webui._core.<name> (not webui.<name>, which is only a mirror copy).

