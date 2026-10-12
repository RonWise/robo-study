"""ArUco measurement in camera optical coordinates (x right, y down, z forward)."""
import cv2
import numpy as np


class MarkerDetector:
    def __init__(self, dictionary_name='DICT_4X4_50', marker_id=0, marker_size=0.24):
        if not dictionary_name.startswith('DICT_') or not hasattr(cv2.aruco, dictionary_name):
            raise ValueError('Unknown ArUco dictionary: ' + dictionary_name)
        self.dictionary = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, dictionary_name))
        if not 0 <= marker_id < len(self.dictionary.bytesList):
            raise ValueError('marker_id is outside dictionary')
        if not np.isfinite(marker_size) or marker_size <= 0:
            raise ValueError('marker_size must be positive (metres)')
        self.marker_id = marker_id
        self.marker_size = marker_size
        self.parameters = (cv2.aruco.DetectorParameters_create()
                           if hasattr(cv2.aruco, 'DetectorParameters_create')
                           else cv2.aruco.DetectorParameters())
        self.parameters.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
        self.detector = (cv2.aruco.ArucoDetector(self.dictionary, self.parameters)
                         if hasattr(cv2.aruco, 'ArucoDetector') else None)

    def detect(self, bgr, matrix, distortion):
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        if self.detector is not None:
            corners, ids, _ = self.detector.detectMarkers(gray)
        else:
            corners, ids, _ = cv2.aruco.detectMarkers(
                gray, self.dictionary, parameters=self.parameters)
        if ids is None:
            return None
        matches = np.flatnonzero(ids.reshape(-1) == self.marker_id)
        if not len(matches):
            return None
        # Select largest if the same ID appears more than once.
        index = max(matches, key=lambda i: abs(cv2.contourArea(corners[i][0])))
        image_points = corners[index].reshape(4, 2)
        half = self.marker_size / 2
        object_points = np.array([
            [-half, half, 0], [half, half, 0],
            [half, -half, 0], [-half, -half, 0]], dtype=np.float64)
        ok, rotation, translation = cv2.solvePnP(
            object_points, image_points.astype(np.float64), matrix, distortion,
            flags=cv2.SOLVEPNP_ITERATIVE)
        if not ok or not np.isfinite(translation).all() or translation[2, 0] <= 0:
            return None
        projected, _ = cv2.projectPoints(object_points, rotation, translation, matrix, distortion)
        error = float(np.sqrt(np.mean(np.sum(
            (projected.reshape(4, 2) - image_points) ** 2, axis=1))))
        return image_points, rotation.reshape(3), translation.reshape(3), error


def quaternion_from_rvec(rotation):
    angle = float(np.linalg.norm(rotation))
    if angle < 1e-12:
        return 0.0, 0.0, 0.0, 1.0
    xyz = rotation / angle * np.sin(angle / 2)
    return float(xyz[0]), float(xyz[1]), float(xyz[2]), float(np.cos(angle / 2))
