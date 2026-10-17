import os
import math

import yaml
import shutil
import subprocess
import threading
import time

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo, Image


def load_camera_info(path, width, height):
    """Load calibration for the exact raw capture resolution; never use a dummy K."""
    with open(path, encoding='utf-8') as stream:
        data = yaml.safe_load(stream)
    if not isinstance(data, dict):
        raise ValueError('Calibration YAML must be a mapping')
    if (data.get('image_width'), data.get('image_height')) != (width, height):
        raise ValueError('Calibration resolution does not match camera capture')
    if data.get('distortion_model') not in ('plumb_bob', 'rational_polynomial'):
        raise ValueError('Unsupported distortion model')

    def matrix(name, rows, columns):
        value = data[name]
        values = [float(v) for v in value['data']]
        if (value['rows'], value['cols']) != (rows, columns):
            raise ValueError('Invalid matrix dimensions: ' + name)
        if len(values) != rows * columns or not all(math.isfinite(v) for v in values):
            raise ValueError('Invalid matrix values: ' + name)
        return values

    info = CameraInfo()
    info.width, info.height = width, height
    info.distortion_model = data['distortion_model']
    info.k = matrix('camera_matrix', 3, 3)
    info.r = matrix('rectification_matrix', 3, 3)
    info.p = matrix('projection_matrix', 3, 4)
    columns = data['distortion_coefficients']['cols']
    allowed = (4, 5) if info.distortion_model == 'plumb_bob' else (8,)
    if columns not in allowed:
        raise ValueError('Invalid distortion coefficient count')
    info.d = matrix('distortion_coefficients', 1, columns)
    if info.k[0] <= 0 or info.k[4] <= 0 or abs(info.k[8] - 1.0) > 1e-6:
        raise ValueError('Invalid camera intrinsic matrix')
    return info


class ImagePublisher(Node):
    def __init__(self):
        super().__init__('pi_image_raw_publisher')

        self.sensor_id = 0
        self.width = 1280
        self.height = 720
        self.fps = 30
        self.frame_bytes = self.width * self.height * 3

        calibration_file = self.declare_parameter(
            'calibration_file',
            os.path.expanduser('~/ros2_ws/src/pi_camera_ros/config/jetbot5.yaml'),
        ).value
        self.camera_info = load_camera_info(calibration_file, self.width, self.height)
        self._info_publisher = self.create_publisher(
            CameraInfo, '/camera/camera_info', 1
        )
        self.get_logger().info('Calibration loaded: ' + calibration_file)

        self._publisher = self.create_publisher(
            Image, '/camera/image/raw', 1
        )

        self._lock = threading.Lock()
        self._latest = None
        self._eof = False
        self._last_frame = time.monotonic()

        # Проверяем необходимые команды и плагины.
        for command in ('gst-launch-1.0', 'gst-inspect-1.0'):
            if shutil.which(command) is None:
                raise RuntimeError(f'Не найдена команда {command}')

        for plugin in (
            'nvarguscamerasrc', 'nvvidconv', 'videoconvert', 'fdsink'
        ):
            subprocess.run(
                ['gst-inspect-1.0', plugin],
                stdout=subprocess.DEVNULL,
                check=True,
            )

        # Отдельный канал для байтов изображения.
        read_fd, write_fd = os.pipe()

        pipeline = [
            'gst-launch-1.0', '-q',
            'nvarguscamerasrc', f'sensor-id={self.sensor_id}',
            '!', (
                f'video/x-raw(memory:NVMM),width={self.width},'
                f'height={self.height},format=NV12,'
                f'framerate={self.fps}/1'
            ),
            '!', 'nvvidconv',
            '!', 'video/x-raw,format=BGRx',
            '!', 'videoconvert',
            '!', 'video/x-raw,format=BGR',
            '!', 'fdsink', f'fd={write_fd}', 'sync=false',
        ]

        try:
            self.process = subprocess.Popen(
                pipeline,
                pass_fds=(write_fd,),
            )
        except Exception:
            os.close(read_fd)
            raise
        finally:
            os.close(write_fd)

        self._pipe = os.fdopen(read_fd, 'rb')
        self._thread = threading.Thread(
            target=self._read_frames,
            daemon=True,
        )
        self._thread.start()

        self.timer = self.create_timer(
            1.0 / self.fps,
            self.frame_publishing_callback,
        )
        self.get_logger().info(
            'GStreamer запущен; ожидаю кадры камеры...'
        )

    def _read_frames(self):
        try:
            while True:
                data = bytearray()

                # Собираем полный кадр: чтение может вернуть его часть.
                while len(data) < self.frame_bytes:
                    chunk = self._pipe.read(
                        self.frame_bytes - len(data)
                    )
                    if not chunk:
                        return
                    data.extend(chunk)

                with self._lock:
                    self._latest = bytes(data)
                    self._last_frame = time.monotonic()
        finally:
            self._eof = True

    def frame_publishing_callback(self):
        if self._eof or self.process.poll() is not None:
            raise RuntimeError(
                'GStreamer завершился: смотрите сообщения выше.'
            )

        with self._lock:
            data = self._latest
            self._latest = None
            last_frame = self._last_frame

        if data is None:
            if time.monotonic() - last_frame > 30:
                raise RuntimeError(
                    'Камера не передаёт кадры более 30 секунд.'
                )
            return

        msg = Image()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'camera_optical_frame'
        msg.height = self.height
        msg.width = self.width
        msg.encoding = 'bgr8'
        msg.is_bigendian = 0
        msg.step = self.width * 3
        msg.data.frombytes(data)

        # Raw image and calibration refer to the same captured frame.
        self.camera_info.header = msg.header
        self._info_publisher.publish(self.camera_info)
        self._publisher.publish(msg)

    def close_camera(self):
        self.timer.cancel()

        if self.process.poll() is None:
            self.process.terminate()

        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()

        self._thread.join()
        self._pipe.close()


def main(args=None):
    rclpy.init(args=args)
    node = None

    try:
        node = ImagePublisher()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.close_camera()
            node.destroy_node()

        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
