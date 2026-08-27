"""Syncs data/history.jsonl with a private repo instead of this (public) one.

Why: history.jsonl accumulates the query city and a timestamp per run — fine
in a private repo, a quiet location/usage-pattern leak in a public one. This
repo stays code-only; the growing correlation dataset lives in the private
puginanatoly-stack/ai_agent repo, path weather-history/history.jsonl.

Usage (both need HISTORY_PUSH_TOKEN, a PAT with Contents:RW on that repo):
    python history_sync.py pull   # before build.py — restores prior history
    python history_sync.py push   # after build.py — commits the updated file
"""

from __future__ import annotations

import base64
import os
import sys
from pathlib import Path

import requests

REPO = "puginanatoly-stack/ai_agent"
REMOTE_PATH = "weather-history/history.jsonl"
LOCAL_PATH = Path(__file__).parent / "data" / "history.jsonl"
API_URL = f"https://api.github.com/repos/{REPO}/contents/{REMOTE_PATH}"


def _headers(token: str) -> dict:
    return {
        "User-Agent": "weather-monitor-history-sync",
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }


def pull(token: str) -> None:
    LOCAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(API_URL, headers=_headers(token), timeout=15)
    if resp.status_code == 404:
        print("No prior history in the private repo yet — starting fresh.")
        LOCAL_PATH.write_text("", encoding="utf-8")
        return
    resp.raise_for_status()
    content_b64 = resp.json()["content"]
    LOCAL_PATH.write_bytes(base64.b64decode(content_b64))
    print(f"Pulled history -> {LOCAL_PATH} ({LOCAL_PATH.stat().st_size} bytes)")


def push(token: str) -> None:
    if not LOCAL_PATH.exists():
        print("No local history.jsonl to push — skipping.")
        return
    content_b64 = base64.b64encode(LOCAL_PATH.read_bytes()).decode("ascii")

    # Need the current file's sha to update it (Contents API requires this
    # for an existing file; omit for a brand-new file).
    sha = None
    existing = requests.get(API_URL, headers=_headers(token), timeout=15)
    if existing.status_code == 200:
        sha = existing.json()["sha"]

    body = {"message": "Update weather history", "content": content_b64, "branch": "main"}
    if sha:
        body["sha"] = sha

    resp = requests.put(API_URL, headers=_headers(token), json=body, timeout=15)
    resp.raise_for_status()
    print(f"Pushed history -> {REPO}/{REMOTE_PATH}")


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    token = os.environ.get("HISTORY_PUSH_TOKEN")
    if not token:
        print("HISTORY_PUSH_TOKEN not set — skipping history sync.", file=sys.stderr)
        sys.exit(0 if cmd == "pull" else 1)  # pull-without-token = fresh start, not fatal

    if cmd == "pull":
        pull(token)
    elif cmd == "push":
        push(token)
    else:
        print("Usage: python history_sync.py {pull|push}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
