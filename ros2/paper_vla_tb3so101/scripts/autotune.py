#!/usr/bin/python3
"""Autotuneo de los controladores locales de Nav2 (MPPI, DWB, RPP) por BÚSQUEDA ALEATORIA reproducible, con validación en un escenario distinto.

Protocolo (para que la comparación sea justa y no haya sobreajuste):
  - Mismo presupuesto para los tres controladores: K candidatos (el candidato 0 es la configuración por defecto del proyecto) y los mismos
    3 objetivos de ENTRENAMIENTO, distintos de la meta del paper (2.0, 1.5): cada (candidato, objetivo) es un ensayo con simulación nueva.
  - Puntuación (menor = mejor), promedio de los objetivos:  t_sim + 20*error_final + 0.5*recuperaciones + 50*(no éxito) + 20*(colisión).
  - Se guarda la mejor configuración y se EVALÚA en la meta del paper (escenario de prueba, no usado al afinar) con N ensayos nuevos.
  - Semilla fija (--seed): el muestreo de candidatos se repite exactamente. Cada candidato queda en autotune/<ctrl>/cand_XX.json.
  - La velocidad máxima NO se afina (0.26 m/s es la especificación del Waffle Pi): solo parámetros del controlador.
Uso: autotune.py --controller mppi --candidates 12 --eval-n 30 --domain 80
"""
import argparse, copy, csv, json, math, os, random, signal, subprocess, sys, time
import yaml

B = os.path.join(os.environ.get('PROYECTO', os.path.expanduser('~/proyecto/paper_rover_vla_2025')), 'colcon')
CFG = f'{B}/install/paper_vla_tb3so101/share/paper_vla_tb3so101/config'
TRAIN_GOALS = [(3.5, 0.0, 0.0), (-2.0, 3.0, 0.0), (4.0, 3.5, 0.0)]
PAPER_GOAL = (2.0, 1.5, 0.0)
# (ruta dentro de controller_server.ros__parameters, tipo, mínimo, máximo)
SPACES = {
    'mppi': [(('FollowPath', 'temperature'), 'f', 0.1, 0.6), (('FollowPath', 'time_steps'), 'i', 30, 60),
             (('FollowPath', 'PathAlignCritic', 'cost_weight'), 'f', 8, 40), (('FollowPath', 'PathFollowCritic', 'cost_weight'), 'f', 8, 40),
             (('FollowPath', 'GoalCritic', 'cost_weight'), 'f', 2, 10), (('FollowPath', 'CostCritic', 'cost_weight'), 'f', 1, 8),
             (('FollowPath', 'PathAngleCritic', 'cost_weight'), 'f', 2, 12)],
    'dwb': [(('FollowPath', 'PathAlign.scale'), 'f', 8, 48), (('FollowPath', 'PathDist.scale'), 'f', 8, 48),
            (('FollowPath', 'GoalDist.scale'), 'f', 8, 48), (('FollowPath', 'GoalAlign.scale'), 'f', 8, 48),
            (('FollowPath', 'BaseObstacle.scale'), 'f', 0.01, 0.5), (('FollowPath', 'sim_time'), 'f', 1.0, 2.5),
            (('FollowPath', 'vtheta_samples'), 'i', 10, 30)],
    'rpp': [(('FollowPath', 'lookahead_dist'), 'f', 0.3, 1.2), (('FollowPath', 'regulated_linear_scaling_min_radius'), 'f', 0.5, 1.5),
            (('FollowPath', 'approach_velocity_scaling_dist'), 'f', 0.3, 1.0), (('FollowPath', 'rotate_to_heading_angular_vel'), 'f', 1.0, 2.0),
            (('FollowPath', 'max_allowed_time_to_collision_up_to_carrot'), 'f', 0.5, 2.0)],
}


def get(d, path):
    for k in path: d = d[k]
    return d


def put(d, path, v):
    for k in path[:-1]: d = d[k]
    d[path[-1]] = v


def make_params(ctrl, values, out):
    d = yaml.safe_load(open(f'{CFG}/nav2_{ctrl}.yaml'))
    cp = d['controller_server']['ros__parameters']
    for (path, typ, lo, hi), v in zip(SPACES[ctrl], values):
        put(cp, path, int(v) if typ == 'i' else float(v))
    if ctrl == 'rpp':   # coherencia: la distancia de anticipación debe quedar entre el mínimo y el máximo
        fp = cp['FollowPath']; fp['min_lookahead_dist'] = min(fp['min_lookahead_dist'], fp['lookahead_dist']); fp['max_lookahead_dist'] = max(fp['max_lookahead_dist'], fp['lookahead_dist'])
    yaml.safe_dump(d, open(out, 'w'), sort_keys=False)


def base_values(ctrl):
    d = yaml.safe_load(open(f'{CFG}/nav2_{ctrl}.yaml'))['controller_server']['ros__parameters']
    return [get(d, p) for p, *_ in SPACES[ctrl]]


def sample(ctrl, rng):
    out = []
    for p, typ, lo, hi in SPACES[ctrl]:
        out.append(rng.randint(lo, hi) if typ == 'i' else round(rng.uniform(lo, hi), 4))
    return out


