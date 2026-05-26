# goTenna Log Analyzer

A local log parsing and visualization tool for goTenna mesh network diagnostic data.

Supports four log formats:
- **Diagnostic** — goTenna Pro+ app export (`diagnostic_*.txt`, named device files)
- **RSDK** — Android/iOS SDK logs from field sessions (Pro+ app)
- **ATAK** — Android ATAK plug-in logs (regular and enhanced)
- **Relay Manager** — Android logcat dumps from the goTenna Relay Manager app (network polling and scheduled health check sub-types)

## Stack

| Layer | Technology |
|---|---|
| Parser | Python 3.10+ |
| API | FastAPI + Uvicorn |
| UI | React 18 + Vite + Chart.js 4.4.1 |
| Tests | Pytest |
| Fonts | Barlow Condensed · Share Tech Mono |

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

## Project Structure

```
qa-log-analyzer/
├── parser/                   # Log parsing engine (Python)
│   ├── diagnostic.py         # Parses goTenna Pro+ diagnostic format
│   ├── rsdk.py               # Parses RSDK iOS/Android SDK log format
│   ├── atak.py               # Parses Android ATAK plug-in log format
│   ├── relay_manager.py      # Parses Relay Manager Android logcat format
│   └── models.py             # Shared dataclasses (ParseResult, SystemSample, etc.)
├── api/                      # FastAPI REST bridge
│   ├── main.py               # App entry point — uvicorn main:app
│   └── routes/
│       ├── parse.py          # POST /parse  — upload & parse log files
│       └── export.py         # GET  /export — download parsed data as CSV/JSON
├── ui/                       # React + Vite frontend
│   └── src/
│       ├── components/
│       │   ├── ChartPanel.jsx        # All chart definitions and rendering
│       │   ├── DataPointSelector.jsx # Data point toggle UI
│       │   ├── DeviceSummary.jsx     # Per-device summary card
│       │   └── FileUpload.jsx        # Upload modal with time window slider
│       ├── hooks/
│       │   └── useLogData.js         # Fetch + cache parsed results from API
│       └── App.jsx                   # Main app — tabs, KPI row, filtering
├── tests/                    # Pytest test suite
│   ├── test_diagnostic.py
│   ├── test_rsdk.py
│   └── fixtures/             # Sample log snippets for testing
├── docs/                     # Reference documentation
│   ├── ui-requirements.md
│   ├── parsing-requirements.md
│   └── log-field-definitions.md
└── .github/workflows/
    └── ci.yml                # CI — runs pytest + UI lint on every push/PR
```

---

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
