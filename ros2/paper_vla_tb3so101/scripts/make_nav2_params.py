#!/usr/bin/python3
"""Genera config/nav2_{mppi,dwb,rpp}.yaml: costmaps, planificador y BT IDÉNTICOS; solo cambia el controlador local."""
import copy, os, yaml
HERE = os.path.dirname(os.path.abspath(__file__)); PKG = os.path.dirname(HERE)
_cfg = yaml.safe_load(open(os.path.join(PKG, 'config', 'arena.yaml'), encoding='utf-8'))
R = _cfg['robot']['radius']
_x0, _x1, _y0, _y1 = _cfg['robot']['footprint']
FOOT = f'[[{_x1}, {_y1}], [{_x1}, {_y0}], [{_x0}, {_y0}], [{_x0}, {_y1}]]'
V = 0.26      # velocidad lineal máxima del Waffle Pi (m/s)
WZ = 1.82     # velocidad angular máxima (rad/s)

BT_PLUGINS = ["nav2_compute_path_to_pose_action_bt_node", "nav2_compute_path_through_poses_action_bt_node",
  "nav2_smooth_path_action_bt_node", "nav2_follow_path_action_bt_node", "nav2_spin_action_bt_node", "nav2_wait_action_bt_node",
  "nav2_assisted_teleop_action_bt_node", "nav2_back_up_action_bt_node", "nav2_drive_on_heading_bt_node",
  "nav2_clear_costmap_service_bt_node", "nav2_is_stuck_condition_bt_node", "nav2_goal_reached_condition_bt_node",
  "nav2_goal_updated_condition_bt_node", "nav2_globally_updated_goal_condition_bt_node", "nav2_is_path_valid_condition_bt_node",
  "nav2_initial_pose_received_condition_bt_node", "nav2_reinitialize_global_localization_service_bt_node",
  "nav2_rate_controller_bt_node", "nav2_distance_controller_bt_node", "nav2_speed_controller_bt_node",
  "nav2_truncate_path_action_bt_node", "nav2_truncate_path_local_action_bt_node", "nav2_goal_updater_node_bt_node",
  "nav2_recovery_node_bt_node", "nav2_pipeline_sequence_bt_node", "nav2_round_robin_node_bt_node",
  "nav2_transform_available_condition_bt_node", "nav2_time_expired_condition_bt_node", "nav2_path_expiring_timer_condition",
  "nav2_distance_traveled_condition_bt_node", "nav2_single_trigger_bt_node", "nav2_goal_updated_controller_bt_node",
  "nav2_is_battery_low_condition_bt_node", "nav2_navigate_through_poses_action_bt_node", "nav2_navigate_to_pose_action_bt_node",
  "nav2_remove_passed_goals_action_bt_node", "nav2_planner_selector_bt_node", "nav2_controller_selector_bt_node",
  "nav2_goal_checker_selector_bt_node", "nav2_controller_cancel_bt_node", "nav2_path_longer_on_approach_bt_node",
  "nav2_wait_cancel_bt_node", "nav2_spin_cancel_bt_node", "nav2_back_up_cancel_bt_node", "nav2_assisted_teleop_cancel_bt_node",
  "nav2_drive_on_heading_cancel_bt_node", "nav2_is_battery_charging_condition_bt_node"]

scan = {'topic': '/scan', 'max_obstacle_height': 2.0, 'clearing': True, 'marking': True, 'data_type': 'LaserScan',
        'raytrace_max_range': 3.0, 'raytrace_min_range': 0.0, 'obstacle_max_range': 2.5, 'obstacle_min_range': 0.0}
inflation = {'plugin': 'nav2_costmap_2d::InflationLayer', 'cost_scaling_factor': 3.0, 'inflation_radius': 0.70}

