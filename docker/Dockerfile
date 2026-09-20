# Ubuntu 22.04 / ROS 2 Humble, the course image verified on 2026-09-20.
FROM osrf/ros:humble-desktop-full@sha256:1db1e4e941d4f77fab55bcd479158a75273329335e86ec468bff280859e8178c

SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ARG HOST_UID=1000
ARG HOST_GID=1000

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    build-essential cmake git git-lfs openssh-client sudo curl ca-certificates \
    nano less bash-completion htop mesa-utils xauth \
    python3-pip python3-venv python3-colcon-common-extensions \
    python3-rosdep python3-vcstool python3-opencv \
    ros-humble-ros-gz \
    ros-humble-rmw-cyclonedds-cpp \
    ros-humble-teleop-twist-keyboard \
    ros-humble-navigation2 ros-humble-nav2-bringup ros-humble-slam-toolbox \
    ros-humble-xacro ros-humble-joint-state-publisher-gui \
    ros-humble-robot-state-publisher \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid "${HOST_GID}" student \
    && useradd --uid "${HOST_UID}" --gid "${HOST_GID}" --create-home --shell /bin/bash student \
    && printf 'student ALL=(ALL) NOPASSWD:ALL\n' > /etc/sudoers.d/student \
    && chmod 0440 /etc/sudoers.d/student \
    && mkdir -p /work/ros2_ws/src \
    && chown -R student:student /work \
    && ln -s /work/ros2_ws /home/student/ros2_ws

COPY docker/ros-env.bash /etc/robo/ros-env.bash
COPY docker/entrypoint.sh /usr/local/bin/robo-exec
RUN chmod 0755 /usr/local/bin/robo-exec \
    && printf '\nsource /etc/robo/ros-env.bash\n' >> /etc/bash.bashrc \
    && printf 'if [ -n "${BASH_VERSION:-}" ]; then . /etc/robo/ros-env.bash; fi\n' > /etc/profile.d/robo.sh \
    && printf '\nPS1="[robo] \\w\\\\$ "\n' >> /home/student/.bashrc

USER student
ENV HOME=/home/student
WORKDIR /work/ros2_ws
ENTRYPOINT ["/usr/local/bin/robo-exec"]
CMD ["sleep", "infinity"]
