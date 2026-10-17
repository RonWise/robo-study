# Запуск HW1 на Jetbot после калибровки

Инструкция для повторного запуска движения реального Jetbot 5 к ArUco после уже выполненной калибровки камеры. Камера, распознавание и управление работают в контейнере **на Jetbot**; ноутбук нужен для SSH, просмотра изображения и диагностики.

Документ подготовлен **17 октября 2026 года** по сохранённым файлам проекта и результатам предыдущей настройки. Повторная проверка на подключённом роботе при подготовке документа не выполнялась. В конце предыдущего сеанса пользователь подтвердил успешный запуск движения. Серия из пяти зачётных заездов на физическом роботе ещё не зафиксирована.

Повторять калибровку при обычном включении не требуется: `publish_raw` загружает сохранённый YAML. Инструкция рассчитана на прежнюю камеру, режим **1280×720** и прежнюю оптику. При изменении разрешения, crop или фокуса применимость внутренних параметров нужно проверить; при изменении крепления камеры — обновить её положение относительно корпуса.

Алгоритмы и исходники описаны в [HW1_IMPLEMENTATION.md](HW1_IMPLEMENTATION.md). Команды ниже относятся к **физическому роботу**, а команды `make hw1*` из старой инструкции — к симулятору.

## Что понадобится для повторного запуска

| Параметр | Сохранённое значение |
|---|---|
| Проект на ноутбуке | `/data/WORK/study/robo` |
| Пользователь SSH на Jetbot | `jetbot` |
| Последний проверенный IP | `10.233.197.31`; в новой сети может измениться |
| Проект на хосте Jetbot | `/home/jetbot/IntelligentRobotics/jetbot_ros2_mipt` |
| Контейнер Jetbot | `jetbot_ros2_mipt-jetbot_educational-1` |
| Образ контейнера Jetbot | `jetbot_full_ros2` |
| Пользователь в контейнере Jetbot | `app` |
| ROS workspace в контейнере Jetbot | `/home/app/ros2_ws` |
| ROS | Humble; `ROS_DOMAIN_ID=5`, `ROS_LOCALHOST_ONLY=0` |
| RMW | `rmw_fastrtps_cpp` |
| Маркер | `DICT_5X5_50`, ID `1`, сторона чёрного квадрата `0.07` м |
| Дистанция остановки | `0.5` м от середины оси ведущих колёс |
| Ограничения скорости | `0.05` м/с и `0.3` рад/с |

На ноутбуке используется Ubuntu 22.04 в контейнере. Проверенный контейнер Jetbot основан на Ubuntu 20.04 и содержит отдельно установленный ROS Humble в `/opt/ros/humble/install`. Не заменяйте его образом ноутбука: на Jetbot используются ARM64 и библиотеки Jetson L4T R32.7.6.

## Что было исправлено

| Проблема | Что изменили или установили при диагностике |
|---|---|
| Топики не приходили на ноутбук, хотя SSH работал | Согласовали домен 5, отключили ограничение ROS на localhost, использовали сеть хоста в Docker. Для меняющегося IP добавили `make new_ip`, обновляющий firewall ноутбука. |
| При чтении камеры через V4L2 было серое изображение или тайм-аут | Устройство сообщало Bayer RG10. Рабочий цветной захват построили через Jetson Argus и GStreamer с преобразованием NV12 → BGRx → BGR. |
| В контейнере отсутствовал `nvarguscamerasrc`, хотя на хосте он был | Выявили необходимость доступа к NVIDIA-библиотекам, устройствам и `/tmp/argus_socket`. После настройки контейнера Argus-захват заработал и внутри него. Точную итоговую копию Compose нужно сохранить при следующем подключении. |
| OpenCV в контейнере показывал `GStreamer: NO` | В `publish_raw.py` запуск GStreamer вынесен в отдельный процесс через `subprocess.Popen`; поддержка GStreamer в OpenCV для захвата больше не требуется. |
| Не было `/camera/camera_info` | Драйвер научили читать сохранённую калибровку, проверять разрешение и матрицы, публиковать CameraInfo вместе с Image с одинаковым header. |
| Возможное смешивание бинарного кадра и служебного вывода Argus | В итоговом драйвере используется отдельный файловый дескриптор: `os.pipe`, `fdsink fd=...` и `pass_fds`. Изображение не читается из stdout с сообщениями GStreamer. |
| Чтение pipe могло вернуть часть кадра | Драйвер собирает полный BGR-кадр в отдельном потоке и хранит последний полученный кадр. Заполнение ROS Image выполнено через `msg.data.frombytes(data)`. |
| Просмотр видео по Wi-Fi был медленным или показывал пустое окно | Для просмотра используем compressed-поток, распаковываем его на ноутбуке. У компрессора исправлено переназначение на `out/compressed:=...`. |
| Настройки симуляции не соответствовали печатному маркеру | Создан `detector_jetbot5.yaml`: словарь 5×5, ID 1, размер 70 мм вместо симуляционных ID 0 и 240 мм. |
| Расстояние от камеры не совпадает с расстоянием от колёс | Добавлена конфигурация геометрии: камера на 5 см впереди оси колёс, наклон вниз примерно 15°. |
| Нужно было соединить регулятор с реальными моторами | Создан `control_jetbot5.launch.py` с `target_follower`, `twist_mux` и `command_router`. Выход явно переназначается на `/diffbot_base_controller/cmd_vel_unstamped`. |
| После сборки возникало `Package not found` | В текущем терминале нужно заново выполнить `source install/setup.bash`. Сборка сама не обновляет окружение уже открытого shell. |
| Разные версии OpenCV на ноутбуке и Jetbot | Алгоритм поддерживает старый и новый API ArUco; генерация маркеров в тестах адаптирована к обеим версиям. |

