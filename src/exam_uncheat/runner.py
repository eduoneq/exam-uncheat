"""Route mixed streams (hello / control / event lines) into a Session."""
from __future__ import annotations

from .session import Session


def dispatch(session: Session, obj: dict) -> dict:
    schema = obj.get("schema", "exam-uncheat.event/v1")
    if schema == "exam-uncheat.hello/v1":
        session.register_sensor(obj)
        return {"ok": True, "hello": obj.get("sensor_id")}
    if schema == "exam-uncheat.control/v1":
        if obj.get("action") == "start_exam":
            if session.phase != "exam":
                return {"ok": True, "baseline": session.start_exam(obj.get("ts"))}
            return {"ok": True}
        return {"ok": False, "errors": [f"unknown control action {obj.get('action')}"]}
    if schema == "exam-uncheat.adapter_error/v1":
        return {"ok": False, "errors": [obj.get("error", "adapter error")]}
    return session.ingest(obj)


def run_offline(session: Session, items: list[dict]) -> Session:
    """Feed a whole stream synchronously (simulator / recorded file)."""
    base_ts = None
    for obj in items:
        if obj.get("schema") == "exam-uncheat.control/v1" and "ts" not in obj and base_ts is not None:
            # stamp control with the timeline of surrounding events
            obj = dict(obj, ts=base_ts)
        res = dispatch(session, obj)
        if obj.get("ts"):
            base_ts = obj["ts"]
        del res
    return session
