import asyncio
import json
import contextvars
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

from monke.core.test_config import TestConfig
from monke.core import events
from monke.utils.logging import get_logger


RUNS_DIR = Path(__file__).resolve().parent.parent / ".runs"
RUNS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class StepRecord:
    name: str
    index: int
    status: str = "pending"  # pending|running|passed|failed
    started_at: Optional[float] = None
    ended_at: Optional[float] = None
    duration: Optional[float] = None


@dataclass
class RunRecord:
    id: str
    config_path: str
    connector: str
    steps: List[StepRecord]
    status: str = "queued"  # queued|running|passed|failed
    started_at: Optional[float] = None
    ended_at: Optional[float] = None
    logs: List[str] = field(default_factory=list)
    subscribers: Set[asyncio.Queue] = field(default_factory=set)
    asset_logo: Optional[str] = None
    asset_gif: Optional[str] = None

    def progress(self) -> float:
        if not self.steps:
            return 0.0
        done = sum(1 for s in self.steps if s.status in ("passed", "failed"))
        return done / len(self.steps)

    def _persist_dir(self) -> Path:
        p = RUNS_DIR / self.id
        p.mkdir(parents=True, exist_ok=True)
        return p

    def persist_state(self) -> None:
        payload = {
            "id": self.id,
            "config_path": self.config_path,
            "connector": self.connector,
            "status": self.status,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "progress": self.progress(),
            "asset_logo": self.asset_logo,
            "asset_gif": self.asset_gif,
            "steps": [
                {
                    "name": s.name,
                    "index": s.index,
                    "status": s.status,
                    "started_at": s.started_at,
                    "ended_at": s.ended_at,
                    "duration": s.duration,
                }
                for s in self.steps
            ],
        }
        (self._persist_dir() / "run.json").write_text(json.dumps(payload, indent=2))
        # Persisted locally only; no external pub/sub

    def persist_log(self, message: str) -> None:
        with (self._persist_dir() / "logs.ndjson").open("a") as f:
            f.write(json.dumps({"t": time.time(), "line": message}) + "\n")

    def broadcast(self, message: str) -> None:
        self.logs.append(message)
        self.persist_log(message)
        # In-process fan-out
        dead = []
        for q in list(self.subscribers):
            try:
                q.put_nowait(message)
            except Exception:
                dead.append(q)
        for q in dead:
            self.subscribers.discard(q)
        # No external pub/sub; in-process fan-out only


class _RunLogHandler(logging.Handler):
    def __init__(self, run: RunRecord):
        super().__init__(level=logging.INFO)
        self.run = run

    def emit(self, record: logging.LogRecord) -> None:
        try:
            # Clean up the message for human readability
            msg = record.getMessage()

            # Skip verbose metadata lines
            skip_patterns = [
                "Creating file with payload:",
                "Token:",
                "URL:",
                "Check response status:",
                "Registered bongo:",
                "Repository:",
                "Creating file:",
                "Checking if file exists",
                "File doesn't exist",
                "   "  # Skip lines that start with multiple spaces (indented metadata)
            ]
            if any(pattern in msg for pattern in skip_patterns):
                return

            # Also skip lines that are just indented metadata
            if msg.strip().startswith(("Repository:", "Token:", "URL:", "Check response")):
                return

            # Replace log levels with emojis
            level_emoji = {
                "INFO": "",  # Remove INFO, emojis in messages are enough
                "WARNING": "⚠️",
                "ERROR": "❌",
                "DEBUG": "🔍",
                "CRITICAL": "🚨"
            }

            # Get the clean message without timestamp and logger name
            clean_msg = msg.strip()

            # Add level emoji if not INFO (INFO messages already have contextual emojis)
            if record.levelname != "INFO" and record.levelname in level_emoji:
                clean_msg = f"{level_emoji[record.levelname]} {clean_msg}"

        except Exception:
            clean_msg = record.getMessage()

        self.run.broadcast(clean_msg)
        self.run.persist_state()


class _RunContextFilter(logging.Filter):
    def __init__(self, run_id: str) -> None:
        super().__init__()
        self.run_id = run_id

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        current = CURRENT_RUN_ID.get()
        return current == self.run_id


# Context variable to tag logs with the current run id
CURRENT_RUN_ID: contextvars.ContextVar[str | None] = contextvars.ContextVar("dm_current_run_id", default=None)


