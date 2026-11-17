#!/usr/bin/python3
"""Un ensayo: envía la meta a Nav2 y mide tiempo (de simulación), longitud, error final, holgura mínima real a obstáculos,
colisión y recuperaciones. La holgura se calcula con la geometría exacta de config/arena.yaml, no con el LiDAR."""
import argparse, csv, json, math, os, sys, time
import rclpy, yaml
from action_msgs.msg import GoalStatus
from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from geometry_msgs.msg import Twist
from tf2_msgs.msg import TFMessage
from nav_msgs.msg import Odometry, Path
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.parameter import Parameter
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint


class Trial(Node):
    def __init__(self):
        super().__init__('nav_trial', parameter_overrides=[Parameter('use_sim_time', Parameter.Type.BOOL, True)])
        self.samples, self.max_rec = [], 0
        self.yaw, self.cmds, self.first_plan = 0.0, [], None
        self.create_subscription(Odometry, '/odom', self._odom, 20)
        self.gt = []
        self.create_subscription(TFMessage, '/gt_tf', self._gt, 50)
        self.create_subscription(Twist, '/cmd_vel', self._cmd, 20)
        self.create_subscription(Path, '/plan', self._plan, 10)
        self.client = ActionClient(self, NavigateToPose, 'navigate_to_pose')

    def _gt(self, m):
        for tr in m.transforms:
            if tr.child_frame_id == 'tb3_so101':
                q = tr.transform.rotation
                yaw = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))
                self.gt.append((self.get_clock().now().nanoseconds * 1e-9, tr.transform.translation.x, tr.transform.translation.y, yaw)); break

    def _cmd(self, m):
        self.cmds.append((self.get_clock().now().nanoseconds * 1e-9, m.linear.x, m.angular.z))

    def _plan(self, m):
        if self.first_plan is None and len(m.poses) > 3:
            self.first_plan = [(q.pose.position.x, q.pose.position.y) for q in m.poses]

    def _odom(self, m):
        q = m.pose.pose.orientation
        self.yaw = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))
        p = m.pose.pose.position
        self.samples.append((self.get_clock().now().nanoseconds * 1e-9, p.x, p.y, self.yaw))


# Geometría real del robot (marco base_footprint), de las mallas del URDF: caja del Waffle Pi + las dos ruedas (xmin, xmax, ymin, ymax)
ROBOT_BOXES = [(-0.197, 0.069, -0.133, 0.133), (-0.033, 0.033, 0.135, 0.153), (-0.033, 0.033, -0.153, -0.135)]


def clearance(cfg, x, y, yaw):
    """Holgura mínima (m) entre la unión de cajas del robot (caja + ruedas, orientada) y los obstáculos/paredes. <0 = contacto."""
    A = cfg['arena']; ox, oy = A['origin']; t = A['wall_thickness']
    c, s = math.cos(yaw), math.sin(yaw)
    best = float('inf')
    for (x0, x1, y0, y1) in ROBOT_BOXES:
        for o in cfg['obstacles']:
            dx, dy = o['x'] - x, o['y'] - y
            rx, ry = c * dx + s * dy, -s * dx + c * dy
            d = math.hypot(max(x0 - rx, 0.0, rx - x1), max(y0 - ry, 0.0, ry - y1))
            best = min(best, d - o['radius'])
        for (px, py) in ((x0, y0), (x0, y1), (x1, y0), (x1, y1)):
            wx, wy = x + c * px - s * py, y + s * px + c * py
            best = min(best, wx - (ox + t), (ox + A['width'] - t) - wx, wy - (oy + t), (oy + A['height'] - t) - wy)
    return best


