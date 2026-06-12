"""tests/test_parse_route.py

Exercises the POST /parse route handler (api/routes/parse.py:parse_logs) the way
a real upload hits it — detection, the temp-file write, parser dispatch, and
serialization — by calling the endpoint coroutine directly with constructed
UploadFile objects. The per-parser unit tests call parse_*_log(path) directly and
so bypass this path; this file covers the gap.

Regression guard for the CRLF temp-file bug: the route wrote the decoded upload
text in text mode, which on Windows double-translated CRLF ("\r\n" -> "\r\r\n").
Path.read_text()'s universal-newline decode then read that back as "\n\n", which
prematurely split the blank-line-delimited diagnostic format so every Received
Message block was dropped (0 parsed) for any CRLF upload. The fix writes the temp
file with newline="" so the upload bytes survive verbatim.
"""

import asyncio
import io
from pathlib import Path

from fastapi import UploadFile

from api.routes.parse import parse_logs

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _post(filename: str, content: bytes) -> dict:
    """Call the real /parse handler with a single in-memory upload."""
    upload = UploadFile(filename=filename, file=io.BytesIO(content))
    return asyncio.run(parse_logs(files=[upload]))


def _diagnostic_bytes(line_ending: str) -> bytes:
    # read_text() normalizes to "\n" regardless of how git checked the fixture
    # out (autocrlf), so re-encoding lets the test control the line ending it
    # uploads rather than depending on the working-tree state.
    text = (FIXTURE_DIR / "diagnostic_sample.txt").read_text(encoding="utf-8")
    return text.replace("\n", line_ending).encode("utf-8")


def test_crlf_diagnostic_upload_parses_blocks():
    """A CRLF-uploaded diagnostic log must parse its Received Message blocks
    through the route — the temp-file write must not corrupt line endings."""
    result = _post("diagnostic_sample.txt", _diagnostic_bytes("\r\n"))["results"][0]
    assert result["log_format"] == "diagnostic"
    assert len(result["received_messages"]) == 2


def test_crlf_and_lf_uploads_agree():
    """Line endings must not change the parse result through the route."""
    crlf = _post("diagnostic_sample.txt", _diagnostic_bytes("\r\n"))["results"][0]
    lf = _post("diagnostic_sample.txt", _diagnostic_bytes("\n"))["results"][0]
    assert len(crlf["received_messages"]) == len(lf["received_messages"]) == 2
