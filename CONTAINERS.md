# Робототехника: Ubuntu 22.04, ROS 2 Humble и Gazebo в Docker

Рабочая папка на ноутбуке: `/data/WORK/study/robo`.
Команды `make` ниже выполняются **на хосте, от пользователя work, без sudo**.
Для графических приложений запускайте их из терминала текущего сеанса KDE.

## Быстрый старт

```bash
cd /data/WORK/study/robo
make up
make shell
```

`make up` создаёт `.env` и `ros2_ws/src`, собирает образ при необходимости
и запускает контейнер в фоне. Первая сборка скачивает пакеты и занимает время.
`make shell` открывает Bash внутри Ubuntu. Приглашение начинается с `[robo]`.
ROS Humble и собранное рабочее пространство подключаются автоматически.

```bash
# Эти команды выполняются уже ВНУТРИ контейнера:
cat /etc/os-release
echo "$ROS_DISTRO"
pwd
ros2 topic list
exit
```

`exit` закрывает только этот терминал. Контейнер продолжает работать.
Для второго терминала откройте ещё один терминал KDE, перейдите в папку проекта
и снова выполните `make shell`.

После перезагрузки ноутбука снова выполните `make up`: контейнер намеренно
не запускается автоматически до появления графического сеанса. Команда также
обновляет авторизацию X11/XWayland. При смене `DISPLAY` Compose пересоздаёт
контейнер с актуальным значением.

## Основные команды

| На хосте | Действие |
|---|---|
| `make help` | Все доступные команды |
| `make init` | Создать локальные настройки и workspace без сборки |
| `make up` / `make start` | Собрать при необходимости и запустить |
| `make shell` | Открыть Bash от пользователя `student` |
| `make root` | Открыть Bash от root **внутри контейнера** |
| `make status` | Показать состояние контейнера |
| `make stop` | Остановить контейнер и все процессы внутри |
| `make down` | Удалить контейнер, сохранив рабочие файлы и домашний том |
| `make restart` | Пересоздать контейнер из текущего образа |
| `make build` | Собрать образ, не меняя работающий контейнер |
| `make rebuild` | Пересобрать с кэшем и пересоздать контейнер |
| `make rebuild-clean` | Пересобрать без кэша и пересоздать контейнер |
| `make run CMD='ros2 topic list'` | Выполнить одну команду внутри Ubuntu |
| `make logs` | Журнал основного процесса; Ctrl+C завершает просмотр |
| `make doctor` | Проверить Docker, GPU, ROS и состояние контейнера |
| `make config` | Проверить синтаксис Compose |

Остановка и пересоздание прерывают запущенные симуляторы и ROS-ноды.
Основной процесс — `sleep infinity`, поэтому `make logs` обычно пуст:
вывод команд, запущенных через `make shell`/`make gazebo`, остаётся в их терминале.

Сервис в Compose называется `robo`, проект — `robo-study`. Команды не управляют
контейнером `xray-vless` и не перезапускают Docker на хосте.

## Где сохраняются файлы

| Хост | Внутри Ubuntu | Назначение |
|---|---|---|
| `/data/WORK/study/robo` | `/work` | Вся рабочая папка проекта |
| `ros2_ws/src` | `/work/ros2_ws/src` | Исходники ROS-пакетов |
| `ros2_ws/build`, `install`, `log` | Те же папки внутри `/work/ros2_ws` | Результаты сборки colcon |
| Том Docker `robo-study_student-home` | `/home/student` | История Bash, настройки, кэш моделей Gazebo, пользовательские библиотеки |
| `~/.gitconfig` на хосте | `/home/student/.gitconfig`, только чтение | Имя и email автора Git-коммитов |

`~/ros2_ws` внутри контейнера — ссылка на `/work/ros2_ws`.
UID/GID пользователя `student` совпадают с UID/GID пользователя хоста,
поэтому обычные команды создают файлы с владельцем `work`.

`stop`, `down`, `restart`, `rebuild` сохраняют исходники и домашний том.
Установки `sudo apt install ...` внутри работающего контейнера сохраняются
после `stop/up`, но теряются при **пересоздании**. Для постоянных зависимостей
добавляйте пакеты в `docker/Dockerfile` и выполняйте `make rebuild`.
Не используйте `docker compose down -v`, если хотите сохранить домашний том.

