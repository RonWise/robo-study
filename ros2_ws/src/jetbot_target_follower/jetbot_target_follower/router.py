"""Filter idle teleop zeros and stop on missing mux output (steady-clock watchdog)."""
import math
import time
import rclpy
from geometry_msgs.msg import Twist
from rclpy.clock import Clock, ClockType
from rclpy.node import Node
from std_msgs.msg import Bool


# Связывает teleop с mux и ограничивает выбранную mux команду перед отправкой роботу.
# Сам приоритет источников выбирает twist_mux, а не этот узел.
class CommandRouter(Node):
    def __init__(self):
        super().__init__('command_router')
        self.declare_parameter('command_timeout',.3)
        self.declare_parameter('teleop_timeout',.4)
        self.declare_parameter('max_linear_speed',.15)
        self.declare_parameter('max_angular_speed',.65)
        self.active=False
        self.teleop_at=0.
        self.mux_at=0.
        # В mux идут только активные ручные команды и один ноль при освобождении управления.
        self.manual_pub=self.create_publisher(Twist,'/cmd_vel_teleop_active',1)
        self.active_pub=self.create_publisher(Bool,'/teleop/active',1)
        # Для физического робота launch переназначает этот выход на топик моторного драйвера.
        self.output=self.create_publisher(Twist,'/cmd_vel',1)
        self.create_subscription(Twist,'/cmd_vel_teleop',self.teleop,1)
        self.create_subscription(Twist,'/cmd_vel_mux',self.mux,1)
        self.create_timer(.05,self.tick,clock=Clock(clock_type=ClockType.STEADY_TIME))

    # Оставляем только linear.x и angular.z, ограничиваем скорости обоих источников.
    # NaN/Inf превращаются в нулевую команду, остальные компоненты Twist не используются.
    def limited(self,msg):
        result=Twist()
        if not math.isfinite(msg.linear.x) or not math.isfinite(msg.angular.z):return result
        v=self.get_parameter('max_linear_speed').value
        w=self.get_parameter('max_angular_speed').value
        result.linear.x=max(-v,min(v,msg.linear.x))
        result.angular.z=max(-w,min(w,msg.angular.z))
        return result

    # Один ноль останавливает ручную команду; повторные нули не удерживают высокий приоритет.
    # После тайм-аута ручного входа mux снова может выбрать автономную команду.
    def release(self):
        if self.active:
            self.manual_pub.publish(Twist())
        self.active=False
        self.active_pub.publish(Bool(data=False))

    # Ненулевая команда активирует ручной режим и сообщает регулятору уступить управление.
    def teleop(self,msg):
        msg=self.limited(msg)
        if abs(msg.linear.x)+abs(msg.angular.z)>1e-6:
            self.active=True
            self.teleop_at=time.monotonic()
            self.active_pub.publish(Bool(data=True))
            self.manual_pub.publish(msg)
        else:
            self.release()

    # Отмечаем получение результата mux и ещё раз применяем общие ограничения скоростей.
    def mux(self,msg):
        self.mux_at=time.monotonic()
        self.output.publish(self.limited(msg))

    # Монотонные часы работают независимо от /clock и паузы Gazebo.
    # Потеря teleop освобождает ручной режим; потеря mux обнуляет конечную скорость.
    # При остановке самого router нужен независимый тайм-аут в моторном драйвере.
    def tick(self):
        now=time.monotonic()
        if self.active and now-self.teleop_at>self.get_parameter('teleop_timeout').value:self.release()
        self.active_pub.publish(Bool(data=self.active))
        if now-self.mux_at>self.get_parameter('command_timeout').value:self.output.publish(Twist())


def main(args=None):
    rclpy.init(args=args);node=CommandRouter()
    try:rclpy.spin(node)
    except KeyboardInterrupt:pass
    finally:
        # Попытка отправить остановку при штатном завершении, пока ROS-контекст доступен.
        if rclpy.ok():node.output.publish(Twist())
        node.destroy_node()
        if rclpy.ok():rclpy.shutdown()
