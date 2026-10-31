"""SLO computation + rendering. Single source of truth for the math."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any, Iterable

# Add server and root to sys.path if invoked directly
current_dir = Path(__file__).resolve().parent
server_dir = current_dir.parent
root_dir = server_dir.parent
for p in [str(root_dir), str(server_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from server.app.pipeline.telemetry import SCHEMA_VERSION, TRACE_PATH
except ImportError:
    from app.pipeline.telemetry import SCHEMA_VERSION, TRACE_PATH

MIN_SAMPLES_FOR_P95 = 20


def load_records(path: Path = TRACE_PATH) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    out: list[dict] = []
    with open(p, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue  # tolerate one corrupt line
            if rec.get("v") != SCHEMA_VERSION:
                continue
            out.append(rec)
    return out


def percentile(values: list[float], p: float) -> float | None:
    """Nearest-rank percentile. Exact for any N. Documented, not guessed."""
    if not values:
        return None
    vals = sorted(values)
    rank = math.ceil(p / 100.0 * len(vals))
    return vals[max(0, rank - 1)]


def _rate(numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "num": numerator,
        "den": denominator,
        "rate": (numerator / denominator) if denominator else None,
    }


def compute_slos(records: Iterable[dict]) -> dict[str, Any]:
    recs = [r for r in records if r.get("v") == SCHEMA_VERSION]
    n = len(recs)
    ttfa = [r.get("stages", {}).get("first_audio") for r in recs]
    ttfa = [x for x in ttfa if x is not None]

    # Language segmentation
    languages: dict[str, int] = {}
    lang_ttfa: dict[str, list[float]] = {}
    for r in recs:
        lang = r.get("language") or "unknown"
        languages[lang] = languages.get(lang, 0) + 1
        fa = r.get("stages", {}).get("first_audio")
        if fa is not None:
            lang_ttfa.setdefault(lang, []).append(fa)

    by_language = {}
    for lang, count in languages.items():
        vals = lang_ttfa.get(lang, [])
        by_language[lang] = {
            "count": count,
            "ttfa_p50_ms": percentile(vals, 50),
            "ttfa_p95_ms": percentile(vals, 95),
        }

    return {
        "sample_count": n,
        "p95_meaningful": len(ttfa) >= MIN_SAMPLES_FOR_P95,
        "ttfa_p50_ms": percentile(ttfa, 50),
        "ttfa_p95_ms": percentile(ttfa, 95),
        "ttfa_samples": len(ttfa),
        "by_language": by_language,
        # rates, NOT percentiles
        "fallback": _rate(sum(r.get("fallback", {}).get("used", False) for r in recs), n),
        "silent_truncation": _rate(
            sum(r.get("sentences", {}).get("silent_truncation", False) for r in recs), n
        ),
        "crisis": _rate(sum(r.get("safety", {}).get("crisis_triggered", False) for r in recs), n),
        "barge_in": _rate(sum(r.get("barge_in", False) for r in recs), n),
    }


def render_text(s: dict[str, Any]) -> str:
    warn = (
        ""
        if s["p95_meaningful"]
        else f"  ⚠ p95 unreliable (N={s['ttfa_samples']} < {MIN_SAMPLES_FOR_P95})"
    )

    def pct(r: dict[str, Any]) -> str:
        return (
            "n/a"
            if r["rate"] is None
            else f"{r['rate']*100:6.2f}% ({r['num']}/{r['den']})"
        )

    ttfa_p50_str = f"{s['ttfa_p50_ms']} ms" if s['ttfa_p50_ms'] is not None else "n/a"
    ttfa_p95_str = f"{s['ttfa_p95_ms']} ms" if s['ttfa_p95_ms'] is not None else "n/a"

    lang_lines = []
    if "by_language" in s and s["by_language"]:
        for lang, ldata in sorted(s["by_language"].items()):
            p50 = f"{ldata['ttfa_p50_ms']} ms" if ldata['ttfa_p50_ms'] is not None else "n/a"
            lang_lines.append(f"  • {lang:7s}: {ldata['count']} turns (TTFA p50: {p50})")
    lang_section = "\n".join(lang_lines) if lang_lines else "  none"

    return f"""\
turns: {s['sample_count']}
TTFA  p50={ttfa_p50_str}   p95={ttfa_p95_str}{warn}
fallback rate        {pct(s['fallback'])}
silent truncation    {pct(s['silent_truncation'])}   <-- must be 0
crisis trigger rate  {pct(s['crisis'])}
barge-in rate        {pct(s['barge_in'])}
language breakdown:
{lang_section}
"""


if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            if sys.stdout:
                sys.stdout.reconfigure(encoding="utf-8")
        except AttributeError:
            pass
    print(render_text(compute_slos(load_records())))
