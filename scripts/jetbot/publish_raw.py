import os
import shutil
import subprocess
import threading
import time

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image


class ImagePublisher(Node):
    def __init__(self):
        super().__init__('pi_image_raw_publisher')
        self.width, self.height, self.fps = 1280, 720, 30
        self.sensor_id = 0
        self.frame_bytes = self.width * self.height * 3
        self._publisher = self.create_publisher(Image, '/camera/image/raw', 1)
        self._lock = threading.Lock()
        self._latest = None
        self._eof = False
        self._last_frame = time.monotonic()

        for command in ('gst-launch-1.0', 'gst-inspect-1.0'):
            if shutil.which(command) is None:
                raise RuntimeError(f'Не найдена команда {command}')
        for plugin in ('nvarguscamerasrc', 'nvvidconv', 'videoconvert', 'fdsink'):
            subprocess.run(['gst-inspect-1.0', plugin],
                           stdout=subprocess.DEVNULL, check=True)

        # Отдельный канал кадров: сообщения NVIDIA в stdout не испортят видео.
        read_fd, write_fd = os.pipe()
        pipeline = [
            'gst-launch-1.0', '-q',
            'nvarguscamerasrc', f'sensor-id={self.sensor_id}',
            '!', (f'video/x-raw(memory:NVMM),width={self.width},'
                  f'height={self.height},format=NV12,framerate={self.fps}/1'),
            '!', 'nvvidconv',
            '!', 'video/x-raw,format=BGRx',
            '!', 'videoconvert',
            '!', 'video/x-raw,format=BGR',
            '!', 'fdsink', f'fd={write_fd}', 'sync=false',
        ]
        try:
            self.process = subprocess.Popen(
                pipeline, pass_fds=(write_fd,), stdout=None, stderr=None)
        except Exception:
            os.close(read_fd)
            raise
        finally:
            os.close(write_fd)
        self._pipe = os.fdopen(read_fd, 'rb')
        self._thread = threading.Thread(target=self._read_frames, daemon=True)
        self._thread.start()
        self.timer = self.create_timer(1.0 / self.fps, self.frame_publishing_callback)
        self.get_logger().info('GStreamer запущен; ожидаю кадры камеры...')

    def _read_frames(self):
        try:
            while True:
                data = bytearray()
                while len(data) < self.frame_bytes:
                    chunk = self._pipe.read(self.frame_bytes - len(data))
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
            raise RuntimeError('GStreamer завершился: смотрите сообщения выше.')
        with self._lock:
            data, self._latest = self._latest, None
            last_frame = self._last_frame
        if data is None:
            if time.monotonic() - last_frame > 30:
                raise RuntimeError('Камера не передаёт кадры более 30 секунд.')
            return
        msg = Image()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'camera_optical_frame'
        msg.height, msg.width = self.height, self.width
        msg.encoding = 'bgr8'
        msg.is_bigendian = 0
        msg.step = self.width * 3
        msg.data = data
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