В диагностике контейнера встречались также ошибки `cannot allocate memory in static TLS block` для `libGLdispatch.so.0` и `Can't initialize nvrm channel`. Это отдельный слой загрузки библиотек и доступа к устройствам, а не ошибка калибровки или распознавания. Порядок проверки приведён в разделе восстановления контейнера.

## Где сохранены рабочие файлы

| Файл в проекте ноутбука | Назначение и место на роботе |
|---|---|
| [scripts/jetbot/publish_raw.py](../scripts/jetbot/publish_raw.py) | Итоговый драйвер. В контейнере: `/home/app/ros2_ws/src/pi_camera_ros/pi_camera/publish_raw.py` |
| [calibration/jetbot5/jetbot5.yaml](../calibration/jetbot5/jetbot5.yaml) | Калибровка. В контейнере: `/home/app/ros2_ws/src/pi_camera_ros/config/jetbot5.yaml` |
| [calibrationdata.tar.gz](../calibration/jetbot5/calibrationdata.tar.gz) | Архив результатов калибровки; для обычного запуска не нужен |
| [jetbot_target_follower](../ros2_ws/src/jetbot_target_follower) | Пакет HW1. На роботе: `/home/app/ros2_ws/src/jetbot_target_follower` |
| [detector_jetbot5.yaml](../ros2_ws/src/jetbot_target_follower/config/detector_jetbot5.yaml) | Реальный маркер и топики камеры |
| [follower_jetbot5.yaml](../ros2_ws/src/jetbot_target_follower/config/follower_jetbot5.yaml) | Геометрия, дистанция остановки, скорости и тайм-ауты |
| [control_jetbot5.launch.py](../ros2_ws/src/jetbot_target_follower/launch/control_jetbot5.launch.py) | Запуск цепочки управления физическим роботом |

Папка `src` примонтирована с хоста Jetbot:

```text
/home/jetbot/IntelligentRobotics/jetbot_ros2_mipt/src
    → /home/app/ros2_ws/src
```

Поэтому исходники и YAML в `src` сохраняются при пересоздании контейнера. Каталоги `build`, `install` и пакеты, установленные только внутри контейнера, не гарантированно сохранятся при его удалении. Обычный `docker stop/start` сохраняет слой существующего контейнера.

## Последовательность обычного запуска

Длительные команды запускайте в отдельных терминалах и оставляйте работающими. Обычный цикл: **камера → детектор → драйвер моторов → управление**. Перед включением управления можно открыть видео на ноутбуке.

| Терминал | Где работает процесс | Компонент |
|---|---|---|
| J1 | Контейнер Jetbot | Камера |
| J2 | Контейнер Jetbot | Детектор ArUco |
| J3 | Контейнер Jetbot | Драйвер моторов |
| J4 | Контейнер Jetbot | Регулятор, mux и router |
| J5, при необходимости | Контейнер Jetbot | Сжатие размеченного видео |
| L1, при необходимости | Контейнер ноутбука | Распаковка видео |
| L2, при необходимости | Контейнер ноутбука | Просмотрщик |
| Дополнительный | Контейнер Jetbot | Диагностика или teleop |