def run_trial(ctrl, params_file, goal, domain, tag, out_csv=None, tries=2):
    """Simulación nueva + Nav2 con params_file + un ensayo hacia `goal`. Devuelve el dict de nav_trial o {'error': ...}."""
    env = dict(os.environ, ROS_DOMAIN_ID=str(domain), IGN_PARTITION=f'paper_vla_tune_{domain}', GZ_PARTITION=f'paper_vla_tune_{domain}', __GLX_VENDOR_LIBRARY_NAME='nvidia')
    setup = f'source /opt/ros/humble/setup.bash; source {B}/install/setup.bash;'
    for attempt in range(tries):
        log = open(f'{B}/autotune/log_{ctrl}_{tag}.txt', 'w')
        p = subprocess.Popen(['bash', '-c', f'{setup} exec ros2 launch paper_vla_tb3so101 nav.launch.py controller:={ctrl} headless:=true params_file:={params_file}'],
                             env=env, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, preexec_fn=os.setsid)
        res = {'error': 'Nav2 no se activó'}
        try:
            t0 = time.time(); ok = False
            while time.time() - t0 < 180 and not ok:
                time.sleep(5)
                n_ok = 0
                for n in ('map_server', 'amcl', 'controller_server', 'planner_server', 'behavior_server', 'bt_navigator'):
                    r = subprocess.run(['bash', '-c', f'{setup} timeout 6 ros2 lifecycle get /{n}'], env=env, capture_output=True, text=True)
                    n_ok += r.stdout.strip().startswith('active')
                ok = n_ok == 6
            if ok:
                time.sleep(3)
                cmd = f'{setup} timeout 200 ros2 run paper_vla_tb3so101 nav_trial.py --controller {ctrl} --run-id {tag} --timeout 120 --goal {goal[0]} {goal[1]} {goal[2]}' + (f' --out {out_csv}' if out_csv else '')
                r = subprocess.run(['bash', '-c', cmd], env=env, capture_output=True, text=True)
                for line in reversed(r.stdout.strip().splitlines()):
                    if line.startswith('{'):
                        res = json.loads(line); break
                else:
                    res = {'error': 'sin salida de nav_trial: ' + r.stderr[-200:]}
        finally:
            for sig, wait in ((signal.SIGINT, 6), (signal.SIGTERM, 3), (signal.SIGKILL, 2)):
                try: os.killpg(p.pid, sig)
                except ProcessLookupError: break
                time.sleep(wait)
            time.sleep(3)
        if 'error' not in res:
            return res
    return res


def score(res):
    if 'error' in res:
        return 999.0
    pen = 0.0 if res.get('success') else 50.0
    pen += 20.0 if res.get('collision') else 0.0
    return res.get('time_sim_s', 120.0) + 20.0 * res.get('final_error_m', 1.0) + 0.5 * res.get('recoveries', 0) + pen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--controller', required=True, choices=list(SPACES)); ap.add_argument('--candidates', type=int, default=12)
    ap.add_argument('--eval-n', type=int, default=30); ap.add_argument('--domain', type=int, default=80); ap.add_argument('--seed', type=int, default=42)
    a = ap.parse_args(); ctrl = a.controller
    root = f'{B}/autotune/{ctrl}'; os.makedirs(root, exist_ok=True)
    rng = random.Random(a.seed)
    cands = [base_values(ctrl)] + [sample(ctrl, rng) for _ in range(a.candidates - 1)]
    results = []
    for k, vals in enumerate(cands):
        fn = f'{root}/cand_{k:02d}.json'
        if os.path.exists(fn):                                   # reanudable
            results.append(json.load(open(fn))); continue
        pf = f'{root}/params_{k:02d}.yaml'; make_params(ctrl, vals, pf)
        trials = []
        for gi, g in enumerate(TRAIN_GOALS):
            r = run_trial(ctrl, pf, g, a.domain, f'c{k:02d}g{gi}')
            trials.append({'goal': g, 'resultado': r, 'puntuacion': score(r)})
            print(f'[{ctrl}] cand {k} objetivo {gi}: puntuación {score(r):.1f}', flush=True)
        rec = {'candidato': k, 'valores': dict(zip(['.'.join(p) for p, *_ in SPACES[ctrl]], vals)), 'ensayos': trials,
               'puntuacion_media': sum(t['puntuacion'] for t in trials) / len(trials), 'es_base': k == 0}
        json.dump(rec, open(fn, 'w'), ensure_ascii=False, indent=1); results.append(rec)
    best = min(results, key=lambda r: r['puntuacion_media'])
    base = results[0]
    summary = {'controlador': ctrl, 'semilla': a.seed, 'candidatos': len(results), 'objetivos_entrenamiento': TRAIN_GOALS, 'meta_prueba': PAPER_GOAL,
               'puntuacion_base': base['puntuacion_media'], 'mejor_candidato': best['candidato'], 'puntuacion_mejor': best['puntuacion_media'], 'valores_mejor': best['valores']}
    json.dump(summary, open(f'{root}/resumen_busqueda.json', 'w'), ensure_ascii=False, indent=1)
    print('[%s] mejor candidato %d (puntuación %.1f frente a %.1f de la configuración por defecto)' % (ctrl, best['candidato'], best['puntuacion_media'], base['puntuacion_media']), flush=True)
    # evaluación en el escenario de prueba (meta del paper) con la configuración afinada
    best_pf = f'{root}/params_{best["candidato"]:02d}.yaml'
    out_csv = f'{B}/trials_{ctrl}_afinado.csv'
    done = 0
    if os.path.exists(out_csv):
        done = sum(1 for _ in open(out_csv)) - 1
    for i in range(done + 1, a.eval_n + 1):
        r = run_trial(ctrl, best_pf, PAPER_GOAL, a.domain, f'eval{i:02d}', out_csv=out_csv)
        print(f'[{ctrl}] evaluación {i}/{a.eval_n}: {r.get("status", r)}', flush=True)
    print('FIN', ctrl, flush=True)


if __name__ == '__main__':
    main()