def spin_until(node, cond, timeout):
    t0 = time.time()
    while not cond() and time.time() - t0 < timeout: rclpy.spin_once(node, timeout_sec=0.1)
    return cond()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--controller', default='unknown'); ap.add_argument('--run-id', default='0')
    ap.add_argument('--timeout', type=float, default=180.0, help='segundos de reloj real'); ap.add_argument('--out', default='')
    ap.add_argument('--goal', type=float, nargs=3, default=None, help='x y yaw')
    ap.add_argument('--no-stow', action='store_true', help='no plegar el brazo antes de navegar')
    ap.add_argument('--trace', default='', help='archivo JSON con la ruta planificada y la trayectoria real')
    args, _ = ap.parse_known_args()
    cfg = yaml.safe_load(open(os.path.join(get_package_share_directory('paper_vla_tb3so101'), 'config', 'arena.yaml'), encoding='utf-8'))
    gx, gy, gyaw = args.goal or (cfg['goal']['x'], cfg['goal']['y'], cfg['goal']['yaw'])
    rclpy.init(); node = Trial()
    if not node.client.wait_for_server(timeout_sec=60.0):
        print(json.dumps({'error': 'navigate_to_pose no disponible'})); return 2
    if not spin_until(node, lambda: len(node.samples) > 0, 30.0):
        print(json.dumps({'error': 'sin odometría'})); return 2
    if not args.no_stow:                                   # navegar con el brazo plegado dentro de la huella (igual que la misión)
        pub = node.create_publisher(JointTrajectory, '/arm_controller/joint_trajectory', 10)
        spin_until(node, lambda: False, 1.5)
        m = JointTrajectory(); m.joint_names = ['joint1', 'joint2', 'joint3', 'joint4']
        pt = JointTrajectoryPoint(); pt.positions = [0.0, -0.28, -0.90, -0.68]; pt.time_from_start.sec = 3; m.points = [pt]
        pub.publish(m); spin_until(node, lambda: False, 5.0)
    time.sleep(1.0); node.samples.clear(); node.gt.clear(); node.cmds.clear(); node.first_plan = None
    goal = NavigateToPose.Goal(); goal.pose = PoseStamped(); goal.pose.header.frame_id = 'map'
    goal.pose.header.stamp = node.get_clock().now().to_msg()
    goal.pose.pose.position.x, goal.pose.pose.position.y = gx, gy
    goal.pose.pose.orientation.z, goal.pose.pose.orientation.w = math.sin(gyaw / 2), math.cos(gyaw / 2)
    wall0 = time.time()
    fut = node.client.send_goal_async(goal, feedback_callback=lambda f: setattr(node, 'max_rec', max(node.max_rec, f.feedback.number_of_recoveries)))
    spin_until(node, fut.done, 30.0)
    handle = fut.result()
    if handle is None or not handle.accepted:
        print(json.dumps({'error': 'meta rechazada'})); return 2
    res = handle.get_result_async()
    done = spin_until(node, res.done, args.timeout)
    status = res.result().status if done else None
    if not done: handle.cancel_goal_async()
    S = node.gt if len(node.gt) > 20 else node.samples
    length = sum(math.hypot(S[i][1] - S[i - 1][1], S[i][2] - S[i - 1][2]) for i in range(1, len(S)))
    fx, fy = (S[-1][1], S[-1][2]) if S else (float('nan'), float('nan'))
    ferr = math.hypot(fx - gx, fy - gy)
    cmin = min(clearance(cfg, s[1], s[2], s[3]) for s in S) if S else float('nan')
    t0s = S[0][0] if S else 0.0
    first_move = next((s[0] - t0s for s in S if math.hypot(s[1] - S[0][1], s[2] - S[0][2]) > 0.05), None)
    c10 = [c for c in node.cmds if c[0] - t0s <= 10.0]
    turn = None
    if node.first_plan and len(node.first_plan) > 5 and S:
        (x0, y0), (x1, y1) = node.first_plan[0], node.first_plan[min(8, len(node.first_plan) - 1)]
        d = math.atan2(y1 - y0, x1 - x0) - 0.0   # el robot arranca con yaw=0
        turn = round(math.degrees(math.atan2(math.sin(d), math.cos(d))), 1)
    out = {'controller': args.controller, 'run': args.run_id,
           'status': {GoalStatus.STATUS_SUCCEEDED: 'SUCCEEDED', GoalStatus.STATUS_ABORTED: 'ABORTED', GoalStatus.STATUS_CANCELED: 'CANCELED'}.get(status, 'TIMEOUT'),
           'success': bool(status == GoalStatus.STATUS_SUCCEEDED and ferr <= 0.30),
           'time_sim_s': round(S[-1][0] - S[0][0], 2) if S else None, 'time_wall_s': round(time.time() - wall0, 2),
           'path_length_m': round(length, 3), 'final_error_m': round(ferr, 3), 'clearance_min_m': round(cmin, 3),
           'collision': bool(cmin < 0), 'recoveries': node.max_rec, 'pose_source': 'gazebo' if len(node.gt) > 20 else 'odom',
           't_first_motion_s': None if first_move is None else round(first_move, 2),
           'cmd_vx_mean_10s': round(sum(c[1] for c in c10) / len(c10), 3) if c10 else None,
           'cmd_wz_absmean_10s': round(sum(abs(c[2]) for c in c10) / len(c10), 3) if c10 else None,
           'plan_start_dir_deg': turn, 'plan_points': len(node.first_plan) if node.first_plan else 0}
    print(json.dumps(out, ensure_ascii=False))
    if args.trace:
        t0 = S[0][0] if S else 0.0
        json.dump({'result': out, 'goal': [gx, gy, gyaw], 'plan': node.first_plan,
                   'odom': [[round(s[0] - t0, 3), round(s[1], 4), round(s[2], 4)] for s in S[::5]],
                   'cmd': [[round(c[0] - t0, 3), round(c[1], 3), round(c[2], 3)] for c in node.cmds[::5]]}, open(args.trace, 'w'))
    if args.out:
        new = not os.path.exists(args.out) or os.path.getsize(args.out) == 0
        with open(args.out, 'a', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(out)); (w.writeheader() if new else None); w.writerow(out)
    node.destroy_node(); rclpy.shutdown(); return 0


if __name__ == '__main__':
    sys.exit(main())
