import os
import sqlite3
import time
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class StorageManager:
    """
    Manages SQLite database storage for high-frequency WT901C raw sensor data
    and aggregated hourly/daily rollups for long-term trends.
    """

    def __init__(self, db_dir: str = "data", db_filename: str = "wt901c_tracker.db"):
        self.db_dir = os.path.abspath(db_dir)
        os.makedirs(self.db_dir, exist_ok=True)
        self.db_path = os.path.join(self.db_dir, db_filename)
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        """Create a database connection configured with WAL mode and fast synchronous settings."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        # Enable Write-Ahead Logging for fast concurrent reads and writes
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    def _init_db(self):
        """Initialize database tables and indexes if they do not exist."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Raw high-frequency readings table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS raw_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                datetime TEXT NOT NULL,
                roll REAL,
                pitch REAL,
                yaw REAL,
                ax REAL,
                ay REAL,
                az REAL,
                wx REAL,
                wy REAL,
                wz REAL,
                rms_accel REAL,
                temp REAL
            );
            """)
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_raw_ts ON raw_readings (timestamp);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_raw_dt ON raw_readings (datetime);")

            # Hourly aggregated summary table for fast multi-month / multi-year queries
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS hourly_rollups (
                timestamp_hour TEXT PRIMARY KEY,
                sample_count INTEGER NOT NULL,
                roll_min REAL,
                roll_max REAL,
                roll_mean REAL,
                pitch_min REAL,
                pitch_max REAL,
                pitch_mean REAL,
                yaw_mean REAL,
                rms_accel_mean REAL,
                peak_accel_max REAL,
                temp_mean REAL
            );
            """)

            conn.commit()
            logger.info(f"Database initialized at {self.db_path}")

    def insert_batch(self, readings: List[Dict[str, Any]]) -> int:
        """
        Batch insert multiple reading dicts in a single fast transaction.
        Each reading should contain 'timestamp' and sensor fields.
        """
        if not readings:
            return 0

        rows = []
        for r in readings:
            ts = r.get("timestamp", time.time())
            dt_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            rows.append((
                ts,
                dt_str,
                r.get("roll"),
                r.get("pitch"),
                r.get("yaw"),
                r.get("ax"),
                r.get("ay"),
                r.get("az"),
                r.get("wx"),
                r.get("wy"),
                r.get("wz"),
                r.get("rms_accel"),
                r.get("temp")
            ))

        sql = """
        INSERT INTO raw_readings (
            timestamp, datetime, roll, pitch, yaw,
            ax, ay, az, wx, wy, wz, rms_accel, temp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """

        with self.get_connection() as conn:
            conn.executemany(sql, rows)
            conn.commit()

        return len(rows)

    def get_latest_readings(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Fetch latest raw readings."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM raw_readings ORDER BY id DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_raw_in_range(self, start_ts: float, end_ts: float) -> List[Dict[str, Any]]:
        """Fetch raw readings in timestamp range."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM raw_readings WHERE timestamp >= ? AND timestamp <= ? ORDER BY timestamp ASC",
                (start_ts, end_ts)
            )
            return [dict(row) for row in cursor.fetchall()]

    def compute_hourly_rollups(self) -> int:
        """
        Calculates and upserts hourly summary rollups from raw_readings.
        Returns number of hourly buckets processed.
        """
        sql = """
        INSERT INTO hourly_rollups (
            timestamp_hour, sample_count,
            roll_min, roll_max, roll_mean,
            pitch_min, pitch_max, pitch_mean,
            yaw_mean, rms_accel_mean, peak_accel_max, temp_mean
        )
        SELECT 
            strftime('%Y-%m-%d %H:00:00', datetime) as hr,
            COUNT(*) as sample_count,
            MIN(roll), MAX(roll), AVG(roll),
            MIN(pitch), MAX(pitch), AVG(pitch),
            AVG(yaw),
            AVG(rms_accel), MAX(rms_accel),
            AVG(temp)
        FROM raw_readings
        WHERE hr IS NOT NULL
        GROUP BY hr
        ON CONFLICT(timestamp_hour) DO UPDATE SET
            sample_count = excluded.sample_count,
            roll_min = excluded.roll_min,
            roll_max = excluded.roll_max,
            roll_mean = excluded.roll_mean,
            pitch_min = excluded.pitch_min,
            pitch_max = excluded.pitch_max,
            pitch_mean = excluded.pitch_mean,
            yaw_mean = excluded.yaw_mean,
            rms_accel_mean = excluded.rms_accel_mean,
            peak_accel_max = excluded.peak_accel_max,
            temp_mean = excluded.temp_mean;
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql)
            affected = cursor.rowcount
            conn.commit()
            return affected

    def get_hourly_rollups(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """Fetch long-term hourly summary rollups."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM hourly_rollups ORDER BY timestamp_hour ASC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_db_stats(self) -> Dict[str, Any]:
        """Get row counts and file size metrics."""
        size_bytes = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
        with self.get_connection() as conn:
            cursor = conn.cursor()
            raw_count = cursor.execute("SELECT COUNT(*) FROM raw_readings").fetchone()[0]
            hourly_count = cursor.execute("SELECT COUNT(*) FROM hourly_rollups").fetchone()[0]
        
        return {
            "db_path": self.db_path,
            "file_size_mb": round(size_bytes / (1024 * 1024), 2),
            "total_raw_rows": raw_count,
            "total_hourly_rows": hourly_count
        }
