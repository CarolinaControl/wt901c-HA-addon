import unittest
from wt901c_parser import WT901CParser

class TestWT901CParser(unittest.TestCase):
    def setUp(self):
        self.parser = WT901CParser()

    def test_checksum_verification(self):
        # Sample valid frame header 0x55 0x51 ... checksum
        # Frame: 0x55, 0x51, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, checksum
        bytes_10 = bytes([0x55, 0x51, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        checksum = sum(bytes_10) & 0xFF
        valid_frame = bytes_10 + bytes([checksum])
        self.assertTrue(WT901CParser.verify_checksum(valid_frame))

        invalid_frame = bytes_10 + bytes([(checksum + 1) & 0xFF])
        self.assertFalse(WT901CParser.verify_checksum(invalid_frame))

    def test_parse_accel(self):
        # 1g acceleration along Z-axis (32768/16 = 2048) -> 2048 in int16 LE = 0x00, 0x08
        # ax=0, ay=0, az=2048 (1.0g), temp=2500 (25.0 C) -> 2500 in LE = 0xC4, 0x09
        d0, d1, d2, d3 = 0, 0, 2048, 2500
        import struct
        payload = struct.pack('<hhhh', d0, d1, d2, d3)
        header = bytes([0x55, 0x51]) + payload
        cs = sum(header) & 0xFF
        frame = header + bytes([cs])

        res = self.parser.parse_frame(frame)
        self.assertIsNotNone(res)
        self.assertAlmostEqual(res["ax"], 0.0)
        self.assertAlmostEqual(res["ay"], 0.0)
        self.assertAlmostEqual(res["az"], 1.0)
        self.assertAlmostEqual(res["rms_accel"], 1.0)
        self.assertAlmostEqual(res["temp"], 77.0)

    def test_parse_angle(self):
        # Roll = 45 deg -> 45/180 * 32768 = 8192 (0x00, 0x20)
        # Pitch = -10 deg -> -10/180 * 32768 = -1820
        # Yaw = 90 deg -> 90/180 * 32768 = 16384
        d0 = 8192
        d1 = -1820
        d2 = 16384
        d3 = 0
        import struct
        payload = struct.pack('<hhhh', d0, d1, d2, d3)
        header = bytes([0x55, 0x53]) + payload
        cs = sum(header) & 0xFF
        frame = header + bytes([cs])

        res = self.parser.parse_frame(frame)
        self.assertIsNotNone(res)
        self.assertAlmostEqual(res["roll"], 45.0, delta=0.01)
        self.assertAlmostEqual(res["pitch"], -10.0, delta=0.01)
        self.assertAlmostEqual(res["yaw"], 90.0, delta=0.01)

    def test_feed_stream(self):
        # Test stream feeding with noise before valid frame
        d0, d1, d2, d3 = 0, 0, 2048, 2500
        import struct
        payload = struct.pack('<hhhh', d0, d1, d2, d3)
        header = bytes([0x55, 0x51]) + payload
        cs = sum(header) & 0xFF
        valid_frame = header + bytes([cs])

        raw_stream = bytes([0x00, 0xFF, 0x12]) + valid_frame + bytes([0xAA, 0xBB])
        packets = self.parser.feed(raw_stream)
        self.assertEqual(len(packets), 1)
        self.assertEqual(packets[0][0], 0x51)

if __name__ == '__main__':
    unittest.main()