def base():
    return {
     'amcl': {'ros__parameters': {'use_sim_time': True, 'alpha1': 0.2, 'alpha2': 0.2, 'alpha3': 0.2, 'alpha4': 0.2, 'alpha5': 0.2,
        'base_frame_id': 'base_footprint', 'global_frame_id': 'map', 'odom_frame_id': 'odom', 'beam_skip_distance': 0.5,
        'beam_skip_error_threshold': 0.9, 'beam_skip_threshold': 0.3, 'do_beamskip': False, 'lambda_short': 0.1,
        'laser_likelihood_max_dist': 2.0, 'laser_max_range': 12.0, 'laser_min_range': -1.0, 'laser_model_type': 'likelihood_field',
        'max_beams': 60, 'max_particles': 2000, 'min_particles': 500, 'pf_err': 0.05, 'pf_z': 0.99, 'recovery_alpha_fast': 0.0,
        'recovery_alpha_slow': 0.0, 'resample_interval': 1, 'robot_model_type': 'nav2_amcl::DifferentialMotionModel',
        'save_pose_rate': 0.5, 'sigma_hit': 0.2, 'tf_broadcast': True, 'transform_tolerance': 1.0, 'update_min_a': 0.2,
        'update_min_d': 0.25, 'z_hit': 0.5, 'z_max': 0.05, 'z_rand': 0.5, 'z_short': 0.05, 'scan_topic': 'scan',
        'set_initial_pose': True, 'always_reset_initial_pose': True,
        'initial_pose': {'x': _cfg['robot']['start'][0], 'y': _cfg['robot']['start'][1], 'z': 0.0, 'yaw': _cfg['robot']['start'][2]}}},
     'bt_navigator': {'ros__parameters': {'use_sim_time': True, 'global_frame': 'map', 'robot_base_frame': 'base_footprint',
        'odom_topic': '/odom', 'bt_loop_duration': 10, 'default_server_timeout': 20, 'plugin_lib_names': BT_PLUGINS}},
     'controller_server': {'ros__parameters': {'use_sim_time': True, 'controller_frequency': 20.0,
        'min_x_velocity_threshold': 0.001, 'min_y_velocity_threshold': 0.001, 'min_theta_velocity_threshold': 0.001,
        'failure_tolerance': 0.3, 'progress_checker_plugin': 'progress_checker', 'goal_checker_plugins': ['general_goal_checker'],
        'controller_plugins': ['FollowPath'],
        'progress_checker': {'plugin': 'nav2_controller::SimpleProgressChecker', 'required_movement_radius': 0.2, 'movement_time_allowance': 15.0},
        'general_goal_checker': {'plugin': 'nav2_controller::SimpleGoalChecker', 'xy_goal_tolerance': 0.15, 'yaw_goal_tolerance': 3.14, 'stateful': True}}},
     'local_costmap': {'local_costmap': {'ros__parameters': {'update_frequency': 5.0, 'publish_frequency': 2.0, 'global_frame': 'odom',
        'robot_base_frame': 'base_footprint', 'use_sim_time': True, 'rolling_window': True, 'width': 3, 'height': 3, 'resolution': 0.05,
        'footprint': FOOT, 'plugins': ['obstacle_layer', 'inflation_layer'], 'inflation_layer': dict(inflation),
        'obstacle_layer': {'plugin': 'nav2_costmap_2d::ObstacleLayer', 'enabled': True, 'observation_sources': 'scan', 'scan': dict(scan)},
        'always_send_full_costmap': True}}},
     'global_costmap': {'global_costmap': {'ros__parameters': {'update_frequency': 1.0, 'publish_frequency': 1.0, 'global_frame': 'map',
        'robot_base_frame': 'base_footprint', 'use_sim_time': True, 'resolution': 0.05, 'footprint': FOOT, 'track_unknown_space': False,
        'plugins': ['static_layer', 'obstacle_layer', 'inflation_layer'], 'inflation_layer': dict(inflation),
        'static_layer': {'plugin': 'nav2_costmap_2d::StaticLayer', 'map_subscribe_transient_local': True},
        'obstacle_layer': {'plugin': 'nav2_costmap_2d::ObstacleLayer', 'enabled': True, 'observation_sources': 'scan', 'scan': dict(scan)},
        'always_send_full_costmap': True}}},
     'planner_server': {'ros__parameters': {'use_sim_time': True, 'planner_plugins': ['GridBased'],
        'GridBased': {'plugin': 'nav2_smac_planner/SmacPlanner2D', 'tolerance': 0.125, 'downsample_costmap': False, 'downsampling_factor': 1,
          'allow_unknown': False, 'max_iterations': 1000000, 'max_on_approach_iterations': 1000, 'max_planning_time': 2.0,
          'cost_travel_multiplier': 1.0, 'use_final_approach_orientation': False,
          'smoother': {'max_iterations': 1000, 'w_smooth': 0.3, 'w_data': 0.2, 'tolerance': 1e-10}}}},
     'behavior_server': {'ros__parameters': {'use_sim_time': True, 'local_costmap_topic': 'local_costmap/costmap_raw',
        'global_costmap_topic': 'global_costmap/costmap_raw', 'local_footprint_topic': 'local_costmap/published_footprint',
        'global_footprint_topic': 'global_costmap/published_footprint', 'cycle_frequency': 10.0,
        'behavior_plugins': ['spin', 'backup', 'drive_on_heading', 'assisted_teleop', 'wait'],
        'spin': {'plugin': 'nav2_behaviors/Spin'}, 'backup': {'plugin': 'nav2_behaviors/BackUp'},
        'drive_on_heading': {'plugin': 'nav2_behaviors/DriveOnHeading'}, 'wait': {'plugin': 'nav2_behaviors/Wait'},
        'assisted_teleop': {'plugin': 'nav2_behaviors/AssistedTeleop'},
        'local_frame': 'odom', 'global_frame': 'map', 'robot_base_frame': 'base_footprint', 'transform_tolerance': 0.1,
        'simulate_ahead_time': 2.0, 'max_rotational_vel': 1.0, 'min_rotational_vel': 0.4, 'rotational_acc_lim': 3.2}},
    }

