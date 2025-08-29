from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from typing import Dict, Any

from monke.backend.run_manager import RunManager


app = FastAPI(title="Monke Backend", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

manager = RunManager()

# Serve static assets (logos, gifs) if present
_static = Path(__file__).parent / "static"
if _static.exists():
    app.mount("/", StaticFiles(directory=str(_static), html=False), name="static")


def _list_configs() -> Dict[str, Any]:
    cfg_dir = Path(__file__).resolve().parent.parent / "configs"
    items = []
    for p in sorted(cfg_dir.glob("*.yaml")):
        items.append({"name": p.stem, "path": f"configs/{p.name}"})
    return {"tests": items}


@app.get("/api/tests")
async def list_tests():
    return _list_configs()


@app.get("/api/runs")
async def list_runs():
    def to_summary(r):
        return {
            "id": r.id,
            "connector": r.connector,
            "status": r.status,
            "progress": r.progress(),
            "asset_logo": r.asset_logo,
            "asset_gif": r.asset_gif,
            "started_at": r.started_at,
            "ended_at": r.ended_at,
        }
    return {"runs": [to_summary(r) for r in manager.list_runs()]}


@app.post("/api/run")
async def start_run(payload: Dict[str, str]):
    cfg = payload.get("config")
    if not cfg:
        raise HTTPException(status_code=400, detail="Missing 'config'")
    rec = await manager.start_run(cfg)
    return {"run_id": rec.id, "status": rec.status}


@app.post("/api/run/all")
async def start_all_runs():
    runs = await manager.start_all()
    return {"run_ids": [r.id for r in runs]}


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str):
    rec = manager.get_run(run_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Run not found")
    return {
        "id": rec.id,
        "connector": rec.connector,
        "config": rec.config_path,
        "status": rec.status,
        "progress": rec.progress(),
        "started_at": rec.started_at,
        "ended_at": rec.ended_at,
        "asset_logo": rec.asset_logo,
        "asset_gif": rec.asset_gif,
        "steps": [
            {
                "name": s.name,
                "index": s.index,
                "status": s.status,
                "started_at": s.started_at,
                "ended_at": s.ended_at,
                "duration": s.duration,
            }
            for s in rec.steps
        ],
        "logs_tail": rec.logs[-200:],
    }


@app.websocket("/ws/runs/{run_id}")
async def ws_logs(ws: WebSocket, run_id: str):
    rec = manager.get_run(run_id)
    if not rec:
        await ws.close(code=4404)
        return
    await ws.accept()

    # In-process queue only
    q = manager.subscribe(run_id)
    try:
        while True:
            line = await q.get()
            await ws.send_text(line)
    except WebSocketDisconnect:
        return


@app.websocket("/ws/runs")
async def ws_runs(ws: WebSocket):
    await ws.accept()
    # Send initial snapshot so UI updates immediately
    try:
        def to_summary(r):
            return {
                "id": r.id,
                "connector": r.connector,
                "status": r.status,
                "progress": r.progress(),
                "asset_logo": r.asset_logo,
                "asset_gif": r.asset_gif,
                "started_at": r.started_at,
                "ended_at": r.ended_at,
            }
        await ws.send_json({"bootstrap": True, "runs": [to_summary(r) for r in manager.list_runs()]})
    except Exception:
        pass
    # Local run-state events only
    q = manager.subscribe_runs()
    try:
        while True:
            payload = await q.get()
            await ws.send_json(payload)
    except WebSocketDisconnect:
        return
    finally:
        manager.unsubscribe_runs(q)
