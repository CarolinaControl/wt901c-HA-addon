import os
import sys
import glob
import time
import logging
import argparse
import signal
from typing import Optional, List

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    serial = None
    list_ports = None

from wt901c_parser import WT901CParser
from storage import StorageManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("collector")

class SerialCollector:
    """
    Continuous serial collector for WT901C 9-axis sensor.
    Handles USB connection discovery, frame decoding, ring-buffering,
    batch SQLite persistence, and automatic reconnection on USB disconnects.
    """

    def __init__(self, port: Optional[str] = None, baudrate: int = 115200, db_dir: str = "data", batch_size: int = 50):
        self.target_port = port
        self.baudrate = baudrate
        self.batch_size = batch_size
        self.parser = WT901CParser()
        self.storage = StorageManager(db_dir=db_dir)
        self.running = True

        # Signal handlers for clean shutdown
        signal.signal(signal.SIGINT, self._handle_exit)
        signal.signal(signal.SIGTERM, self._handle_exit)

    def _handle_exit(self, signum, frame):
        logger.info(f"Shutdown signal received ({signum}). Stopping collector...")
        self.running = False

    @staticmethod
    def find_wt901c_ports() -> List[str]:
        """Auto-discover potential USB serial ports for WT901C across macOS, Linux, and Windows."""
        discovered = []
        if list_ports:
            for p in list_ports.comports():
                # Common USB serial chips: CH340, CP210x, FTDI, WitMotion USB
                desc = f"{p.device} - {p.description} ({p.hwid})".lower()
                if any(k in desc for k in ["usb", "ch340", "cp210", "ftdi", "witmotion", "ttyusb", "tty.usbserial"]):
                    discovered.append(p.device)

        if not discovered:
            # Fallback glob search for Linux and macOS serial device nodes
            patterns = [
                "/dev/ttyUSB*",
                "/dev/ttyACM*",
                "/dev/tty.usbserial*",
                "/dev/tty.wchusbserial*"
            ]
            for pat in patterns:
                discovered.extend(glob.glob(pat))

        return list(dict.fromkeys(discovered))

    def run(self):
        logger.info("Initializing WT901C Serial Collector...")
        buffer_batch = []
        last_flush_time = time.time()
        last_stat_time = time.time()
        packet_count = 0

        while self.running:
            port_to_open = self.target_port
            if not port_to_open:
                available_ports = self.find_wt901c_ports()
                if available_ports:
                    port_to_open = available_ports[0]
                    logger.info(f"Auto-detected sensor port: {port_to_open}")
                else:
                    logger.warning("No USB serial port found for WT901C. Retrying in 3 seconds...")
                    time.sleep(3)
                    continue

            logger.info(f"Opening serial port {port_to_open} at {self.baudrate} baud...")
            try:
                ser = serial.Serial(
                    port=port_to_open,
                    baudrate=self.baudrate,
                    timeout=0.5,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE
                )
            except Exception as e:
                logger.error(f"Failed to open port {port_to_open}: {e}. Retrying in 3 seconds...")
                time.sleep(3)
                continue

            logger.info(f"Successfully connected to WT901C on {port_to_open}. Listening for data frames...")
            
            try:
                while self.running:
                    raw_bytes = ser.read(128)
                    if not raw_bytes:
                        continue

                    # Feed binary stream into parser
                    packets = self.parser.feed(raw_bytes)
                    now_ts = time.time()

                    for frame_type, parsed_data in packets:
                        packet_count += 1
                        
                        # We trigger database batching primarily on complete Angle (0x53) or Accel (0x51) packets
                        if frame_type in (WT901CParser.TYPE_ANGLE, WT901CParser.TYPE_ACCEL):
                            reading = dict(self.parser.current_readings)
                            reading["timestamp"] = now_ts
                            buffer_batch.append(reading)

                    # Flush buffer if batch size reached or 1 second elapsed
                    if len(buffer_batch) >= self.batch_size or (now_ts - last_flush_time >= 1.0 and buffer_batch):
                        inserted = self.storage.insert_batch(buffer_batch)
                        buffer_batch.clear()
                        last_flush_time = now_ts

                    # Output periodic throughput statistics every 10 seconds
                    if now_ts - last_stat_time >= 10.0:
                        hz = packet_count / (now_ts - last_stat_time)
                        stats = self.storage.get_db_stats()
                        logger.info(
                            f"Live Rate: {hz:.1f} Hz | Total Rows: {stats['total_raw_rows']} | "
                            f"Roll: {self.parser.current_readings['roll']:.2f}° | "
                            f"Pitch: {self.parser.current_readings['pitch']:.2f}° | "
                            f"Yaw: {self.parser.current_readings['yaw']:.2f}° | "
                            f"RMS Accel: {self.parser.current_readings['rms_accel']:.3f}g"
                        )
                        packet_count = 0
                        last_stat_time = now_ts

            except (serial.SerialException, OSError) as se:
                logger.error(f"Serial port connection lost: {se}. Re-scanning in 3 seconds...")
            except Exception as ex:
                logger.error(f"Unexpected error in collector loop: {ex}", exc_info=True)
            finally:
                try:
                    if ser and ser.is_open:
                        ser.close()
                except Exception:
                    pass

                # Flush remaining in-memory buffer before reconnect
                if buffer_batch:
                    self.storage.insert_batch(buffer_batch)
                    buffer_batch.clear()

                time.sleep(3)

        logger.info("Collector stopped gracefully.")

def main():
    parser = argparse.ArgumentParser(description="WT901C Serial Data Collector")
    parser.add_argument("--port", type=str, default=None, help="Serial port path (e.g. /dev/ttyUSB0, /dev/tty.usbserial-110). If omitted, auto-discovers.")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    parser.add_argument("--db-dir", type=str, default="data", help="Directory storing SQLite database")
    parser.add_argument("--batch-size", type=int, default=50, help="Batch write buffer size (default: 50)")
    args = parser.parse_args()

    target_port = args.port
    if target_port and target_port.lower() in ("auto", ""):
        target_port = None

    collector = SerialCollector(
        port=target_port,
        baudrate=args.baud,
        db_dir=args.db_dir,
        batch_size=args.batch_size
    )
    collector.run()

if __name__ == "__main__":
    main()
