"""Baserow helpers for smart bin deposit event logging."""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime
from typing import Any
from urllib import error, request

from smart_bin import config


def local_timestamp() -> str:
    """Return local time in a Baserow-friendly datetime format."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def baserow_enabled() -> bool:
    """Return True when the required Baserow settings are configured."""
    return bool(config.BASEROW_TOKEN and config.BASEROW_TABLE_ID)


def row_endpoint() -> str:
    base_url = config.BASEROW_API_URL.rstrip("/")
    table_id = str(config.BASEROW_TABLE_ID).strip()
    return f"{base_url}/api/database/rows/table/{table_id}/?user_field_names=true"


def request_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    timeout: float = config.BASEROW_REQUEST_TIMEOUT_SEC,
) -> dict[str, Any]:
    data = None
    headers = {
        "Authorization": f"Token {config.BASEROW_TOKEN}",
        "Accept": "application/json",
    }

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    last_error: Exception | None = None

    for attempt in range(1, config.BASEROW_MAX_RETRIES + 1):
        req = request.Request(url=url, data=data, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=timeout) as response:
                body = response.read().decode("utf-8").strip()
                return json.loads(body) if body else {}
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace").strip()
            last_error = RuntimeError(f"HTTP {exc.code}: {body or exc.reason}")
            if 500 <= exc.code < 600 and attempt < config.BASEROW_MAX_RETRIES:
                time.sleep(config.BASEROW_RETRY_BACKOFF_SEC * attempt)
                continue
            raise last_error from exc
        except error.URLError as exc:
            last_error = RuntimeError(f"Network error: {exc.reason}")
            if attempt < config.BASEROW_MAX_RETRIES:
                time.sleep(config.BASEROW_RETRY_BACKOFF_SEC * attempt)
                continue
            raise last_error from exc
        except TimeoutError as exc:
            last_error = RuntimeError("Request timed out")
            if attempt < config.BASEROW_MAX_RETRIES:
                time.sleep(config.BASEROW_RETRY_BACKOFF_SEC * attempt)
                continue
            raise last_error from exc

    if last_error is not None:
        raise last_error

    raise RuntimeError("Unknown Baserow request failure")


def init_db() -> None:
    """Validate configuration and announce whether Baserow logging is available."""
    if not config.BASEROW_TOKEN:
        print("[WARN] Baserow logging disabled: BASEROW_TOKEN is not set.")
        return

    if not config.BASEROW_TABLE_ID:
        print("[WARN] Baserow logging disabled: BASEROW_TABLE_ID is not set.")
        return

    try:
        request_json("GET", row_endpoint())
        print("[INFO] Baserow logging enabled.")
    except Exception as exc:
        print(f"[WARN] Baserow connectivity check failed: {exc}")


def start_session(distance_cm: float | None = None, notes: str | None = None) -> str:
    """Create and return a local session identifier."""
    del distance_cm, notes
    return uuid.uuid4().hex


def end_session(
    session_id: str | None,
    distance_cm: float | None = None,
    notes: str | None = None,
) -> None:
    """End a local session."""
    del session_id, distance_cm, notes


def log_deposit_event(
    *,
    session_id: str | None,
    weight_before: float,
    weight_after: float,
    weight_delta: float,
    ultrasonic_distance_cm: float | None,
    person_present: bool,
    event_type: str = "trash_detected",
    notes: str | None = None,
    debug_info: dict[str, Any] | None = None,
) -> int:
    """Post one confirmed deposit event to Baserow."""
    del notes, debug_info

    if not baserow_enabled():
        return -1

    payload = {
        "event": "Deposit",
        "timestamp": local_timestamp(),
        "session_id": session_id or "",
        "weight_before": float(weight_before),
        "weight_after": float(weight_after),
        "weight_delta": float(weight_delta),
        "distance_cm": None if ultrasonic_distance_cm is None else float(ultrasonic_distance_cm),
        "person_present": bool(person_present),
        "event_type": event_type,
    }

    try:
        response_data = request_json("POST", row_endpoint(), payload=payload)
        return int(response_data.get("id", -1))
    except Exception as exc:
        print(f"[WARN] Failed to send deposit event to Baserow: {exc}")
        return -1


def send_test_row() -> int:
    """Send one fake deposit row for integration testing."""
    session_id = start_session(distance_cm=12.5, notes="manual_test")
    row_id = log_deposit_event(
        session_id=session_id,
        weight_before=1000.0,
        weight_after=1325.0,
        weight_delta=325.0,
        ultrasonic_distance_cm=9.8,
        person_present=True,
        event_type="trash_detected",
        notes="manual_test",
        debug_info={"source": "python -m smart_bin.db_logger"},
    )
    print(f"[INFO] Test row result id={row_id}")
    return row_id


def main() -> None:
    init_db()
    send_test_row()


if __name__ == "__main__":
    main()
