import unittest
from pathlib import Path
import xml.etree.ElementTree as ET
from jetbot_target_follower.control import ControlConfig, Follower


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.config=ControlConfig();self.follower=Follower()

    def step(self,target=(2.,0.),**kw):
        return self.follower.step(self.config,target,1.,.05,**kw)

    def test_speeds_are_limited(self):
        for _ in range(100):v,w,s=self.step((3.,.3))
        self.assertLessEqual(abs(v),self.config.max_linear_speed)
        self.assertLessEqual(abs(w),self.config.max_angular_speed)
        self.assertGreater(v,0)

    def test_turn_before_forward_motion(self):
        v,w,s=self.step((1.,1.))
        self.assertEqual(v,0);self.assertGreater(w,0);self.assertEqual(s,'ALIGN')

    def test_arrival_hysteresis_and_resume(self):
        self.assertEqual(self.step((.51,0.))[2],'ARRIVED')
        self.assertEqual(self.step((.54,0.))[2],'ARRIVED')
        self.assertEqual(self.step((.7,0.))[2],'APPROACH')

    def test_image_loss_overrides_search(self):
        self.assertEqual(self.step(None,image_fresh=False),(0.,0.,'NO_IMAGE'))
        v,w,s=self.step(None)
        self.assertEqual(v,0);self.assertNotEqual(w,0);self.assertEqual(s,'SEARCH')

    def test_manual_override_and_disable(self):
        self.step()
        self.assertEqual(self.step(manual=True),(0.,0.,'MANUAL'))
        self.assertEqual(self.step(enabled=False),(0.,0.,'DISABLED'))

    def test_reverse_when_too_close(self):
        self.assertLess(self.step((.3,0.))[0],0)

    def test_total_robot_mass(self):
        model=Path(__file__).resolve().parents[1]/'models/jetbot_hw1_drive/model.sdf'
        mass=sum(float(x.text) for x in ET.parse(model).findall('.//link/inertial/mass'))
        self.assertAlmostEqual(mass,1.5,places=8)

    def test_bad_parameters_rejected(self):
        for cfg in [ControlConfig(stop_distance=-1),ControlConfig(max_linear_speed=float('nan')),
                    ControlConfig(distance_tolerance=.6)]:
            with self.assertRaises(ValueError):cfg.validate()


if __name__=='__main__':unittest.main()