MPPI = {'plugin': 'nav2_mppi_controller::MPPIController', 'time_steps': 40, 'model_dt': 0.05, 'batch_size': 2000,
  'vx_std': 0.2, 'vy_std': 0.2, 'wz_std': 0.4, 'vx_max': V, 'vx_min': 0.0, 'vy_max': 0.5, 'wz_max': WZ, 'iteration_count': 1,
  'prune_distance': 2.0, 'transform_tolerance': 0.1, 'temperature': 0.3, 'gamma': 0.015, 'motion_model': 'DiffDrive',
  'visualize': False, 'regenerate_noises': True,
  'critics': ['ConstraintCritic', 'CostCritic', 'GoalCritic', 'GoalAngleCritic', 'PathAlignCritic', 'PathFollowCritic', 'PathAngleCritic', 'PreferForwardCritic'],
  'ConstraintCritic': {'enabled': True, 'cost_power': 1, 'cost_weight': 4.0},
  'GoalCritic': {'enabled': True, 'cost_power': 1, 'cost_weight': 5.0, 'threshold_to_consider': 1.4},
  'GoalAngleCritic': {'enabled': True, 'cost_power': 1, 'cost_weight': 3.0, 'threshold_to_consider': 0.5},
  'PreferForwardCritic': {'enabled': True, 'cost_power': 1, 'cost_weight': 5.0, 'threshold_to_consider': 0.5},
  'CostCritic': {'enabled': True, 'cost_power': 1, 'cost_weight': 3.81, 'critical_cost': 300.0, 'consider_footprint': True,
                 'collision_cost': 1000000.0, 'near_goal_distance': 0.5, 'trajectory_point_step': 2},
  'PathAlignCritic': {'enabled': True, 'cost_power': 1, 'cost_weight': 22.0, 'max_path_occupancy_ratio': 0.05,
                      'trajectory_point_step': 6, 'threshold_to_consider': 0.3, 'offset_from_furthest': 14, 'use_path_orientations': False},
  'PathFollowCritic': {'enabled': True, 'cost_power': 1, 'cost_weight': 22.0, 'offset_from_furthest': 5, 'threshold_to_consider': 0.25},
  'PathAngleCritic': {'enabled': True, 'cost_power': 1, 'cost_weight': 6.0, 'offset_from_furthest': 6,
                      'threshold_to_consider': 0.5, 'max_angle_to_furthest': 1.0, 'mode': 0}}

