import unittest
from pd_drone.control import velocity, fresh

class ControlTests(unittest.TestCase):
    def test_camera_axis_mapping(self):
        self.assertEqual(velocity((320,240),640,480,4),(0.,0.))
        forward,right=velocity((400,160),640,480,4)
        self.assertGreater(forward,0)
        self.assertGreater(right,0)
    def test_speed_bound_and_lost_target(self):
        f,r=velocity((10000,-10000),640,480,4)
        self.assertAlmostEqual((f*f+r*r)**.5,.7)
        self.assertEqual(velocity(None,640,480,4),(0.,0.))
    def test_stale_or_future_frames(self):
        self.assertFalse(fresh(0,1))
        self.assertFalse(fresh(1,2))
        self.assertFalse(fresh(3,2))
        self.assertTrue(fresh(1,1.2))

if __name__=='__main__': unittest.main()
