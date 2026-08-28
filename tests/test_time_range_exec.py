"""Executes the real extractTimeRange() from FileUpload.jsx under node.

Companion to test_time_range_scan.py, which re-runs the scanner's regex
*literals* in Python. That guard is strong on the patterns and blind to
everything around them: the union order, ctimeToMs()'s month lookup, UTC vs
local, and the head/tail sampling. Three correct regexes composed wrongly still
produce a wrong slider, and nothing in this repo executed the composition —
the strongest check on the ctime fix lived in a commit message, not in CI.

No new dependency: node is already required to run Vite, and nothing is
imported from the component (it's a JSX module with React imports, so it can't
be imported directly) — tests/js/run_extract_time_range.mjs lifts the pure
functions out by name and runs them.

If node is missing the tests skip rather than fail; if the lift breaks because
someone refactored the component, they fail loudly, the same contract as the
regex-extraction guard next door.
"""

import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent
FILE_UPLOAD = REPO / "ui" / "src" / "components" / "FileUpload.jsx"
DRIVER = Path(__file__).parent / "js" / "run_extract_time_range.mjs"
FIXTURE_DIR = Path(__file__).parent / "fixtures"

HOUR_MS = 3_600_000


@pytest.fixture(scope="module")
def node():
    exe = shutil.which("node")
    if exe:
        return exe
    # Skipping locally is fine — a contributor without node still gets the rest
    # of the suite. Skipping in CI is not: this file exists precisely because the
    # only execution of extractTimeRange used to live outside CI, and a silent
    # skip would quietly restore that. The workflow sets node up for this job;
    # if that step is ever removed, fail here rather than pass with 11 skips.
    if os.environ.get("CI"):
        pytest.fail(
            "node is not on PATH in CI, so the only test that actually executes "
            "extractTimeRange did not run. Restore the 'Set up Node' step in "
            ".github/workflows/ci.yml — do not silence this by deleting the test."
        )
    pytest.skip("node not on PATH — this guard needs the runtime Vite already requires")


def _range(node, *fixture_names, paths=None):
    """Run the real extractTimeRange over one or more inputs.

    The result comes back through a temp file, not stdout: on Windows `node`
    commonly resolves to a WindowsApps .CMD shim that echoes the command line
    ahead of the program's own output, so stdout is not reliably just JSON.
    """
    inputs = [str(p) for p in (paths or [])] + [str(FIXTURE_DIR / n) for n in fixture_names]
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "range.json"
        proc = subprocess.run(
            [node, str(DRIVER), str(out), str(FILE_UPLOAD), *inputs],
            capture_output=True, text=True, timeout=180,
        )
        if not out.exists():
            pytest.fail(
                "the extractTimeRange driver produced no result file "
                f"(rc={proc.returncode}): {proc.stderr or proc.stdout}"
            )
        result = json.loads(out.read_text(encoding="utf-8"))
    if proc.returncode != 0:
        pytest.fail(
            f"extractTimeRange could not be executed: {result}\n"
            "If FileUpload.jsx was refactored, update tests/js/run_extract_time_range.mjs — "
            "do not delete this test; it is the only thing that runs the function."
        )
    return result


def _utc(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).replace(tzinfo=None)


# ── ctime (ht-modem) — the dialect the scan test cannot compose ───────────────

def test_htmodem_range_matches_the_parsers_session_bounds(node):
    """The bug this closes returned null here, so the modal claimed the file had
    no parseable timestamps. The bounds must agree with what the parser reports
    as session_start/session_end (see test_htmodem.py::test_session_bounds),
    which is the real check — a range that parsed but disagreed would be worse
    than none."""
    r = _range(node, "htmodem_sample.log")
    assert r is not None
    assert _utc(r["minMs"]) == datetime(2026, 8, 12, 5, 13, 23)
    assert _utc(r["maxMs"]) == datetime(2026, 8, 12, 5, 49, 44)


def test_htmodem_unset_rtc_capture_reads_its_real_2036_bounds(node):
    """Year-2036 timestamps are a real capture's unset RTC, not corruption —
    they must be read as-is, not rejected or clamped into the present."""
    r = _range(node, "htmodem_sample2.log")
    assert _utc(r["minMs"]) == datetime(2036, 4, 28, 2, 48, 28)
    assert _utc(r["maxMs"]) == datetime(2036, 4, 28, 5, 24, 53)


def test_ctime_is_read_as_utc_not_local(node, tmp_path):
    """Bare wall-clock stamps are read as UTC elsewhere in the scanner, so ctime
    must be too. Read as local time this shifts by the runner's offset, which
    would silently misalign a ctime session against an ISO one in a combined
    range — and would pass on a UTC machine while failing in another timezone."""
    f = tmp_path / "one.log"
    f.write_text("Wed Aug 12 05:13:23 2026 : only line\n", encoding="utf-8")
    r = _range(node, paths=[f])
    assert _utc(r["minMs"]) == datetime(2026, 8, 12, 5, 13, 23)


