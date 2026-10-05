"""Guards the client-side time-window scanner in ui/src/components/FileUpload.jsx.

There is no JS test runner in this project and adding one would mean new npm
packages, which the stack rules forbid. But `extractTimeRange` is pure
text-in/range-out, and its three regexes are plain enough to be read out of the
JSX and exercised from here — so the behaviour is guarded in CI at zero
dependency cost rather than resting on a manual check.

This does NOT execute the JSX. It extracts the regex literals by name and
re-runs them in Python, which is why the patterns must stay ECMAScript/Python
compatible. If someone rewrites one using a JS-only construct, the translation
assertion below fails loudly rather than silently testing nothing.

What that leaves uncovered — the union order, `ctimeToMs`, UTC-vs-local, the
head/tail sampling — is covered by `test_time_range_exec.py`, which runs the
real `extractTimeRange` under node. Three correct regexes composed wrongly still
give a wrong slider, so the two files guard different halves of the same code.
"""

import re
from datetime import datetime
from pathlib import Path

import pytest

FILE_UPLOAD = Path(__file__).parent.parent / "ui" / "src" / "components" / "FileUpload.jsx"
FIXTURE_DIR = Path(__file__).parent / "fixtures"

_LITERAL_RE = re.compile(r"^const (\w+) = /(.+)/[gimsuy]*$", re.MULTILINE)


def _regexes() -> dict:
    """Read the scanner's regex literals straight out of the component."""
    source = FILE_UPLOAD.read_text(encoding="utf-8")
    found = {name: body for name, body in _LITERAL_RE.findall(source)}
    return found


_SCANNER_NAMES = ("TS_RE", "XML_TS_ATTR_RE", "CTIME_RE")


@pytest.fixture(scope="module")
def scanner():
    found = _regexes()
    missing = set(_SCANNER_NAMES) - set(found)
    if missing:
        pytest.fail(
            f"FileUpload.jsx no longer defines {sorted(missing)} as a top-level "
            "regex literal. If the scanner was refactored, update this test — "
            "do not delete it; it is the only guard on that code path."
        )
    try:
        return {name: re.compile(found[name]) for name in _SCANNER_NAMES}
    except re.error as e:
        pytest.fail(f"Regex is no longer Python-translatable, so this guard cannot run: {e}")


def _span_hours(text: str, scanner: dict) -> float:
    """Mirror of extractTimeRange's wall-clock path: strip XML attribute
    timestamps, then scan what remains."""
    stripped = scanner["XML_TS_ATTR_RE"].sub("", text)
    stamps = [datetime.fromisoformat(s.replace(" ", "T")) for s in scanner["TS_RE"].findall(stripped)]
    if not stamps:
        return 0.0
    return (max(stamps) - min(stamps)).total_seconds() / 3600


def test_cot_xml_attributes_do_not_inflate_the_range(scanner):
    """The bug: `stale` is an expiry, not an observation — markers set it a full
    day out — so scanning it read the sample's 18-minute session as 24 hours,
    and hour-snapping then left the slider unable to narrow to the data."""
    text = (FIXTURE_DIR / "tak_stream_sample.json").read_text(encoding="utf-8")
    assert _span_hours(text, scanner) < 1.0


def test_tak_range_matches_the_json_session_fields(scanner):
    """The session bounds are the JSON members, not the XML attributes: the
    sample's own "time"/"receivedAt" span 19:24:15 -> 19:42:26."""
    text = (FIXTURE_DIR / "tak_stream_sample.json").read_text(encoding="utf-8")
    assert _span_hours(text, scanner) == pytest.approx(18.183 / 60, abs=0.01)


def test_strip_keeps_every_json_timestamp_member(scanner):
    """91 records x ("time" + "receivedAt") must all survive the strip — the
    pattern has to remove attributes only."""
    text = (FIXTURE_DIR / "tak_stream_sample.json").read_text(encoding="utf-8")
    stripped = scanner["XML_TS_ATTR_RE"].sub("", text)
    assert len(scanner["TS_RE"].findall(stripped)) == 182


def test_ndjson_real_capture_range_matches_session_bounds(scanner):
    """The NDJSON shape (tak-capture-*.log) embeds the same dense CoT XML
    attributes as the array shape, just wrapped per-line in a logger
    envelope — the strip must handle it the same way, at real-file scale
    (804 lines, ~800KB), without pathological slowdown."""
    text = (FIXTURE_DIR / "tak_ndjson_real_sample.log").read_text(encoding="utf-8")
    span = _span_hours(text, scanner)
    # Real session runs 2026-08-25 14:56:51 -> 16:58:02, ~2h1m
    assert 1.9 < span < 2.2