### 1 Подключить ноутбук и проверить контейнер Jetbot

На **хосте ноутбука** откройте `.env` в проекте и убедитесь, что там заданы:

```dotenv
ROS_DOMAIN_ID=5
ROS_LOCALHOST_ONLY=0
```

Затем выполните, подставив актуальный адрес:

```bash
cd /data/WORK/study/robo
make new_ip IP=10.233.197.31
make up
ssh jetbot@10.233.197.31
```

`make new_ip` меняет правило firewall ноутбука, а не адрес робота. При смене сети повторите его с новым IP. `make up` использует уже собранный образ; повторная сборка для каждого запуска не нужна.

На **хосте Jetbot**, после SSH:

```bash
docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'
```

Если существующий контейнер остановлен:

```bash
docker start jetbot_ros2_mipt-jetbot_educational-1
```

Если имя другое, используйте имя из вывода `docker ps -a` во всех командах ниже. Если контейнер удалён, перейдите к разделу восстановления; не создавайте произвольный контейнер без настроек камеры.

### 2 Подготовить каждый терминал Jetbot

В **каждом новом терминале ноутбука**, предназначенном для робота:

```bash
ssh jetbot@10.233.197.31
```

На **хосте Jetbot**:

```bash
docker exec -it jetbot_ros2_mipt-jetbot_educational-1 bash
```

В **контейнере Jetbot**, где приглашение имеет вид `app@jetbotj5:~/ros2_ws$`:

```bash
cd /home/app/ros2_ws
source install/setup.bash
export ROS_DOMAIN_ID=5 ROS_LOCALHOST_ONLY=0
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
```

Команды `ros2` и `colcon` далее выполняются именно в этом контейнере. У пользователя хоста `jetbot` нет рабочего каталога `~/ros2_ws` и может не быть команды `colcon`.

Один раз перед запуском проверьте пакеты и уже работающие узлы:

```bash
ros2 pkg prefix pi_camera
ros2 pkg prefix jetbot_target_follower
ros2 pkg prefix diffdrive_jetbot
ros2 pkg prefix twist_mux
ros2 node list
ps -eo pid,args | grep -E '[p]ublish_raw|[t]arget_detector|[c]ontrol_jetbot5|[r]os2_control_node'
```

Если нужный процесс уже работает, используйте его или сначала завершите прежний запуск. Два экземпляра камеры, регулятора или моторного драйвера одновременно не нужны. `exit` из другого shell не останавливает процессы, ранее запущенные через `docker exec -d`.

### 3 Запустить камеру в J1

После подготовки терминала:

```bash
test -f /home/app/ros2_ws/src/pi_camera_ros/config/jetbot5.yaml
ros2 run pi_camera publish_raw
```

Ожидаются сообщения `Calibration loaded: ...jetbot5.yaml`, запуск GStreamer и захвата Argus. Драйвер публикует:

- `/camera/image/raw` — цветной `sensor_msgs/msg/Image`, `bgr8`, 1280×720;
- `/camera/camera_info` — сохранённые параметры этой камеры.

В отдельном подготовленном терминале контейнера Jetbot:

```bash
timeout 8s ros2 topic hz /camera/image/raw
timeout 10s ros2 topic echo /camera/camera_info --once
```

Ранее на Jetbot наблюдали примерно 29–30 кадров/с. Частота зависит от нагрузки; окончание команды `timeout` по сроку нормально. Не нужно гонять несжатый поток по Wi-Fi для проверки частоты на самом роботе.

### 4 Запустить детектор в J2

```bash
ros2 run jetbot_target_follower target_detector --ros-args \
  --params-file /home/app/ros2_ws/src/jetbot_target_follower/config/detector_jetbot5.yaml
```

Покажите камере маркер **DICT_5X5_50, ID 1, 70 мм**. Размер — весь чёрный квадрат вместе с чёрной рамкой, без белого поля.

При распознавании детектор выводит ID, `range`, `depth` и `reprojection`. В дополнительном терминале:

