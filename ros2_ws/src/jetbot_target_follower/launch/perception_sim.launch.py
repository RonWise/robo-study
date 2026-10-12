"""Camera-only experiment. No command bridge and no velocity publishers."""
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, OpaqueFunction, SetEnvironmentVariable
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def start(context):
    share = get_package_share_directory('jetbot_target_follower')
    gui = LaunchConfiguration('gui').perform(context).lower() == 'true'
    camera = '/world/hw1_aruco/model/jetbot/link/camera_link/sensor/color'
    gazebo = ['ign', 'gazebo', '-r', '-v', '2']
    if not gui:
        gazebo.append('-s')
    gazebo.append(os.path.join(share, 'worlds', 'hw1_aruco.sdf'))
    return [
        ExecuteProcess(cmd=gazebo, output='screen'),
        Node(package='ros_gz_bridge', executable='parameter_bridge', name='hw1_bridge',
             arguments=[
                 camera + '/image@sensor_msgs/msg/Image[ignition.msgs.Image',
                 camera + '/camera_info@sensor_msgs/msg/CameraInfo[ignition.msgs.CameraInfo',
                 '/clock@rosgraph_msgs/msg/Clock[ignition.msgs.Clock',
             ],
             remappings=[(camera + '/image', '/camera/image/raw'),
                         (camera + '/camera_info', '/camera/camera_info')],
             output='screen'),
        Node(package='jetbot_target_follower', executable='target_detector',
             name='target_detector', output='screen',
             parameters=[os.path.join(share, 'config', 'detector.yaml'),
                         {'use_sim_time': True}]),
    ]


def generate_launch_description():
    share = get_package_share_directory('jetbot_target_follower')
    resources = os.path.join(share, 'models')
    existing = os.environ.get('IGN_GAZEBO_RESOURCE_PATH', '')
    return LaunchDescription([
        DeclareLaunchArgument('gui', default_value='true', choices=['true', 'false']),
        SetEnvironmentVariable('IGN_GAZEBO_RESOURCE_PATH', resources + ':' + existing),
        OpaqueFunction(function=start),
    ])
