#!/usr/bin/python3
"""Banco (14-nov), variante para video (16-nov): ¿se mueve solo el robot con el cubo sujeto, según cuánto apriete la pinza?
Copia de tools/prueba_sujecion.py con dos añadidos:
  --sin-vecinos   deja SOLO el cubo que se agarra en su sitio (p. ej. azul a -13 cm) y aleja los otros dos (incluido el
                  central pick_object si no es el agarrado) a ~18 m, fuera del alcance del robot.
  --traza <csv>   traza a ~10 Hz (tiempo de simulación): t_sim, yaw_odom, yaw_real, x_real, y_real, cmd_wz, cmd_vx, fase,
                  pinza_rad y z del cubo agarrado.
Todo lo demás es igual. Uso: python3 prueba_sujecion_video.py <csv> [aprietes] [colores] [--sin-vecinos] [--traza t.csv]"""
import csv, math, sys, rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.action import ActionClient
from rclpy.task import Future
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from tf2_msgs.msg import TFMessage
from sensor_msgs.msg import JointState
from std_srvs.srv import Trigger
from control_msgs.action import GripperCommand
from paper_vla_interfaces.action import Pick
from so101_manipulation import set_cube_pose

args = list(sys.argv[1:])
SIN_VECINOS = '--sin-vecinos' in args
if SIN_VECINOS:
    args.remove('--sin-vecinos')
TRAZA = None
if '--traza' in args:
    i = args.index('--traza'); TRAZA = args[i + 1]; del args[i:i + 2]
NOMBRE_CUBO = {'verde': 'pick_object', 'rojo': 'cubo_rojo', 'azul': 'cubo_azul'}


def yaw(q):
    return math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))


rclpy.init(); n = Node('prueba_sujecion', parameter_overrides=[Parameter('use_sim_time', value=True)])
st = {'cmd': (0.0, 0.0), 'fase': 'inicio', 'col': None}
n.create_subscription(Odometry, '/odom', lambda m: st.__setitem__('odom', yaw(m.pose.pose.orientation)), 10)
def _gt(m):
    for t in m.transforms:
        if t.child_frame_id == 'tb3_so101':
            st['gt'] = (t.transform.translation.x, t.transform.translation.y, yaw(t.transform.rotation))
        elif t.child_frame_id in ('pick_object', 'cubo_rojo', 'cubo_azul'):
            st['z_' + t.child_frame_id] = t.transform.translation.z
n.create_subscription(TFMessage, '/gt_tf', _gt, 10)
n.create_subscription(JointState, '/joint_states', lambda m: st.update({k: v for k, v in zip(m.name, m.position) if k == 'gripper'}), 10)
cmd = n.create_publisher(Twist, '/cmd_vel', 10)
obs = n.create_client(Trigger, '/so101/observe'); rel = n.create_client(Trigger, '/so101/release')
pick = ActionClient(n, Pick, '/so101/pick'); grip = ActionClient(n, GripperCommand, '/gripper_controller/gripper_cmd')

ft = wt = None
if TRAZA:
    ft = open(TRAZA, 'w', newline=''); wt = csv.writer(ft)
    wt.writerow(['t_sim', 'yaw_odom_deg', 'yaw_real_deg', 'x_real', 'y_real', 'cmd_wz', 'cmd_vx', 'fase', 'pinza_rad', 'cubo_z'])
    def _traza():
        if 'odom' not in st or 'gt' not in st:
            return
        g = st['gt']; wz, vx = st['cmd']
        cz = st.get('z_' + NOMBRE_CUBO[st['col']], float('nan')) if st['col'] else float('nan')
        wt.writerow([f'{n.get_clock().now().nanoseconds * 1e-9:.2f}', f'{math.degrees(st["odom"]):.2f}', f'{math.degrees(g[2]):.2f}',
                     f'{g[0]:.4f}', f'{g[1]:.4f}', wz, vx, st['fase'], f'{st.get("gripper", float("nan")):.4f}', f'{cz:.4f}'])
        ft.flush()
    n.create_timer(0.1, _traza)


def esperar(s):
    rclpy.spin_until_future_complete(n, Future(), timeout_sec=s)


def mover(wz, vx, dur):
    esperar(0.5); o0, g0 = st['odom'], st['gt']
    t0 = n.get_clock().now().nanoseconds * 1e-9
    st['cmd'] = (wz, vx)
    while n.get_clock().now().nanoseconds * 1e-9 - t0 < dur:
        tw = Twist(); tw.angular.z = wz; tw.linear.x = vx; cmd.publish(tw); rclpy.spin_once(n, timeout_sec=0.05)
    st['cmd'] = (0.0, 0.0)
    for _ in range(10):
        cmd.publish(Twist()); rclpy.spin_once(n, timeout_sec=0.05)
    esperar(1.0); o1, g1 = st['odom'], st['gt']
    return math.degrees(math.remainder(o1 - o0, 2 * math.pi)), math.degrees(math.remainder(g1[2] - g0[2], 2 * math.pi)), math.hypot(g1[0] - g0[0], g1[1] - g0[1])