Домашняя папка хоста и SSH-приватные ключи в контейнер не подключены.
Операции с приватными Git-репозиториями можно выполнять на хосте в `ros2_ws/src`;
результат сразу виден внутри контейнера.

## Проверка GPU и запуск графики

```bash
make up
make gpu       # NVIDIA и версия драйвера
make opengl    # OpenGL renderer должен содержать NVIDIA GeForce RTX 5060
make cuda      # реальное вычисление на GPU, результат PASS
make gazebo    # пустой мир Gazebo Fortress
```

В других терминалах хоста:

```bash
cd /data/WORK/study/robo
make rviz      # RViz2
make lidar     # отдельный пример visualize_lidar.sdf
```

Для первых проверок запускайте один мир Gazebo за раз; перед другим примером
остановите предыдущий через Ctrl+C. Ctrl+C в терминале симулятора завершает
эту команду, но не учебный контейнер.

Аналогичные команды из `make shell`:

```bash
ign gazebo -v 3 -r /usr/share/ignition/ignition-gazebo6/worlds/empty.sdf
ign gazebo -v 3 -r /usr/share/ignition/ignition-gazebo6/worlds/visualize_lidar.sdf
rviz2
```

Хост использует KDE Wayland; GUI контейнера выводится через XWayland.
Скрипт создаёт `.runtime/xauth/Xauthority` с правами `600` и передаёт контейнеру
только запись авторизации текущего X-дисплея. `xhost +` не требуется.
Каталог `.runtime` исключён из Git и Docker-контекста сборки.

Для этого ноутбука используется проверенный runtime `nvidia` с
`NVIDIA_VISIBLE_DEVICES=all`, а не `--gpus all`, который ранее давал ошибку
`AMD CDI spec not found`. Для доступа к X11-сокету SELinux-метки отключены
только у учебного контейнера (`label=disable`).

CUDA Toolkit, PyTorch и другие ML-фреймворки в этот образ не включены.
`make cuda` проверяет вычисления через CUDA Driver API из `gpu-check`.
Учебный симулятор использует NVIDIA OpenGL; драйвер берётся с хоста.

## Лидар Gazebo → ROS: проверенный пример

В первом терминале хоста:

```bash
cd /data/WORK/study/robo
make lidar
```

Во втором терминале хоста откройте контейнер и запустите мост:

```bash
cd /data/WORK/study/robo
make shell
ros2 run ros_gz_bridge parameter_bridge '/lidar@sensor_msgs/msg/LaserScan[ignition.msgs.LaserScan'
```

В третьем терминале:

```bash
cd /data/WORK/study/robo
make shell
ros2 topic echo /lidar --once
```

Кавычки в команде bridge нужны для передачи `[` как части аргумента.
Этот мост передаёт данные из Gazebo в ROS. Для конкретной модели Jetbot
имена топиков необходимо сверить с её SDF/launch-файлами.

## Работа с ROS-пакетами и Jetbot

Клонирование модели преподавателя на хосте, один раз:

```bash
cd /data/WORK/study/robo
git clone https://github.com/KirillMouraviev/jetbot_ros_gazebo.git ros2_ws/src/jetbot_ros_gazebo
make up
make rosdep
make colcon
make shell
```

В уже открытом контейнерном терминале после сборки подключите новые пакеты:

```bash
source /work/ros2_ws/install/local_setup.bash
ros2 pkg list | grep jetbot
```

Новый `make shell` делает это автоматически. Репозиторий модели не встроен
в образ: его можно менять и коммитить без пересборки Docker-образа.
Команды запуска конкретного launch-файла и привязка камеры/лидара выполняются
по материалам лабораторной работы и файлам репозитория.

`make rosdep` обновляет списки apt и rosdep, затем устанавливает зависимости
пакетов из `src`. Эти установки относятся к текущему контейнеру; найденные
постоянные зависимости затем стоит перенести в Dockerfile.

Примеры команд из нескольких контейнерных терминалов:

```bash
ros2 topic list
ros2 node list
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

В образ включены `ros_gz` (в том числе bridge), Nav2, SLAM Toolbox,
OpenCV, colcon, rosdep, инструменты C/C++ и Python. Само наличие пакетов
не настраивает автоматически топики, TF, параметры Nav2 или модель робота.

В методичке кэш Gazebo расположен в `/root/.ignition`. Здесь пользователь
`student`, поэтому соответствующий путь — `/home/student/.ignition`.
Скачанные Fuel-модели сохраняются в домашнем томе.

## Сеть и реальный робот

Настройки находятся в `.env`:

```dotenv
ROS_DOMAIN_ID=0
ROS_LOCALHOST_ONLY=1
```

По умолчанию ROS работает только на этом ноутбуке. Для реального Jetbot:
укажите `ROS_DOMAIN_ID`, равный номеру робота/бригады, и
`ROS_LOCALHOST_ONLY=0`, затем выполните `make up`.
Пересоздание контейнера применит значения ко всем новым процессам.

Контейнер использует сеть хоста и Cyclone DDS. Подключение к Wi-Fi робота,
маршруты VPN, firewall и прямой доступ к USB-устройствам настраиваются отдельно
при появлении реального оборудования. Сокет Docker в контейнер не проброшен.

При запуске через Makefile контейнер и сборка получают переменные прокси
из текущего терминала (`HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY` и варианты
в нижнем регистре). Сеть хоста позволяет обращаться к локальному прокси VPN.
Если доступ к репозиториям пропал, проверьте `vless-status` на хосте и
повторите команду из терминала с правильными переменными прокси.

## Если что-то не запускается

- **Нет NVIDIA на хосте:** выполните `nvidia-smi` и `uname -r`.
  Проверенная связка — ядро `7.2.4-1-default`, драйвер `595.99.02`.
  В ранее проверенном ядре 7.2.5 модуль NVIDIA отсутствовал.
- **Cannot open display / No protocol specified:** откройте новый терминал KDE,
  выполните `make up`, затем `make opengl`. Не запускайте Makefile через sudo.
- **Контейнер остановлен:** `make up`, затем `make shell`.
- **Изменился Dockerfile:** `make rebuild`. `make restart` образ не пересобирает.
- **Изменились ROS-пакеты:** обычно достаточно `make colcon`; Docker пересобирать не нужно.
- **Пакет установлен, но ros2 его не видит:** новый `make shell` или
  `source /work/ros2_ws/install/local_setup.bash`.
- **Permission denied на исходниках:** проверьте владельца файлов. Не собирайте
  workspace от root. `make root` предназначен для администрирования Ubuntu.

## Проверено на ноутбуке 2026-09-20

- Образ `robo-study:humble` собран; контейнер `robo-study-robo-1` запущен.
- Ubuntu 22.04, ROS Humble, Gazebo Fortress 6.18.0.
- Пользователь контейнера: `student`, UID/GID 1000:1000.
- NVIDIA OpenGL 4.6, renderer RTX 5060 Laptop; вычислительный тест CUDA — PASS.
- ROS 2 / Cyclone DDS: сообщения передаются между двумя процессами.
- GUI Gazebo и RViz2 запущены; RViz сообщает OpenGL 4.6.
- GPU-лидар Gazebo → ros_gz_bridge → ROS LaserScan: получено 640 лучей,
  из них 333 с конечной дальностью в проверочном кадре.
- `make stop` / `make up` сохраняют тот же контейнер.
- `make restart` пересоздаёт контейнер; файлы workspace и домашнего тома сохраняются.
- Git внутри контейнера: `Roman N. <7211393+RonWise@users.noreply.github.com>`.
- VPN-контейнер `xray-vless` не перезапускался.

В GUI штатного примера `visualize_lidar.sdf` при старте были сообщения о
`tooltipDelay`/`tooltipTimeout` и `Lidar pointer is not set`. Они не помешали
проверенному получению измерений через мост ROS. Полный сценарий Jetbot,
камера, навигация Nav2 и подключение к физическому роботу ещё не проверялись.

## Основа конфигурации

Выбран Ubuntu 22.04, потому что это целевая Ubuntu для
[ROS 2 Humble](https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debs.html).
В материалах курса указан `osrf/ros:humble-desktop-full`; конкретный проверенный
образ закреплён по digest в Dockerfile. Дополнительные apt-пакеты устанавливаются
из текущих репозиториев, поэтому `rebuild-clean` не гарантирует побитово одинаковый образ.

Полезные ссылки:

- [ROS 2 Humble и Gazebo](https://docs.ros.org/en/humble/Tutorials/Advanced/Simulators/Gazebo/Gazebo.html)
- [Модель Jetbot преподавателя](https://github.com/KirillMouraviev/jetbot_ros_gazebo)
- [Справочник Docker Compose](https://docs.docker.com/reference/compose-file/services/)
- [Результаты первичной настройки GPU](gpu-check/README.md)
