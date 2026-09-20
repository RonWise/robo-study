# Проверка GPU в Ubuntu 22.04 / Docker

Проверено на ноутбуке mobile-study 2026-09-20.

## Подтверждённая конфигурация

- openSUSE Slowroll, ядро `7.2.4-1-default`.
- NVIDIA RTX 5060 Laptop, 8151 MiB, драйвер `595.99.02`.
- Secure Boot включён; Intel — основной GPU, NVIDIA — дополнительный.
- Штатная `sddm.service` включена вместо `display-manager-legacy.service`.
  Обычный графический вход после перезагрузки подтверждён пользователем.
- NVIDIA Container Toolkit `1.20.1`, Docker runtime `nvidia`.
- Docker хранит данные через существующий bind mount `/data/docker` → `/var/lib/docker`.
  Настройки журналирования и `selinux-enabled: true` сохранены.
- Конфигурация Docker перечитана без перезапуска `xray-vless`.

## Повторная проверка

Из этой папки:

```bash
docker build -t robo-gpu-check:ubuntu22.04 .
bash check-cuda.sh
bash check-opengl.sh
```

Графический тест нужно запускать из терминала текущего рабочего стола,
где установлены `DISPLAY` и `XAUTHORITY`. На хосте используется `xauth`.
Скрипт копирует только запись авторизации текущего дисплея во временный файл,
подключает его и X11-сокет, после завершения удаляет временную копию.
Исходный файл авторизации не выводится и не изменяется. `xhost +` не используется.

CUDA-тест компилирует PTX через драйвер NVIDIA и запускает ядро, вычисляющее
4096 значений `3*i+7`. Все значения сверяются на CPU. CUDA Toolkit на хосте
или в диагностическом образе для этого теста не требуется.

Результат CUDA: `PASS: GPU computed all 4096 values correctly (3*i+7).`
Результат OpenGL: `NVIDIA GeForce RTX 5060 Laptop GPU`, direct rendering Yes,
OpenGL 4.6 NVIDIA 595.99.02.

## Параметры будущего контейнера ROS/Gazebo

База по материалам курса: Ubuntu 22.04, ROS 2 Humble,
образ преподавателя `osrf/ros:humble-desktop-full`.
Этот диагностический образ не содержит ROS или Gazebo.

- Явно выбирать runtime `nvidia` и `NVIDIA_VISIBLE_DEVICES=all`.
- Для GUI задавать `NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics,display`.
- Для OpenGL offload задавать `__NV_PRIME_RENDER_OFFLOAD=1`
  и `__GLX_VENDOR_LIBRARY_NAME=nvidia`.
- На проверенной конфигурации `--gpus all` без явного runtime выдавал
  `AMD CDI spec not found`; использован успешно проверенный способ выше.
- SELinux блокировал соединение контейнера с X11-сокетом (`user_tmp_t`).
  Графический тест использует `--security-opt label=disable` только для себя:
  SELinux-изоляция этого контейнера отключена. SELinux хоста и обычных
  контейнеров остаётся включённым. CUDA-тест не требует этой опции.
- Доступ к устройствам робота и сетевые параметры ROS настраиваются отдельно.

## Восстановление

- Если графический вход не появился: Ctrl+Alt+F3, вход как work, `plasma-start`.
- Откат службы входа из TTY: `sudo /usr/local/sbin/robo-sddm-rollback`.
- Копия старой службы: `/var/lib/robo-sddm-backup-20260920`.
- Копия Docker daemon.json до добавления NVIDIA:
  `/var/lib/robo-docker-gpu-backup.Ys83Fm/daemon.json`.
- Для ядра 7.2.5 модуль NVIDIA пока отсутствует; проверенная связка — 7.2.4.
  Выбор ядра GRUB по умолчанию в ходе этих работ не изменялся.
- Файл `/etc/sddm.conf.d/20-wayland.conf.disabled` фактически читается SDDM:
  суффикс `.disabled` не выключает конфигурацию в этом каталоге.

Полный запуск учебной сцены Gazebo, камеры/лидара, ros_gz_bridge и RViz2
на этом этапе ещё не проверялся. CUDA/OpenGL-тесты подтверждают доступ к GPU,
но не заменяют проверку совместимости конкретных пакетов и моделей.
