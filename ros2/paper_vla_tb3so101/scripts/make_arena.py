#!/usr/bin/env python3
"""Genera, desde config/arena.yaml, el mundo SDF (Gazebo Fortress) y el mapa PGM/YAML de Nav2, coherentes entre sí."""
import os, yaml
HERE = os.path.dirname(os.path.abspath(__file__)); PKG = os.path.dirname(HERE)
cfg = yaml.safe_load(open(os.path.join(PKG, 'config', 'arena.yaml'), encoding='utf-8'))
A = cfg['arena']; W, H = A['width'], A['height']; ox, oy = A['origin']; res = A['resolution']; t = A['wall_thickness']
obs = cfg['obstacles']

# ---------------- mapa
nx, ny = int(round(W / res)), int(round(H / res))
rows = []
for r in range(ny):
    y = oy + (ny - 1 - r + 0.5) * res
    row = bytearray([254]) * nx
    for c in range(nx):
        x = ox + (c + 0.5) * res
        occ = x < ox + t or x > ox + W - t or y < oy + t or y > oy + H - t
        if not occ:
            occ = any((x - o['x']) ** 2 + (y - o['y']) ** 2 <= o['radius'] ** 2 for o in obs)
        if occ: row[c] = 0
    rows.append(bytes(row))
with open(os.path.join(PKG, 'maps', 'paper_vla_arena.pgm'), 'wb') as f:
    f.write(f'P5\n{nx} {ny}\n255\n'.encode())
    for r in rows: f.write(r)
open(os.path.join(PKG, 'maps', 'paper_vla_arena.yaml'), 'w').write(
    f"image: paper_vla_arena.pgm\nmode: trinary\nresolution: {res}\norigin: [{ox}, {oy}, 0.0]\nnegate: 0\noccupied_thresh: 0.65\nfree_thresh: 0.25\n")

# ---------------- mundo
def box(name, x, y, sx, sy, sz=0.5):
    return f"""    <model name="{name}"><static>true</static><pose>{x:.3f} {y:.3f} {sz/2:.3f} 0 0 0</pose>
      <link name="link">
        <collision name="c"><geometry><box><size>{sx:.3f} {sy:.3f} {sz:.3f}</size></box></geometry></collision>
        <visual name="v"><geometry><box><size>{sx:.3f} {sy:.3f} {sz:.3f}</size></box></geometry>
          <material><ambient>0.35 0.35 0.4 1</ambient><diffuse>0.35 0.35 0.4 1</diffuse></material></visual>
      </link></model>"""
def cyl(o):
    return f"""    <model name="{o['name']}"><static>true</static><pose>{o['x']:.3f} {o['y']:.3f} 0.25 0 0 0</pose>
      <link name="link">
        <collision name="c"><geometry><cylinder><radius>{o['radius']}</radius><length>0.5</length></cylinder></geometry></collision>
        <visual name="v"><geometry><cylinder><radius>{o['radius']}</radius><length>0.5</length></cylinder></geometry>
          <material><ambient>0.85 0.35 0.1 1</ambient><diffuse>0.85 0.35 0.1 1</diffuse></material></visual>
      </link></model>"""
def pick(c):
    s, m = c['size'], c['mass']; i = m * s * s / 6
    return f"""    <model name="pick_object"><pose>{c['x']:.3f} {c['y']:.3f} {s/2:.4f} 0 0 0</pose>
      <link name="link">
        <inertial><mass>{m}</mass><inertia><ixx>{i:.3e}</ixx><iyy>{i:.3e}</iyy><izz>{i:.3e}</izz></inertia></inertial>
        <collision name="c"><geometry><box><size>{s} {s} {s}</size></box></geometry>
          <surface><friction><ode><mu>1.5</mu><mu2>1.5</mu2></ode></friction></surface></collision>
        <visual name="v"><geometry><box><size>{s} {s} {s}</size></box></geometry>
          <material><ambient>0.1 0.85 0.1 1</ambient><diffuse>0.1 0.85 0.1 1</diffuse></material></visual>
      </link></model>"""
def cubo(c, size, mass):
    i = mass * size * size / 6; r, g, b = c['rgb']
    return f"""    <model name="{c['name']}"><pose>{c['x']:.3f} {c['y']:.3f} {size/2:.4f} 0 0 0</pose>
      <link name="link">
        <inertial><mass>{mass}</mass><inertia><ixx>{i:.3e}</ixx><iyy>{i:.3e}</iyy><izz>{i:.3e}</izz></inertia></inertial>
        <collision name="c"><geometry><box><size>{size} {size} {size}</size></box></geometry>
          <surface><friction><ode><mu>1.5</mu><mu2>1.5</mu2></ode></friction></surface></collision>
        <visual name="v"><geometry><box><size>{size} {size} {size}</size></box></geometry>
          <material><ambient>{r} {g} {b} 1</ambient><diffuse>{r} {g} {b} 1</diffuse></material></visual>
      </link></model>"""
