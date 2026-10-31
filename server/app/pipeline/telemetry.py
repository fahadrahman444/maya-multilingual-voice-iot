"""Per-turn trace sink + JSONL persistence. Zero-blocking by construction.

Contract with the pipeline:
  - The pipeline is the source of truth for `truncated`, `recovered`,
    and `honest_error_delivered`. Telemetry records, it does not infer
    those three. Everything else is derived here.
"""
from __future__ import annotations

import atexit
import json
import math
import os
import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

SCHEMA_VERSION = 1
_SERVER_ROOT = Path(__file__).resolve().parent.parent.parent
TRACE_PATH = Path(os.getenv("MAYA_TRACE_PATH", str(_SERVER_ROOT / "data" / "traces.jsonl")))
QUEUE_MAX = 4096
ROTATE_BYTES = 50 * 1024 * 1024
KEEP_ROTATED = 5


# --------------------------------------------------------------------------- #
# Trace object
# --------------------------------------------------------------------------- #
@dataclass
class TurnTrace:
    """Accumulates one turn. All `stages` values are CUMULATIVE ms from t0."""

    turn_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ts: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    stages: dict[str, float] = field(default_factory=dict)
    provider: Optional[str] = None
    fallback: dict[str, Any] = field(
        default_factory=lambda: {
            "used": False,
            "reason": None,
            "at_sentence": None,
            "recovered": False,
        }
    )
    sentences: dict[str, Any] = field(
        default_factory=lambda: {
            "count": 0,
            "max_chunk_chars": 0,
            "terminated_last": False,
            "truncated": False,  # set by pipeline
        }
    )
    memory: dict[str, Any] = field(
        default_factory=lambda: {"writes": [], "reads": 0, "injected_tokens": 0}
    )
    safety: dict[str, Any] = field(
        default_factory=lambda: {"crisis_triggered": False}
    )
    tokens: dict[str, int] = field(default_factory=lambda: {"in": 0, "out": 0})
    language: str = "unknown"
    barge_in: bool = False
    honest_error_delivered: bool = False  # pipeline sets
    errors: list[str] = field(default_factory=list)

    _t0: float = field(default_factory=time.perf_counter, repr=False)

    # -- marks (cumulative ms from turn start) ------------------------------ #
    def mark(self, name: str) -> None:
        """Record a point-in-time event, e.g. trace.mark('first_audio')."""
        self.stages[name] = round((time.perf_counter() - self._t0) * 1000, 1)

    def record_user_input(self, text: str) -> None:
        """Classify and record turn language without storing raw speech transcript."""
        try:
            from server.app.pipeline.bengali import detect_language
            self.language = detect_language(text)
        except Exception:
            self.language = "unknown"

    # -- sentence bookkeeping ---------------------------------------------- #
    def observe_sentence(self, chunk: str, *, terminated: bool) -> None:
        self.sentences["count"] += 1
        self.sentences["max_chunk_chars"] = max(
            self.sentences["max_chunk_chars"], len(chunk)
        )
        self.sentences["terminated_last"] = terminated
        if "first_sentence" not in self.stages:
            self.mark("first_sentence")

    # -- finalize ----------------------------------------------------------- #
    def finish(self) -> dict[str, Any]:
        self.mark("total")

        # Derived: silent truncation = the stream was cut AND we did not
        # recover on the secondary AND we did not ask the user to repeat.
        truncated = bool(self.sentences.get("truncated"))
        recovered = bool(self.fallback.get("recovered"))
        self.sentences["silent_truncation"] = (
            truncated and not recovered and not self.honest_error_delivered
        )

        return {
            "v": SCHEMA_VERSION,
            "turn_id": self.turn_id,
            "ts": self.ts,
            **{k: v for k, v in self.__dict__.items()
               if k not in ("_t0", "turn_id", "ts")},
        }


# --------------------------------------------------------------------------- #
# Background sink
# --------------------------------------------------------------------------- #
class TraceSink:
    def __init__(self, path: Path = TRACE_PATH) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._q: "queue.Queue[Optional[dict]]" = queue.Queue(maxsize=QUEUE_MAX)
        self._dropped = 0
        self._lock = threading.Lock()
        self._thread = threading.Thread(
            target=self._run, name="trace-writer", daemon=True
        )
        self._thread.start()
        atexit.register(self.close)

    # non-blocking, never raises
    def enqueue(self, record: dict) -> None:
        try:
            self._q.put_nowait(record)
        except queue.Full:
            with self._lock:
                self._dropped += 1

    @property
    def dropped_count(self) -> int:
        with self._lock:
            return self._dropped

    def close(self) -> None:
        try:
            self._q.put_nowait(None)
        except queue.Full:
            pass
        if self._thread.is_alive():
            self._thread.join(timeout=2.0)

    # -- writer thread ----------------------------------------------------- #
    def _run(self) -> None:
        while True:
            record = self._q.get()
            if record is None:
                self._flush_and_exit()
                return
            self._write(record)
            # drain burst without blocking the producer
            while True:
                try:
                    nxt = self._q.get_nowait()
                except queue.Empty:
                    break
                if nxt is None:
                    self._flush_and_exit()
                    return
                self._write(nxt)

    def _write(self, record: dict) -> None:
        try:
            self._rotate_if_needed()
            line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
            # single write() of a full line => no partial-line corruption
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            with self._lock:
                self._dropped += 1

    def _rotate_if_needed(self) -> None:
        if not self._path.exists() or self._path.stat().st_size < ROTATE_BYTES:
            return
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self._path.rename(self._path.with_name(f"traces.{stamp}.jsonl"))
        rotated = sorted(self._path.parent.glob("traces.*.jsonl"))
        for old in rotated[:-KEEP_ROTATED]:
            old.unlink(missing_ok=True)

    def _flush_and_exit(self) -> None:
        return


# module-level singleton
_sink = TraceSink()


def emit_turn(trace: TurnTrace) -> None:
    _sink.enqueue(trace.finish())
