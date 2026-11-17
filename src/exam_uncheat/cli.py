"""Command line: exam-uncheat {hub,simulate,demo,replay,verify,report,purge,signatures}."""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path


def _cmd_hub(a):
    import uvicorn

    from .adapters import SerialNDJSONAdapter
    from .hub import create_app

    def factory(sink):
        out = []
        for spec in a.serial or []:
            port, _, baud = spec.partition(":")
            loc = {"room": a.room} if a.room else None
            out.append(SerialNDJSONAdapter(sink, port, int(baud or 115200), location=loc))
        return out

    if a.host not in ("127.0.0.1", "localhost") and not a.allow_lan:
        sys.exit("refusing to bind to a non-local address without --allow-lan (hub has no auth in v0.1)")
    app = create_app(a.data, adapters_factory=factory, retention_days=a.retention_days)
    uvicorn.run(app, host=a.host, port=a.port, log_level="info")


def _cmd_simulate(a):
    from .simulator import build, write_jsonl
    items = build(a.scenario, seed=a.seed)
    p = write_jsonl(items, Path(a.out))
    print(f"wrote {len(items)} lines → {p}")


def _cmd_demo(a):
    from .adapters.replay import load_jsonl
    from .runner import run_offline
    from .session import Session
    from .signatures import SignatureDB
    from .simulator import build

    items = load_jsonl(Path(a.input)) if a.input else build(a.scenario, seed=a.seed)
    first_ts = next((o["ts"] for o in items if o.get("ts")), None)
    s = Session(Path(a.data), {"site": "demo-school", "room": "301", "exam": "시뮬레이션 데모", "period": "1"},
                SignatureDB.load(), started_at=first_ts)
    run_offline(s, items)
    last_ts = next((o["ts"] for o in reversed(items) if o.get("ts")), None)
    if a.decide:  # mark every urgent clue as "needs_more_check" to show the action flow
        for c in s.clues():
            if c["level"] == "urgent":
                s.add_action({"clue_id": c["clue_id"], "decision": "needs_more_check", "actor_role": "proctor-1",
                              "checklist": ["안경 다리 두께 확인", "LED 점등 관찰"], "note": "시뮬레이션 조치 예시"}, ts=c["ts_last"])
    s.close(last_ts)
    for c in s.clues():
        print(f"{c['clue_id']}  {c['level']:<6}  {c['title']}  ({'; '.join(c['reasons'])})")
    print(f"\nsession: {s.dir}\nreport:  {s.dir / 'report.md'}\n         {s.dir / 'report.html'}")


def _cmd_replay(a):
    import urllib.request

    from .adapters.replay import load_jsonl

    items = load_jsonl(Path(a.file))
    hub = a.hub.rstrip("/")

    def post(path, payload, ctype="application/json"):
        req = urllib.request.Request(hub + path, data=payload.encode(), method="POST", headers={"Content-Type": ctype})
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())

    start = time.monotonic()
    t0 = datetime.now().astimezone()
    for obj in items:
        off = obj.get("offset_s")
        if off is not None and a.speed > 0:
            delay = start + off / a.speed - time.monotonic()
            if delay > 0:
                time.sleep(delay)
        if obj.get("schema") == "exam-uncheat.control/v1" and obj.get("action") == "start_exam":
            post("/api/v1/session/exam", "{}")
            print("→ exam phase")
            continue
        if a.restamp and off is not None:
            # shift the scenario timeline to "now", preserving relative timing even when sped up
            obj = dict(obj, ts=(t0 + timedelta(seconds=off)).isoformat(timespec="milliseconds"))
        post("/api/v1/events", json.dumps(obj, ensure_ascii=False), "application/x-ndjson")
    print("replay done")


def _cmd_verify(a):
    from .evidence import verify
    ok, msgs = verify(Path(a.session_dir))
    for m in msgs:
        print(m)
    print("OK" if ok else "FAILED")
    sys.exit(0 if ok else 1)


def _cmd_report(a):
    from .evidence import read_ledger
    d = Path(a.session_dir)
    f = d / ("report.html" if a.format == "html" else "report.md")
    if not f.exists():
        sys.exit(f"{f} not found (session not closed?) — ledger has {len(read_ledger(d))} records")
    print(f.read_text(encoding="utf-8"))


def _cmd_purge(a):
    from .session import purge_expired
    for name in purge_expired(Path(a.data)):
        print("removed", name)


def _cmd_signatures(a):
    from .signatures import SignatureDB
    db = SignatureDB.load()
    for s in db.signatures:
        print(f"{s['id']:<36} {s['category']:<14} {s['confidence']:<6} w={s['weight']:<3} {s['verified_by']}")
    print(f"{len(db.signatures)} signatures from {', '.join(db.files)}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="exam-uncheat", description="Receive-only RF sensor hub for exam integrity "
                                "(proctor decision support — never a verdict).")
    sub = p.add_subparsers(dest="cmd", required=True)

    h = sub.add_parser("hub", help="run the local hub + proctor console")
    h.add_argument("--host", default="127.0.0.1")
    h.add_argument("--port", type=int, default=8765)
    h.add_argument("--data", default="./data")
    h.add_argument("--serial", action="append", help="PORT[:BAUD], repeatable (e.g. /dev/ttyACM0:921600)")
    h.add_argument("--room", default=None)
    h.add_argument("--retention-days", type=int, default=30)
    h.add_argument("--allow-lan", action="store_true")
    h.set_defaults(func=_cmd_hub)

    s = sub.add_parser("simulate", help="write a scenario as JSONL (sensor wire format)")
    s.add_argument("--scenario", default="all")
    s.add_argument("--seed", type=int, default=7)
    s.add_argument("--out", default="scenarios/all.jsonl")
    s.set_defaults(func=_cmd_simulate)

    d = sub.add_parser("demo", help="run a scenario or recorded JSONL through the full pipeline offline")
    d.add_argument("--scenario", default="all")
    d.add_argument("--input", help="recorded JSONL instead of a built-in scenario")
    d.add_argument("--seed", type=int, default=7)
    d.add_argument("--data", default="./data")
    d.add_argument("--decide", action="store_true", help="record example proctor actions")
    d.set_defaults(func=_cmd_demo)

    r = sub.add_parser("replay", help="replay JSONL into a running hub over HTTP")
    r.add_argument("file")
    r.add_argument("--hub", default="http://127.0.0.1:8765")
    r.add_argument("--speed", type=float, default=10.0, help="time acceleration; 0 = as fast as possible")
    r.add_argument("--no-restamp", dest="restamp", action="store_false",
                   help="keep original timestamps (default: shift scenario timeline to start now)")
    r.set_defaults(func=_cmd_replay)

    v = sub.add_parser("verify", help="verify a session's hash chain and SHA256SUMS")
    v.add_argument("session_dir")
    v.set_defaults(func=_cmd_verify)

    rp = sub.add_parser("report", help="print a closed session's report")
    rp.add_argument("session_dir")
    rp.add_argument("--format", choices=["md", "html"], default="md")
    rp.set_defaults(func=_cmd_report)

    pg = sub.add_parser("purge", help="delete sessions past retention")
    pg.add_argument("--data", default="./data")
    pg.set_defaults(func=_cmd_purge)

    sg = sub.add_parser("signatures", help="list loaded signatures")
    sg.set_defaults(func=_cmd_signatures)

    a = p.parse_args(argv)
    a.func(a)


if __name__ == "__main__":
    main()