class RunManager:
    def __init__(self) -> None:
        self._runs: Dict[str, RunRecord] = {}
        self._logger = get_logger("monke.run_manager")
        self._run_state_subscribers: Set[asyncio.Queue] = set()

    def list_runs(self) -> List[RunRecord]:
        return list(self._runs.values())

    def get_run(self, run_id: str) -> Optional[RunRecord]:
        return self._runs.get(run_id)

    def subscribe(self, run_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        run = self._runs[run_id]
        run.subscribers.add(q)
        for line in run.logs[-200:]:
            try:
                q.put_nowait(line)
            except Exception:
                break
        return q

    def subscribe_runs(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._run_state_subscribers.add(q)
        return q

    def unsubscribe_runs(self, q: asyncio.Queue) -> None:
        if q in self._run_state_subscribers:
            self._run_state_subscribers.remove(q)

    def _broadcast_run_state_local(self, run: RunRecord) -> None:
        payload = {
            "id": run.id,
            "connector": run.connector,
            "status": run.status,
            "progress": run.progress(),
            "asset_logo": run.asset_logo,
            "asset_gif": run.asset_gif,
            "started_at": run.started_at,
            "ended_at": run.ended_at,
        }
        dead: List[asyncio.Queue] = []
        for q in list(self._run_state_subscribers):
            try:
                q.put_nowait(payload)
            except Exception:
                dead.append(q)
        for q in dead:
            self._run_state_subscribers.discard(q)

    def _pick_logo(self, connector: str) -> str:
        # Frontend serves from /public/icons
        return f"icons/{connector.lower()}.svg"

    # Frontend chooses GIFs; backend doesn't need to know

    async def start_run(self, config_rel_path: str) -> RunRecord:
        base = Path(__file__).resolve().parent.parent
        cfg_path = (base / config_rel_path).resolve()
        cfg = TestConfig.from_file(str(cfg_path))
        steps = [StepRecord(name=s.lower(), index=i) for i, s in enumerate(cfg.test_flow.steps)]
        run_id = str(uuid.uuid4())
        record = RunRecord(
            id=run_id,
            config_path=str(cfg_path),
            connector=cfg.connector.type,
            steps=steps,
            status="queued",
            asset_logo=self._pick_logo(cfg.connector.type),
            asset_gif=None,
        )
        self._runs[run_id] = record
        record.persist_state()
        self._broadcast_run_state_local(record)
        # Start tasks: consume events and run the test
        asyncio.create_task(self._consume_events(record))
        asyncio.create_task(self._run(record))
        return record

    async def start_all(self) -> List[RunRecord]:
        base = Path(__file__).resolve().parent.parent
        cfg_dir = base / "configs"
        runs: List[RunRecord] = []
        for p in sorted(cfg_dir.glob("*.yaml")):
            runs.append(await self.start_run(f"configs/{p.name}"))
        return runs

    async def _consume_events(self, record: RunRecord) -> None:
        q = events.subscribe()
        try:
            while True:
                ev = await q.get()
                if not isinstance(ev, dict):
                    continue
                if ev.get("run_id") != record.id:
                    continue
                et = ev.get("type")
                if et == "flow_started":
                    record.status = "running"
                    record.started_at = ev.get("ts", time.time())
                elif et == "step_started":
                    step = ev.get("step", "").lower()
                    for s in record.steps:
                        if s.name == step and s.status == "pending":
                            s.status = "running"
                            s.started_at = ev.get("ts", time.time())
                            break
                elif et == "step_completed":
                    step = ev.get("step", "").lower()
                    for s in record.steps:
                        if s.name == step and s.status in ("running", "pending"):
                            s.status = "passed"
                            s.ended_at = ev.get("ts", time.time())
                            dur = ev.get("duration")
                            s.duration = float(dur) if dur is not None else (
                                (s.ended_at - s.started_at) if s.started_at else None
                            )
                            break
                elif et == "step_failed":
                    step = ev.get("step", "").lower()
                    for s in record.steps:
                        if s.name == step and s.status in ("running", "pending"):
                            s.status = "failed"
                            s.ended_at = ev.get("ts", time.time())
                            dur = ev.get("duration")
                            s.duration = float(dur) if dur is not None else (
                                (s.ended_at - s.started_at) if s.started_at else None
                            )
                            break
                elif et in ("flow_completed", "flow_failed"):
                    record.ended_at = ev.get("ts", time.time())
                    # If any step failed -> failed; else passed
                    record.status = "failed" if any(s.status == "failed" for s in record.steps) else "passed"
                # persist
                record.persist_state()
                self._broadcast_run_state_local(record)
        finally:
            events.unsubscribe(q)

    async def _run(self, record: RunRecord) -> None:
        # Attach logging handler for log streaming
        handler = _RunLogHandler(record)
        # No formatter - we handle formatting in the handler for clean UI logs
        root_logger = logging.getLogger()
        previous_level = root_logger.level
        root_logger.setLevel(logging.INFO)
        # Only forward records emitted within this run's context
        handler.addFilter(_RunContextFilter(record.id))
        root_logger.addHandler(handler)
        # Ensure uvicorn access logs and httpx/fastapi don't dominate by lowering their level
        noisy_loggers = [
            "uvicorn",
            "uvicorn.access",
            "uvicorn.error",
            "uvicorn.asgi",
            "httpx",
            "starlette",
            "fastapi",
        ]
        previous_levels: Dict[str, int] = {}
        for name in noisy_loggers:
            lg = logging.getLogger(name)
            previous_levels[name] = lg.level
            lg.setLevel(logging.WARNING)
        try:
            from monke.test import run_test
            # Tag this task's logs with run id so handler filter isolates records
            token = CURRENT_RUN_ID.set(record.id)
            try:
                ok = await run_test(record.config_path, run_id=record.id)
            finally:
                CURRENT_RUN_ID.reset(token)
            # final status is computed by event consumer; ensure not missing
            if not any(s.status == "failed" for s in record.steps):
                record.status = "passed" if ok else "failed"
        except Exception as e:
            self._logger.error(f"Run {record.id} failed: {e}")
            record.broadcast(f"ERROR: {e}")
            record.status = "failed"
        finally:
            root_logger.removeHandler(handler)
            for name, lvl in previous_levels.items():
                logging.getLogger(name).setLevel(lvl)
            root_logger.setLevel(previous_level)
            if record.ended_at is None:
                record.ended_at = time.time()
            record.broadcast(f"Run finished with status: {record.status}")
            record.persist_state()