```bash
timeout 10s ros2 topic echo /target/visible --once
timeout 10s ros2 topic echo /target/distance --once
```

Ожидается `data: true` и правдоподобная дистанция в метрах. При смене ID, размера или словаря отредактируйте `detector_jetbot5.yaml` и перезапустите детектор: его параметры объявлены только для чтения во время работы.

### 5 Запустить драйвер моторов в J3

Перед этим уберите старые источники команд движения. Путь к цели должен быть свободен: текущий HW1 не использует лидар для обхода препятствий.

В подготовленном терминале контейнера Jetbot:

```bash
ros2 launch diffdrive_jetbot diffbot.launch.py robot_ip:=10.233.197.31
```

Подставьте актуальный адрес Jetbot. Оставьте launch работать. В другом подготовленном терминале проверьте:

```bash
ros2 control list_controllers
ros2 param get /diffbot_base_controller use_stamped_vel
ros2 param get /diffbot_base_controller cmd_vel_timeout
ros2 topic info /diffbot_base_controller/cmd_vel_unstamped -v
```

В проверенной конфигурации:

- `joint_state_broadcaster` — `active`;
- `diffbot_base_controller` — `active`;
- `use_stamped_vel` — `False`;
- `cmd_vel_timeout` — `0.5` с;
- моторный вход — `geometry_msgs/msg/Twist` в `/diffbot_base_controller/cmd_vel_unstamped`.

До запуска нашего управления у этого топика не должно быть постороннего издателя. Не запускайте параллельно `activate_all_drivers.launch.py` с его собственным mux: наш control-launch уже содержит mux.

### 6 Подключить управление в J4

Для повторного старта удобно сначала подключить цепочку к моторам **с отключённым автономным движением**:

```bash
ros2 launch jetbot_target_follower control_jetbot5.launch.py \
  cmd_vel_topic:=/diffbot_base_controller/cmd_vel_unstamped \
  enabled:=false
```

В дополнительном подготовленном терминале Jetbot:

```bash
ros2 topic echo /follower/state --once
ros2 topic echo /target/base_distance --once
ros2 topic echo /diffbot_base_controller/cmd_vel_unstamped --once
```

Ожидаются `DISABLED`, дистанция до видимого маркера и нулевые скорости. Команда чтения расстояния ожидает сообщения, пока маркер не распознан. Параметр `enabled=false` отключает автономный регулятор; отдельный активный teleop по-прежнему может управлять роботом.

Поставьте маркер неподвижно примерно в 80 см перед роботом. Когда изображение и дистанция верны, включите автономный режим:

```bash
ros2 param set /target_follower enabled true
```

**Эта команда разрешает движение.** Робот должен подойти со скоростью до 5 см/с и перейти в `ARRIVED` около 0.5 м от оси колёс до маркера.

Для уже проверенной конфигурации возможен прямой запуск с движением — именно этот вариант заработал в предыдущем сеансе:

```bash
ros2 launch jetbot_target_follower control_jetbot5.launch.py \
  cmd_vel_topic:=/diffbot_base_controller/cmd_vel_unstamped \
  enabled:=true
```

Это **альтернатива** предыдущему запуску, а не второй экземпляр: сначала завершите прежний control-launch.

Запуск без аргументов оставляет `enabled=false` и выход `/jetbot_hw1/cmd_vel_preview`. Он предназначен для проверки и не подключает регулятор к моторам. Даже `enabled:=true` без нужного `cmd_vel_topic` будет публиковать только в preview.

### 7 Остановить работу

Для остановки автономного подхода с сохранением запущенных узлов:

```bash
ros2 param set /target_follower enabled false
```

Для завершения цепочки управления нажмите **Ctrl+C в терминале J4**. Моторный драйвер должен прекратить движение после исчезновения команд в соответствии со своим тайм-аутом. Не используйте закрытие SSH как способ остановки: исчезновение окна не доказывает, что удалённый процесс завершился.

При полном завершении сеанса сначала остановите teleop и control-launch, затем драйвер моторов в J3, детектор в J2, камеру в J1 и процессы просмотра. Если нужно выключить сам контейнер после завершения ROS-процессов, на **хосте Jetbot**:

```bash
docker stop jetbot_ros2_mipt-jetbot_educational-1
```

## Как видеть ArUco и расстояние на ноутбуке

