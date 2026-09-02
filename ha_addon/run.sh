#!/usr/bin/env bash
set -e

CONFIG_PATH="/data/options.json"

SERIAL_PORT="auto"
BAUDRATE=115200
MQTT_HOST="core-mosquitto"
MQTT_PORT=1883
MQTT_USER=""
MQTT_PASSWORD=""
PUBLISH_INTERVAL=0.5

if [ -f "$CONFIG_PATH" ]; then
    echo "Loading Home Assistant configuration from $CONFIG_PATH..."
    SERIAL_PORT=$(jq --raw-output '.serial_port // "auto"' "$CONFIG_PATH")
    BAUDRATE=$(jq --raw-output '.baudrate // 115200' "$CONFIG_PATH")
    MQTT_HOST=$(jq --raw-output '.mqtt_host // "core-mosquitto"' "$CONFIG_PATH")
    MQTT_PORT=$(jq --raw-output '.mqtt_port // 1883' "$CONFIG_PATH")
    MQTT_USER=$(jq --raw-output '.mqtt_user // ""' "$CONFIG_PATH")
    MQTT_PASSWORD=$(jq --raw-output '.mqtt_password // ""' "$CONFIG_PATH")
    PUBLISH_INTERVAL=$(jq --raw-output '.publish_interval_sec // 0.5' "$CONFIG_PATH")
fi

# Fallback to HA supervisor service credentials if option is empty
if [ -z "$MQTT_USER" ] && [ -n "$CONFIG_SERVICES_MQTT_USER" ]; then
    MQTT_USER="$CONFIG_SERVICES_MQTT_USER"
    MQTT_PASSWORD="$CONFIG_SERVICES_MQTT_PASSWORD"
fi

echo "=========================================================="
echo " Starting WT901C 9-Axis Tracker Add-on"
echo " Serial Port : $SERIAL_PORT ($BAUDRATE baud)"
echo " MQTT Broker : $MQTT_HOST:$MQTT_PORT (User: ${MQTT_USER:-none})"
echo " Ingress     : Enabled (Port 8501)"
echo "=========================================================="

mkdir -p /app/data

export PYTHONPATH=/app
export DB_DIR=/app/data

# 1. Start Serial Data Collector Daemon
echo "Starting WT901C Collector Daemon..."
python3 /app/collector.py --port "$SERIAL_PORT" --baud "$BAUDRATE" --db-dir /app/data &

# 2. Start Hourly Downsampler Background Worker
echo "Starting Downsampler Worker..."
python3 /app/downsampler.py --db-dir /app/data --interval 300 &

# 3. Start MQTT Auto-Discovery & Telemetry Publisher
echo "Starting Home Assistant MQTT Publisher..."
python3 /app/mqtt_publisher.py \
    --host "$MQTT_HOST" \
    --port "$MQTT_PORT" \
    --user "$MQTT_USER" \
    --password "$MQTT_PASSWORD" \
    --interval "$PUBLISH_INTERVAL" \
    --db-dir /app/data &

# 4. Start Streamlit Dashboard Webpage for Ingress and direct access
echo "Starting Streamlit Dashboard Webpage..."
exec streamlit run /app/dashboard.py \
    --server.port=8501 \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.allowRunOnSave=false \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false
