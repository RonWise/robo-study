"""Check measured Jetbot camera geometry independently of the Euler-angle convention."""
import math
from pathlib import Path
import unittest

import numpy as np
import yaml
from jetbot_target_follower.follower import rotation_rpy


class CameraTransformTests(unittest.TestCase):
    def test_downward_camera_axes_and_axle_distance(self):
        path = Path(__file__).resolve().parents[1] / 'config/follower_jetbot5.yaml'
        params = yaml.safe_load(path.read_text())['target_follower']['ros__parameters']
        rotation = rotation_rpy(*params['camera_rotation_rpy'])
        translation = np.array(params['camera_translation'])
        angle = math.radians(15)
        c, s = math.cos(angle), math.sin(angle)
        # The optical axis points forward and down; image-right is robot-right.
        np.testing.assert_allclose(rotation @ [0, 0, 1], [c, 0, -s], atol=1e-12)
        np.testing.assert_allclose(rotation @ [1, 0, 0], [0, -1, 0], atol=1e-12)
        np.testing.assert_allclose(rotation @ [0, 1, 0], [-s, 0, -c], atol=1e-12)
        # Marker at lens height, 45 cm ahead of lens = 50 cm ahead of wheel axle.
        for lateral in [0., .1, -.1]:
            camera_point = np.array([-lateral, -.45 * s, .45 * c])
            body_point = rotation @ camera_point + translation
            np.testing.assert_allclose(body_point[:2], [.5, lateral], atol=1e-12)


if __name__ == '__main__':
    unittest.main()
