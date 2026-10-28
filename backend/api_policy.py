"""Fail-closed model API gate. Changing this policy requires new user approval."""
from contextlib import closing
import hashlib
import json
import sqlite3
import threading
from pathlib import Path

POLICY_PATH = Path(__file__).resolve().parents[1] / "config" / "model-policy.json"
_lock = threading.Lock()


class APIBlocked(RuntimeError):
    pass


def policy_status():
    try:
        data = json.loads(POLICY_PATH.read_text())
    except (OSError, ValueError):
        data = {}
    return {"enabled": data.get("enabled") is True, "requires_user_approval": True,
            "reason": data.get("reason", "Model APIs are disabled until the user explicitly approves."),
            "approved_provider": data.get("approved_provider"), "max_requests": data.get("max_requests", 0)}


def require_model_permission(provider, api_key=None):
    with _lock:
        try:
            data = json.loads(POLICY_PATH.read_text())
        except (OSError, ValueError):
            raise APIBlocked("Model API disabled: explicit user approval is required") from None
        if api_key and hashlib.sha256(api_key.encode()).hexdigest() in data.get("blocked_key_sha256", []):
            raise APIBlocked("This credential was revoked by the user and cannot be reused")
        if data.get("enabled") is not True or data.get("approved_provider") != provider:
            raise APIBlocked("Model API disabled: explicit user approval is required")
        if not data.get("approval_note") or type(data.get('max_requests')) is not int or data['max_requests'] <= 0:
            raise APIBlocked("No valid model API approval budget remains")
        # A grant is counted atomically across server/CLI processes and restarts.
        grant = hashlib.sha256(json.dumps([provider, data.get('grant_id'), data['approval_note']]).encode()).hexdigest()
        with closing(sqlite3.connect(POLICY_PATH.with_suffix('.usage.sqlite3'), timeout=5)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS usage(grant_id TEXT PRIMARY KEY, used INTEGER)')
            db.execute('BEGIN IMMEDIATE')
            used = db.execute('SELECT used FROM usage WHERE grant_id=?', (grant,)).fetchone()
            if used and used[0] >= data['max_requests']:
                raise APIBlocked('No valid model API approval budget remains')
            db.execute('INSERT INTO usage VALUES(?,1) ON CONFLICT(grant_id) DO UPDATE SET used=used+1', (grant,))
