"""FastAPI hub: ingestion (HTTP NDJSON / WebSocket / serial adapters), proctor API, console."""
from __future__ import annotations

import json
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse

from . import __version__
from .engine import EngineConfig
from .evidence import verify
from .runner import dispatch
from .session import Session, purge_expired
from .signatures import SignatureDB

WEB = Path(__file__).parent / "web"


class HubState:
    def __init__(self, data_dir: Path, sigdb: SignatureDB, retention_days: int = 30,
                 engine_cfg: EngineConfig | None = None):
        self.data_dir = Path(data_dir)
        self.sigdb = sigdb
        self.retention_days = retention_days
        self.engine_cfg = engine_cfg
        self.session: Session | None = None
        self.last_closed: Session | None = None
        self.lock = threading.Lock()
        self.adapter_errors: list[str] = []

    def require(self) -> Session:
        if self.session is None or self.session.closed:
            raise HTTPException(409, "no active session — POST /api/v1/session/start first")
        return self.session

    def sink(self, obj: dict) -> dict:
        """Entry point used by every adapter and transport."""
        if obj.get("schema") == "exam-uncheat.adapter_error/v1":
            self.adapter_errors = (self.adapter_errors + [obj.get("error", "")])[-20:]
            return {"ok": False}
        s = self.session
        if s is None or s.closed:
            return {"ok": False, "errors": ["no active session"]}
        return dispatch(s, obj)


def create_app(data_dir: Path | str = "./data", sigdb: SignatureDB | None = None, adapters_factory=None,
               retention_days: int = 30, engine_cfg: EngineConfig | None = None) -> FastAPI:
    state = HubState(Path(data_dir), sigdb or SignatureDB.load(), retention_days, engine_cfg)
    purge_expired(state.data_dir)
    adapters = []

    @asynccontextmanager
    async def lifespan(_app):
        if adapters_factory:
            adapters.extend(a.start() for a in adapters_factory(state.sink))
        yield
        for a in adapters:
            a.stop()

    app = FastAPI(title="exam-uncheat hub", version=__version__, lifespan=lifespan)
    app.state.hub = state

    # ---------------- session ----------------
    @app.post("/api/v1/session/start")
    def start(meta: dict = Body(default={})):
        with state.lock:
            if state.session and not state.session.closed:
                raise HTTPException(409, "a session is already active")
            allowed = {k: meta.get(k) for k in ("site", "room", "exam", "period")}
            state.session = Session(state.data_dir, allowed, state.sigdb, state.engine_cfg,
                                    retention_days=state.retention_days)
            return state.session.status()

    @app.post("/api/v1/session/exam")
    def start_exam():
        s = state.require()
        if s.phase == "exam":
            raise HTTPException(409, "already in exam phase")
        return {"baseline": s.start_exam()}

    @app.post("/api/v1/session/close")
    def close():
        s = state.require()
        st = s.close()
        state.last_closed = s
        ok, msgs = verify(s.dir)
        return {"status": st, "verify": {"ok": ok, "messages": msgs}}

    @app.get("/api/v1/status")
    def status():
        s = state.session
        return {"version": __version__, "session": s.status() if s else None,
                "signatures": len(state.sigdb.signatures), "adapter_errors": state.adapter_errors}

    @app.get("/api/v1/clues")
    def clues():
        s = state.session
        return [] if s is None else s.clues()

    # ---------------- ingestion ----------------
    @app.post("/api/v1/events")
    async def post_events(request: Request):
        body = (await request.body()).decode("utf-8")
        state.require()
        body_s = body.strip()
        if body_s.startswith("["):
            objs = json.loads(body_s)
        else:
            objs = [json.loads(l) for l in body_s.splitlines() if l.strip()]
        results = [state.sink(o) for o in objs]
        return {"accepted": sum(1 for r in results if r.get("ok")),
                "rejected": [r for r in results if not r.get("ok")][:10]}

    @app.websocket("/ws/ingest")
    async def ws_ingest(ws: WebSocket):
        await ws.accept()
        try:
            while True:
                text = await ws.receive_text()
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    await ws.send_json({"ok": False, "errors": ["invalid JSON"]})
                    continue
                objs = data if isinstance(data, list) else [data]
                res = [state.sink(o) for o in objs]
                await ws.send_json({"ok": all(r.get("ok") for r in res), "n": len(res),
                                    "errors": [e for r in res for e in r.get("errors", [])][:5]})
        except WebSocketDisconnect:
            return

    # ---------------- proctor ----------------
    @app.post("/api/v1/actions")
    def action(a: dict = Body(...)):
        s = state.require()
        try:
            return s.add_action(a)
        except KeyError:
            raise HTTPException(404, "unknown clue")
        except ValueError as e:
            raise HTTPException(422, str(e))

    @app.post("/api/v1/manual-alert")
    def manual_alert(a: dict = Body(...)):
        s = state.require()
        evt = {"schema": "exam-uncheat.event/v1", "sensor": {"id": "manual", "driver": "proctor-console"},
               "kind": "detector.alert",
               "attrs": {"manual": True, "level": str(a.get("level", "alert"))[:20],
                         "vendor": str(a.get("vendor", ""))[:40], "model": str(a.get("model", ""))[:40],
                         "raw_text": str(a.get("note", ""))[:300]}}
        return s.ingest(evt)

    # ---------------- reports ----------------
    def _report_session() -> Session:
        s = state.session or state.last_closed
        if s is None:
            raise HTTPException(404, "no session")
        return s

    @app.get("/api/v1/report.md", response_class=PlainTextResponse)
    def report_md():
        from .report import render_markdown
        return render_markdown(_report_session().report_data())

    @app.get("/api/v1/report.html", response_class=HTMLResponse)
    def report_html():
        from .report import render_html
        return render_html(_report_session().report_data())

    @app.get("/api/v1/verify")
    def verify_current():
        s = _report_session()
        ok, msgs = verify(s.dir)
        return {"ok": ok, "messages": msgs}

    @app.get("/", response_class=HTMLResponse)
    def console():
        return FileResponse(WEB / "index.html")

    return app
