#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
export HOST_UID HOST_GID
HOST_UID=$(id -u)
HOST_GID=$(id -g)
compose=(docker compose --project-directory "$ROOT" --env-file "$ROOT/.env" -f "$ROOT/compose.yaml")

init() {
    if (( HOST_UID == 0 )); then
        echo 'Запускайте make от work, без sudo.' >&2
        exit 1
    fi
    [[ -f .env ]] || cp .env.example .env
    mkdir -p ros2_ws/src .runtime/xauth
    chmod 700 .runtime .runtime/xauth
}

gui_auth() {
    : "${DISPLAY:?Запустите команду из терминала графического сеанса KDE.}"
    command -v xauth >/dev/null || { echo 'На хосте нужен xauth.' >&2; exit 1; }
    local record temporary
    record=$(xauth nlist "$DISPLAY" 2>/dev/null)
    [[ -n "$record" ]] || { echo 'Нет X11-авторизации. Откройте новый терминал KDE и повторите make up.' >&2; exit 1; }
    temporary=$(mktemp "$ROOT/.runtime/xauth/.Xauthority.XXXXXX")
    if ! printf '%s\n' "$record" | sed 's/^..../ffff/' | xauth -f "$temporary" nmerge -; then
        rm -f -- "$temporary"
        return 1
    fi
    [[ -s "$temporary" ]] || { rm -f -- "$temporary"; return 1; }
    chmod 600 "$temporary"
    # Mount the directory, so replacement also works for a running container.
    mv -f -- "$temporary" "$ROOT/.runtime/xauth/Xauthority"
}

running() {
    [[ -n "$("${compose[@]}" ps --status running -q robo)" ]] || {
        echo 'Контейнер остановлен. Сначала выполните make up.' >&2
        exit 1
    }
}

gui_running() {
    running
    gui_auth
    local id current_display
    id=$("${compose[@]}" ps -q robo)
    current_display=$(docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "$id" | sed -n 's/^DISPLAY=//p')
    [[ "$current_display" == "$DISPLAY" ]] || {
        echo 'DISPLAY изменился. Выполните make up, чтобы обновить контейнер.' >&2
        exit 1
    }
}

exec_ros() {
    local options=()
    [[ -t 0 && -t 1 ]] || options+=(-T)
    "${compose[@]}" exec "${options[@]}" robo /usr/local/bin/robo-exec "$@"
}

command=${1:-help}
(( $# == 0 )) || shift
init
case "$command" in
    init) echo "Готово: $ROOT/ros2_ws/src; настройки в .env." ;;
    config) "${compose[@]}" config --quiet ;;
    build) "${compose[@]}" build "$@" robo ;;
    up) gui_auth; "${compose[@]}" up -d --no-build robo ;;
    stop) "${compose[@]}" stop robo ;;
    down) "${compose[@]}" down ;;
    restart) gui_auth; "${compose[@]}" up -d --force-recreate robo ;;
    rebuild|rebuild-clean)
        gui_auth
        options=()
        [[ "$command" != rebuild-clean ]] || options+=(--no-cache)
        "${compose[@]}" build "${options[@]}" robo
        "${compose[@]}" up -d --force-recreate robo
        ;;
    shell) gui_running; exec "${compose[@]}" exec robo bash ;;
    root) gui_running; exec "${compose[@]}" exec --user root --env HOME=/root robo bash ;;
    status) "${compose[@]}" ps -a ;;
    logs) "${compose[@]}" logs --follow --tail=100 robo ;;
    run) running; : "${CMD:?Пример: make run CMD='ros2 topic list'}"; exec_ros bash -lc "$CMD" ;;
    exec) running; (( $# > 0 )); exec_ros "$@" ;;
    opengl) gui_running; exec_ros glxinfo -B ;;
    gazebo) gui_running; exec_ros ign gazebo -v 3 -r /usr/share/ignition/ignition-gazebo6/worlds/empty.sdf ;;
    hw1)
        gui_running
        exec_ros colcon build --symlink-install --packages-select jetbot_target_follower
        exec_ros env ROS_DOMAIN_ID=45 ROS_LOCALHOST_ONLY=1 IGN_PARTITION=robo_hw1 ros2 launch jetbot_target_follower perception_sim.launch.py
        ;;
    hw1-drive)
        gui_running
        exec_ros colcon build --symlink-install --packages-select jetbot_target_follower
        exec_ros env ROS_DOMAIN_ID=45 ROS_LOCALHOST_ONLY=1 IGN_PARTITION=robo_hw1 ros2 launch jetbot_target_follower drive_sim.launch.py
        ;;
    # Готовый клавиатурный узел: команды направляются в router, а не прямо к колёсам.
    # Ноль (клавиша k) освобождает ручной режим для автономного после тайм-аута mux.
    # Домен 45 относится только к симулятору, не к физическому Jetbot.
    hw1-teleop)
        running
        exec_ros env ROS_DOMAIN_ID=45 ROS_LOCALHOST_ONLY=1 ros2 run teleop_twist_keyboard teleop_twist_keyboard --ros-args -r cmd_vel:=/cmd_vel_teleop -p speed:=0.12 -p turn:=0.5 -p repeat_rate:=10.0 -p key_timeout:=0.3
        ;;
    # Готовый просмотрщик показывает размеченный кадр детектора: рамку, оси и расстояние.
    # Сам просмотрщик не распознаёт маркеры и не публикует команды движения.
    hw1-view)
        gui_running
        exec_ros env ROS_DOMAIN_ID=45 ROS_LOCALHOST_ONLY=1 ros2 run rqt_image_view rqt_image_view /target/debug_image
        ;;
    warehouse) gui_running; exec_ros ign gazebo -v 4 -r /work/assets/worlds/warehouse/jetbot_warehouse.sdf ;;
    lidar) gui_running; exec_ros ign gazebo -v 3 -r /usr/share/ignition/ignition-gazebo6/worlds/visualize_lidar.sdf ;;
    rviz) gui_running; exec_ros rviz2 ;;
    run-rosdep)
        running
        exec_ros bash -lc 'sudo apt-get update && rosdep update --rosdistro humble && rosdep install --from-paths src --ignore-src --rosdistro humble -r -y'
        ;;
    doctor)
        printf 'Ядро: '; uname -r
        command -v xauth
        docker compose version
        docker info --format 'Docker root: {{.DockerRootDir}}; NVIDIA runtime: {{if index .Runtimes "nvidia"}}yes{{else}}NO{{end}}'
        nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv
        "${compose[@]}" config --quiet
        "${compose[@]}" ps -a
        if [[ -n "$("${compose[@]}" ps --status running -q robo)" ]]; then
            exec_ros bash -lc 'id; echo "ROS_DISTRO=$ROS_DISTRO ROS_DOMAIN_ID=$ROS_DOMAIN_ID ROS_LOCALHOST_ONLY=$ROS_LOCALHOST_ONLY"; ros2 pkg prefix ros_gz_bridge; ign gazebo --versions'
        fi
        ;;
    *) echo "Неизвестная команда: $command. Используйте make help." >&2; exit 2 ;;
esac