Просмотр необязателен для управления: распознавание работает на самом Jetbot с исходными кадрами. Для Wi-Fi передаём сжатое отладочное изображение.

В **контейнере Jetbot, терминал J5**, после общей подготовки:

```bash
ros2 run image_transport republish raw compressed --ros-args \
  -r __node:=target_debug_compressor \
  -r in:=/target/debug_image \
  -r out/compressed:=/target/debug_image/compressed
```

В **терминале ноутбука L1**:

```bash
cd /data/WORK/study/robo
make shell
```

Затем **в контейнере ноутбука**:

```bash
export ROS_DOMAIN_ID=5 ROS_LOCALHOST_ONLY=0
ros2 run image_transport republish compressed raw --ros-args \
  -r __node:=target_debug_decompressor \
  -r in/compressed:=/target/debug_image/compressed \
  -r out:=/target/debug_image_local
```

В **другом терминале ноутбука L2** снова выполните `cd /data/WORK/study/robo`, `make shell`, затем:

```bash
export ROS_DOMAIN_ID=5 ROS_LOCALHOST_ONLY=0
ros2 run rqt_image_view rqt_image_view /target/debug_image_local
```

Должны появиться цветное изображение, рамка маркера и подпись с расстоянием. Программа `republish` может не писать ничего в терминал — это само по себе не ошибка.

Для обычной картинки без разметки используйте ту же схему, заменив вход компрессора на `/camera/image/raw`, его выход — на `/camera/image/compressed`, а локальный выход распаковки — на `/camera/image_local`. При работающем debug-просмотре второй видеопоток обычно не нужен.

Именно `out/compressed` следует переназначать у компрессора. При ошибочном `out:=...` в нашей конфигурации поток обнаруживался в `/out/compressed`, а ожидаемый топик оставался пустым.

## Ручной перехват управления для HW1

При работающем control-launch откройте дополнительный подготовленный терминал **контейнера Jetbot**:

```bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard --ros-args \
  -r cmd_vel:=/cmd_vel_teleop \
  -p speed:=0.03 \
  -p turn:=0.2 \
  -p repeat_rate:=10.0 \
  -p key_timeout:=0.3
```

Управляйте клавишами из подсказки программы. Ненулевая команда проходит через router в `/cmd_vel_teleop_active`, получает приоритет 100 в mux и переводит автономный регулятор в `MANUAL`. Автономный вход имеет приоритет 10.

**Клавиша k освобождает ручное управление для автономного режима.** Она не фиксирует остановку всего робота: после тайм-аута ручного входа автономный подход может возобновиться. Для остановки автономного режима используйте `enabled=false`, для завершения управления — Ctrl+C в J4. Ручное управление проверяйте отдельно от отключения автономного.

Команда `make hw1-teleop` настроена на **симуляционный домен 45**, поэтому для физического Jetbot нужна команда выше в домене 5.

## Как устроено движение и что означают расстояния

```text
publish_raw
  ├─ /camera/image/raw ─────────→ target_detector
  │                        └───→ target_follower (свежесть кадров)
  └─ /camera/camera_info ───────→ target_detector
                                      │
                         /target/pose и /target/visible
                                      ↓
                               target_follower
                                      ↓ /cmd_vel_nav
teleop → command_router → /cmd_vel_teleop_active → twist_mux
                                                      ↓ /cmd_vel_mux
                                                command_router
                                                      ↓
                                 /diffbot_base_controller/cmd_vel_unstamped
                                                      ↓
                                           моторный контроллер
```

В распознавании используются OpenCV ArUco, субпиксельное уточнение углов и `solvePnP`. Управление использует P-регуляторы расстояния и направления, ограничение ускорения и автомат состояний; полный PID с интегральной и дифференциальной частями не реализован.

| Состояние | Поведение |
|---|---|
| `DISABLED` | Автономное движение выключено |
| `APPROACH` | Подход или корректирующее движение назад с поворотом к цели |
| `ALIGN` | Поворот к цели без линейного движения |
| `ARRIVED` | Остановка в допуске дистанции |
| `LOST` | Краткая остановка после потери цели |
| `SEARCH` | Поиск вращением до 0.15 рад/с после задержки 0.6 с |
| `NO_IMAGE` | Нет свежего изображения или сообщений видимости; автономная скорость нулевая |
| `MANUAL` | Приоритет у ручного управления |