while 'odom' not in st or 'gt' not in st:
    rclpy.spin_once(n, timeout_sec=0.1)
pick.wait_for_server(timeout_sec=60); grip.wait_for_server(timeout_sec=60)
aprietes = [float(v) for v in (args[1] if len(args) > 1 else 'cerrar,0.08,0.04,0.02').replace('cerrar', '-1').split(',')]
COLORES_P = (args[2] if len(args) > 2 else 'verde').split(',')   # cubo que se agarra: verde centro, rojo izquierda (+13 cm, lado del mástil), azul derecha
CASOS = [(ap, col) for col in COLORES_P for ap in aprietes]
f = open(args[0], 'w', newline=''); w = csv.writer(f)
w.writerow(['apriete', 'pinza_rad', 'quieto_giro_real_deg', 'quieto_desp_cm', 'prueba', 'giro_odom_deg', 'giro_real_deg', 'dif_deg', 'desp_m', 'cubo_z_final'])
print(f'vecinos: {"NO (alejados a ~18 m)" if SIN_VECINOS else "sí (±13 cm)"}', flush=True)
for ap, col in CASOS:
    st['col'] = col; st['fase'] = 'preparar'
    set_cube_pose(0.0, 0.0, 0.0, 0.02, 'tb3_so101'); esperar(2.0)     # cada caso desde el inicio (lejos de los cilindros)
    fu = obs.call_async(Trigger.Request()); rclpy.spin_until_future_complete(n, fu, timeout_sec=60); esperar(1.0)
    x, y, th = st['gt']; c_, s_ = math.cos(th), math.sin(th)
    for nom, lat in (('pick_object', 0.0), ('cubo_rojo', 0.13), ('cubo_azul', -0.13)):
        if SIN_VECINOS and nom != NOMBRE_CUBO[col]:
            set_cube_pose(18.0, 18.0 + 0.5 * lat / 0.13, 0.0, name=nom)       # fuera del alcance (suelo de 40x40 m, arena de 15 m)
        else:
            set_cube_pose(x + 0.16 * c_ - lat * s_, y + 0.16 * s_ + lat * c_, th, name=nom)
    esperar(1.5)
    st['fase'] = 'agarre'
    g = Pick.Goal(); g.strategy = 'ik_directa'; g.color = col; g.hold = True
    fu = pick.send_goal_async(g); rclpy.spin_until_future_complete(n, fu); r = fu.result().get_result_async()
    rclpy.spin_until_future_complete(n, r)
    if not r.result().result.success:
        print(f'apriete {ap}: agarre fallido ({r.result().result.message})', flush=True); st['fase'] = 'fallo'; continue
    p = st.get('gripper', 0.0)
    if ap >= 0:
        gg = GripperCommand.Goal(); gg.command.position = float(p - ap); gg.command.max_effort = 1.0
        grip.send_goal_async(gg); esperar(2.0)
    p2 = st.get('gripper', 0.0)
    st['fase'] = 'asentar'
    esperar(2.0); g0 = st['gt']; st['fase'] = 'quieto'; esperar(8.0); g1 = st['gt']
    qg, qd = math.degrees(math.remainder(g1[2] - g0[2], 2 * math.pi)), 100 * math.hypot(g1[0] - g0[0], g1[1] - g0[1])
    nombre = ('cerrar(0.0)' if ap < 0 else f'{ap:.2f}') + '_' + col
    cz = st.get('z_' + NOMBRE_CUBO[col], 0)
    print(f'apriete {nombre}: pinza {p:.3f} -> {p2:.3f} rad; QUIETO 8 s: giro real {qg:+.1f}°, desplazamiento {qd:.1f} cm; cubo z {cz:.3f}', flush=True)
    for nom_p, wz, vx in (('giro', -0.6, 0.0), ('giro_avance', 0.6, 0.12), ('avance', 0.0, 0.15)):
        st['fase'] = nom_p
        go, gr, d = mover(wz, vx, 4.0)
        cz = st.get('z_' + NOMBRE_CUBO[col], 0)
        w.writerow([nombre, round(p2, 3), round(qg, 1), round(qd, 1), nom_p, round(go, 1), round(gr, 1), round(gr - go, 1), round(d, 3), round(cz, 3)]); f.flush()
        print(f'    {nom_p:12s}: odometría {go:+6.1f}°  real {gr:+6.1f}°  diferencia {gr - go:+5.1f}°  cubo z {cz:.3f}', flush=True)
    st['fase'] = 'soltar'
    fu = rel.call_async(Trigger.Request()); rclpy.spin_until_future_complete(n, fu, timeout_sec=60)
    st['fase'] = 'fin'; esperar(1.0)
if ft:
    ft.close()
rclpy.shutdown()
