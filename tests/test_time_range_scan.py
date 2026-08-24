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


@pytest.fixture(scope="module")
def scanner():
    found = _regexes()
    missing = {"TS_RE", "XML_TS_ATTR_RE"} - set(found)
    if missing:
        pytest.fail(
            f"FileUpload.jsx no longer defines {sorted(missing)} as a top-level "
            "regex literal. If the scanner was refactored, update this test — "
            "do not delete it; it is the only guard on that code path."
        )
    try:
        return {name: re.compile(found[name]) for name in ("TS_RE", "XML_TS_ATTR_RE")}
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


@pytest.mark.parametrize("fixture_name", sorted(
    f.name for f in FIXTURE_DIR.glob("*")
    if f.is_file() and not f.name.startswith("tak_stream_")
))
def test_non_tak_fixtures_are_untouched_by_the_strip(fixture_name, scanner):
    """The other five formats write bare timestamps with no preceding `=`, so
    the pattern must match nothing in them. This is the regression guard: a
    widened pattern would start eating real session timestamps."""
    text = (FIXTURE_DIR / fixture_name).read_text(encoding="utf-8", errors="replace")
    assert scanner["XML_TS_ATTR_RE"].sub("", text) == text