После изменения положения цели робот может выйти из `ARRIVED` и снова начать движение. Если цель слишком близко, допускается корректирующий задний ход, ограниченный текущим пределом скорости.

`/target/distance` и надпись `range` — пространственная дистанция **от камеры**. `depth` — координата вдоль оптической оси камеры. `/target/base_distance` — горизонтальная дистанция **от середины оси колёс**, по которой работает регулятор. Эти значения не обязаны совпадать.

В конфигурации реального робота:

```yaml
camera_translation: [0.05, 0.0, 0.0]
camera_rotation_rpy: [-1.8325957145940461, 0.0, -1.5707963267948966]
```

Это учитывает 5 см выноса камеры вперёд и наклон вниз около 15°. Угол roll −105° в записи дополнительно включает перевод оптических осей в оси корпуса. Камера предполагается по центру и без бокового поворота. Высота не измерена и задана нулём: для управления используются только преобразованные x/y, поэтому запись не является полной измеренной 3D-калибровкой TF.

## Как менять параметры

Постоянные настройки реального робота находятся в `follower_jetbot5.yaml`. Не путайте его с `follower.yaml` для симуляции.

На работающем регуляторе, в контейнере Jetbot:

```bash
ros2 param set /target_follower enabled false
ros2 param set /target_follower stop_distance 0.6
ros2 param get /target_follower stop_distance
```

После проверки положения робота и цели возобновите движение:

```bash
ros2 param set /target_follower enabled true
```

Изменение через `ros2 param set` действует до перезапуска и не записывает YAML. Для постоянного изменения отредактируйте YAML, пересоберите пакет и перезапустите соответствующий launch.

Ограничения скорости есть и у `target_follower`, и у `command_router`. Увеличение только первого не позволит превысить предел второго. Размер и ID маркера задаются в отдельном `detector_jetbot5.yaml` и требуют перезапуска детектора.

## Что уже проверено и что осталось для сдачи HW1

В предыдущем сеансе подтверждены:

- Цветной захват Argus внутри контейнера Jetbot.
- Публикация Image и CameraInfo с согласованными header.
- Распознавание печатного маркера 5×5, ID 1, размер 70 мм.
- Приблизительная проверка расстояния рулеткой:

| От камеры по рулетке | По распознаванию |
|---|---|
| 20 см | около 20 см |
| 40 см | около 40 см |
| 60 см | около 62 см |
| 80 см | около 82 см |

Постоянную поправку −2 см не вводили: результаты ближних измерений её не подтверждают.

Также выполнены проверки вращения вывешенных колёс командой 0.03 м/с на 1 с и на 5 с; после отправки нулей наблюдали нулевые скорости колёс. Проверены активность контроллеров и параметр моторного тайм-аута 0.5 с. Это не отдельный тест всех сценариев аварийного обрыва связи.

Перед первым заездом цепочка управления с `enabled=false` публиковала только нули, состояние было `DISABLED`, дистанция от оси колёс — около 0.83 м. После прямого запуска с `enabled=true` пользователь сообщил, что всё заработало.

По [заданию HW1](<Интеллектуальная робототехника 2026 - ДЗ 1.docx>) нужно отдельно зафиксировать на физическом роботе:

1. Пять стартов с разных позиций, где маркер изначально виден.
2. Не менее четырёх успешных остановок в интервале `(0.75 × stop_distance, 1.25 × stop_distance)`. Для 0.5 м это **строго между 0.375 и 0.625 м**.
3. Возобновление подхода после ручного перехвата, который вывел маркер из кадра.
4. Возобновление подхода после временного перекрытия маркера.

Итоговую дистанцию измеряйте рулеткой от той же точки корпуса, что использует регулятор, а не только по его собственному топику. Сохранённые 5 из 5 успешных попыток в `HW1_IMPLEMENTATION.md` относятся к **симуляции**; они не заменяют серию на Jetbot.

## Если пакет не найден или контейнер пересоздан

Сначала в **контейнере Jetbot** подключите окружение заново:

```bash
cd /home/app/ros2_ws
source install/setup.bash
ros2 pkg prefix jetbot_target_follower
```

Если установка отсутствует, но исходники сохранились, выполните в новом shell контейнера:

