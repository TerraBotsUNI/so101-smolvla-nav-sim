"""Simulación (Fortress) + Nav2 con el controlador elegido: controller:=mppi | dwb | rpp.
Localización: AMCL (LiDAR + mapa estático) corrige la deriva de la odometría; marco map = marco del mundo."""
from os.path import join
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _setup(context, *args, **kwargs):
    pkg = get_package_share_directory('paper_vla_tb3so101')
    ctrl = LaunchConfiguration('controller').perform(context).strip().lower()
    params = join(pkg, 'config', {'mppi': 'nav2_mppi.yaml', 'dwb': 'nav2_dwb.yaml', 'rpp': 'nav2_rpp.yaml', 'mision': 'nav2_mision.yaml'}[ctrl])
    pf = LaunchConfiguration('params_file').perform(context).strip()
    if pf:
        params = pf          # YAML alternativo (autotuneo)
    sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(join(pkg, 'launch', 'sim.launch.py')),
        launch_arguments={'headless': LaunchConfiguration('headless').perform(context),
                          'world': LaunchConfiguration('world').perform(context)}.items())
    sim_time = {'use_sim_time': True}
    nodes = [
        Node(package='nav2_map_server', executable='map_server', name='map_server', output='screen',
             parameters=[{'use_sim_time': True, 'yaml_filename': join(pkg, 'maps', 'paper_vla_arena.yaml')}]),
        Node(package='nav2_amcl', executable='amcl', name='amcl', output='screen', parameters=[params]),
        Node(package='nav2_controller', executable='controller_server', name='controller_server', output='screen', parameters=[params]),
        Node(package='nav2_planner', executable='planner_server', name='planner_server', output='screen', parameters=[params]),
        Node(package='nav2_behaviors', executable='behavior_server', name='behavior_server', output='screen', parameters=[params]),
        Node(package='nav2_bt_navigator', executable='bt_navigator', name='bt_navigator', output='screen', parameters=[params]),
        Node(package='nav2_lifecycle_manager', executable='lifecycle_manager', name='lifecycle_manager_navigation', output='screen',
             parameters=[{'use_sim_time': True, 'autostart': True, 'bond_timeout': 10.0,
                          'node_names': ['map_server', 'amcl', 'controller_server', 'planner_server', 'behavior_server', 'bt_navigator']}]),
    ]
    # Nav2 arranca cuando el robot ya existe en Gazebo y publica TF, /scan y /odom
    # el gestor del ciclo de vida arranca DESPUÉS que los nodos de Nav2: si arranca a la vez, DDS aún no los ha descubierto,
    # la respuesta a change_state se pierde ('failed to send response ... timeout') y Nav2 queda en 'Configuring' para siempre
    return [sim, TimerAction(period=16.0, actions=nodes[:-1]), TimerAction(period=22.0, actions=nodes[-1:])]


def generate_launch_description():
    pkg = get_package_share_directory('paper_vla_tb3so101')
    return LaunchDescription([
        DeclareLaunchArgument('controller', default_value='mppi', description='mppi | dwb | rpp | mision (MPPI con meta estricta)'),
        DeclareLaunchArgument('headless', default_value='false'),
        DeclareLaunchArgument('params_file', default_value='', description='YAML de Nav2 alternativo (vacío = el del controlador)'),
        DeclareLaunchArgument('world', default_value=join(pkg, 'worlds', 'paper_vla_arena.sdf')),
        OpaqueFunction(function=_setup),
    ])
