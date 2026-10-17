import unittest
import cv2
import numpy as np
from jetbot_target_follower.vision import MarkerDetector, quaternion_from_rvec


class VisionTests(unittest.TestCase):
    def setUp(self):
        self.k = np.array([[600., 0, 424], [0, 600., 240], [0, 0, 1]])
        self.d = np.zeros(5)
        self.detector = MarkerDetector()

    def synthetic_image(self, marker_id=0, x=0.0, distance=1.5):
        dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        draw_marker = (cv2.aruco.generateImageMarker
                       if hasattr(cv2.aruco, 'generateImageMarker')
                       else cv2.aruco.drawMarker)
        marker = draw_marker(dictionary, marker_id, 240)
        half = .12
        points = np.array([[-half,half,0],[half,half,0],[half,-half,0],[-half,-half,0]])
        rotation = np.array([np.pi, 0., 0.])
        translation = np.array([x, 0., distance])
        pixels, _ = cv2.projectPoints(points, rotation, translation, self.k, self.d)
        transform = cv2.getPerspectiveTransform(np.float32([[0,0],[239,0],[239,239],[0,239]]),
                                                pixels.reshape(4,2).astype(np.float32))
        gray = cv2.warpPerspective(marker, transform, (848,480), borderValue=255)
        return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

    def test_range_and_lateral_position(self):
        for x, distance in [(0.,1.5),(.2,1.),(-.25,2.)]:
            with self.subTest(x=x,distance=distance):
                result = self.detector.detect(self.synthetic_image(x=x,distance=distance),self.k,self.d)
                self.assertIsNotNone(result)
                np.testing.assert_allclose(result[2], [x,0,distance], atol=.03)
                self.assertLess(result[3], 1.)

    def test_wrong_marker_is_not_target(self):
        self.assertIsNone(self.detector.detect(self.synthetic_image(marker_id=1),self.k,self.d))

    def test_blank_and_hidden_target(self):
        frame = self.synthetic_image()
        frame[140:340,324:524] = 255
        self.assertIsNone(self.detector.detect(frame,self.k,self.d))
        self.assertIsNone(self.detector.detect(np.full_like(frame,255),self.k,self.d))

    def test_invalid_marker_parameters(self):
        for args in [('DICT_BAD',0,.24),('DICT_4X4_50',50,.24),('DICT_4X4_50',0,0.)]:
            with self.assertRaises(ValueError): MarkerDetector(*args)

    def test_rotation_quaternion(self):
        np.testing.assert_allclose(quaternion_from_rvec(np.array([np.pi,0.,0.])),[1,0,0,0],atol=1e-10)


if __name__ == '__main__':
    unittest.main()
