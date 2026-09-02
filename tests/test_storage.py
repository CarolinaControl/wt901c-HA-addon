import os
import shutil
import tempfile
import time
import unittest
from storage import StorageManager

class TestStorageManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.storage = StorageManager(db_dir=self.test_dir, db_filename="test_wt901c.db")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_insert_and_retrieve_batch(self):
        readings = [
            {
                "timestamp": time.time(),
                "roll": 1.25,
                "pitch": -0.5,
                "yaw": 45.0,
                "ax": 0.01,
                "ay": 0.02,
                "az": 1.0,
                "wx": 0.1,
                "wy": 0.2,
                "wz": 0.0,
                "rms_accel": 1.0002,
                "temp": 26.5
            },
            {
                "timestamp": time.time() + 0.1,
                "roll": 1.30,
                "pitch": -0.4,
                "yaw": 45.1,
                "ax": 0.02,
                "ay": 0.01,
                "az": 1.01,
                "wx": 0.0,
                "wy": 0.1,
                "wz": 0.0,
                "rms_accel": 1.0102,
                "temp": 26.5
            }
        ]

        inserted = self.storage.insert_batch(readings)
        self.assertEqual(inserted, 2)

        latest = self.storage.get_latest_readings(limit=10)
        self.assertEqual(len(latest), 2)
        self.assertAlmostEqual(latest[0]["roll"], 1.30)
        self.assertAlmostEqual(latest[1]["roll"], 1.25)

    def test_hourly_rollups(self):
        readings = []
        base_ts = time.time()
        for i in range(10):
            readings.append({
                "timestamp": base_ts + i,
                "roll": float(i),
                "pitch": float(i * 2),
                "yaw": 100.0,
                "ax": 0.0,
                "ay": 0.0,
                "az": 1.0,
                "rms_accel": 1.0 + (i * 0.1),
                "temp": 25.0
            })

        self.storage.insert_batch(readings)
        affected = self.storage.compute_hourly_rollups()
        self.assertGreaterEqual(affected, 1)

        rollups = self.storage.get_hourly_rollups()
        self.assertEqual(len(rollups), 1)
        r0 = rollups[0]
        self.assertEqual(r0["sample_count"], 10)
        self.assertAlmostEqual(r0["roll_min"], 0.0)
        self.assertAlmostEqual(r0["roll_max"], 9.0)
        self.assertAlmostEqual(r0["roll_mean"], 4.5)

    def test_db_stats(self):
        stats = self.storage.get_db_stats()
        self.assertIn("total_raw_rows", stats)
        self.assertIn("file_size_mb", stats)
        self.assertEqual(stats["total_raw_rows"], 0)

if __name__ == '__main__':
    unittest.main()
