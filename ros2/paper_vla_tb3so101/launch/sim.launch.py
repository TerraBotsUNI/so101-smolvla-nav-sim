"""TurtleBot3 Waffle Pi + OpenManipulator-X en Gazebo Fortress (ROS 2 Humble). Sin Gazebo Classic."""
import os
from os.path import join
import xacro
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, SetEnvironmentVariable, TimerAction
from launch.conditions import IfCondition, UnlessCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg = get_package_share_directory('paper_vla_tb3so101')
    pkg_desc = get_package_share_directory('turtlebot3_manipulation_description')
    pkg_gz = get_package_share_directory('ros_gz_sim')

    headless = LaunchConfiguration('headless')
    world = LaunchConfiguration('world')

    robot_description = xacro.process_file(
        join(pkg, 'urdf', 'tb3_so101_fortress.urdf.xacro'),
        mappings={'controllers_yaml': join(pkg, 'config', 'controllers.yaml')},
    ).toxml()

    # package:// de las mallas de ROBOTIS: el padre de share/ debe estar en el path de recursos de Gazebo
    share_parent = os.path.dirname(pkg_desc) + ':' + os.path.dirname(pkg)   # mallas del Waffle Pi y del SO-101
    prev_ign = os.environ.get('IGN_GAZEBO_RESOURCE_PATH', '')
    prev_gz = os.environ.get('GZ_SIM_RESOURCE_PATH', '')
    res_ign = SetEnvironmentVariable('IGN_GAZEBO_RESOURCE_PATH', share_parent + (':' + prev_ign if prev_ign else ''))
    res_gz = SetEnvironmentVariable('GZ_SIM_RESOURCE_PATH', share_parent + (':' + prev_gz if prev_gz else ''))
    nvidia = SetEnvironmentVariable('__GLX_VENDOR_LIBRARY_NAME', 'nvidia')

    rsp = Node(package='robot_state_publisher', executable='robot_state_publisher', name='tb3_so101_rsp', output='screen',
               parameters=[{'robot_description': robot_description, 'use_sim_time': True}],
               remappings=[('robot_description', '/tb3_so101/robot_description')])

    gz_gui = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(join(pkg_gz, 'launch', 'gz_sim.launch.py')),
        launch_arguments={'gz_args': ['-r -v 3 ', world]}.items(), condition=UnlessCondition(headless))
    gz_headless = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(join(pkg_gz, 'launch', 'gz_sim.launch.py')),
        launch_arguments={'gz_args': ['-r -s --headless-rendering -v 3 ', world]}.items(),
        condition=IfCondition(headless))

    spawn = TimerAction(period=4.0, actions=[Node(
        package='ros_gz_sim', executable='create', output='screen',
        arguments=['-topic', '/tb3_so101/robot_description', '-name', 'tb3_so101', '-allow_renaming', 'false',
                   '-x', '0.0', '-y', '0.0', '-z', '0.02'])])

    bridge = Node(package='ros_gz_bridge', executable='parameter_bridge', output='screen',
                  parameters=[{'config_file': join(pkg, 'config', 'bridge.yaml'), 'use_sim_time': True}])

    def spawner(name, delay):
        return TimerAction(period=delay, actions=[Node(
            package='controller_manager', executable='spawner', output='screen',
            arguments=[name, '--controller-manager', '/controller_manager', '--controller-manager-timeout', '60'])])

    return LaunchDescription([
        DeclareLaunchArgument('headless', default_value='false', description='true = solo servidor, sin ventana'),
        DeclareLaunchArgument('world', default_value=join(pkg, 'worlds', 'paper_vla_empty.sdf')),
        res_ign, res_gz, nvidia, rsp, gz_gui, gz_headless, spawn, bridge,
        spawner('joint_state_broadcaster', 8.0), spawner('arm_controller', 10.0), spawner('gripper_controller', 12.0),
    ])
