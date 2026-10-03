"""Send Finance notifications through ARMADA's machine-local Telegram connection.

Credentials stay in the machine-local ~/.armada store, outside the realm and repository.
This example helper records delivery evidence against the scheduled job's individual run ID.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
import uuid
import datetime as dt
from pathlib import Path

CAPITAL = Path(__file__).resolve().parent
STORE = Path.home() / ".armada" / "telegram.json"


def credentials() -> tuple[str, str]:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if token and chat:
        return token, chat
    state = json.loads(STORE.read_text(encoding="utf-8-sig"))
    env_file = state.get("env_file")
    if env_file and (not token or not chat):
        for raw in Path(env_file).read_text(encoding="utf-8-sig").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key == "TELEGRAM_BOT_TOKEN" and not token:
                token = value.strip().strip('"').strip("'")
            elif key == "TELEGRAM_CHAT_ID" and not chat:
                chat = value.strip().strip('"').strip("'")
    token = token or str(state.get("token") or "").strip()
    chat = chat or str(state.get("chat_id") or "").strip()
    if not token or not chat:
        raise ValueError("ARMADA Telegram is not connected")
    return token, chat


def _post(token: str, method: str, body: bytes, content_type: str) -> dict:
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=body,
        headers={"Content-Type": content_type},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Telegram returned HTTP {exc.code}") from None
    except (OSError, urllib.error.URLError):
        raise RuntimeError("Telegram transport failed") from None
    if not result.get("ok"):
        raise RuntimeError("Telegram rejected the message")
    return result


def send_text(token: str, chat: str, message: str, parse_mode: str = "", receipts=None) -> int:
    parts = [message[i:i + 3900] for i in range(0, len(message), 3900)]
    for part in parts:
        payload = {"chat_id": chat, "text": part, "disable_web_page_preview": True}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        response = _post(token, "sendMessage", json.dumps(payload).encode("utf-8"), "application/json")
        if receipts is not None:
            receipts.append(response["result"]["message_id"])
    return len(parts)


def send_document(token: str, chat: str, filename: str, caption: str, parse_mode: str = "") -> dict:
    path = Path(filename).resolve()
    if not path.is_file() or not path.is_relative_to(CAPITAL):
        raise ValueError("The document must be an existing file inside the sender's folder")
    if path.stat().st_size > 25 * 1024 * 1024:
        raise ValueError("The document exceeds the 25 MiB Finance notification limit")
    boundary = uuid.uuid4().hex
    fields = {"chat_id": chat, "caption": caption}
    if parse_mode:
        fields["parse_mode"] = parse_mode
    body = bytearray()
    for key, value in fields.items():
        body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{value}\r\n".encode("utf-8"))
    body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"document\"; filename=\"{path.name}\"\r\nContent-Type: application/octet-stream\r\n\r\n".encode("utf-8"))
    body.extend(path.read_bytes())
    body.extend(f"\r\n--{boundary}--\r\n".encode("ascii"))
    return _post(token, "sendDocument", bytes(body), f"multipart/form-data; boundary={boundary}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("message", nargs="?", default="")
    parser.add_argument("--document")
    parser.add_argument("--caption", default="")
    parser.add_argument("--parse-mode", default="")
    parser.add_argument("--stdin", action="store_true")
    parser.add_argument("--job-id", default="")
    parser.add_argument("--run-id", default=os.getenv("ARMADA_RUN_ID", ""))
    parser.add_argument("--resend", action="store_true", help="Send again even if this job has a successful receipt today")
    parser.add_argument("--check", action="store_true", help="Check credentials without sending")
    args = parser.parse_args(argv)
    message_ids = []
    try:
        receipt = None
        if args.run_id and not re.fullmatch(r"[a-zA-Z0-9_-]{1,128}", args.run_id):
            raise ValueError("Invalid Armada run id for Telegram receipt")
        if args.run_id and not args.job_id:
            raise ValueError("A run-bound Telegram receipt needs --job-id")
        if args.job_id:
            if not re.fullmatch(r"[a-z0-9-]+", args.job_id):
                raise ValueError("Invalid job id for Telegram receipt")
            receipt = CAPITAL / "telegram-receipts" / (args.job_id + ".json")
            if receipt.is_file() and not args.resend and not args.check:
                try:
                    prior = json.loads(receipt.read_text(encoding="utf-8-sig"))
                except (OSError, ValueError) as exc:
                    raise ValueError("Existing Telegram receipt is unreadable; refusing a possible duplicate") from exc
                if prior.get("date") == dt.datetime.now().astimezone().date().isoformat() and prior.get("status", "sent") == "sent":
                    if prior.get("job_id") != args.job_id:
                        raise ValueError("Existing Telegram receipt belongs to a different job")
                    print(json.dumps({"ok": True, "already_sent": True,
                                      "matched_run": bool(args.run_id and prior.get("run_id") == args.run_id),
                                      "receipt_path": str(receipt),
                                      "message_parts": prior.get("message_parts", 0),
                                      "document": prior.get("document", False)}))
                    return 0
            if args.run_id and receipt.with_name(args.job_id + "--" + args.run_id + ".json").exists():
                raise ValueError("Per-run Telegram receipt already exists; refusing to resend or overwrite delivery history")
        token, chat = credentials()
        if args.check:
            print(json.dumps({"ready": True}))
            return 0
        message = sys.stdin.read().strip() if args.stdin else args.message.strip()
        if not message and not args.document:
            raise ValueError("Provide a message or --document")
        parts = send_text(token, chat, message, args.parse_mode, message_ids) if message else 0
        if args.document:
            response = send_document(token, chat, args.document, args.caption, args.parse_mode)
            message_ids.append(response["result"]["message_id"])
        if receipt is not None:
            receipt.parent.mkdir(exist_ok=True)
            record = {"schema_version": 1, "run_id": args.run_id, "destination": "telegram", "status": "sent",
                      "message_ids": message_ids, "date": dt.datetime.now().astimezone().date().isoformat(),
                      "job_id": args.job_id, "message_parts": parts,
                      "document": bool(args.document),
                      "sent_at": dt.datetime.now(dt.timezone.utc).isoformat()}
            if args.document:
                record["document_path"] = str(Path(args.document).resolve())
                record["document_sha256"] = hashlib.sha256(Path(args.document).read_bytes()).hexdigest()
            if args.run_id:
                bound = receipt.with_name(args.job_id + "--" + args.run_id + ".json")
                if bound.exists():
                    raise ValueError("Per-run Telegram receipt already exists; refusing to overwrite delivery history")
                bound.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            temporary = receipt.with_suffix(".json.tmp")
            temporary.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            temporary.replace(receipt)
        print(json.dumps({"ok": True, "message_parts": parts, "document": bool(args.document),
                          "receipt_path": str(bound if args.run_id and receipt else receipt or ""),
                          "run_id": args.run_id}))
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Telegram send failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
