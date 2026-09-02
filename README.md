# WT901C 9-Axis Vibration & Inclinometer Tracker

A production-grade Python long-term data logging, storage, aggregation, and Home Assistant Add-on system designed for the **WT901C-TTL / USB 9-Axis Inclinometer** (Acceleration, Gyroscope, XY 0.05° Angle, Digital Compass, and Kalman Filtered Tilt Sensor).

---

## 🌟 Key Features

- **🏠 Native Home Assistant Add-on & MQTT Auto-Discovery**: Automatically creates entities for Roll Angle, Pitch Angle, Yaw, RMS Vibration ($g$), Acceleration ($A_x, A_y, A_z$), and Temperature ($^\circ\text{F}$) in Home Assistant—**zero manual YAML editing required**.
- **🖼️ Home Assistant Ingress Sidebar Panel**: Access the full interactive 3D tilt/vibration web app directly inside Home Assistant's left navigation sidebar.
- **🔌 USB Auto-Detection & Hot-Plug Resilience**: Automatically discovers connected USB serial ports (`/dev/ttyUSB*`, `/dev/tty.usbserial*`, `COM*`) and auto-reconnects seamlessly if the cable is unplugged.
- **⚡ Dual Storage Architecture**: High-rate MQTT state updates to Home Assistant + fast local SQLite WAL database storage to preserve raw high-frequency logs without overloading Home Assistant's recorder database.
- **📊 Automated Long-Term Aggregations**: Computes hourly rollup summaries (Min, Max, Mean, RMS Vibration, Peak Acceleration), keeping multi-year trend queries lightning-fast under 10 MB per year.
- **🌡️ Temperature in Fahrenheit ($^\circ\text{F}$)**: All telemetry and dashboard readouts are formatted in Fahrenheit.

---

## 🏡 Home Assistant Add-on Installation Guide

### Step 1: Add Custom Repository to Home Assistant
1. Push this project folder to your GitHub repository (e.g. `https://github.com/YOUR_USERNAME/wt901c-addon`).
2. Open Home Assistant -> Navigate to **Settings** -> **Add-ons** -> **Add-on Store**.
3. Click the **3 dots (⋮)** in the top right corner -> **Repositories**.
4. Paste your repository URL and click **Add**.

### Step 2: Install & Configure Add-on
1. Plug your **WT901C USB Sensor** into your Home Assistant host device.
2. In the Add-on Store, refresh the page and select **WT901C Vibration & Inclinometer Tracker**.
3. Click **Install**.
4. (Optional) Under **Configuration**, adjust parameters if needed:
   ```yaml
   serial_port: "auto"        # Auto-detects USB port or specify e.g. /dev/ttyUSB0
   baudrate: 115200
   mqtt_host: "core-mosquitto"
   mqtt_port: 1883
   publish_interval_sec: 0.5
   ```
5. Toggle **Show in sidebar** and click **Start**.

### Step 3: Access Entities & Web Dashboard
- **Sidebar Panel**: Click **Vibration Tracker** in your Home Assistant left navigation menu to open the interactive dashboard.
- **MQTT Entities**: Check Home Assistant **Settings** -> **Devices & Services** -> **MQTT**. Your sensor entities will appear automatically:
  - `sensor.wt901c_roll` (XY 0.05° Roll Angle °)
  - `sensor.wt901c_pitch` (XY 0.05° Pitch Angle °)
  - `sensor.wt901c_yaw` (Yaw Angle °)
  - `sensor.wt901c_rms_vibration` (RMS Vibration g)
  - `sensor.wt901c_temperature` (Temperature °F)
  - `sensor.wt901c_accel_x`, `_y`, `_z` (Acceleration g)

---

## 💻 Standalone Quick Start (Without Home Assistant)

### 1. Setup Virtual Environment
```bash
cd "/Users/nevernothing/Developer/viberation tracker"
source venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. pytest tests/
```

### 2. Run Serial Collector
```bash
# Auto-detects USB sensor port and logs readings to SQLite
python3 collector.py
```

### 3. Launch Web Dashboard
In a new terminal window:
```bash
source venv/bin/activate
streamlit run dashboard.py
```
Open **`http://localhost:8501`** in your browser.

### 4. Background Downsampler (Hourly Rollups)
```bash
python3 downsampler.py
```

### 5. 24/7 Unattended Background Service (macOS / Linux)
To run automatically on system startup:
```bash
./setup_service.sh
```
- **macOS**: Installs `~/Library/LaunchAgents/com.vibrationtracker.collector.plist`
- **Linux / Raspberry Pi**: Installs `/etc/systemd/system/wt901c-collector.service`

---

## 📁 Project Structure

```
viberation tracker/
├── wt901c_parser.py          # Binary 0x55 frame decoder & checksum validator
├── storage.py                # SQLite WAL storage engine & rollup aggregator
├── collector.py              # Resilient USB serial listener daemon (auto-reconnect)
├── downsampler.py            # Background worker for multi-month summary rollups
├── dashboard.py              # Streamlit & Plotly interactive web app
├── mqtt_publisher.py        # Home Assistant MQTT Auto-Discovery & telemetry publisher
├── setup_service.sh          # Standalone service daemon installer (macOS & Linux)
├── repository.json          # Home Assistant Add-on repository manifest
├── ha_addon/                 # Home Assistant Add-on Docker & Ingress package
│   ├── config.yaml          # Add-on configuration & Ingress panel definition
│   ├── build.yaml           # Multi-arch build manifest (aarch64 / amd64)
│   ├── Dockerfile           # Docker container build script
│   └── run.sh               # Add-on startup entrypoint script
├── requirements.txt          # Python dependencies
└── tests/                    # Automated unit test suite
    ├── test_mqtt.py
    ├── test_parser.py
    └── test_storage.py
```
