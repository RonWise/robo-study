"""Jetbot 5 control with external camera/detector and an isolated preview output by default."""
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, EmitEvent, RegisterEventHandler, SetEnvironmentVariable
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    share = Path(get_package_share_directory('jetbot_target_follower'))
    config = str(share / 'config/follower_jetbot5.yaml')
    # Камера, детектор и драйвер моторов запускаются отдельно на Jetbot.
    # Здесь соединяем регулятор, mux и router; физический робот использует реальные часы.
    nodes = [
        Node(package='jetbot_target_follower', executable='target_follower',
             name='target_follower', output='screen',
             parameters=[config, {'enabled': ParameterValue(LaunchConfiguration('enabled'), value_type=bool)}]),
        Node(package='twist_mux', executable='twist_mux', name='twist_mux', output='screen',
             parameters=[str(share / 'config/twist_mux.yaml'), {'use_sim_time': False}],
             remappings=[('cmd_vel_out', '/cmd_vel_mux')]),
        Node(package='jetbot_target_follower', executable='command_router',
             name='command_router', output='screen', parameters=[config],
             remappings=[('/cmd_vel', LaunchConfiguration('cmd_vel_topic'))]),
    ]
    actions = [
        # По умолчанию автономное движение выключено, а выход изолирован от моторов.
        # Для заезда явно задаются enabled и cmd_vel_topic моторного контроллера.
        DeclareLaunchArgument('enabled', default_value='false', choices=['true', 'false']),
        DeclareLaunchArgument('cmd_vel_topic', default_value='/jetbot_hw1/cmd_vel_preview',
                              description='Final Twist output; change to motor controller input only for a motion test'),
        SetEnvironmentVariable('ROS_DOMAIN_ID', '5'),
        SetEnvironmentVariable('ROS_LOCALHOST_ONLY', '0'),
    ]
    # Обработчики регистрируются до запуска узлов, чтобы учесть и ошибки старта.
    # Завершение любого обязательного узла останавливает всю цепочку управления.
    for node in nodes:
        actions.append(RegisterEventHandler(OnProcessExit(
            target_action=node,
            on_exit=[EmitEvent(event=Shutdown(reason='Required Jetbot control node exited'))])))
    return LaunchDescription(actions + nodes)
