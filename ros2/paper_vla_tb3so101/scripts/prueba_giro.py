#!/usr/bin/python3
"""Diagnóstico del deslizamiento de la base: el robot gira en el sitio (cmd_vel) y se compara cuánto giró según la odometría de las ruedas
(/odom) con cuánto giró de verdad (Gazebo /gt_tf). Casos: brazo en pose de observación sin cubo, y con un cubo agarrado y levantado
(acción Pick con hold=True, como en la misión antes de IR_A_ENTREGA). Velocidades 0.5 y 1.0 rad/s, a izquierda y derecha.
Requiere cinematica.launch.py (sin Nav2). Uso: python3 prueba_giro.py <csv>"""
import csv, math, sys, rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.action import ActionClient
from rclpy.task import Future
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from tf2_msgs.msg import TFMessage
from std_srvs.srv import Trigger
from paper_vla_interfaces.action import Pick
from so101_manipulation import set_cube_pose


def yaw(q):
    return math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))


rclpy.init(); n = Node('prueba_giro', parameter_overrides=[Parameter('use_sim_time', value=True)])
st = {}
n.create_subscription(Odometry, '/odom', lambda m: st.__setitem__('odom', yaw(m.pose.pose.orientation)), 10)
n.create_subscription(TFMessage, '/gt_tf', lambda m: [st.__setitem__('gt', (t.transform.translation.x, t.transform.translation.y, yaw(t.transform.rotation)))
                                                       for t in m.transforms if t.child_frame_id == 'tb3_so101'], 10)
cmd = n.create_publisher(Twist, '/cmd_vel', 10)
obs = n.create_client(Trigger, '/so101/observe'); pick = ActionClient(n, Pick, '/so101/pick')


def esperar(s):
    rclpy.spin_until_future_complete(n, Future(), timeout_sec=s)


def girar(wz, dur):
    """Gira dur s de simulación a wz y para; devuelve (giro_odom, giro_real, desplazamiento_real) en grados / m."""
    esperar(0.5); o0, g0 = st['odom'], st['gt']
    t0 = n.get_clock().now().nanoseconds * 1e-9
    while n.get_clock().now().nanoseconds * 1e-9 - t0 < dur:
        tw = Twist(); tw.angular.z = wz; cmd.publish(tw); rclpy.spin_once(n, timeout_sec=0.05)
    for _ in range(10):
        cmd.publish(Twist()); rclpy.spin_once(n, timeout_sec=0.05)
    esperar(1.0); o1, g1 = st['odom'], st['gt']
    return (math.degrees(math.remainder(o1 - o0, 2 * math.pi)), math.degrees(math.remainder(g1[2] - g0[2], 2 * math.pi)), math.hypot(g1[0] - g0[0], g1[1] - g0[1]))


while 'odom' not in st or 'gt' not in st:
    rclpy.spin_once(n, timeout_sec=0.1)
pick.wait_for_server(timeout_sec=60)
f = open(sys.argv[1], 'w', newline=''); w = csv.writer(f); w.writerow(['caso', 'wz', 'giro_odom_deg', 'giro_real_deg', 'diferencia_deg', 'desplazamiento_m'])
for caso in ('sin_cubo', 'con_cubo'):
    fu = obs.call_async(Trigger.Request()); rclpy.spin_until_future_complete(n, fu, timeout_sec=60); esperar(1.0)
    if caso == 'con_cubo':                     # cubo verde 16 cm delante del robot, como tras ACERCAR; se recoge y se queda sujeto
        x, y, th = st['gt']
        set_cube_pose(x + 0.16 * math.cos(th), y + 0.16 * math.sin(th), th, name='pick_object'); esperar(1.5)
        g = Pick.Goal(); g.strategy = 'ik_directa'; g.color = 'verde'; g.hold = True
        fu = pick.send_goal_async(g); rclpy.spin_until_future_complete(n, fu); r = fu.result().get_result_async()
        rclpy.spin_until_future_complete(n, r); print('agarre:', r.result().result.success, r.result().result.message, flush=True)
    for wz in (0.5, -0.5, 1.0, -1.0):
        go, gr, d = girar(wz, 3.0)
        w.writerow([caso, wz, round(go, 1), round(gr, 1), round(gr - go, 1), round(d, 3)]); f.flush()
        print(f'{caso:9s} wz={wz:+.1f}: odometría {go:+6.1f}°  real {gr:+6.1f}°  diferencia {gr - go:+6.1f}°  desplazamiento {100 * d:.1f} cm', flush=True)
rclpy.shutdown()
