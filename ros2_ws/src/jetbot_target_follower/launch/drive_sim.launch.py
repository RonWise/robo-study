"""HW1 autonomous simulation, isolated from the physical Jetbot ROS domain."""
import os
import tempfile
import xml.etree.ElementTree as ET
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, EmitEvent, ExecuteProcess, OpaqueFunction, RegisterEventHandler, SetEnvironmentVariable
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def start(context):
    share=get_package_share_directory('jetbot_target_follower')
    value=lambda key:LaunchConfiguration(key).perform(context)
    # Стартовую позу меняем во временной копии мира, сохраняя исходный SDF.
    tree=ET.parse(os.path.join(share,'worlds','hw1_drive.sdf'))
    robot=next(x for x in tree.findall('.//world/include') if x.findtext('name')=='jetbot')
    robot.find('pose').text=f"{float(value('x'))} {float(value('y'))} 0.08 -1.5707963267948966 0 {float(value('yaw'))}"
    fd,path=tempfile.mkstemp(prefix='hw1-drive-',suffix='.sdf')
    with os.fdopen(fd,'wb') as stream:tree.write(stream)
    camera='/world/hw1_drive/model/jetbot/link/camera_link/sensor/color'
    command=['ign','gazebo','-r','-v','2']
    if value('gui')!='true':command.append('-s')
    command.append(path)
    gazebo=ExecuteProcess(cmd=command,output='screen')
    actions = [
        gazebo,
        RegisterEventHandler(OnProcessExit(target_action=gazebo,on_exit=[EmitEvent(event=Shutdown(reason='Gazebo closed'))])),
        # drive_bridge: изображения, калибровка и часы идут Gazebo → ROS; скорости ROS → Gazebo.
        # В строках моста '[' задаёт направление Gazebo → ROS, ']' — обратное.
        # /simulation/poses предназначен для тестов, регулятор на него не подписан.
        Node(package='ros_gz_bridge',executable='parameter_bridge',name='drive_bridge',output='screen',
             arguments=[camera+'/image@sensor_msgs/msg/Image[ignition.msgs.Image',
                        camera+'/camera_info@sensor_msgs/msg/CameraInfo[ignition.msgs.CameraInfo',
                        '/clock@rosgraph_msgs/msg/Clock[ignition.msgs.Clock',
                        '/model/jetbot/cmd_vel@geometry_msgs/msg/Twist]ignition.msgs.Twist',
                        '/world/hw1_drive/dynamic_pose/info@tf2_msgs/msg/TFMessage[ignition.msgs.Pose_V'],
             remappings=[(camera+'/image','/camera/image/raw'),(camera+'/camera_info','/camera/camera_info'),
                         ('/model/jetbot/cmd_vel','/cmd_vel'),
                         ('/world/hw1_drive/dynamic_pose/info','/simulation/poses')]),
        # Детектор получает кадры от моста и публикует измерения цели.
        Node(package='jetbot_target_follower',executable='target_detector',name='target_detector',output='screen',
             parameters=[os.path.join(share,'config','detector.yaml'),{'use_sim_time':True}]),
        # Регулятор использует измерения цели и выдаёт автономный вход mux.
        Node(package='jetbot_target_follower',executable='target_follower',name='target_follower',output='screen',
             parameters=[os.path.join(share,'config','follower.yaml'),
                         {'use_sim_time':True,'enabled':value('enabled')=='true',
                          **({'stop_distance':float(value('stop_distance'))} if value('stop_distance') else {})}]),
        # Готовый mux выбирает свежий вход с максимальным приоритетом из YAML.
        Node(package='twist_mux',executable='twist_mux',name='twist_mux',output='screen',
             parameters=[os.path.join(share,'config','twist_mux.yaml'),{'use_sim_time':True}],
             remappings=[('cmd_vel_out','/cmd_vel_mux')]),
        # Router фильтрует ручные нули и передаёт ограниченный выход mux в мост.
        Node(package='jetbot_target_follower',executable='command_router',name='command_router',output='screen',
             parameters=[os.path.join(share,'config','follower.yaml')]),
    ]
    # Если обязательный ROS-процесс завершился, завершаем весь опыт.
    for action in list(actions):
        if isinstance(action, Node):
            actions.append(RegisterEventHandler(OnProcessExit(
                target_action=action,
                on_exit=[EmitEvent(event=Shutdown(reason='Required ROS node exited'))])))
    return actions


def generate_launch_description():
    share=get_package_share_directory('jetbot_target_follower')
    return LaunchDescription([
        DeclareLaunchArgument('gui',default_value='true',choices=['true','false']),
        DeclareLaunchArgument('enabled',default_value='true',choices=['true','false']),
        DeclareLaunchArgument('stop_distance',default_value=''),
        DeclareLaunchArgument('x',default_value='0.0'),
        DeclareLaunchArgument('y',default_value='0.0'),
        DeclareLaunchArgument('yaw',default_value='0.0'),
        # Изолируем симуляцию от физического Jetbot, работающего в домене 5.
        SetEnvironmentVariable('ROS_DOMAIN_ID','45'),
        SetEnvironmentVariable('ROS_LOCALHOST_ONLY','1'),
        SetEnvironmentVariable('IGN_PARTITION','robo_hw1'),
        SetEnvironmentVariable('IGN_GAZEBO_RESOURCE_PATH',os.path.join(share,'models')+':'+os.environ.get('IGN_GAZEBO_RESOURCE_PATH','')),
        OpaqueFunction(function=start),
    ])