```bash
cd /home/app/ros2_ws
source /opt/ros/humble/install/setup.bash
colcon list
colcon build --packages-select pi_camera jetbot_target_follower --symlink-install
source install/setup.bash
ros2 pkg prefix pi_camera
ros2 pkg prefix jetbot_target_follower
```

Эта сборка восстанавливает наши два пакета. Если после пересоздания отсутствуют также `diffdrive_jetbot` и `jetbot_bringup`, при наличии их исходников добавьте их в сборку:

```bash
colcon build --packages-select diffdrive_jetbot jetbot_bringup --symlink-install
source install/setup.bash
```

Проверьте зависимости, ранее присутствовавшие в рабочем контейнере:

```bash
python3 -c 'import cv2, yaml, numpy; import cv_bridge; print(cv2.__version__); print(hasattr(cv2, "aruco"))'
ros2 pkg prefix twist_mux
ros2 pkg prefix image_transport
ros2 pkg prefix compressed_image_transport
```

Проверенный Jetbot использовал OpenCV 4.10, ноутбук — 4.5.4. Не копируйте `build` и `install` с ноутбука на Jetbot: сборку выполняют внутри ARM64-контейнера робота. Для Ubuntu 20.04 с нестандартной установкой Humble не следует вслепую применять инструкции установки пакетов для Ubuntu 22.04.

### Восстановить исходники с ноутбука

Это нужно только если файлы на Jetbot отсутствуют или вы намеренно обновляете их. Сначала завершите соответствующие ROS-процессы и сохраните отдельную копию изменённых на роботе файлов: следующие команды перезаписывают совпадающие файлы.

На **хосте ноутбука**:

```bash
cd /data/WORK/study/robo
JETBOT_IP=10.233.197.31

ssh "jetbot@$JETBOT_IP" 'mkdir -p /home/jetbot/IntelligentRobotics/jetbot_ros2_mipt/src/pi_camera_ros/config'
scp scripts/jetbot/publish_raw.py \
  "jetbot@$JETBOT_IP:/home/jetbot/IntelligentRobotics/jetbot_ros2_mipt/src/pi_camera_ros/pi_camera/publish_raw.py"
scp calibration/jetbot5/jetbot5.yaml \
  "jetbot@$JETBOT_IP:/home/jetbot/IntelligentRobotics/jetbot_ros2_mipt/src/pi_camera_ros/config/jetbot5.yaml"
scp -r ros2_ws/src/jetbot_target_follower \
  "jetbot@$JETBOT_IP:/home/jetbot/IntelligentRobotics/jetbot_ros2_mipt/src/"
```

Предполагается, что исходный пакет `pi_camera_ros` уже есть на роботе. В его `setup.py` внутри списка `console_scripts` должна быть запись:

```python
'publish_raw = pi_camera.publish_raw:main',
```

Это файл **`/home/app/ros2_ws/src/pi_camera_ros/setup.py` внутри контейнера**. Затем выполните сборку и `source` из предыдущего подраздела. Новый запуск камеры использует YAML автоматически; калибратор запускать не нужно.

## Проверка контейнера и Argus при неисправности камеры

Полная итоговая копия `docker-compose.yml` робота не сохранена в этом проекте. Поэтому ниже — проверка требований, а не готовая замена файла. Локальный [compose.yaml](../compose.yaml) относится к **ноутбуку**, изменять его для проброса камеры Jetbot не требуется.

На **хосте Jetbot**:

```bash
cd /home/jetbot/IntelligentRobotics/jetbot_ros2_mipt
cat docker-compose.yml
docker inspect jetbot_ros2_mipt-jetbot_educational-1 --format \
  'Runtime={{.HostConfig.Runtime}} Network={{.HostConfig.NetworkMode}} {{range .Mounts}}{{println .Source "->" .Destination}}{{end}}'
systemctl status nvargus-daemon --no-pager
ls -l /tmp/argus_socket
ls -ln /dev/video0 /dev/nvmap /dev/nvhost-vic
```

Проверяются: runtime NVIDIA, host network, bind mount `src`, доступ контейнера к Argus-сокету и устройствам Jetson. В прежнем выводе `nvmap` и `nvhost-vic` имели владельца root и группу с GID **44**, поэтому доступ пользователя `app` к этой группе имеет значение.

В **контейнере Jetbot**:

