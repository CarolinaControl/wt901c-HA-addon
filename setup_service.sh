#!/usr/bin/env bash
set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

mkdir -p "$SCRIPT_DIR/data"

OS_TYPE="$(uname -s)"

echo "=========================================================="
echo " Setting up WT901C 24/7 Background Logging Service"
echo " Detected Operating System: $OS_TYPE"
echo "=========================================================="

if [ "$OS_TYPE" = "Darwin" ]; then
    PLIST_PATH="$HOME/Library/LaunchAgents/com.vibrationtracker.collector.plist"
    echo "Installing macOS launchd service to $PLIST_PATH..."
    
    cat << EOF > "$PLIST_PATH"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.vibrationtracker.collector</string>
    <key>ProgramArguments</key>
    <array>
        <string>$SCRIPT_DIR/venv/bin/python3</string>
        <string>$SCRIPT_DIR/collector.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$SCRIPT_DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$SCRIPT_DIR/data/collector.log</string>
    <key>StandardErrorPath</key>
    <string>$SCRIPT_DIR/data/collector_error.log</string>
</dict>
</plist>
EOF

    echo "Loading launchd service..."
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
    launchctl load "$PLIST_PATH"
    echo "✅ macOS Service installed and started!"
    echo "Logs are available at $SCRIPT_DIR/data/collector.log"

elif [ "$OS_TYPE" = "Linux" ]; then
    SERVICE_PATH="/etc/systemd/system/wt901c-collector.service"
    echo "Installing Linux systemd service to $SERVICE_PATH..."
    
    sudo cat << EOF > "$SERVICE_PATH"
[Unit]
Description=WT901C 9-Axis Vibration & Inclinometer Data Collector Service
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$SCRIPT_DIR
ExecStart=$SCRIPT_DIR/venv/bin/python3 $SCRIPT_DIR/collector.py
Restart=always
RestartSec=5
StandardOutput=append:$SCRIPT_DIR/data/collector.log
StandardError=append:$SCRIPT_DIR/data/collector_error.log

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable wt901c-collector.service
    sudo systemctl restart wt901c-collector.service
    echo "✅ Linux systemd service installed and started!"
    echo "Check status with: sudo systemctl status wt901c-collector.service"
else
    echo "Unsupported OS type for automated service setup: $OS_TYPE"
fi