DWB = {'plugin': 'dwb_core::DWBLocalPlanner', 'debug_trajectory_details': False,
  'min_vel_x': 0.0, 'min_vel_y': 0.0, 'max_vel_x': V, 'max_vel_y': 0.0, 'max_vel_theta': 1.0,
  'min_speed_xy': 0.0, 'max_speed_xy': V, 'min_speed_theta': 0.0,
  'acc_lim_x': 2.5, 'acc_lim_y': 0.0, 'acc_lim_theta': 3.2, 'decel_lim_x': -2.5, 'decel_lim_y': 0.0, 'decel_lim_theta': -3.2,
  'vx_samples': 20, 'vy_samples': 5, 'vtheta_samples': 20, 'sim_time': 1.7, 'linear_granularity': 0.05, 'angular_granularity': 0.025,
  'transform_tolerance': 0.2, 'xy_goal_tolerance': 0.15, 'trans_stopped_velocity': 0.25, 'short_circuit_trajectory_evaluation': True,
  'stateful': True, 'critics': ['RotateToGoal', 'Oscillation', 'BaseObstacle', 'GoalAlign', 'PathAlign', 'PathDist', 'GoalDist'],
  'BaseObstacle.scale': 0.02, 'PathAlign.scale': 32.0, 'PathAlign.forward_point_distance': 0.1, 'GoalAlign.scale': 24.0,
  'GoalAlign.forward_point_distance': 0.1, 'PathDist.scale': 32.0, 'GoalDist.scale': 24.0,
  'RotateToGoal.scale': 32.0, 'RotateToGoal.slowing_factor': 5.0, 'RotateToGoal.lookahead_time': -1.0}

RPP = {'plugin': 'nav2_regulated_pure_pursuit_controller::RegulatedPurePursuitController', 'desired_linear_vel': V,
  'lookahead_dist': 0.6, 'min_lookahead_dist': 0.3, 'max_lookahead_dist': 0.9, 'lookahead_time': 1.5,
  'rotate_to_heading_angular_vel': 1.8, 'transform_tolerance': 0.1, 'use_velocity_scaled_lookahead_dist': False,
  'min_approach_linear_velocity': 0.05, 'approach_velocity_scaling_dist': 0.6, 'use_collision_detection': True,
  'max_allowed_time_to_collision_up_to_carrot': 1.0, 'use_regulated_linear_velocity_scaling': True,
  'use_cost_regulated_linear_velocity_scaling': False, 'regulated_linear_scaling_min_radius': 0.9,
  'regulated_linear_scaling_min_speed': 0.1, 'use_rotate_to_heading': True, 'rotate_to_heading_min_angle': 0.785,
  'max_angular_accel': 3.2, 'max_robot_pose_search_dist': 10.0, 'use_interpolation': False}

for name, block in (('mppi', MPPI), ('dwb', DWB), ('rpp', RPP)):
    p = base(); p['controller_server']['ros__parameters']['FollowPath'] = copy.deepcopy(block)
    out = os.path.join(PKG, 'config', f'nav2_{name}.yaml')
    open(out, 'w').write(f"# GENERADO por scripts/make_nav2_params.py. No editar a mano: cambiar el script y regenerar.\n" + yaml.safe_dump(p, sort_keys=False, default_flow_style=False))
    print('escrito', out)
