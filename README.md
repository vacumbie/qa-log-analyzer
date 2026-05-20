# goTenna Log Analyzer

A local log parsing and visualization tool for goTenna mesh network diagnostic data.

Supports two log formats:
- **Diagnostic** — goTenna Pro+ app export (`diagnostic_*.txt`, named device files)
- **RSDK** — Android/iOS SDK logs from field sessions

## Stack

| Layer | Technology |
|---|---|
| Parser | Python 3.10+ |
| API | FastAPI + Uvicorn |
| UI | React 18 + Vite + Chart.js |
| Tests | Pytest |

## Quick Start

### 1. Clone the repo
```bash
git clone https://github.com/YOUR-ORG/gotenna-log-analyzer.git
cd gotenna-log-analyzer
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

### 5. Activate the virtual environment each time PowerShell is launched
The project requires a virtual environment for its specific Python library dependencies (FastAPI, PyTest, Uvicorn). Run these two commands at the start of every PowerShell session before working on the project:
```powershell
cd C:\Users\Valerie.Cumbie\Documents\qa-log-analyzer
.\venv\Scripts\activate
```

## Project Structure

```
gotenna-log-analyzer/
├── parser/               # Log parsing engine (Python)
│   ├── diagnostic.py     # Parses goTenna Pro+ diagnostic format
│   ├── rsdk.py           # Parses RSDK SDK log format
│   └── models.py         # Shared dataclasses
├── api/                  # FastAPI REST bridge
│   ├── main.py
│   └── routes/
│       ├── parse.py      # POST /parse  – upload & parse a log file
│       └── export.py     # GET  /export – download parsed data as CSV/JSON
├── ui/                   # React + Vite frontend
│   └── src/
│       ├── components/   # FileUpload, ChartPanel, DataPointSelector, DeviceSummary
│       ├── hooks/        # useLogData – fetches & caches parsed data
│       └── pages/        # Dashboard, Compare, Export
├── tests/                # Pytest test suite
│   ├── test_diagnostic.py
│   ├── test_rsdk.py
│   └── fixtures/         # Sample log snippets for testing
└── .github/workflows/    # CI — runs tests on every push/PR
    └── ci.yml
```

## Supported Data Points

### Diagnostic format
- Device & app version info
- Session timestamps and gaps
- System info (battery, PA temp, firmware)
- Received messages (PLI + chat/map)
- Message hop count and RSSI
- PLI interval per originator
- Message Count Details (sent/received)
- Radio lifetime stat blocks
- Frequency set configuration

### RSDK format
- BLE reconnection failures (per radio serial)
- Battery and temperature over time
- Broadcast message counter (outbound PLI cadence)
- Unicast TX: Final ACKs, NACKs, timeouts
- Device info (firmware version, serial)

## Contributing

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Make your changes and add tests
3. Run `pytest tests/` before pushing
4. Open a pull request against `main`
