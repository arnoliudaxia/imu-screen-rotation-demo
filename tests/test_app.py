import unittest

from imu_reader.app import App


class ValueLayoutTests(unittest.TestCase):
    def test_fields_wrap_in_pairs(self):
        class Capture:
            def set(self, value):
                self.value = value

        class Stub:
            values = {'q_w': 1.0, 'q_x': 2.0, 'q_y': 3.0, 'q_z': 4.0,
                      'roll_deg': 10.0, 'pitch_deg': 20.0, 'yaw_deg': 30.0}
            info = Capture()

        stub = Stub()
        App.update_values(stub)
        lines = stub.info.value.splitlines()
        self.assertTrue(all(line.count(':') <= 2 for line in lines))
        self.assertIn('z:    4.0000', stub.info.value)
        self.assertIn('yaw:   30.0000', stub.info.value)


if __name__ == '__main__':
    unittest.main()
