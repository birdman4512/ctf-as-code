#!/usr/bin/env python3
import argparse
import json
import mimetypes
import os
import pathlib
import sys
import uuid
from urllib import error, request


CTFD_URL = os.environ.get("CTFD_URL", "http://localhost").rstrip("/")
CTFD_TOKEN = os.environ.get("CTFD_TOKEN")
CHALLENGES_DIR = pathlib.Path(os.environ.get("CHALLENGES_DIR", "challenges"))
CTFD_MANIFEST = os.environ.get("CTFD_MANIFEST")
UPLOAD_FILES_ON_UPDATE = os.environ.get("CTFD_UPLOAD_FILES_ON_UPDATE", "").lower() == "true"


def parse_args():
    parser = argparse.ArgumentParser(description="Sync challenge manifests to a CTFd instance.")
    parser.add_argument("--url", default=CTFD_URL, help="CTFd base URL (env: CTFD_URL)")
    parser.add_argument("--token", default=CTFD_TOKEN, help="CTFd admin API token (env: CTFD_TOKEN)")
    return parser.parse_args()


def api(method, path, payload=None, headers=None):
    # CTFd only inspects the Authorization header when the request looks like
    # JSON (Flask's request.is_json, keyed off Content-Type) - see
    # CTFd/utils/initialization/__init__.py's `tokens()` before_request hook.
    # Without this header even a valid token is silently ignored on GETs.
    body = None
    req_headers = {"Authorization": f"Token {CTFD_TOKEN}", "Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")

    req = request.Request(f"{CTFD_URL}{path}", data=body, headers=req_headers, method=method)
    try:
        with request.urlopen(req, timeout=30) as res:
            data = res.read()
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} failed: HTTP {exc.code}: {detail}") from exc

    return json.loads(data.decode("utf-8")) if data else {}


def multipart(fields, files):
    boundary = f"----ctf-as-code-{uuid.uuid4().hex}"
    chunks = []

    for name, value in fields.items():
        chunks.extend([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
            str(value).encode(),
            b"\r\n",
        ])

    for name, path in files:
        filename = path.name
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        chunks.extend([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode(),
            f"Content-Type: {content_type}\r\n\r\n".encode(),
            path.read_bytes(),
            b"\r\n",
        ])

    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), {"Content-Type": f"multipart/form-data; boundary={boundary}"}


def existing_challenges():
    # ?view=admin is required to see hidden challenges - the default listing
    # only returns visible ones, which would otherwise cause every hidden
    # challenge to look "new" and get duplicated on each sync.
    response = api("GET", "/api/v1/challenges?view=admin")
    return {item["name"].lower(): item for item in response.get("data", [])}


def load_challenges():
    if CTFD_MANIFEST:
        manifest_path = pathlib.Path(CTFD_MANIFEST)
        with manifest_path.open(encoding="utf-8-sig") as handle:
            manifest = json.load(handle)
        for relative in manifest.get("challenges", []):
            challenge_path = manifest_path.parent / relative
            with challenge_path.open(encoding="utf-8-sig") as handle:
                data = json.load(handle)
            yield challenge_path.parent, data
        return

    for manifest in sorted(CHALLENGES_DIR.glob("*/challenge.json")):
        with manifest.open(encoding="utf-8-sig") as handle:
            data = json.load(handle)
        yield manifest.parent, data


def sync_flags(challenge_id, flags):
    current = api("GET", f"/api/v1/flags?challenge_id={challenge_id}").get("data", [])
    current_values = {flag.get("content") for flag in current}

    for flag in flags:
        content = flag["content"] if isinstance(flag, dict) else flag
        if content in current_values:
            continue
        payload = {
            "challenge_id": challenge_id,
            "type": flag.get("type", "static") if isinstance(flag, dict) else "static",
            "content": content,
            "data": flag.get("data", "") if isinstance(flag, dict) else "",
        }
        api("POST", "/api/v1/flags", payload)


def sync_files(challenge_dir, challenge_id, files):
    for relative in files:
        path = challenge_dir / relative
        if not path.exists():
            raise FileNotFoundError(f"Challenge file does not exist: {path}")
        body, headers = multipart({"type": "challenge", "challenge": challenge_id}, [("file", path)])
        req = request.Request(
            f"{CTFD_URL}/api/v1/files",
            data=body,
            headers={"Authorization": f"Token {CTFD_TOKEN}", **headers},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=60) as res:
                res.read()
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"POST /api/v1/files failed for {path}: HTTP {exc.code}: {detail}") from exc


def main():
    args = parse_args()
    global CTFD_URL, CTFD_TOKEN
    CTFD_URL = args.url.rstrip("/")
    CTFD_TOKEN = args.token

    if not CTFD_TOKEN:
        print("Set CTFD_TOKEN env var or pass --token with an admin API token from CTFd.", file=sys.stderr)
        return 2

    known = existing_challenges()
    for challenge_dir, challenge in load_challenges():
        payload = {
            "name": challenge["name"],
            "category": challenge.get("category", "General"),
            "description": challenge.get("description", ""),
            "value": challenge.get("value", 100),
            "state": challenge.get("state", "visible"),
            "type": challenge.get("type", "standard"),
        }

        if challenge["name"].lower() in known:
            challenge_id = known[challenge["name"].lower()]["id"]
            api("PATCH", f"/api/v1/challenges/{challenge_id}", payload)
            action = "updated"
            upload_files = UPLOAD_FILES_ON_UPDATE
        else:
            created = api("POST", "/api/v1/challenges", payload)
            challenge_id = created["data"]["id"]
            action = "created"
            upload_files = True

        sync_flags(challenge_id, challenge.get("flags", []))
        if upload_files:
            sync_files(challenge_dir, challenge_id, challenge.get("files", []))
        print(f"{action}: {challenge['name']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
