import json
import math
import os
import sys
import time
from pathlib import Path

# Add project root and server dir to sys.path
root_dir = Path(__file__).resolve().parent.parent.parent
server_dir = root_dir / "server"
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
if str(server_dir) not in sys.path:
    sys.path.insert(0, str(server_dir))

import pytest

try:
    from app.pipeline.telemetry import TurnTrace, TraceSink, SCHEMA_VERSION
    from app.dashboard import compute_slos, percentile, load_records
except ImportError:
    from server.app.pipeline.telemetry import TurnTrace, TraceSink, SCHEMA_VERSION
    from server.app.dashboard import compute_slos, percentile, load_records


def test_schema_roundtrip(tmp_path):
    sink = TraceSink(tmp_path / "t.jsonl")
    tr = TurnTrace()
    tr.mark("first_audio")
    sink.enqueue(tr.finish())
    sink.close()
    rec = json.loads((tmp_path / "t.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert rec["v"] == SCHEMA_VERSION
    for k in (
        "turn_id",
        "ts",
        "stages",
        "provider",
        "fallback",
        "sentences",
        "memory",
        "safety",
        "tokens",
        "errors",
    ):
        assert k in rec
    assert "text" not in rec  # no raw speech, by design


def test_percentile_nearest_rank_exact():
    assert percentile(list(range(1, 101)), 50) == 50
    assert percentile(list(range(1, 101)), 95) == 95
    # N=20: ceil(0.95*20)=19 -> index 18 -> value 19
    assert percentile(list(range(1, 21)), 95) == 19
    assert percentile([], 95) is None


def test_silent_truncation_derivation():
    t = TurnTrace()
    t.sentences["truncated"] = True
    assert t.finish()["sentences"]["silent_truncation"] is True

    t2 = TurnTrace()
    t2.sentences["truncated"] = True
    t2.fallback["recovered"] = True
    assert t2.finish()["sentences"]["silent_truncation"] is False

    t3 = TurnTrace()
    t3.sentences["truncated"] = True
    t3.honest_error_delivered = True
    assert t3.finish()["sentences"]["silent_truncation"] is False


def test_enqueue_never_blocks_on_full_queue(tmp_path):
    sink = TraceSink(tmp_path / "t.jsonl")
    sink._q = __import__("queue").Queue(maxsize=1)  # shrink for the test
    sink._q.put_nowait({})                          # fill it
    t0 = time.perf_counter()
    for _ in range(100):
        sink.enqueue(TurnTrace().finish())
    assert time.perf_counter() - t0 < 0.05          # ~instant, dropped
    assert sink.dropped_count == 100
    sink.close()


def test_dashboard_rates_and_percentiles(tmp_path):
    sink = TraceSink(tmp_path / "t.jsonl")
    for i, ttfa in enumerate([100, 200, 300, 400, 500]):
        t = TurnTrace()
        t.stages["first_audio"] = ttfa
        if i == 0:
            t.fallback["used"] = True
        sink.enqueue(t.finish())
    sink.close()
    s = compute_slos(load_records(tmp_path / "t.jsonl"))
    assert s["sample_count"] == 5
    assert s["ttfa_p50_ms"] == 300
    assert s["fallback"]["num"] == 1 and s["fallback"]["den"] == 5
    assert s["p95_meaningful"] is False             # N=5 < 20


def test_corrupt_line_is_skipped(tmp_path):
    p = tmp_path / "t.jsonl"
    p.write_text('{"v":1}\nnot json\n{"v":1}\n', encoding="utf-8")
    assert len(load_records(p)) == 2


def test_schema_version_mismatch_ignored(tmp_path):
    p = tmp_path / "t.jsonl"
    p.write_text(
        '{"v":999,"turn_id":"x"}\n{"v":1,"stages":{},"fallback":'
        '{"used":false},"sentences":{},"safety":{"crisis_triggered":false},'
        '"barge_in":false}\n',
        encoding="utf-8",
    )
    assert len(load_records(p)) == 1


def test_rotation(tmp_path, monkeypatch):
    import app.pipeline.telemetry as tm
    monkeypatch.setattr(tm, "ROTATE_BYTES", 200)
    sink = TraceSink(tmp_path / "t.jsonl")
    for _ in range(10):
        sink.enqueue(TurnTrace().finish())
    sink.close()
    assert (tmp_path / "t.jsonl").exists()
    assert list(tmp_path.glob("traces.*.jsonl"))


def test_render_text_warns_below_threshold():
    from app.dashboard import render_text
    s = compute_slos([
        {
            "v": 1,
            "stages": {"first_audio": 100},
            "fallback": {"used": False},
            "sentences": {"silent_truncation": False},
            "safety": {"crisis_triggered": False},
            "barge_in": False,
        }
    ])
    assert "unreliable" in render_text(s)
