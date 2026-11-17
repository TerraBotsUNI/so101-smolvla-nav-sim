# Configuraciones

Las configuraciones viven dentro del paquete ROS (`ros2/paper_vla_tb3so101/`), porque `colcon` las instala desde ahí. Esta carpeta es el índice y guarda el parche del overlay de la pinza.

## Nav2

| Archivo | Uso |
|---|---|
| `ros2/paper_vla_tb3so101/config/nav2_mision.yaml` | Nav2 de la misión: AMCL (configuración A2: alpha1 0.4, alpha2 0.3, alpha3-5 0.1, recovery_alpha_fast 0.1, slow 0.001), SmacPlanner2D y MPPI; footprint con la lengüeta del brazo hasta 0.22 m |
| `ros2/paper_vla_tb3so101/config/nav2_mppi.yaml`, `nav2_dwb.yaml`, `nav2_rpp.yaml` | un controlador cada uno con parámetros por defecto (generados por `scripts/make_nav2_params.py`); base para `controller:=mppi|dwb|rpp` |
| `orquestacion/vla/nav_so101/nav2_so101_{mppi,dwb,rpp}.yaml` | **los usados en la Tabla IX**: idénticos a `nav2_mision.yaml` (AMCL, mapas de costos, contorno con el brazo) salvo el bloque `controller_server`, tomado de los anteriores; se pasan con `params_file:=` desde `orquestacion/vla/nav_batch_so101.sh` |
| `ros2/paper_vla_tb3so101/config/controllers.yaml` | controladores de `ros2_control` (base, brazo y pinza) |
| `ros2/paper_vla_tb3so101/config/bridge.yaml` | puente ROS-Gazebo (incluye `/scene_camera/image_raw`) |
| `ros2/paper_vla_tb3so101/config/arena.yaml`, `ubicaciones.yaml` | arena (genera mundo y mapa con `make_arena.py`) y poses de recojo y entrega |

El controlador se elige con `ros2 launch paper_vla_tb3so101 nav.launch.py controller:=mppi|dwb|rpp|mision`.

## Robot (URDF/xacro)

| Archivo | Contenido |
|---|---|
| `ros2/paper_vla_tb3so101/urdf/tb3_so101_fortress.urdf.xacro` | robot completo: TurtleBot3 Waffle Pi + SO-101, rueda loca delantera, `lidar_range_min` 0.20 |
| `ros2/paper_vla_tb3so101/urdf/so101.urdf.xacro` | brazo SO-101 (cadena del URDF oficial). **Articulación `gripper`: `<limit effort="2.0">`** (2 N·m, cercano al servo STS3215 real) |
| `ros2/paper_vla_tb3so101/urdf/fortress_sim.xacro` | sensores y plugins; mástil `mast_link` y cámara de escena `scene_camera` (640×480, 15 Hz) |

### Por qué 2 N·m y el overlay de 10 N·m

La pinza usa `position_controllers/GripperActionController`, que ignora `max_effort`: la fuerza real la limita el URDF. Con el valor original (10 N·m) la mordaza se hundía en el cubo y Gazebo generaba fuerzas de contacto espurias que hacían girar y patinar al robot con las ruedas quietas, de modo que AMCL se perdía en el transporte. Con 2 N·m la mordaza se detiene en la superficie del cubo y el giro espurio desaparece (banco en `datos/16nov/banco_pinza_10_vs_2Nm/`).

Las demostraciones v1 se grabaron con 10 N·m. Para reproducirlo se compila un overlay del paquete con un solo cambio:

```bash
git clone <este_repo> <copia_repo> && git -C <copia_repo> apply config/overlay_pinza_10Nm.patch   # effort="10" en la pinza (o editar a mano)
colcon build --base-paths <copia_repo>/ros2 --install-base $PROYECTO/overlays/pinza_10Nm/install --packages-select paper_vla_tb3so101
source $PROYECTO/overlays/pinza_10Nm/install/setup.bash   # después del entorno normal
```

`orquestacion/banco_pinza/limite_pinza.py` comprueba el límite efectivo leyendo `robot_description`.
