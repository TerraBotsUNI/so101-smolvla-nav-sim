cmake_minimum_required(VERSION 3.8)
project(paper_vla_tb3so101)
find_package(ament_cmake REQUIRED)
install(DIRECTORY urdf launch config worlds maps scripts meshes DESTINATION share/${PROJECT_NAME})
install(PROGRAMS scripts/nav_trial.py scripts/so101_manip_server.py scripts/so101_pick_client.py scripts/so101_trial.py
        scripts/so101_manipulation.py scripts/so101_kinematics.py scripts/so101_mision.py scripts/guardar_ubicacion.py scripts/so101_demos.py scripts/so101_grabador.py DESTINATION lib/${PROJECT_NAME})
ament_package()
