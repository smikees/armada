"""Small stdio MCP transport for a single, scoped ARMADA managed-tools invocation.

The capability credential travels in the subprocess environment, never in a prompt or argv.
No owner API credential and no production mutation endpoint is available here.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def serve():
    endpoint = os.environ["ARMADA_TOOL_ENDPOINT"]
    token = os.environ["ARMADA_TOOL_TOKEN"]
    for line in sys.stdin:
        request = None
        try:
            if len(line) > 2 * 1024 * 1024:
                raise ValueError("MCP request is too large.")
            request = json.loads(line)
            if "id" not in request:
                continue
            method = request.get("method")
            if method == "initialize":
                result = {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}},
                          "serverInfo": {"name": "armada", "version": "1.0"}}
            elif method == "ping":
                result = {}
            elif method in ("tools/list", "tools/call"):
                body = json.dumps({"method": method, "params": request.get("params") or {}}).encode()
                req = urllib.request.Request(endpoint, body, headers={"Authorization": "Bearer " + token,
                    "Content-Type": "application/json"})
                with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=180) as response:
                    result = json.load(response)
            else:
                raise ValueError("Unsupported MCP method.")
            reply = {"jsonrpc": "2.0", "id": request["id"], "result": result}
        except (ValueError, KeyError, OSError, urllib.error.URLError) as exc:
            if not isinstance(request, dict) or "id" not in request:
                continue
            reply = {"jsonrpc": "2.0", "id": request["id"],
                     "error": {"code": -32603, "message": str(exc)}}
        sys.stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    serve()
