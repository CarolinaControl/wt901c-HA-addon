import unittest
from mqtt_publisher import HomeAssistantMqttPublisher

class TestMqttPublisher(unittest.TestCase):
    def setUp(self):
        self.publisher = HomeAssistantMqttPublisher(host="localhost", port=1883)

    def test_discovery_payload_structure(self):
        cfg = {
            "name": "WT901C Roll Angle",
            "unit": "°",
            "icon": "mdi:rotate-3d-variant",
            "device_class": "inclination",
            "state_class": "measurement",
            "value_template": "{{ value_json.roll }}"
        }
        payload = self.publisher.build_discovery_payload("roll", cfg)
        
        self.assertEqual(payload["name"], "WT901C Roll Angle")
        self.assertEqual(payload["unique_id"], "wt901c_roll")
        self.assertEqual(payload["unit_of_measurement"], "°")
        self.assertEqual(payload["device_class"], "inclination")
        self.assertEqual(payload["state_class"], "measurement")
        self.assertEqual(payload["device"]["manufacturer"], "WitMotion")
        self.assertEqual(payload["device"]["model"], "WT901C-TTL")

    def test_all_sensors_defined(self):
        self.assertIn("roll", HomeAssistantMqttPublisher.SENSORS)
        self.assertIn("pitch", HomeAssistantMqttPublisher.SENSORS)
        self.assertIn("yaw", HomeAssistantMqttPublisher.SENSORS)
        self.assertIn("rms_accel", HomeAssistantMqttPublisher.SENSORS)
        self.assertIn("temp", HomeAssistantMqttPublisher.SENSORS)

if __name__ == '__main__':
    unittest.main()
