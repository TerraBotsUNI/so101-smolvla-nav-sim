"""Servidor del brazo SO-101 (acción /so101/pick y servicios observe/stow/release). Se lanza DESPUÉS de sim.launch.py o nav.launch.py."""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('strategy', default_value='ik_directa', description='ik_directa | multietapa | servovisual'),
        Node(package='paper_vla_tb3so101', executable='so101_manip_server.py', name='so101_manipulator', output='screen',
             parameters=[{'strategy': LaunchConfiguration('strategy'), 'use_sim_time': True}]),
    ])
