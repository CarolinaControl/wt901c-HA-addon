import struct
import math
from typing import Dict, Any, Optional, Tuple, List

class WT901CParser:
    """
    Parser for WitMotion WT901C / WT901 series 9-axis sensor serial binary frames.
    Each valid frame is 11 bytes long, starting with header byte 0x55.
    
    Data Types:
    0x51: Acceleration (Ax, Ay, Az, Temperature)
    0x52: Gyroscope / Angular Velocity (Wx, Wy, Wz, Temperature)
    0x53: Angle / Tilt (Roll, Pitch, Yaw, Temperature/Version)
    0x54: Magnetometer (Hx, Hy, Hz, Temperature)
    """

    HEADER = 0x55
    FRAME_LEN = 11

    TYPE_ACCEL = 0x51
    TYPE_GYRO = 0x52
    TYPE_ANGLE = 0x53
    TYPE_MAG = 0x54

    def __init__(self):
        self._buffer = bytearray()
        
        # State tracking for combined reading frame
        self.current_readings: Dict[str, Any] = {
            "ax": 0.0, "ay": 0.0, "az": 0.0,
            "wx": 0.0, "wy": 0.0, "wz": 0.0,
            "roll": 0.0, "pitch": 0.0, "yaw": 0.0,
            "hx": 0.0, "hy": 0.0, "hz": 0.0,
            "rms_accel": 0.0,
            "temp": 0.0
        }

    @staticmethod
    def verify_checksum(frame: bytes) -> bool:
        """Verify WitMotion 11-byte frame checksum: sum of first 10 bytes & 0xFF == 11th byte."""
        if len(frame) != WT901CParser.FRAME_LEN:
            return False
        return (sum(frame[:10]) & 0xFF) == frame[10]

    def parse_frame(self, frame: bytes) -> Optional[Dict[str, Any]]:
        """
        Parse an 11-byte frame and update reading state.
        Returns a dictionary of updated attributes if frame is valid.
        """
        if not self.verify_checksum(frame):
            return None

        frame_type = frame[1]
        
        # Decode signed 16-bit short values
        # bytes [2..9] format: 4 x int16 little-endian
        d0, d1, d2, d3 = struct.unpack('<hhhh', frame[2:10])

        result: Dict[str, Any] = {"type": frame_type}

        if frame_type == self.TYPE_ACCEL:
            # Acceleration in 'g' (range +/- 16g)
            self.current_readings["ax"] = (d0 / 32768.0) * 16.0
            self.current_readings["ay"] = (d1 / 32768.0) * 16.0
            self.current_readings["az"] = (d2 / 32768.0) * 16.0
            temp_c = d3 / 100.0
            self.current_readings["temp"] = (temp_c * 1.8) + 32.0
            
            # Calculate RMS acceleration magnitude (vibration indicator)
            ax = self.current_readings["ax"]
            ay = self.current_readings["ay"]
            az = self.current_readings["az"]
            self.current_readings["rms_accel"] = math.sqrt(ax * ax + ay * ay + az * az)

            result.update({
                "ax": self.current_readings["ax"],
                "ay": self.current_readings["ay"],
                "az": self.current_readings["az"],
                "rms_accel": self.current_readings["rms_accel"],
                "temp": self.current_readings["temp"]
            })

        elif frame_type == self.TYPE_GYRO:
            # Gyro / Angular velocity in deg/s (range +/- 2000 deg/s)
            self.current_readings["wx"] = (d0 / 32768.0) * 2000.0
            self.current_readings["wy"] = (d1 / 32768.0) * 2000.0
            self.current_readings["wz"] = (d2 / 32768.0) * 2000.0
            temp_c = d3 / 100.0
            self.current_readings["temp"] = (temp_c * 1.8) + 32.0
            
            result.update({
                "wx": self.current_readings["wx"],
                "wy": self.current_readings["wy"],
                "wz": self.current_readings["wz"],
                "temp": self.current_readings["temp"]
            })

        elif frame_type == self.TYPE_ANGLE:
            # Angle in degrees (range +/- 180 deg)
            self.current_readings["roll"] = (d0 / 32768.0) * 180.0
            self.current_readings["pitch"] = (d1 / 32768.0) * 180.0
            self.current_readings["yaw"] = (d2 / 32768.0) * 180.0
            
            result.update({
                "roll": self.current_readings["roll"],
                "pitch": self.current_readings["pitch"],
                "yaw": self.current_readings["yaw"],
            })

        elif frame_type == self.TYPE_MAG:
            self.current_readings["hx"] = float(d0)
            self.current_readings["hy"] = float(d1)
            self.current_readings["hz"] = float(d2)
            temp_c = d3 / 100.0
            self.current_readings["temp"] = (temp_c * 1.8) + 32.0

            result.update({
                "hx": self.current_readings["hx"],
                "hy": self.current_readings["hy"],
                "hz": self.current_readings["hz"],
                "temp": self.current_readings["temp"]
            })

        return result

    def feed(self, raw_bytes: bytes) -> List[Tuple[int, Dict[str, Any]]]:
        """
        Feed byte stream into internal ring buffer and yield parsed packets.
        Returns list of (frame_type, parsed_dict) tuples.
        """
        self._buffer.extend(raw_bytes)
        parsed_packets = []

        while len(self._buffer) >= self.FRAME_LEN:
            # Find header byte 0x55
            try:
                header_idx = self._buffer.index(self.HEADER)
            except ValueError:
                # Header not found in entire buffer
                self._buffer.clear()
                break

            if header_idx > 0:
                # Discard invalid bytes prior to header
                del self._buffer[:header_idx]

            if len(self._buffer) < self.FRAME_LEN:
                break

            frame = bytes(self._buffer[:self.FRAME_LEN])
            if self.verify_checksum(frame):
                frame_type = frame[1]
                pkt = self.parse_frame(frame)
                if pkt:
                    parsed_packets.append((frame_type, pkt))
                # Advance buffer by 11 bytes
                del self._buffer[:self.FRAME_LEN]
            else:
                # Invalid checksum; skip header byte and search for next frame
                del self._buffer[0]

        return parsed_packets