def test_ndjson_strip_keeps_every_json_timestamp_member(scanner):
    """The count assertion the span check can't make. A strip regression that ate
    most timestamps but happened to leave the two extremes would keep the span
    correct and pass the test above — the array-shape sibling guards against that
    with a count, and the NDJSON shape needs the same.

    804 lines x three members: the logger envelope's own "timestamp" plus the
    event's "time" and "receivedAt". The envelope timestamp is deliberately
    included — it is a JSON member, not an XML attribute, and it records when the
    server logged the line, so it belongs in the session range.
    """
    text = (FIXTURE_DIR / "tak_ndjson_real_sample.log").read_text(encoding="utf-8")
    stripped = scanner["XML_TS_ATTR_RE"].sub("", text)
    assert len(scanner["TS_RE"].findall(stripped)) == 804 * 3


# ── ctime timestamps (ht-modem) ───────────────────────────────────────────────
# ht-modem writes "Wed Aug 12 05:13:23 2026" on every line, matching neither
# TS_RE nor EPOCH_MS_RE. Both ht-modem fixtures therefore routed to
# `range-unavailable` and were told "no parseable timestamps were found" — about
# files whose timestamps the parser reads and the Overview timeline prints. Same
# defect the ATAK epoch-ms item closed, for a different timestamp dialect.

