"""Synthetic local MCP server for opt-in capture verification; no broker access."""
import json
import sys
import os
import subprocess

TOOLS = ("get_positions", "get_balances", "get_cash")
PAYLOAD = '{ "amount": 12345.6700, "large": 9007199254740993, "currency": "EUR" }\r\n'


def main():
    for line in sys.stdin:
        request = json.loads(line)
        if "id" not in request:
            continue
        method = request.get("method")
        if method == "initialize":
            result = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
                      "serverInfo": {"name": "capture-fixture", "version": "1"}}
        elif method == "tools/list":
            result = {"tools": [{"name": name, "description": "Read synthetic capture test data.",
                      "inputSchema": {"type": "object", "properties": {}},
                      "annotations": {"readOnlyHint": True}} for name in (TOOLS + (("verify_capture",) if os.environ.get("ARMADA_CAPTURE_PROBE_SCRIPT") else ())) ]}
        elif method == "tools/call" and request.get("params", {}).get("name") == "verify_capture":
            # The opt-in verifier supplies this exact local script; tool arguments cannot choose a command.
            script = os.environ["ARMADA_CAPTURE_PROBE_SCRIPT"]
            child = subprocess.run([sys.executable, script], capture_output=True, text=True, timeout=20)
            result = {"content": [{"type": "text", "text": child.stdout or child.stderr}],
                      "isError": child.returncode != 0}
        elif method == "tools/call":
            result = {"content": [{"type": "text", "text": PAYLOAD}],
                      "structuredContent": {"amount": "12345.6700", "large": "9007199254740993"},
                      "isError": False}
        else:
            result = {}
        print(json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": result}), flush=True)


if __name__ == "__main__":
    main()
