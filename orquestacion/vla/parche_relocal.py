"""Parche (14-nov, sobre parche_afinar.py): relocalización local de AMCL antes del acercamiento fino en la entrega.
Tras llevar el cubo, AMCL queda con ~9 cm y ~9° de sesgo y partículas muy concentradas (no cubren la pose real). Se reabre la incertidumbre
alrededor de la estimación actual (/initialpose con sigma 0.15 m y 0.3 rad) y se fuerzan actualizaciones del LiDAR sin mover la base
(servicio request_nomotion_update de nav2_amcl). Solo usa LiDAR + mapa. Uso: python3 parche_relocal.py <so101_mision.py>"""
import sys
f = sys.argv[1]; s = open(f, encoding='utf-8').read()
assert 'def afinar' in s and 'def relocal_local' not in s

a = "    def afinar(self, name, tol=0.015, iters=3):\n"
b = '''    def relocal_local(self, sigma=0.15, sigma_yaw=0.3, n=25):
        """Reabre la nube de partículas de AMCL alrededor de su estimación actual y la deja converger con el LiDAR sin mover la base."""
        from std_srvs.srv import Empty
        if not hasattr(self, 'nomotion'):
            self.nomotion = self.create_client(Empty, '/request_nomotion_update')
        p = self.pose_actual()
        if p is None or not self.nomotion.wait_for_service(timeout_sec=5):
            print('    relocal: sin pose o sin servicio request_nomotion_update', flush=True); return
        p.pose.covariance[0] = p.pose.covariance[7] = sigma ** 2; p.pose.covariance[35] = sigma_yaw ** 2
        for _ in range(2):
            p.header.stamp = self.get_clock().now().to_msg(); self.pose_pub.publish(p); self.spin_for(0.3)
        x0, y0 = p.pose.pose.position.x, p.pose.pose.position.y
        r = self.robot_xy()                                   # solo medición para el registro (no se usa para controlar)
        e0 = None if r is None else 1000 * math.hypot(r[0] - x0, r[1] - y0)
        for _ in range(n):
            fu = self.nomotion.call_async(Empty.Request()); rclpy.spin_until_future_complete(self, fu, timeout_sec=2); self.spin_for(0.3)
        q = self.pose_actual(); r = self.robot_xy()
        if q is not None:
            x1, y1 = q.pose.pose.position.x, q.pose.pose.position.y
            e1 = None if r is None else 1000 * math.hypot(r[0] - x1, r[1] - y1)
            print(f'    relocal: AMCL se movió {1000 * math.hypot(x1 - x0, y1 - y0):.0f} mm; error real de AMCL {e0:.0f} -> {e1:.0f} mm (medición)', flush=True)

''' + a
assert a in s; s = s.replace(a, b, 1)

a = "            print(f'[{i}] AFINAR (pose AMCL)', flush=True); self.afinar('entrega')"
b = ("            print(f'[{i}] AFINAR (pose AMCL)', flush=True)\n"
     "            if self.relocal_on:\n"
     "                self.relocal_local()\n"
     "            self.afinar('entrega')")
assert a in s; s = s.replace(a, b, 1)

a = "    ap.add_argument('--desde'"
b = "    ap.add_argument('--sin-relocal', action='store_true', help='no reabrir AMCL (relocalización local) antes de afinar en la entrega')\n" + a
assert a in s; s = s.replace(a, b, 1)
a = "    n.afinar_on = not a.sin_afinar\n"
assert a in s; s = s.replace(a, a + "    n.relocal_on = not a.sin_relocal\n", 1)
open(f, 'w', encoding='utf-8', newline='\n').write(s); print('ok relocal')
