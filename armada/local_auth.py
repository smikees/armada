"""Per-server loopback credentials, bootstrapped through an owner-only local file.

The browser exchanges a URL fragment for an HttpOnly cookie, then removes the fragment.
Neither public health checks nor content pages disclose the credential. Browser origin
guards remain necessary: cookies are scoped to hosts, not TCP ports.
"""
from __future__ import annotations

import hmac
import html
from http.cookies import SimpleCookie, CookieError
import json
import os
from pathlib import Path
import secrets
import threading
from urllib.parse import urlsplit

from . import util


def _private_directory() -> Path:
    folder = util.data_dir() / "local-auth"
    folder.mkdir(parents=True, exist_ok=True)
    if folder.is_symlink() or (hasattr(folder, "is_junction") and folder.is_junction()):
        raise OSError("The authentication directory must not be a link")
    if os.name == "nt":
        import ctypes as c
        from ctypes import wintypes as w
        adv = c.WinDLL("advapi32", use_last_error=True)
        kernel = c.WinDLL("kernel32", use_last_error=True)
        convert = adv.ConvertStringSecurityDescriptorToSecurityDescriptorW
        convert.argtypes = [w.LPCWSTR, w.DWORD, c.POINTER(c.c_void_p), c.POINTER(w.ULONG)]
        convert.restype = w.BOOL
        set_security = adv.SetFileSecurityW
        set_security.argtypes = [w.LPCWSTR, w.DWORD, c.c_void_p]
        set_security.restype = w.BOOL
        kernel.LocalFree.argtypes = [c.c_void_p]
        kernel.LocalFree.restype = c.c_void_p
        descriptor = c.c_void_p()
        # Protected DACL; only the object's owner and LocalSystem, inherited by children.
        if not convert("D:P(A;OICI;FA;;;OW)(A;OICI;FA;;;SY)", 1, c.byref(descriptor), None):
            raise c.WinError(c.get_last_error())
        try:
            if not set_security(str(folder), 0x80000004, descriptor):
                raise c.WinError(c.get_last_error())
        finally:
            kernel.LocalFree(descriptor)
    else:
        folder.chmod(0o700)
    return folder


def _path(port: int) -> Path:
    return util.data_dir() / "local-auth" / f"{int(port)}.json"


def headers(port: int) -> dict:
    """Internal clients must possess the owning user's per-server credential."""
    try:
        value = json.loads(_path(port).read_text(encoding="utf-8"))
        token = value["token"]
        if isinstance(token, str) and len(token) == 43:
            return {"Authorization": "Bearer " + token}
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return {}


def browser_url(url: str) -> str:
    parsed = urlsplit(url)
    token = headers(parsed.port or 8756).get("Authorization", "").removeprefix("Bearer ")
    if not token:
        raise OSError("ARMADA's private local session is unavailable; reopen the app")
    # The token is a fragment: never a request path, query string, or Referer.
    return f"{parsed.scheme}://{parsed.netloc}/auth#{token}"


class Session:
    def __init__(self, port: int):
        self.port = port
        self._close_lock = threading.Lock()
        self._closed = False
        self.token = secrets.token_urlsafe(32)
        self.cookie_name = f"armada_session_{port}"
        folder = _private_directory()  # Fail closed before writing a secret.
        self.path = folder / f"{port}.json"
        self.launch_file = folder / f"{port}.html"
        url = f"http://127.0.0.1:{port}/auth#{self.token}"
        with util.file_lock(self.path, validate_state=False):
            util.write_json_atomic(self.path, {"pid": os.getpid(), "token": self.token})
            util.write_text_atomic(self.launch_file,
            '<!doctype html><meta name="referrer" content="no-referrer">'
            '<meta http-equiv="refresh" content="0;url=' + html.escape(url, quote=True) + '">'
            '<title>Open ARMADA</title>Opening ARMADA…')

    def allows(self, headers) -> bool:
        bearer = headers.get("Authorization", "")
        if bearer.startswith("Bearer ") and hmac.compare_digest(bearer[7:].encode(), self.token.encode()):
            return True
        try:
            cookies = SimpleCookie()
            cookies.load(headers.get("Cookie", ""))
            cookie = cookies.get(self.cookie_name)
            return bool(cookie and hmac.compare_digest(cookie.value.encode(), self.token.encode()))
        except (CookieError, TypeError):
            return False

    def close(self):
        # Cleanup can be requested by the serving thread and its owning window/fixture.
        with self._close_lock, util.file_lock(self.path, validate_state=False):
            if self._closed:
                return
            self._closed = True
            try:
                value = json.loads(self.path.read_text(encoding="utf-8"))
                if value.get("token") == self.token:
                    self.path.unlink(missing_ok=True)
                    self.launch_file.unlink(missing_ok=True)
            except FileNotFoundError:
                pass


BOOTSTRAP_HTML = '''<!doctype html><html><head><meta charset="utf-8">
<meta name="referrer" content="no-referrer"><title>Open ARMADA</title></head>
<body><p id="state">Opening ARMADA…</p><script>
(async function(){
  const token=location.hash.slice(1);
  history.replaceState(null,'','/auth');
  if(!/^[A-Za-z0-9_-]{43}$/.test(token)){
    document.getElementById('state').textContent='Open ARMADA from its desktop shortcut or private launch file.';
    return;
  }
  try{
    const result=await fetch('/auth',{method:'POST',headers:{Authorization:'Bearer '+token}});
    if(!result.ok)throw new Error();
    location.replace('/');
  }catch(e){document.getElementById('state').textContent='This session expired. Reopen ARMADA.';}
})();
</script></body></html>'''
