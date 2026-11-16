"""Parche (14-nov): acercamiento fino en la entrega con la pose de AMCL (TF map->base_footprint), sin verdad de Gazebo.
Nav2 da la meta por alcanzada a < xy_goal_tolerance (0.12 m) y el robot se quedaba ~14 cm corto; el cubo caía fuera del plato (radio 0.10).
Uso: python3 parche_afinar.py <so101_mision.py>"""
import sys
f = sys.argv[1]; s = open(f, encoding='utf-8').read()
assert 'def afinar' not in s

a = "'nav2_ok', 'nav2_s', 'nav2_err_mm', 'cubo_sujeto', 'place_ok', 'place_msg', 'place_s', 'cubo_err_plato_mm', 'total_s']"
assert a in s; s = s.replace(a, a[:-1] + ", 'afinar_err_mm']", 1)

a = "    def _err(self, x, y):\n"
b = '''    def afinar(self, name, tol=0.015, iters=3):
        """Acercamiento fino tras Nav2 (como un «docking»): con la pose ESTIMADA por AMCL (TF map->base_footprint) gira hacia la meta,
        avanza (o retrocede si la meta queda detrás) con odometría y termina orientado al rumbo de la meta. Nav2 da la meta por
        alcanzada a < xy_goal_tolerance (0.12 m), y en la entrega no hay otra corrección antes de colocar. Devuelve el resto estimado (m)."""
        x, y, yaw = self.loc(name)
        ang_n = lambda a: math.atan2(math.sin(a), math.cos(a))
        d = None
        for it in range(iters):
            self.spin_for(0.5); p = self.pose_actual()
            if p is None:
                return None
            q = p.pose.pose.orientation; th = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y ** 2 + q.z ** 2))
            dx, dy = x - p.pose.pose.position.x, y - p.pose.pose.position.y; d = math.hypot(dx, dy)
            if d < tol:
                break
            giro, dist = ang_n(math.atan2(dy, dx) - th), d
            if abs(giro) > math.pi / 2:                     # la meta queda detrás: retrocede en vez de dar media vuelta
                giro, dist = ang_n(giro - math.pi), -d
            print(f'    afinar {it + 1}: faltan {1000 * d:.0f} mm según AMCL -> giro {math.degrees(giro):+.1f} grados, avanzo {1000 * dist:+.0f} mm', flush=True)
            self._drive(turn=giro, dist=dist)
        self.spin_for(0.5); p = self.pose_actual()
        if p is not None:
            q = p.pose.pose.orientation; th = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y ** 2 + q.z ** 2))
            e = ang_n(yaw - th)
            if abs(e) > 0.02:
                print(f'    afinar: oriento {math.degrees(e):+.1f} grados', flush=True); self._drive(turn=e)
        return d

    def _err(self, x, y):
'''
assert a in s; s = s.replace(a, b, 1)

a = '''        if not ok:
            return fin('nav_entrega')
        print(f'[{i}] COLOCAR', flush=True)'''
b = '''        if not ok:
            return fin('nav_entrega')
        if self.afinar_on:
            print(f'[{i}] AFINAR (pose AMCL)', flush=True); self.afinar('entrega')
            x_e, y_e, _ = self.loc('entrega'); e2 = self._err(x_e, y_e)
            row['afinar_err_mm'] = None if e2 is None else round(e2, 1)   # error real tras afinar (solo medición)
        print(f'[{i}] COLOCAR', flush=True)'''
assert a in s; s = s.replace(a, b, 1)

a = "    ap.add_argument('--desde'"
b = "    ap.add_argument('--sin-afinar', action='store_true', help='no hacer el acercamiento fino con AMCL en la entrega (comportamiento anterior)')\n" + a
assert a in s; s = s.replace(a, b, 1)

a = "    rclpy.init(); n = Mision(ub, 0.04, a.seed)\n"
assert a in s; s = s.replace(a, a + "    n.afinar_on = not a.sin_afinar\n", 1)

open(f, 'w', encoding='utf-8', newline='\n').write(s); print('ok afinar')
