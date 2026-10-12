import math
import time
import numpy as np
import rclpy
from geometry_msgs.msg import PoseStamped, Twist
from rclpy.clock import Clock, ClockType
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rcl_interfaces.msg import SetParametersResult
from sensor_msgs.msg import Image
from std_msgs.msg import Bool, Float64, String
from .control import ControlConfig, Follower


def rotation_rpy(r, p, y):
    cx,sx=math.cos(r),math.sin(r); cy,sy=math.cos(p),math.sin(p); cz,sz=math.cos(y),math.sin(y)
    return np.array([[cz,-sz,0],[sz,cz,0],[0,0,1]]) @ np.array([[cy,0,sy],[0,1,0],[-sy,0,cy]]) @ np.array([[1,0,0],[0,cx,-sx],[0,sx,cx]])


class TargetFollower(Node):
    def __init__(self):
        super().__init__('target_follower')
        for key,value in vars(ControlConfig()).items():
            self.declare_parameter(key,value)
        for key,value in {'enabled':True,'image_timeout':0.8,'target_timeout':0.5,
                          'camera_translation':[0.06,0.0,0.14],
                          'camera_rotation_rpy':[-math.pi/2,0.0,-math.pi/2]}.items():
            self.declare_parameter(key,value)
        self.config().validate()
        self.add_on_set_parameters_callback(self.validate_params)
        self.core=Follower()
        self.target=None
        self.target_time=0.
        self.image_time=0.
        self.manual=False
        self.visible=False
        self.visible_time=0.
        self.started=self.previous=time.monotonic()
        self.last_state=''
        self.cmd=self.create_publisher(Twist,'/cmd_vel_nav',1)
        self.state_pub=self.create_publisher(String,'/follower/state',1)
        self.distance_pub=self.create_publisher(Float64,'/target/base_distance',1)
        self.create_subscription(PoseStamped,'/target/pose',self.on_pose,1)
        self.create_subscription(Image,'/camera/image/raw',self.on_image,qos_profile_sensor_data)
        self.create_subscription(Bool,'/target/visible',self.on_visible,1)
        self.create_subscription(Bool,'/teleop/active',lambda m:setattr(self,'manual',m.data),1)
        self.create_timer(.05,self.tick,clock=Clock(clock_type=ClockType.STEADY_TIME))

    def config(self):
        return ControlConfig(**{k:self.get_parameter(k).value for k in vars(ControlConfig())})

    def validate_params(self, params):
        values=vars(self.config())
        for param in params:
            if param.name in values: values[param.name]=param.value
            if param.name in ('image_timeout','target_timeout') and (not math.isfinite(param.value) or param.value<=0):
                return SetParametersResult(successful=False,reason='Timeout must be positive')
            if param.name in ('camera_translation','camera_rotation_rpy') and (len(param.value)!=3 or not all(math.isfinite(x) for x in param.value)):
                return SetParametersResult(successful=False,reason='Camera transform needs three finite values')
        try: ControlConfig(**values).validate()
        except (ValueError,TypeError) as exc: return SetParametersResult(successful=False,reason=str(exc))
        return SetParametersResult(successful=True)

    def fresh_stamp(self, stamp, limit):
        age=self.get_clock().now().nanoseconds*1e-9-(stamp.sec+stamp.nanosec*1e-9)
        return -.1 <= age <= limit

    def on_visible(self,msg):
        self.visible=msg.data
        self.visible_time=time.monotonic()

    def on_image(self,msg):
        if self.fresh_stamp(msg.header.stamp,self.get_parameter('image_timeout').value):
            self.image_time=time.monotonic()

    def on_pose(self,msg):
        if not self.fresh_stamp(msg.header.stamp,self.get_parameter('target_timeout').value): return
        p=msg.pose.position
        t=np.asarray(self.get_parameter('camera_translation').value)
        rotation=rotation_rpy(*self.get_parameter('camera_rotation_rpy').value)
        point=rotation@np.array([p.x,p.y,p.z])+t
        if not np.isfinite(point).all(): return
        self.target=(float(point[0]),float(point[1]))
        self.target_time=time.monotonic()
        self.distance_pub.publish(Float64(data=math.hypot(*self.target)))

    def tick(self):
        now=time.monotonic()
        dt=min(.1,max(.001,now-self.previous)); self.previous=now
        target=self.target if self.visible and now-self.target_time<=self.get_parameter('target_timeout').value else None
        v,w,state=self.core.step(self.config(),target,now-max(self.target_time,self.started),dt,
            image_fresh=(now-self.image_time<=self.get_parameter('image_timeout').value and now-self.visible_time<=self.get_parameter('image_timeout').value),
            manual=self.manual,enabled=self.get_parameter('enabled').value)
        msg=Twist();msg.linear.x=v;msg.angular.z=w
        self.cmd.publish(msg)
        self.state_pub.publish(String(data=state))
        if state!=self.last_state:
            self.get_logger().info(state); self.last_state=state


def main(args=None):
    rclpy.init(args=args); node=TargetFollower()
    try:rclpy.spin(node)
    except KeyboardInterrupt:pass
    finally:
        if rclpy.ok():node.cmd.publish(Twist())
        node.destroy_node()
        if rclpy.ok():rclpy.shutdown()
