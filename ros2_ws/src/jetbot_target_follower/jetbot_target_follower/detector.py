"""Stationary HW1 perception: no velocity publishers or motion controllers."""
import time

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from geometry_msgs.msg import PoseStamped
from rclpy.node import Node
from rcl_interfaces.msg import ParameterDescriptor
from rclpy.clock import Clock, ClockType
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CameraInfo, Image
from std_msgs.msg import Bool, Float64

from .vision import MarkerDetector, quaternion_from_rvec


# Узел распознавания: Image + CameraInfo → поза, расстояние, видимость и отладочный кадр.
# Команды движения здесь не вычисляются: их публикует отдельный target_follower.
class TargetDetector(Node):
    def __init__(self):
        super().__init__('target_detector')
        # Значения для симулятора; параметры реального Jetbot передаются через YAML.
        # marker_size — сторона всего чёрного квадрата с рамкой, в метрах.
        defaults = {
            'dictionary': 'DICT_4X4_50', 'marker_id': 0, 'marker_size': 0.24,
            'image_topic': '/camera/image/raw',
            'camera_info_topic': '/camera/camera_info',
            'optical_frame': 'camera_optical_frame',
            'detection_timeout': 1.0, 'max_reprojection_error': 3.0,
        }
        # Детектор создаётся один раз, поэтому смена параметров требует перезапуска узла.
        for key, value in defaults.items():
            self.declare_parameter(key, value, ParameterDescriptor(read_only=True))
        p = lambda name: self.get_parameter(name).value
        self.detector = MarkerDetector(p('dictionary'), p('marker_id'), p('marker_size'))
        self.timeout = float(p('detection_timeout'))
        self.max_error = float(p('max_reprojection_error'))
        if self.timeout <= 0 or self.max_error <= 0:
            raise ValueError('timeouts and error limits must be positive')
        self.optical_frame = p('optical_frame')
        self.bridge = CvBridge()
        self.calibration = None
        self.last_detection = None
        self.last_log = 0.0
        # Очередь из одного сообщения не накапливает историю измерений у издателя.
        self.pose_pub = self.create_publisher(PoseStamped, '/target/pose', 1)
        self.distance_pub = self.create_publisher(Float64, '/target/distance', 1)
        self.visible_pub = self.create_publisher(Bool, '/target/visible', 1)
        self.debug_pub = self.create_publisher(Image, '/target/debug_image', 1)
        # QoS сенсорных данных допускает потерю кадров и совместим с best-effort источниками.
        self.create_subscription(CameraInfo, p('camera_info_topic'), self.on_info,
                                 qos_profile_sensor_data)
        self.create_subscription(Image, p('image_topic'), self.on_image,
                                 qos_profile_sensor_data)
        # Тайм-аут продолжает отсчитываться даже при остановке часов Gazebo.
        self.create_timer(0.2, self.on_timeout,
                          clock=Clock(clock_type=ClockType.STEADY_TIME))
        self.get_logger().info('Waiting for image and CameraInfo; detector publishes measurements only.')

    # Храним последнюю пригодную калибровку; синхронизации CameraInfo с кадрами здесь нет.
    def on_info(self, msg):
        # K содержит фокусные расстояния и главную точку, D — коэффициенты дисторсии.
        matrix = np.asarray(msg.k, dtype=np.float64).reshape(3, 3)
        distortion = np.asarray(msg.d, dtype=np.float64)
        if (msg.distortion_model not in ('', 'plumb_bob', 'rational_polynomial')
                or not np.isfinite(matrix).all() or not np.isfinite(distortion).all()
                or matrix[0, 0] <= 0 or matrix[1, 1] <= 0):
            self.calibration = None
            return
        self.calibration = (matrix, distortion, msg.width, msg.height)

    # При исчезновении потока кадров нельзя бессрочно оставлять visible=true.
    def on_timeout(self):
        if self.last_detection is None or time.monotonic() - self.last_detection > self.timeout:
            self.visible_pub.publish(Bool(data=False))

    def on_image(self, msg):
        if self.calibration is None:
            self.get_logger().warning('No valid CameraInfo yet.', throttle_duration_sec=5.0)
            self.visible_pub.publish(Bool(data=False))
            return
        # Калибровка другого разрешения без пересчёта K даст неверную оценку расстояния.
        matrix, distortion, width, height = self.calibration
        if (msg.width, msg.height) != (width, height):
            self.get_logger().error('Image and CameraInfo sizes differ.', throttle_duration_sec=5.0)
            self.visible_pub.publish(Bool(data=False))
            return
        try:
            # CvBridge переводит ROS Image в BGR-массив OpenCV; алгоритм вынесен в vision.py.
            frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
            result = self.detector.detect(frame, matrix, distortion)
        except (cv2.error, ValueError) as exc:
            self.get_logger().error(str(exc), throttle_duration_sec=5.0)
            self.visible_pub.publish(Bool(data=False))
            return
        # Отбрасываем позу, если её углы плохо совпадают с найденными на изображении.
        # Порог — среднеквадратичная ошибка обратного проецирования в пикселях.
        found = result is not None and result[3] <= self.max_error
        self.visible_pub.publish(Bool(data=bool(found)))
        debug = frame.copy()
        if found:
            corners, rotation, translation, error = result
            self.last_detection = time.monotonic()
            pose = PoseStamped()
            # Сохраняем время исходного кадра, чтобы регулятор мог отбросить запоздавшую позу.
            pose.header.stamp = msg.header.stamp
            # PnP использует оптические оси: x вправо, y вниз, z вперёд.
            # frame_id только называет систему; TF-преобразование этим не создаётся.
            pose.header.frame_id = self.optical_frame
            pose.pose.position.x, pose.pose.position.y, pose.pose.position.z = map(float, translation)
            q = quaternion_from_rvec(rotation)
            pose.pose.orientation.x, pose.pose.orientation.y = q[0], q[1]
            pose.pose.orientation.z, pose.pose.orientation.w = q[2], q[3]
            # Это пространственное расстояние от камеры, не расстояние от оси колёс.
            distance = float(np.linalg.norm(translation))
            self.pose_pub.publish(pose)
            self.distance_pub.publish(Float64(data=distance))
            cv2.polylines(debug, [corners.astype(np.int32)], True, (0, 255, 0), 2)
            cv2.drawFrameAxes(debug, matrix, distortion, rotation, translation,
                             self.detector.marker_size / 2)
            caption = f'ID {self.detector.marker_id}  range {distance:.3f} m  depth {translation[2]:.3f} m'
            if time.monotonic() - self.last_log > 2:
                self.get_logger().info(caption + f'  reprojection {error:.2f} px')
                self.last_log = time.monotonic()
        else:
            # При потере цели не публикуем фиктивную нулевую позу или дистанцию.
            # Потребитель должен учитывать visible и возраст последней позы.
            caption = f'ID {self.detector.marker_id}: NOT VISIBLE'
        cv2.putText(debug, caption, (12, 28), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, (0, 180, 0) if found else (0, 0, 255), 2)
        # Рамка и подписи нужны только для просмотра; регулятор использует числовую позу.
        out = self.bridge.cv2_to_imgmsg(debug, encoding='bgr8')
        out.header = msg.header
        self.debug_pub.publish(out)


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = TargetDetector()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