def plato(c):
    return f"""    <model name="plato_entrega"><static>true</static><pose>{c['x']:.3f} {c['y']:.3f} 0.002 0 0 0</pose>
      <link name="link"><visual name="v"><geometry><cylinder><radius>{c['radius']}</radius><length>0.004</length></cylinder></geometry>
        <material><ambient>0.15 0.35 0.9 1</ambient><diffuse>0.15 0.35 0.9 1</diffuse></material></visual></link></model>"""
walls = [box('wall_bottom', ox + W / 2, oy + t / 2, W, t), box('wall_top', ox + W / 2, oy + H - t / 2, W, t),
         box('wall_left', ox + t / 2, oy + H / 2, t, H), box('wall_right', ox + W - t / 2, oy + H / 2, t, H)]
sdf = f"""<?xml version="1.0" ?>
<!-- GENERADO por scripts/make_arena.py desde config/arena.yaml. No editar a mano. -->
<sdf version="1.8">
  <world name="paper_vla_world">
    <physics name="1ms" type="ignored"><max_step_size>0.001</max_step_size><real_time_factor>1.0</real_time_factor></physics>
    <plugin filename="gz-sim-physics-system" name="gz::sim::systems::Physics"/>
    <plugin filename="gz-sim-user-commands-system" name="gz::sim::systems::UserCommands"/>
    <plugin filename="gz-sim-scene-broadcaster-system" name="gz::sim::systems::SceneBroadcaster"/>
    <plugin filename="gz-sim-sensors-system" name="gz::sim::systems::Sensors"><render_engine>ogre2</render_engine></plugin>
    <plugin filename="gz-sim-imu-system" name="gz::sim::systems::Imu"/>
    <light type="directional" name="sun"><cast_shadows>true</cast_shadows><pose>0 0 10 0 0 0</pose>
      <diffuse>0.9 0.9 0.9 1</diffuse><specular>0.3 0.3 0.3 1</specular><direction>-0.5 0.1 -0.9</direction></light>
    <model name="ground_plane"><static>true</static><link name="link">
      <collision name="collision"><geometry><plane><normal>0 0 1</normal><size>40 40</size></plane></geometry></collision>
      <visual name="visual"><geometry><plane><normal>0 0 1</normal><size>40 40</size></plane></geometry>
        <material><ambient>0.75 0.75 0.75 1</ambient><diffuse>0.75 0.75 0.75 1</diffuse></material></visual></link></model>
{chr(10).join(walls)}
{chr(10).join(cyl(o) for o in obs)}
{chr(10).join(cubo(c, cfg['pick_object']['size'], cfg['pick_object']['mass']) for c in cfg['cubos']) if 'cubos' in cfg else pick(cfg['pick_object'])}
{plato(cfg['mision']['plato'])}
  </world>
</sdf>
"""
open(os.path.join(PKG, 'worlds', 'paper_vla_arena.sdf'), 'w').write(sdf)
print(f"mapa {nx}x{ny} px y mundo generados; obstáculos: {[o['name'] for o in obs]}")


# ---------------- mundo con cámaras externas (SOLO para fotografiar el robot en las figuras del paper; las pruebas usan paper_vla_arena.sdf)
def vista(name, pose, w=1280, h=960, hfov=1.0):
    return f"""    <model name="{name}"><static>true</static><pose>{pose}</pose>
      <link name="link"><sensor name="cam" type="camera"><topic>{name}/image_raw</topic><update_rate>5</update_rate><always_on>true</always_on>
        <camera><horizontal_fov>{hfov}</horizontal_fov><image><width>{w}</width><height>{h}</height><format>R8G8B8</format></image><clip><near>0.05</near><far>100</far></clip></camera></sensor></link></model>
"""
cams = (vista('vista_arena', f"{ox + W/2:.2f} {oy + H/2:.2f} 17 0 1.5708 0", hfov=1.15) +
        vista('vista_robot', '0.85 -0.80 0.50 0 0.25 2.38', hfov=0.95) +
        vista('vista_robot2', '0.20 -1.00 0.40 0 0.20 1.57', hfov=0.95) +
        vista('vista_meta', '3.10 0.55 0.55 0 0.30 2.28', hfov=1.0))
open(os.path.join(PKG, 'worlds', 'paper_vla_arena_vistas.sdf'), 'w').write(sdf.replace("  </world>", cams + "  </world>"))
print('mundo con vistas generado')
