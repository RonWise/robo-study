# Склад с Jetbot

Запуск с хоста из корня проекта: `make warehouse`.
Внутри контейнера: `ign gazebo -v 4 -r /work/assets/worlds/warehouse/jetbot_warehouse.sdf`.

Основа: OpenRobotics / Tugbot in warehouse, Fuel, версия 2.
Источник: https://fuel.gazebosim.org/1.0/OpenRobotics/worlds/Tugbot%20in%20warehouse/2
Скопирован из кэша контейнера 2026-09-20 вместе с миниатюрами оригинала.

Изменения:
- Робот Tugbot заменён на `model://jetbot`, имя экземпляра — `jetbot`.
- Сохранены мир `world_demo`, расстановка склада и начальная позиция робота.
  Поза Jetbot: `13.9 -10.6 0.1 -1.57079632679 0 0`.
  Поворот roll = −π/2 необходим из-за ориентации осей модели Jetbot;
  при нулевом roll, унаследованном от Tugbot, робот появляется на боку.
- GUI Teleop публикует в `/model/jetbot/cmd_vel`.
- Все Fuel-ссылки SDF заменены локальными `model://...`.
- Модели окружения скопированы в `assets/models` вместе с meshes и материалами.
  В SDF моделей pallet и pallet_box_mobile локализованы ссылки на meshes.

Версии моделей из кэша Fuel: Warehouse 5; shelf 1; shelf_big 2;
pallet_box_mobile 3; pallet 2; cart_model_2 2; Tugbot-charging-station 2.
Warehouse опубликован OpenRobotics, остальные модели окружения — MovAi.
Исходные имена авторов и metadata в model.config сохранены.
Первоначальный мир и модели в кэше Fuel не изменены.

Этот запуск не требует сборки ROS-пакета Jetbot. Мосты ROS и ноды запускаются
отдельно; само открытие Gazebo не публикует сенсоры автоматически в ROS.

## Сенсоры в ROS

Оставьте `make warehouse` работающим в первом терминале. Во втором терминале
из корня проекта войдите в контейнер и запустите мост:

```bash
make shell
ros2 run ros_gz_bridge parameter_bridge \
  '/world/world_demo/model/jetbot/link/lidar_link/sensor/scan_front/scan@sensor_msgs/msg/LaserScan[ignition.msgs.LaserScan' \
  '/world/world_demo/model/jetbot/link/camera_link/sensor/color/image@sensor_msgs/msg/Image[ignition.msgs.Image'
```

В третьем терминале можно получить один кадр лидара:

```bash
make shell
ros2 topic echo /world/world_demo/model/jetbot/link/lidar_link/sensor/scan_front/scan --once --qos-reliability best_effort
```

Мост передаёт оба сенсора из Gazebo в ROS. Остановить мост — `Ctrl+C`.
Топик камеры в ROS:
`/world/world_demo/model/jetbot/link/camera_link/sensor/color/image`.

Для графического просмотра топиков и изображения камеры в дополнительном
терминале контейнера:

```bash
ros2 run rqt_topic rqt_topic &
ros2 run rqt_image_view rqt_image_view &
```

В окне камеры выберите топик изображения, указанный выше. Gazebo и мост
должны продолжать работать. Подробная последовательность входа в контейнер
и запуска окон приведена в [CONTAINERS.md](../../../CONTAINERS.md#окна-ros-топиков-и-камеры).

Проверено 2026-09-20: GUI склада, камера 848×480 RGB и лидар 720 лучей;
оба сенсора получены подписчиками ROS через мост. Ошибок Gazebo в повторном
проверочном запуске не было. В локальной модели Jetbot исправлена геометрия
коллизии камеры (подробности в `assets/README.md`). Управление движением
и навигация этим тестом не проверялись.

Проверка исправленной начальной ориентации (`model.sdf`): после получения
сенсоров симуляция наблюдалась ещё 15 секунд. Итоговые roll ≈ −90.12°,
pitch ≈ 2.69°, высота начала модели ≈ 0.033 м; робот не опрокинулся.
Получены камера 848×480 и 710 конечных дальностей из 720 лучей лидара.
Проверка выполнялась без команд движения.