def test_unknown_month_name_is_ignored_without_losing_the_file(node, tmp_path):
    """A line matching CTIME_RE's shape but carrying a month name that isn't
    real ("Xyz") must be dropped on its own, leaving the surrounding good stamps
    to define the range — not rejected wholesale, and not turning the file into
    a `range-unavailable` upload.

    Note what this does NOT prove, since an earlier version of this docstring
    claimed it: the NaN cannot "poison" min/max even with both guards removed,
    because `NaN < minMs` and `NaN > maxMs` are each false, so `consider()`
    rejects it structurally. Verified by mutation — deleting either
    `Number.isNaN` check or the `month === undefined` check leaves this range
    unchanged. The guards are belt-and-braces, and the real behaviour worth
    pinning is that one malformed line doesn't cost the file its slider.
    """
    f = tmp_path / "bad.log"
    f.write_text(
        "Wed Aug 12 05:13:23 2026 : good\n"
        "Wed Xyz 12 05:13:23 2026 : bad month\n"
        "Wed Aug 12 06:13:23 2026 : good\n",
        encoding="utf-8",
    )
    r = _range(node, paths=[f])
    assert _utc(r["minMs"]) == datetime(2026, 8, 12, 5, 13, 23)
    assert _utc(r["maxMs"]) == datetime(2026, 8, 12, 6, 13, 23)


# ── The other two dialects still work through the real function ───────────────

def test_wall_clock_still_works(node):
    r = _range(node, "diagnostic_sample.txt")
    assert (r["maxMs"] - r["minMs"]) / HOUR_MS == pytest.approx(1.02, abs=0.02)


def test_xml_attribute_strip_applies_before_the_scan(node):
    """The composition the regex test can only approximate: TAK's embedded CoT
    XML carries `stale` attributes a day out, and the strip has to run inside
    extractTimeRange, not just exist. An 18-minute session must not read as 24
    hours."""
    r = _range(node, "tak_stream_sample.json")
    assert (r["maxMs"] - r["minMs"]) / HOUR_MS < 1.0


def test_atak_epoch_ms_still_works(node):
    r = _range(node, "atak_sample.json")
    assert r is not None and r["maxMs"] > r["minMs"]


def test_all_three_dialects_union_into_one_range(node):
    """The union itself. Three files, three dialects, one range spanning all of
    them — this is what no single-pattern test can assert."""
    r = _range(node, "htmodem_sample.log", "diagnostic_sample.txt", "atak_sample.json")
    per_file = [
        _range(node, name)
        for name in ("htmodem_sample.log", "diagnostic_sample.txt", "atak_sample.json")
    ]
    assert r["minMs"] == min(x["minMs"] for x in per_file)
    assert r["maxMs"] == max(x["maxMs"] for x in per_file)


# ── range-unavailable is now reached by exactly one format ────────────────────

def test_fw_log_is_the_only_range_unavailable_format(node):
    """fw_log timestamps are relative ms from boot, so it genuinely has no
    wall-clock and null is the honest answer. Every other format must produce a
    range — ht-modem returning null here is the defect that told users their
    timestamps didn't exist."""
    assert _range(node, "fw_log_sample.log") is None
    for name in (
        "htmodem_sample.log", "htrouter_sample3.log", "diagnostic_sample.txt",
        "atak_sample.json", "tak_stream_sample.json", "tak_ndjson_real_sample.log",
        "rsdk_sample_ios.txt", "relay_manager_sample.txt",
    ):
        assert _range(node, name) is not None, f"{name} lost its time-window slider"


# ── The cross-file offset premise, measured through the real function ─────────

def test_unset_rtc_capture_beside_a_real_dated_log_spans_a_decade(node):
    """Pins the Cross-File Date/Time Offset backlog item's justification, which
    has now been wrong twice. This is the actual measured consequence: a 2036
    unset-RTC capture and a 2026 log share one hour-snapped slider spanning ten
    years. If a future change makes this stop reproducing, that item needs
    re-justifying again rather than quietly keeping a stale rationale."""
    r = _range(node, "htmodem_sample2.log", "diagnostic_sample.txt")
    years = (r["maxMs"] - r["minMs"]) / HOUR_MS / 24 / 365.25
    assert years == pytest.approx(10.0, abs=0.1)


def test_ht_router_alone_also_reproduces_the_decade_span(node):
    """Recorded because the backlog item first blamed the thermal chart, then
    credited the ctime fix. Neither is right: ht-router writes ISO timestamps
    TS_RE always matched, so the defect predates both."""
    r = _range(node, "htrouter_sample3.log", "tak_ndjson_real_sample.log")
    years = (r["maxMs"] - r["minMs"]) / HOUR_MS / 24 / 365.25
    assert years > 9.0