```bash
id
printenv | grep '^NVIDIA_'
ls -l /tmp/argus_socket /dev/video0 /dev/nvmap /dev/nvhost-vic
gst-inspect-1.0 nvarguscamerasrc
gst-inspect-1.0 nvvidconv
```

При восстановлении Compose существенны NVIDIA runtime, `NVIDIA_VISIBLE_DEVICES=all`, `NVIDIA_DRIVER_CAPABILITIES=all`, mount `/tmp/argus_socket`, доступ к NVIDIA-устройствам и подходящие дополнительные группы. Одного `/dev/video0` для всей цепочки Argus и nvvidconv недостаточно. После изменения Compose простой `docker restart` не применяет новые mounts и environment: потребуется пересоздание контейнера с сохранением исходников.

Если `gst-inspect` сообщает именно ошибку static TLS для `libGLdispatch.so.0`, можно проверить раннюю загрузку библиотеки **в контейнере Jetbot**:

```bash
LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libGLdispatch.so.0 \
  GST_REGISTRY=/tmp/jetbot-gst-registry-check.bin \
  gst-inspect-1.0 nvarguscamerasrc
```

Это диагностическая команда с отдельным реестром плагинов; она не исправляет права на устройства и не заменяет NVIDIA runtime. Ошибка `Can't initialize nvrm channel` требует отдельной проверки видимости устройств и прав пользователя, а не автоматического вывода, что закончилась оперативная память.

При следующем подключении стоит сохранить фактический рабочий `docker-compose.yml` с Jetbot в репозитории: это устранит оставшийся пробел для восстановления контейнера с нуля.

## Быстрая диагностика повторяющихся проблем

| Симптом | Что проверить |
|---|---|
| `Package 'jetbot_target_follower' not found` | Контейнер и каталог правильные; выполнен свежий `source install/setup.bash`; при необходимости пакет собран |
| `colcon: command not found`, нет `~/ros2_ws` | Команда введена на хосте Jetbot вместо контейнера |
| Нет CameraInfo | Используется обновлённый `publish_raw.py`; YAML существует; в журнале есть `Calibration loaded` |
| `No valid CameraInfo yet` или разные размеры Image/CameraInfo | Калибровка доступна в том же ROS-домене и соответствует 1280×720 |
| `No such element nvarguscamerasrc` | Сначала проверить полный вывод `gst-inspect`: плагин может отсутствовать либо не загружаться из-за зависимостей |
| Камера занята или Argus не выдаёт кадры | Не запущен ли второй экземпляр камеры; доступен ли socket; работает ли daemon на хосте |
| SSH работает, топики не видны на ноутбуке | Актуальный `make new_ip`, домен 5, localhost=0, host network; SSH сам по себе не проверяет DDS |
| Пустое окно просмотрщика | Есть ли поток compressed, работает ли распаковка, выбран ли `/target/debug_image_local` |
| `republish` молчит | Проверить частоту выходного топика; отсутствие текстового вывода допустимо |
| `NOT VISIBLE` при видимом маркере | Словарь 5×5, ID 1, отсутствие перекрытия и размытия; размер влияет на масштаб расстояния |
| `DISABLED` | Включить `enabled`, когда робот готов к движению |
| `APPROACH`, но колёса стоят | Выбран ли реальный `cmd_vel_topic`, активен ли моторный контроллер, не запущен ли preview |
| `MANUAL` без ожидаемого автономного движения | Есть ли активный источник teleop; не работает ли второй mux |
| `NO_IMAGE` | Проверить частоту raw на Jetbot и свежесть сообщений детектора |
| Ошибка расстояния | Правильный размер чёрного квадрата, YAML и геометрия; сравнивать camera range и base distance с соответствующими точками отсчёта |

Диагностические команды выполняются в подготовленном **контейнере Jetbot**:

```bash
ros2 node list
ros2 topic list -t
ros2 topic info /diffbot_base_controller/cmd_vel_unstamped -v
ros2 topic echo /follower/state
```

Последняя команда работает до Ctrl+C. Для другого наблюдения используйте отдельный терминал или завершите её. При устаревшем списке узлов после смены окружения можно перезапустить только ROS CLI daemon:

```bash
ros2 daemon stop
ros2 daemon start
```

Это не перезапускает камеру, детектор и управление. Для обычного повторного запуска после калибровки достаточно последовательности из раздела запуска; сборка и восстановление нужны только при отсутствующих или изменённых файлах.