_CTIME_MONTHS = {m: i for i, m in enumerate(
    "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), start=1)}


def _ctime_span_hours(text: str, scanner: dict) -> float:
    """Mirror of extractTimeRange's ctime path, read as UTC like the JS does."""
    stamps = [
        datetime(int(year), _CTIME_MONTHS[mon], int(day), int(hh), int(mm), int(ss))
        for mon, day, hh, mm, ss, year in scanner["CTIME_RE"].findall(text)
    ]
    if not stamps:
        return 0.0
    return (max(stamps) - min(stamps)).total_seconds() / 3600


@pytest.mark.parametrize("fixture_name", [
    "htmodem_sample.log", "htmodem_sample2.log", "htmodem_edge_cases.log",
])
def test_ctime_timestamps_are_found_in_every_htmodem_fixture(fixture_name, scanner):
    """The bug was a total miss, not a wrong range — so the assertion that
    matters is simply that the scan finds something."""
    text = (FIXTURE_DIR / fixture_name).read_text(encoding="utf-8", errors="replace")
    assert scanner["CTIME_RE"].search(text) is not None


def test_ctime_range_matches_the_real_session_bounds(scanner):
    """htmodem_sample.log runs 05:13:23 -> 05:49:44 on 2026-08-12 — the same
    bounds the parser reports as session_start/session_end (see
    test_htmodem.py::test_session_bounds), so the slider and the parsed session
    agree instead of the slider showing nothing at all."""
    text = (FIXTURE_DIR / "htmodem_sample.log").read_text(encoding="utf-8")
    assert _ctime_span_hours(text, scanner) == pytest.approx(36.35 / 60, abs=0.01)


def test_ctime_accepts_both_zero_padded_and_space_padded_days(scanner):
    """Real ctime() space-pads a single-digit day ("Apr  8"); the observed
    captures zero-pad ("Jan 05"). Both must match or a log drops out on the
    first nine days of a month."""
    assert scanner["CTIME_RE"].search("Mon Jan 05 08:00:00 2026") is not None
    assert scanner["CTIME_RE"].search("Tue Apr  8 08:00:00 2026") is not None


def test_ctime_requires_the_leading_weekday(scanner):
    """Anchoring on the weekday is what stops a bare date-like fragment
    elsewhere in a log from being read as a session timestamp."""
    assert scanner["CTIME_RE"].search("Aug 12 05:13:23 2026") is None


@pytest.mark.parametrize("fixture_name", sorted(
    f.name for f in FIXTURE_DIR.glob("*")
    if f.is_file() and not f.name.startswith("htmodem_")
))
def test_ctime_pattern_matches_nothing_outside_htmodem(fixture_name, scanner):
    """The regression guard, mirroring the XML-strip sweep below: ht-modem is
    the only format writing ctime, so a widened pattern that starts matching
    another format's text would corrupt that format's range."""
    text = (FIXTURE_DIR / fixture_name).read_text(encoding="utf-8", errors="replace")
    assert scanner["CTIME_RE"].search(text) is None


# ── Single-quoted CoT XML (ATAK plugin build ebb7b8c5) ───────────────────────
# ebb7b8c5's cotDispatchedToAtak records embed CoT XML in a JSON string, like a
# TAK stream does — but single-quoted (stale='…'), so the original double-quote-
# only strip missed every attribute. The real logs carry two kinds of out-of-
# session value there: a `stale` a full day out on markers, shapes and chats,
# and a `time='1970-01-01…'` epoch placeholder on the `<creator>` element of map
# objects drawn on an iOS device (four per real log, as EXTERNAL/INTERNAL pairs;
# never on the token-request). The fixture carries both — the 1970 on a drawn
# u-d-c-c circle's <creator> — so either one surviving the strip stretches an
# ~8-minute session (17:00:00 -> 17:08:09 on 2026-10-02) to a day or to 56
# years.

ATAK_EBB7B8C5 = "diagnostic_ALPHA_90000000000001_2026-10-02 13_26_58.66.log"

# Fixtures whose text legitimately carries XML attribute timestamps: every TAK
# stream (each record embeds its raw CoT document) and the ebb7b8c5 ATAK log.
# Explicit by name, not by format, because other ATAK fixtures — older plugin
# builds — carry no CoT XML and must stay inside the sweep below.
def _embeds_cot_xml(name: str) -> bool:
    return name.startswith("tak_") or name == ATAK_EBB7B8C5


def test_ebb7b8c5_fixture_still_carries_the_attributes_that_caused_the_bug():
    """Fixture premise. If someone tidies the <creator> 1970 placeholder or the
    day-out stale out of the fixture, the tests below would pass against the old
    regex too and stop proving anything. The 1970 is checked on <creator>
    specifically, because that is the only element the real logs carry it on."""
    text = (FIXTURE_DIR / ATAK_EBB7B8C5).read_text(encoding="utf-8")
    assert re.search(r"<creator [^>]*time='1970-01-01T", text) is not None
    assert "stale='2026-10-03T" in text


def test_single_quoted_cot_attribute_timestamps_are_all_stripped(scanner):
    """Every time/start/stale attribute in the ebb7b8c5 CoT XML must go — one
    survivor is enough to wreck the range."""
    text = (FIXTURE_DIR / ATAK_EBB7B8C5).read_text(encoding="utf-8")
    stripped = scanner["XML_TS_ATTR_RE"].sub("", text)
    assert re.search(r"\w+='\d{4}-\d{2}-\d{2}", stripped) is None


def test_ebb7b8c5_wall_clock_survivors_are_only_the_sdk_timestamp_members(scanner):
    """The strip must remove attributes and nothing else: the two SDK Logging
    2.0 records' JSON "timestamp" members are real session times and must
    survive it. (The rest of this log's range comes from epoch-ms keys, which
    the regex mirror here does not cover — test_time_range_exec.py asserts the
    composed bounds.)"""
    text = (FIXTURE_DIR / ATAK_EBB7B8C5).read_text(encoding="utf-8")
    stripped = scanner["XML_TS_ATTR_RE"].sub("", text)
    assert scanner["TS_RE"].findall(stripped) == ["2026-10-02T17:02:08", "2026-10-02T17:02:09"]


def test_ebb7b8c5_wall_clock_span_is_seconds_not_days(scanner):
    """Same mirror as the TAK span tests: with the strip applied the wall-clock
    span is the 1 s between the two SDK records — not the 1970 placeholder and
    not the next-day stale."""
    text = (FIXTURE_DIR / ATAK_EBB7B8C5).read_text(encoding="utf-8")
    assert _span_hours(text, scanner) < 1 / 60


@pytest.mark.parametrize("fixture_name", sorted(
    f.name for f in FIXTURE_DIR.glob("*")
    if f.is_file() and _embeds_cot_xml(f.name)
))
def test_cot_xml_exemption_is_earned(fixture_name, scanner):
    """Keeps the exemption list honest: every fixture excused from the sweep
    below must actually contain something the strip removes. A fixture that
    stops carrying CoT XML goes back under the guard instead of hiding there."""
    text = (FIXTURE_DIR / fixture_name).read_text(encoding="utf-8", errors="replace")
    assert scanner["XML_TS_ATTR_RE"].search(text) is not None


@pytest.mark.parametrize("fixture_name", sorted(
    f.name for f in FIXTURE_DIR.glob("*")
    if f.is_file() and not _embeds_cot_xml(f.name)
))
def test_fixtures_without_cot_xml_are_untouched_by_the_strip(fixture_name, scanner):
    """Formats with bare timestamps — diagnostic, rsdk, relay_manager, fw_log,
    ht-modem, ht-router, and ATAK logs from builds that embed no CoT XML —
    write no preceding `=` and quote, so the pattern must match nothing in
    them. This is the regression guard: a widened pattern would start eating
    real session timestamps."""
    text = (FIXTURE_DIR / fixture_name).read_text(encoding="utf-8", errors="replace")
    assert scanner["XML_TS_ATTR_RE"].sub("", text) == text
