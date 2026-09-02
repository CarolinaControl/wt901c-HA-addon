# WT901C 9-Axis Vibration & Inclinometer Long-Term Tracker

A production-grade Python long-term data logging, storage, aggregation, and web dashboard system designed for the **WT901C-TTL / USB 9-Axis Inclinometer** (Acceleration, Gyroscope, XY 0.05° Angle, Digital Compass, and Kalman Filtered Tilt Sensor).

---

## Features

- **Continuous 24/7 Logging**: Auto-detects USB serial connections (`/dev/ttyUSB*`, `/dev/tty.usbserial*`, `COM*`) with automatic reconnect resilience if unplugged.
- **Fast SQLite WAL Storage**: High-performance transaction batching to store high-rate (10Hz to 200Hz) raw sensor data with zero disk lockups.
- **Automated Long-Term Aggregations**: Downsamples high-frequency raw logs into 1-minute and 1-hour rollup summaries (Mean, Min, Max, RMS Vibration, Peak Acceleration), keeping multi-year trend queries lightning-fast under 10 MB per year.
- **Interactive Web Dashboard**: Built with Streamlit and Plotly for real-time 3-axis tilt/vibration gauge cards, live time-series charts, long-term multi-month trend analysis, and CSV export.
- **Unattended Service Daemons**: Auto-install scripts for macOS `launchd` and Raspberry Pi / Linux `systemd`.

---

## Quick Start

### 1. Activate Environment & Test Installation
```bash
cd "/Users/nevernothing/Developer/viberation tracker"
source venv/bin/activate
pytest tests/
```

### 2. Plug in WT901C & Start Serial Data Collector
```bash
# Auto-detects USB port and logs sensor readings to SQLite
python3 collector.py
```
*Optional parameters:*
- `--port /dev/tty.usbserial-110` (Specify exact port)
- `--baud 115200` (Default WitMotion baud rate)

### 3. Launch Web Dashboard
In a new terminal window:
```bash
source venv/bin/activate
streamlit run dashboard.py
```
Open your browser at **http://localhost:8501** to view live tilt metrics, acceleration graphs, and long-term trend analysis.

### 4. Background Downsampler (Hourly Aggregates)
To run periodic hourly rollups for long-term trend queries:
```bash
python3 downsampler.py
```

---

## 24/7 Background Service Installation

To run the logging service automatically in the background on startup (Raspberry Pi OS / Linux or macOS):

```bash
./setup_service.sh
```

- **macOS**: Installs `~/Library/LaunchAgents/com.vibrationtracker.collector.plist`
- **Raspberry Pi / Linux**: Installs `/etc/systemd/system/wt901c-collector.service`

Logs are automatically streamed to `data/collector.log`.

---

## Project Structure

```
viberation tracker/
├── wt901c_parser.py      # Binary 0x55 frame decoder & checksum validator
├── storage.py            # SQLite WAL storage manager & rollup aggregation engine
├── collector.py          # Resilient USB serial listener daemon (auto-reconnect)
├── downsampler.py        # Background worker for multi-month summary rollups
├── dashboard.py          # Streamlit & Plotly interactive web app
├── setup_service.sh      # Service daemon installer script (macOS & Linux)
├── requirements.txt      # Python dependencies
└── tests/                # Automated unit test suite
    ├── test_parser.py
    └── test_storage.py
```
