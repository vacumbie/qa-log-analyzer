# goTenna Log Analyzer

A local log parsing and visualization tool for goTenna mesh network diagnostic data.

Supports eight log formats:

**goTenna radios and apps**
- **Diagnostic** — goTenna Pro+ app export (`diagnostic_*.txt`, named device files)
- **RSDK** — Android/iOS SDK logs from field sessions (Pro+ app)
- **ATAK** — Android ATAK plug-in logs (regular and enhanced, including plug-in v3.0)
- **Relay Manager** — Android logcat dumps from the goTenna Relay Manager app (network polling and scheduled health check sub-types)
- **FW Log** — relay radio firmware UART/USB serial debug console

**⚡ Next-Gen Radio (SDR/FPGA platform)**
- **HT-Modem** — `ht-modem` process log (SDR/RF layer)
- **HT-Router** — `ht-router` process log (network/link layer)

**Server-side**
- **TAK Server** — Cursor-on-Target (CoT) event stream export (JSON array or NDJSON)

The format is detected automatically from the file name and content — see [Format Detection](#format-detection).

## Stack

| Layer | Technology |
|---|---|
| Parser | Python 3.10+ |
| API | FastAPI + Uvicorn |
| UI | React 18 + Vite + Chart.js 4.4.1 |
| Maps | Leaflet 1.9.4 (loaded from CDN, not npm) |
| Tests | Pytest |
| Fonts | Barlow Condensed · Rajdhani · Share Tech Mono |

## Quick Start

### 1. Clone the repo
```bash
git clone https://github.com/vacumbie/qa-log-analyzer.git
cd qa-log-analyzer
```

### 2. Install Python dependencies
```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Start the API
```bash
cd api
uvicorn main:app --reload --port 8000
```

### 4. Install and start the UI (new terminal)
```bash
cd ui
npm install
npm run dev
```

Open **http://localhost:5173** in your browser.

### 5. Activate the virtual environment (Windows PowerShell)
The project requires a virtual environment for its Python dependencies (FastAPI, Pytest, Uvicorn). Run these two commands at the start of every PowerShell session:
```powershell
cd C:\Users\Valerie.Cumbie\Documents\qa-log-analyzer
.\venv\Scripts\activate
```

---

## Claude Code Agents

The project includes ten Claude Code sub-agents in `.claude/agents/`. They
are invoked from a Claude Code terminal session (`claude` from the repo root)
and share the context defined in `CLAUDE.md`. `CLAUDE.md` is the source of
truth for the gate sequence below.

### Quality gate — run before merging

Every feature or fix passes these six agents in order. Each one assumes the
previous one has already passed.

| Step | Agent | Role |
|------|-------|------|
| 1 | `vera` | Unit test specialist — coverage depth, fixture realism, sentinel values, `DATA LIMITATION` entries in `parse_errors` |
| 2 | `task-completion-validator` | End-to-end completion checklist — ParseResult chain, pytest clean, docs updated |
| 3 | `jenny` | Spec compliance — implementation vs `docs/` and `CLAUDE.md` |
| 4 | `karen` | Live browser verification — real log, real data, no dashes or NoData |
| 5 | `peer-reviewer` | Pre-merge code review — cited findings only |
| 6 | `claude-md-compliance-checker` | `CLAUDE.md` rules — ParseResult chain, detection order, temperature conversion, commit format |

```
vera → task-completion-validator → jenny → karen → peer-reviewer → claude-md-compliance-checker
```

**Optional:** `code-quality-pragmatist` — simplicity and readability check. Run
it when a solution feels over-engineered, not as a routine checkbox.

### Workflow agents — day-to-day development

| Agent | Role | Invoke when |
|-------|------|-------------|
| `log-analyst` | Reads a raw log file and identifies fields, record types, and unknowns | A new log file arrives before any parser is written |
| `parser-agent` | Adds or updates parsers, walks the full `models.py` → parser → `_result_to_dict()` → UI chain | Adding a log format or ParseResult field |
| `docs-agent` | Keeps `parsing-requirements.md`, `log-field-definitions.md`, `ui-requirements.md`, and `CLAUDE.md` in sync | After any code change |

### Example usage

```bash
# From the repo root with Claude Code running
run peer-reviewer on the current branch
use log-analyst to analyze networkPolling.txt
use parser-agent to add firmware version to the relay_manager parser
run vera to audit coverage for the htrouter parser
run docs-agent and verify the four docs reflect the current codebase
run task-completion-validator on the relay_manager parser
```


## Project Structure

```
qa-log-analyzer/
├── parser/                   # Log parsing engine (Python)
│   ├── diagnostic.py         # goTenna Pro+ diagnostic export (detection fallback)
│   ├── rsdk.py               # RSDK iOS/Android SDK log
│   ├── atak.py               # Android ATAK plug-in log (regular, enhanced, v3.0)
│   ├── relay_manager.py      # Relay Manager Android logcat
│   ├── fw_log.py             # Relay radio firmware UART/USB debug log
│   ├── htmodem.py            # Next-Gen Radio ht-modem log (SDR/RF layer)
│   ├── htrouter.py           # Next-Gen Radio ht-router log (network/link layer)
│   ├── tak.py                # TAK server CoT event stream (JSON array / NDJSON)
│   └── models.py             # Shared dataclasses (ParseResult, SystemSample, etc.)
├── api/                      # FastAPI REST bridge
│   ├── main.py               # App entry point — uvicorn main:app
│   └── routes/
│       ├── parse.py          # POST /parse  — upload, detect format, parse
│       └── export.py         # GET  /export — download parsed data as CSV/JSON
├── ui/                       # React + Vite frontend
│   └── src/
│       ├── components/
│       │   ├── ChartPanel.jsx        # All chart definitions and rendering
│       │   ├── DataPointSelector.jsx # Data point toggle UI
│       │   ├── DeviceSummary.jsx     # Per-device summary card
│       │   ├── FileUpload.jsx        # Upload modal with time window slider
│       │   └── TakTab.jsx            # TAK Server tab — position map + latency chart
│       ├── hooks/
│       │   ├── useLeaflet.js         # Loads Leaflet from CDN (shared by both maps)
│       │   └── useLogData.js         # Fetch + cache parsed results from API
│       └── App.jsx                   # Main app — tabs (incl. ⚡ Next-Gen Radio group), KPI row, filtering
├── tests/                    # Pytest test suite
│   ├── test_<format>.py      # One per parser: atak, diagnostic, fw_log, htmodem,
│   │                         #   htrouter, relay_manager, rsdk, tak
│   ├── test_detect_format.py # Format detection order
│   ├── test_parse_route.py   # API-path regression tests
│   ├── test_time_range_*.py  # Time window scan + execution tests
│   ├── test_timewindow_trigger.py
│   ├── js/                   # Node helper for JS-execution tests
│   └── fixtures/             # Sample log snippets for testing
├── docs/                     # Reference documentation
│   ├── parsing-requirements.md
│   ├── log-field-definitions.md
│   ├── ui-requirements.md
│   ├── atak_enhanced_log_analysis.md
│   ├── atak_v3_early_integration_notes.md
│   └── session_summary.md    # Running session history — read at the start of a session
├── CLAUDE.md                 # Project rules shared by all Claude Code agents
├── .claude/
│   └── agents/               # Claude Code sub-agents (quality gate + workflow)
│       ├── vera.md
│       ├── task-completion-validator.md
│       ├── jenny.md
│       ├── karen.md
│       ├── peer-reviewer.md
│       ├── claude-md-compliance-checker.md
│       ├── code-quality-pragmatist.md
│       ├── parser-agent.md
│       ├── docs-agent.md
│       └── log-analyst.md
└── .github/workflows/
    └── ci.yml                # CI — runs pytest + UI lint on every push/PR
```

---

## Format Detection

`_detect_format()` in `api/routes/parse.py` checks formats in this order, and
**the order matters**:

| Priority | Format | Detected by |
|----------|--------|-------------|
| 1 | `fw_log` | `[digits-digits, MODULE, LEVEL]` bracket lines |
| 2 | `htmodem` | ctime-prefixed lines + modem markers (FPGA Version, AD936X, LIBIIO) |
| 3 | `htrouter` | Stat-counter keys (`input.total_m2m`, `output.*`) or ht-router process markers |
| 4 | `tak` | JSON with `receivedAt` + `nodeType` + `category` |
| 5 | `atak` | JSON with `logId` / `connectionState` / `atakVersion` |
| 6 | `relay_manager` | `com.gotenna.relaymanager` markers |
| 7 | `rsdk` | `IosBleRadio`, `AndroidBleRadio`, or `GRIP_SENDER` |
| 8 | `diagnostic` | Fallback when nothing else matches |

Two rules are load-bearing: `tak` must sit immediately before `atak` (both are
JSON with different fields), and `relay_manager` must come before `rsdk` (both
contain `AndroidBleRadio` lines). Breaking either causes silent misdetection.

## Supported Data Points

### Diagnostic format (goTenna Pro+, iOS)
- Device identity: callsign, GID, app version, build number, device model
- Radio identity: firmware version, serial number (from System Information block)
- Session timestamps and gap detection (>30 min = session break)
- System health over time: battery %, PA temperature (°C → °F)
- Received messages: PLI and chat/map with hop count and RSSI
- PLI interval per originator (5s / 15s / 30s / 60s / 300s)
- Message Count Details: sent/received counters
- Radio lifetime stat blocks (firmware all-time counters)
- Frequency set configuration

> ⚠️ Firmware 3.1.11 omits callsign and GID from Received Message blocks. Hop count and RSSI are still present.

### RSDK format (Pro+ iOS and Android)
- Platform detection: iOS (`IosBleRadio`) or Android (`AndroidBleRadio`)
- Battery % and PA temperature over time (from `DeviceInfo` polling)
- BLE reconnection failures with timestamps (iOS only)
- Unicast TX outcomes: Final ACKs, NACKs
- Contact discovery (peer callsigns via `ContactManager`)
- Radio firmware version and serial

> ⚠️ `hopCount` in `SendMessageResponse` is an SDK sequence counter — not RF mesh hop count. Excluded from all hop count analysis.

### ATAK format (Android ATAK plug-in)
- Filenames: legacy `diagnostic_ATAK_<CALLSIGN>_<GID>_...` and v3.0 `diagnostic_<CALLSIGN>_<GID>_...` (no `ATAK_` segment) are both recognized
- App version, ATAK version, device model, Android API level
- Device health over time: battery, PA temp, connection state
- Messages: PLI, text chat, map objects, file transfers
- Delivery status: FULLY_RECEIVED, SENT, DELIVERED, PARTIALLY_RECEIVED
- Hop count and RSSI (real RF data — signed dBm)
- Device lifecycle events: connect/disconnect, power changes, PLI setting changes, frequency updates

### Relay Manager format (Android logcat)
- Log sub-type auto-detection: `networkPolling` vs `scheduledHealthRequest`
- Environment detection: stage (confirmed) vs prod (TBD — not yet analyzed)
- Relay device serial number and BLE MAC address
- `relayHealthRequestCall` event timestamps and poll interval
- Raw BLE payload bytes captured per health request (decoded values pending BLE protocol implementation)
- Firmware notification type breakdown (type 72/8 = keepalive, type 73 = response ready, type 74 = alert, type 104 = battery change)
- Named events: health response ready, device alert, battery state change

> ⚠️ Relay health attribute values (SNR, battery %, temperature °F, uptime, firmware version) are present in BLE payload bytes but not yet decoded — requires BLE protocol implementation.
>
> ⚠️ Stage logs confirmed. Prod logs not yet analyzed — environment detection will be updated when prod samples are available.

### FW Log format (relay radio firmware, UART/USB debug console)
- Device identity: origin hash (short address) from RHC response lines
- RF configuration: device type, TX power, bit rate, region, frequencies, control and data channels
- Channel energy samples (`last_rssi` per preamble detection) — the RSSI stand-in shown in the UI
- Routing decisions: transmit / flood / echo / vine counts, plus duplicate suppression (already Rx / already TX)
- Neighbor table: unique node hashes seen
- Message-history buckets: rx'd / relayed / tx'd counts per 6-hour window
- Health poll count, and ERROR / WARN counts per module (up to 20 unique messages each)

> ⚠️ Timestamps are milliseconds since boot, not wall-clock time, so the time window step is skipped for this format.
>
> ⚠️ Serial number and firmware version are inside the binary RHC payload and are not extracted. `RSSI[]` lines are DEBUG-level and skipped; channel energy stands in for RSSI.
>
> ⚠️ "Battery stabilization" errors are a known firmware quirk and are counted separately from real errors.

### HT-Modem format (⚡ Next-Gen Radio — SDR/RF layer)
- Init checks: FPGA version, AD936X transceiver init, LIBIIO version, filter bank, gpsd connection
- Calibration offsets: clock and Si4460
- RX/TX frequency changes and TX power level changes over time
- TX packet lifecycle: encoding details, queued vs dropped (CSMA queue full), and RF "Packet Transmitted" confirmations
- Thermal: LPD / FPD / PL Zynq zones about every 10 seconds (logged in °C, displayed in °F), plotted against elapsed time

> ⚠️ An AD936X init failure produces ~20 near-identical error lines from one root cause; they are collapsed into a single `parse_errors` entry.
>
> ⚠️ Transmit confirmations carry no `packetID`, so they are matched to packets by position. `retransmit_count` counts extra confirmations, not proven RF retries (reported as a `DATA LIMITATION`).
>
> ⚠️ Some captures carry year-2036 timestamps because the radio's clock was never set.

### HT-Router format (⚡ Next-Gen Radio — network/link layer)
- Session identity: router PID and the `ht-modem` PID it started (a correlation key when both logs are loaded)
- UDP client/management sockets and startup socket warnings
- Protocol messages: client-hdr / mgt-hdr type breakdown with source and destination node addresses
- Management hub forward events
- Periodic stat snapshots (`input.*` / `output.*` counters, about every 10 seconds) and a connection-state timeline

> ⚠️ Snapshot counters are cumulative session-lifetime totals, not per-interval values. A session total is the last snapshot's value, never a sum.
>
> ⚠️ Snapshot schemas differ between sessions — a session that never transmitted omits the `output.*` group entirely. Absent fields stay absent (shown as —), never as zero.
>
> ⚠️ Rotated files (e.g. `ht-router_log.1`) are detected correctly by content but are currently rejected by the upload dropzone because of the extension (backlog).

### TAK Server format (server-side CoT event stream)
- Two container shapes: JSON array, or NDJSON with one logger-wrapped event per line
- Per event: device time, server receipt time, latency (receipt − event time), category, CoT type, uid, callsign, node type, platform
- Positions: lat/lon with no-fix detection (the CoT `0,0` convention)
- Raw CoT XML retained per event
- UI: Leaflet position map (one color per callsign) and latency scatter chart

> ⚠️ Server-side source — no serial, GID, firmware, battery, thermal, RSSI, or hop count. Excluded from the Health Score.
>
> ⚠️ Negative latency is real data (the device's clock runs ahead of the server), not a parsing error.
>
> ⚠️ Chat message bodies and device telemetry inside the raw CoT XML are not extracted.

---

## Key Features

### Time Window Filtering
The upload modal includes a dual-handle range slider. After dropping files, the app scans timestamps client-side and presents the full session span. Drag handles to narrow the analysis window before parsing. Hour-level snapping — start rounds down, end rounds up (e.g. 2:30–5:30 → 2:00–6:00). Active window shown as a badge in the header with ✕ to clear.

### Duplicate Log Detection
Files with the same `radio_serial + session_start + session_end` are deduplicated automatically. This handles the common case of loading both a named file (`RSO_HagenM.txt`) and its auto-exported equivalent (`diagnostic_20263727083706.txt`).

### PLI Frequency Analysis
The PLI tab shows one card per originator node with:
- Dominant interval (by message count) in color-coded large text
- ⚠ CHANGES badge when multiple intervals were observed
- ALSO OBSERVED chips listing each other interval with message count
- Stacked bar chart below showing estimated time per interval per node

**Color thresholds:** ≤5s = VERY HIGH (red) · ≤15s = CRITICAL (red) · ≤30s = HIGH (red) · ≤180s = ELEVATED (yellow) · >180s = STANDARD (green)

### Summary Recomputation
When a time window filter is active, all computable summary fields (`peak_temp_f`, `min_battery_pct`, `avg_hop_count`, `pli_count`, `ble_fail_count`, etc.) are recomputed from the filtered data arrays. Static fields (session count, contact names, cumulative message counters) retain parse-time values.

---

## Running Tests

```bash
pytest tests/
```

Run before every push. The CI workflow runs `pytest` and a UI lint check on every push to `main`.

---

## Contributing

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Make changes and add or update tests in `tests/`
3. Run `pytest tests/` and confirm passing before pushing
4. Open a pull request against `main`

---

## Documentation

Full field definitions, parsing rules, and UI requirements live in `docs/`:

| File | Contents |
|------|----------|
| `docs/log-field-definitions.md` | Every log field: raw name, parsed value, model field, caveats |
| `docs/parsing-requirements.md` | Parser rules per format, known limitations, sample observations |
| `docs/ui-requirements.md` | Dashboard layout, KPI cards, tab specs, design tokens |
