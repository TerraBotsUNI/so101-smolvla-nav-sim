"""Stack completo de la versión 2 en UN comando: mundo + robot (TurtleBot3 + SO-101) + controladores + servidor del brazo,
y opcionalmente Nav2 (nav:=true) y RViz (rviz:=true). Después, los experimentos se lanzan a mano con `ros2 run`.
Uso típico (misión):
  ros2 launch paper_vla_tb3so101 cinematica.launch.py nav:=true controller:=mision rviz:=true
Argumentos: headless (false) | nav (false) | controller (mppi|dwb|rpp|mision) | strategy (ik_directa|multietapa|servovisual) | rviz (false)"""
from os.path import join
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, TimerAction
from launch.conditions import IfCondition, UnlessCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg = get_package_share_directory('paper_vla_tb3so101')
    world = join(pkg, 'worlds', 'paper_vla_arena.sdf')

    def inc(f, args, cond=None):
        return IncludeLaunchDescription(PythonLaunchDescriptionSource(join(pkg, 'launch', f)), launch_arguments=args.items(), condition=cond)

    h, c, nav = LaunchConfiguration('headless'), LaunchConfiguration('controller'), LaunchConfiguration('nav')
    rviz = Node(package='rviz2', executable='rviz2', name='rviz_v2', output='log', arguments=['-d', join(pkg, 'config', 'v2.rviz')],
                parameters=[{'use_sim_time': True}], condition=IfCondition(LaunchConfiguration('rviz')))
    return LaunchDescription([
        DeclareLaunchArgument('headless', default_value='false', description='true = Gazebo sin ventana'),
        DeclareLaunchArgument('nav', default_value='false', description='true = también Nav2 (mapa, AMCL, planificador, controlador)'),
        DeclareLaunchArgument('controller', default_value='mppi', description='mppi | dwb | rpp | mision (MPPI con meta estricta, para la misión)'),
        DeclareLaunchArgument('strategy', default_value='ik_directa', description='estrategia por defecto del brazo'),
        DeclareLaunchArgument('rviz', default_value='false', description='true = abre RViz con config/v2.rviz'),
        inc('sim.launch.py', {'headless': h, 'world': world}, UnlessCondition(nav)),
        inc('nav.launch.py', {'headless': h, 'world': world, 'controller': c}, IfCondition(nav)),
        TimerAction(period=20.0, actions=[inc('manipulation.launch.py', {'strategy': LaunchConfiguration('strategy')})]),
        TimerAction(period=18.0, actions=[rviz]),
    ])
