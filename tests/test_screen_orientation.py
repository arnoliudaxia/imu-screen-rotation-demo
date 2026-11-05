import math
import unittest
from imu_reader.screen_orientation import Orientation, angle, simulated_up, quaternion_up, acceleration_up

class ScreenOrientationTests(unittest.TestCase):
    def test_four_directions(self):
        for degrees, expected in [(0,(1,0)),(90,(0,-1)),(180,(-1,0)),(270,(0,1))]:
            up = simulated_up(degrees)
            self.assertAlmostEqual(up[0], expected[0]); self.assertAlmostEqual(up[1], expected[1])
            self.assertAlmostEqual(angle(up), degrees)
            self.assertEqual(Orientation().update(up, 0), degrees)
    def test_hysteresis_dwell_and_wrap(self):
        o=Orientation()
        self.assertEqual(o.update(simulated_up(0),0),0)
        for t,a in [(1,50),(2,56),(3,359)]: self.assertEqual(o.update(simulated_up(a),t),0)
        self.assertEqual(o.update(simulated_up(58),4),0)
        self.assertEqual(o.update(simulated_up(58),4.2),0)
        self.assertEqual(o.update(simulated_up(58),4.26),90)
    def test_flat_cancels_pending(self):
        o=Orientation(); o.update(simulated_up(0),0); o.update(simulated_up(90),1)
        self.assertEqual(o.update(simulated_up(90,0),2),0)
        self.assertEqual(o.update(simulated_up(90),3),0)
        self.assertEqual(o.update(simulated_up(90),3.3),90)
        self.assertIsNone(Orientation().update(simulated_up(0,0),0))
    def test_quaternion(self):
        for q,expected in [((1,0,0,0),(0,0,1)),((math.sqrt(.5),0,math.sqrt(.5),0),(-1,0,0)),((math.sqrt(.5),math.sqrt(.5),0,0),(0,1,0))]:
            for a,b in zip(quaternion_up(q),expected): self.assertAlmostEqual(a,b)
    def test_invalid(self):
        for v in [(0,0,0), (float("nan"),0,1), (float("inf"),0,1)]:
            self.assertIsNone(acceleration_up(v)); self.assertIsNone(angle(v))
        self.assertIsNone(quaternion_up((0,0,0,0))); self.assertIsNone(quaternion_up((float("nan"),0,0,0)))
        self.assertEqual(acceleration_up((0,0,-9.8)),(0,0,1))
        o=Orientation(); o.update(simulated_up(0),0); self.assertEqual(o.update((0,0,0),1),0)
