import os
import json
import time
import logging
import argparse
from typing import Dict, Any, Optional

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None

from storage import StorageManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("mqtt_publisher")

class HomeAssistantMqttPublisher:
    """
    Publishes WT901C sensor metrics to Home Assistant via MQTT Auto-Discovery.
    Home Assistant automatically creates entities without requiring manual YAML edits.
    """

    DISCOVERY_PREFIX = "homeassistant"
    NODE_ID = "wt901c"
    STATE_TOPIC = "homeassistant/sensor/wt901c/state"

    SENSORS = {
        "roll": {
            "name": "WT901C Roll Angle",
            "unit": "°",
            "icon": "mdi:rotate-3d-variant",
            "state_class": "measurement",
            "value_template": "{{ value_json.roll }}"
        },
        "pitch": {
            "name": "WT901C Pitch Angle",
            "unit": "°",
            "icon": "mdi:axis-arrow",
            "state_class": "measurement",
            "value_template": "{{ value_json.pitch }}"
        },
        "yaw": {
            "name": "WT901C Yaw Angle",
            "unit": "°",
            "icon": "mdi:compass",
            "state_class": "measurement",
            "value_template": "{{ value_json.yaw }}"
        },
        "rms_accel": {
            "name": "WT901C RMS Vibration",
            "unit": "g",
            "icon": "mdi:vibrate",
            "state_class": "measurement",
            "value_template": "{{ value_json.rms_accel }}"
        },
        "temp": {
            "name": "WT901C Temperature",
            "unit": "°F",
            "device_class": "temperature",
            "state_class": "measurement",
            "value_template": "{{ value_json.temp }}"
        },
        "ax": {
            "name": "WT901C Accel X",
            "unit": "g",
            "icon": "mdi:axis-x-arrow",
            "state_class": "measurement",
            "value_template": "{{ value_json.ax }}"
        },
        "ay": {
            "name": "WT901C Accel Y",
            "unit": "g",
            "icon": "mdi:axis-y-arrow",
            "state_class": "measurement",
            "value_template": "{{ value_json.ay }}"
        },
        "az": {
            "name": "WT901C Accel Z",
            "unit": "g",
            "icon": "mdi:axis-z-arrow",
            "state_class": "measurement",
            "value_template": "{{ value_json.az }}"
        }
    }

    def __init__(
        self,
        host: str = "localhost",
        port: int = 1883,
        user: Optional[str] = None,
        password: Optional[str] = None,
        db_dir: str = "data"
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.storage = StorageManager(db_dir=db_dir)
        self.client = None
        self._connected = False

    def build_discovery_payload(self, sensor_id: str, cfg: Dict[str, Any]) -> Dict[str, Any]:
        """Generate Home Assistant MQTT Auto-Discovery configuration JSON payload."""
        payload = {
            "name": cfg["name"],
            "unique_id": f"wt901c_{sensor_id}",
            "state_topic": self.STATE_TOPIC,
            "value_template": cfg["value_template"],
            "device": {
                "identifiers": ["wt901c_inclinometer"],
                "name": "WT901C 9-Axis Inclinometer & Vibration Sensor",
                "model": "WT901C-TTL",
                "manufacturer": "WitMotion"
            }
        }
        if "unit" in cfg:
            payload["unit_of_measurement"] = cfg["unit"]
        if "icon" in cfg:
            payload["icon"] = cfg["icon"]
        if "device_class" in cfg:
            payload["device_class"] = cfg["device_class"]
        if "state_class" in cfg:
            payload["state_class"] = cfg["state_class"]

        return payload

    def connect(self) -> bool:
        """Establish connection to MQTT broker."""
        if not mqtt:
            logger.error("paho-mqtt library is not installed. Install with `pip install paho-mqtt`.")
            return False

        try:
            self.client = mqtt.Client(client_id="wt901c_ha_publisher")
            if self.user and self.password:
                self.client.username_pw_set(self.user, self.password)

            def on_connect(client, userdata, flags, rc):
                if rc == 0:
                    logger.info(f"Connected to MQTT Broker at {self.host}:{self.port}")
                    self._connected = True
                    self.publish_discovery()
                else:
                    logger.error(f"MQTT connection failed with return code {rc}")

            def on_disconnect(client, userdata, rc):
                logger.warning(f"Disconnected from MQTT Broker (rc: {rc})")
                self._connected = False

            self.client.on_connect = on_connect
            self.client.on_disconnect = on_disconnect
            self.client.connect(self.host, self.port, keepalive=60)
            self.client.loop_start()
            return True
        except Exception as e:
            logger.error(f"Error connecting to MQTT Broker ({self.host}:{self.port}): {e}")
            return False

    def publish_discovery(self):
        """Publish Auto-Discovery config messages for all sensors."""
        if not self.client:
            return

        logger.info("Publishing Home Assistant MQTT Auto-Discovery topics...")
        for sensor_id, cfg in self.SENSORS.items():
            topic = f"{self.DISCOVERY_PREFIX}/sensor/{self.NODE_ID}_{sensor_id}/config"
            payload = self.build_discovery_payload(sensor_id, cfg)
            self.client.publish(topic, json.dumps(payload), retain=True)

    def publish_state(self, reading: Dict[str, Any]):
        """Publish current state telemetry payload."""
        if not self.client or not self._connected:
            return

        payload = {
            "roll": round(reading.get("roll", 0.0), 3),
            "pitch": round(reading.get("pitch", 0.0), 3),
            "yaw": round(reading.get("yaw", 0.0), 3),
            "rms_accel": round(reading.get("rms_accel", 0.0), 4),
            "temp": round(reading.get("temp", 0.0), 1),
            "ax": round(reading.get("ax", 0.0), 3),
            "ay": round(reading.get("ay", 0.0), 3),
            "az": round(reading.get("az", 0.0), 3),
            "timestamp": reading.get("timestamp", time.time())
        }
        self.client.publish(self.STATE_TOPIC, json.dumps(payload))

    def run_loop(self, interval_sec: float = 0.5):
        """Poll latest database reading and publish state to Home Assistant."""
        logger.info(f"Starting Home Assistant MQTT publishing loop (interval: {interval_sec}s)...")
        while True:
            try:
                latest = self.storage.get_latest_readings(limit=1)
                if latest:
                    self.publish_state(latest[0])
            except Exception as e:
                logger.error(f"Error reading DB or publishing state: {e}")

            time.sleep(interval_sec)

def main():
    parser = argparse.ArgumentParser(description="WT901C Home Assistant MQTT Auto-Discovery Publisher")
    parser.add_argument("--host", type=str, default=os.getenv("MQTT_HOST", "localhost"), help="MQTT broker host")
    parser.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", 1883)), help="MQTT broker port")
    parser.add_argument("--user", type=str, default=os.getenv("MQTT_USER", None), help="MQTT username")
    parser.add_argument("--password", type=str, default=os.getenv("MQTT_PASSWORD", None), help="MQTT password")
    parser.add_argument("--interval", type=float, default=0.5, help="Telemetry update interval in seconds (default: 0.5s)")
    parser.add_argument("--db-dir", type=str, default="data", help="Directory storing SQLite database")
    args = parser.parse_args()

    publisher = HomeAssistantMqttPublisher(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        db_dir=args.db_dir
    )

    if publisher.connect():
        publisher.run_loop(interval_sec=args.interval)

if __name__ == "__main__":
    main()
