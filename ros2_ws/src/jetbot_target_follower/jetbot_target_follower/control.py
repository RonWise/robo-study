"""Planar target controller, independent of ROS for deterministic tests."""
from dataclasses import dataclass
import math


# Параметры в единицах СИ: метры, секунды, радианы и производные от них.
@dataclass
class ControlConfig:
    stop_distance: float = 0.5
    max_linear_speed: float = 0.15
    max_angular_speed: float = 0.65
    kp_distance: float = 0.65
    kp_angle: float = 1.8
    distance_tolerance: float = 0.02
    arrival_hysteresis: float = 0.04
    turn_in_place_angle: float = 0.4
    search_speed: float = 0.25
    search_delay: float = 0.6
    linear_acceleration: float = 0.25
    angular_acceleration: float = 1.5

    def validate(self):
        for name, value in vars(self).items():
            if not math.isfinite(value) or value <= 0:
                raise ValueError(name + ' must be finite and positive')
        if self.distance_tolerance >= self.stop_distance:
            raise ValueError('distance_tolerance must be less than stop_distance')


# Логика управления без ROS: удобна для проверки переходов состояний на обычных данных.
class Follower:
    def __init__(self):
        self.arrived = False
        self.v = self.w = 0.0
        self.search_direction = 1.0

    # target — (x, y) в корпусе или None; lost_for — время с последней принятой позы.
    # Результат: линейная скорость, угловая скорость и строковое имя состояния.
    def step(self, cfg, target, lost_for, dt, image_fresh=True, manual=False, enabled=True):
        if target is not None:
            bearing = math.atan2(target[1], target[0])
            if abs(bearing) > 0.03:
                self.search_direction = 1.0 if bearing > 0 else -1.0
        # Отключение, ручной режим и устаревшее изображение обнуляют автономный выход сразу.
        if not enabled or not image_fresh or manual:
            self.v = self.w = 0.0
            self.arrived = False
            return self.v, self.w, ('DISABLED' if not enabled else 'MANUAL' if manual else 'NO_IMAGE')
        # LOST: короткая остановка; SEARCH: вращение в сторону последнего направления цели.
        # Движение вперёд без видимой цели запрещено. Это поиск, а не обход препятствий.
        if target is None:
            self.arrived = False
            self.v = 0.0
            self.w = (self.search_direction * min(cfg.search_speed, cfg.max_angular_speed)
                      if lost_for >= cfg.search_delay else 0.0)
            return self.v, self.w, 'SEARCH' if self.w else 'LOST'
        x, y = target
        distance = math.hypot(x, y)
        angle = math.atan2(y, x)
        if abs(angle) > 0.03:
            self.search_direction = 1.0 if angle > 0 else -1.0
        # Положительная ошибка — нужно приблизиться; отрицательная — немного отъехать.
        error = distance - cfg.stop_distance
        # Гистерезис: выходим из ARRIVED дальше от заданной дистанции, чем входим.
        # Это предотвращает постоянные старты/остановки из-за небольшого шума измерений.
        if self.arrived and abs(error) > cfg.distance_tolerance + cfg.arrival_hysteresis:
            self.arrived = False
        if abs(error) <= cfg.distance_tolerance:
            self.arrived = True
        if self.arrived:
            self.v = self.w = 0.0
            return 0.0, 0.0, 'ARRIVED'
        # Два P-регулятора: направление управляет поворотом, расстояние — линейной скоростью.
        w = max(-cfg.max_angular_speed, min(cfg.max_angular_speed, cfg.kp_angle * angle))
        # Задний ход дополнительно ограничен 0.06 м/с и общим пределом скорости.
        v = max(-min(.06, cfg.max_linear_speed), min(cfg.max_linear_speed, cfg.kp_distance * error))
        # Чем сильнее цель сбоку, тем медленнее поступательное движение.
        v *= max(0., math.cos(angle))
        if abs(angle) > cfg.turn_in_place_angle:
            v = 0.0
        # Ограничиваем изменение скорости величиной ускорение × длительность шага.
        def slew(old, desired, rate):
            return old + max(-rate * dt, min(rate * dt, desired - old))
        # За пределами углового порога линейная скорость обнуляется сразу, без плавного спада.
        # ALIGN разворачивает к цели, APPROACH совмещает поворот и движение.
        self.v = 0.0 if abs(angle) > cfg.turn_in_place_angle else slew(self.v, v, cfg.linear_acceleration)
        self.w = slew(self.w, w, cfg.angular_acceleration)
        return self.v, self.w, 'ALIGN' if abs(angle) > cfg.turn_in_place_angle else 'APPROACH'
